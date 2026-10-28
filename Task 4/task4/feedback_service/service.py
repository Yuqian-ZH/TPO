"""Transport-independent core of the pipeline (plan 3): sessions, feedback ingestion, complaint processing,
triggering TPO, replies, acceptance and rollback, logging. app.py maps it onto HTTP.

Concurrency: HTTP threads validate, store and enqueue; every job that needs Gurobi or the LLM runs on the single
engine thread (worker.py). A job reads its feedback record, works without holding the store lock, and writes
everything back in one step at the end; if it fails, nothing it computed is kept."""
from .bridge import CONFIGS, FEEDBACK_UNRESOLVED, MAIN, check_modification, canon, t2
from .engine import SERVICE_SETTINGS, Engine, thread_mods, with_ids
from .processor import ComplaintProcessor
from .store import Store, now, random_id
from .worker import CountingLLM, EngineWorker, LLMUnavailable

DEFAULT_CONFIG = "A0B0C1"
MODEL = "qwen3.8-max"
WAIT_LIMIT_S = 600
OPEN = ("received", "processing", "needs_clarification", "awaiting_reply")
TERMINAL = ("resolved", "not_converged", "stopped_low_confidence", "stopped_by_user", "failed")


class ApiError(Exception):
    def __init__(self, status, code, detail):
        super().__init__(f"{status} {code}: {detail}")
        self.status, self.code, self.detail = status, code, detail


def _usage_add(a, b):
    return {k: round(a.get(k, 0) + b.get(k, 0), 3) for k in set(a) | set(b)}


def _usage_diff(after, before):
    return {k: round(after[k] - before.get(k, 0), 3) for k in after}


class FeedbackService:
    def __init__(self, store, engine, llm, worker=None, default_config=DEFAULT_CONFIG, startup_checks=None):
        self.store, self.engine, self.llm = store, engine, llm
        self.processor = ComplaintProcessor(engine)
        self.worker = worker or EngineWorker()
        self.default_config = default_config
        self.startup_checks = startup_checks or {}
        self.recovered = self._recover()

    def start(self):
        self.worker.start()

    def stop(self):
        self.worker.stop(timeout=WAIT_LIMIT_S)

    # ---------- helpers ----------

    def _session(self, sid):
        s = self.store.get_session(sid)
        if s is None:
            raise ApiError(404, "unknown_session", f"no session {sid}")
        return s

    def _feedback(self, fid):
        fb = self.store.get_feedback(fid)
        if fb is None:
            raise ApiError(404, "unknown_feedback", f"no feedback {fid}")
        return fb

    @staticmethod
    def _set_status(fb, status, **extra):
        fb["status"] = status
        fb["status_history"].append({"status": status, "time": now(), **extra})

    def _close(self, fb, s, status, revert):
        """Terminal state. Only an accepted plan changes the session: otherwise it returns to the plan the
        complaint was about, and this complaint's modifications are dropped (they stay in the logs)."""
        self._set_status(fb, status)
        s["open_feedback"] = None
        if revert and s["current_version"] != fb["solution"]["version"]:
            self.store.log_event(s["session_id"], "reverted", feedback_id=fb["feedback_id"],
                                 from_version=s["current_version"], to_version=fb["solution"]["version"])
            s["current_version"] = fb["solution"]["version"]

    def _recover(self):
        """At start-up a job that was queued or running when the process stopped cannot be resumed safely."""
        out = []
        with self.store.lock:
            for fid, fb in list(self.store.feedback.items()):
                if fb["status"] in ("received", "processing"):
                    fb, s = self.store.get_feedback(fid), self.store.get_session(fb["session_id"])
                    fb["error"] = {"kind": "interrupted_by_restart", "detail": f"was {fb['status']} at shutdown"}
                    self._close(fb, s, "failed", revert=True)
                    self.store.save_feedback(fb)
                    self.store.save_session(s)
                    self.store.log_event(s["session_id"], "failed", feedback_id=fid, error=fb["error"])
                    out.append(fid)
        return out

    def _respond(self, fid, job, wait):
        if wait:
            job.done.wait(WAIT_LIMIT_S)
        return self.feedback_view(self.store.get_feedback(fid)), job.done.is_set()

    def _run(self, fid, fn, name):
        """Job body on the engine thread: mark processing, run, and on any failure keep nothing it computed."""
        fb = self.store.get_feedback(fid)
        self._set_status(fb, "processing", job=name)
        self.store.save_feedback(fb)
        self.llm.reset()
        try:
            fn(fb)
        except Exception as e:
            kind = "llm_unavailable" if isinstance(e, LLMUnavailable) else "engine_error"
            with self.store.lock:
                fb, s = self.store.get_feedback(fid), self.store.get_session(fb["session_id"])
                fb["error"] = {"kind": kind, "detail": f"{type(e).__name__}: {str(e)[:500]}", "job": name}
                fb["usage"] = _usage_add(fb["usage"], self.llm.snapshot())
                self._close(fb, s, "failed", revert=True)
                self.store.save_feedback(fb)
                self.store.save_session(s)
                self.store.log_event(s["session_id"], "failed", feedback_id=fid, error=fb["error"],
                                     llm=self.llm.snapshot())

    def _submit(self, fid, fn, name):
        return self.worker.submit(lambda: self._run(fid, fn, name), name)

    # ---------- sessions ----------

    def create_session(self, body):
        config = body.get("config") or self.default_config
        if config not in MAIN:
            raise ApiError(422, "unknown_config", f"config must be one of {list(MAIN)}")
        n, K = self.engine.base["n"], self.engine.base["K"]
        mods = body.get("model_modifications") or []
        errs = [f"modification {i + 1}: {e}" for i, m in enumerate(mods) for e in check_modification(m, n, K)]
        if errs:
            raise ApiError(422, "invalid_modification", errs)
        mods = with_ids(mods, "s0")
        provided = body.get("solution")
        if provided is not None:
            provided = {"routes": [list(r) for r in provided["routes"]]}
            if not canon.is_feasible(provided, self.engine.data(mods)):
                raise ApiError(422, "infeasible_solution", "the plan must have one non-empty route per vehicle, "
                                                           "visit every customer once and respect capacity")
        job = self.worker.submit(lambda: self.engine.initial_plan(mods), "initial_plan")
        if not job.done.wait(WAIT_LIMIT_S) or job.error:
            raise ApiError(500, "engine_error", job.error or "initial solve timed out")
        if job.result is None:
            raise ApiError(422, "no_feasible_plan", "no plan satisfies the capacity with these modifications")
        opt_sol, opt_obj = job.result
        with self.store.lock:
            sid = self.store.new_id("s")
            plan = self.engine.plan_record(provided or opt_sol, mods, 0,
                                           {"kind": "client" if provided else "solver"})
            s = {"session_id": sid, "label": body.get("label"), "config": config,
                 "max_iterations": body.get("max_iterations") or SERVICE_SETTINGS.max_iters, "created_at": now(),
                 "model_modifications": mods, "accepted_modifications": [], "accepted_feedback": [],
                 "plans": [plan], "current_version": 0,
                 "initial_plan": {"provided_by_client": provided is not None, "optimal_objective": opt_obj,
                                  "is_optimal": abs(plan["objective"] - opt_obj) < 1e-6},
                 "open_feedback": None, "feedback_ids": []}
            self.store.save_session(s)
            self.store.log_event(sid, "session_created", config=config, label=s["label"],
                                 model_modifications=mods, initial_plan=s["initial_plan"], routes=plan["routes"])
        return self.session_view(s)

    # ---------- feedback ingestion ----------

    def submit_feedback(self, sid, body, wait=True):
        complaint = body["complaint"].strip()
        if not complaint:
            raise ApiError(422, "empty_complaint", "the complaint is empty")
        with self.store.lock:
            s = self._session(sid)
            if s["open_feedback"]:
                open_fb = self.store.get_feedback(s["open_feedback"])
                raise ApiError(409, "feedback_open", f"feedback {open_fb['feedback_id']} is still "
                                                     f"{open_fb['status']}; reply to it or stop it first")
            cur = s["plans"][s["current_version"]]
            if body.get("solution_version") is not None and body["solution_version"] != cur["version"]:
                raise ApiError(409, "stale_solution", f"the current plan is version {cur['version']}, "
                                                      f"not {body['solution_version']}")
            if body.get("solution") is not None and [list(r) for r in body["solution"]["routes"]] != cur["routes"]:
                raise ApiError(409, "stale_solution", f"the plan sent is not the current plan (version "
                                                      f"{cur['version']})")
            fid = self.store.new_id("f")
            fb = {"feedback_id": fid, "session_id": sid, "complaint": complaint, "received_at": now(),
                  "solution": {"version": cur["version"], "routes": cur["routes"]},
                  "config": s["config"], "max_iterations": s["max_iterations"],
                  "session_modifications": s["model_modifications"],
                  "accepted_modifications": s["accepted_modifications"],
                  "status": "received", "status_history": [{"status": "received", "time": now()}],
                  "localization": None, "critique": None, "trial": None,
                  "last_feedback_text": FEEDBACK_UNRESOLVED.format(complaint=complaint),
                  "iterations": [], "replies": [], "usage": {}, "error": None}
            s["open_feedback"] = fid
            s["feedback_ids"].append(fid)
            self.store.save_feedback(fb)
            self.store.save_session(s)
            self.store.log_event(sid, "feedback_received", feedback_id=fid, complaint=complaint,
                                 solution=fb["solution"])
        return self._respond(fid, self._submit(fid, self._process_feedback, "process_feedback"), wait)

    def _process_feedback(self, fb):
        if CONFIGS[fb["config"]].C:
            loc = self.processor.first_pass(fb)
            self.llm.raise_if_failed("localization")
            fb["localization"] = loc
            if not self.processor.ready(loc):
                with self.store.lock:
                    fb["usage"] = _usage_add(fb["usage"], self.llm.snapshot())
                    self._set_status(fb, "needs_clarification")
                    self.store.save_feedback(fb)
                    self.store.log_event(fb["session_id"], "clarification_requested", feedback_id=fb["feedback_id"],
                                         localization=self.processor.summary(loc), llm=self.llm.snapshot())
                return
        self._refine(fb, "feedback")

    def clarify(self, fid, answer, wait=True):
        answer = answer.strip()
        if not answer:
            raise ApiError(422, "empty_answer", "the answer is empty")
        with self.store.lock:
            fb = self._feedback(fid)
            if fb["status"] != "needs_clarification":
                raise ApiError(409, "not_waiting_for_clarification", f"feedback {fid} is {fb['status']}")
            fb["localization"]["answer"] = answer
            self._set_status(fb, "received")
            self.store.save_feedback(fb)
            self.store.log_event(fb["session_id"], "clarification_received", feedback_id=fid,
                                 question=fb["localization"]["question"], answer=answer)
        return self._respond(fid, self._submit(fid, self._process_clarification, "process_clarification"), wait)

    def _process_clarification(self, fb):
        loc = self.processor.second_pass(fb)
        self.llm.raise_if_failed("localization after clarification")
        fb["localization"] = loc
        if not self.processor.ready(loc):
            with self.store.lock:
                s = self.store.get_session(fb["session_id"])
                fb["usage"] = _usage_add(fb["usage"], self.llm.snapshot())
                self._close(fb, s, "stopped_low_confidence", revert=False)
                self.store.save_feedback(fb)
                self.store.save_session(s)
                self.store.log_event(fb["session_id"], "stopped_low_confidence", feedback_id=fb["feedback_id"],
                                     localization=self.processor.summary(loc), llm=self.llm.snapshot())
            return
        self._refine(fb, "clarification")

    # ---------- refinement ----------

    def _refine(self, fb, trigger):
        """TPO iterations until a plan the user has not seen exists (then ask the user) or the iteration budget
        is spent. An iteration without a new plan (all candidates rejected, no feasible plan, or the same
        routes) is not shown: the user's last statement about this plan is fed back and the loop goes on."""
        if fb["critique"] is None:
            fb["critique"] = self.processor.critique(fb)
            self.store.log_event(fb["session_id"], "critique_ready", feedback_id=fb["feedback_id"],
                                 critique=fb["critique"],
                                 localization=self.processor.summary(fb["localization"])
                                 if fb["localization"] else None)
        trial = self.engine.trial(fb)
        st = fb["trial"] or {"t": 0, "plan_version": fb["solution"]["version"]}
        s = self.store.get_session(fb["session_id"])
        new_plans, logs = [], []
        while True:
            t = st["t"] + 1
            before = self.llm.snapshot()
            critique = self.engine.critique_on(fb, trial)
            rec = trial.step(t)
            self.llm.raise_if_failed(f"iteration {t}")
            in_v = st["plan_version"]
            new = rec["status"] == "committed" and rec["solution_after"]["routes"] != rec["input_solution"]["routes"]
            out_v = len(s["plans"]) + len(new_plans) if new else in_v
            if new:
                new_plans.append(self.engine.plan_record(trial.sol, trial.model_mods(), out_v,
                                                         {"kind": "refined", "feedback_id": fb["feedback_id"],
                                                          "iteration": t}))
            st = {"t": t, "plan_version": out_v, "sol": trial.sol, "mods": trial.mods, "history": trial.history}
            log = self.engine.iteration_record(fb, rec, trial, trigger, critique, (in_v, out_v),
                                               _usage_diff(self.llm.snapshot(), before))
            logs.append(log)
            fb["iterations"].append({k: log[k] for k in ("iteration", "trigger", "status", "note", "rationale",
                                                          "committed_modifications", "feasibility", "time")}
                                    | {"input_version": in_v, "plan_version": out_v, "new_plan": new,
                                       "changes": log["refined_solution"]["changes"]})
            if new or t >= fb["max_iterations"]:
                break
            trial.history[-1]["feedback"] = fb["last_feedback_text"]
            trigger = "auto_continue"
        fb["trial"] = st
        with self.store.lock:
            s = self.store.get_session(fb["session_id"])
            s["plans"].extend(new_plans)
            fb["usage"] = _usage_add(fb["usage"], self.llm.snapshot())
            for log in logs:
                self.store.log_iteration(fb["session_id"], log)
            if new_plans:
                s["current_version"] = st["plan_version"]
                self._set_status(fb, "awaiting_reply", iteration=st["t"])
            else:
                self._close(fb, s, "not_converged", revert=True)
            self.store.save_feedback(fb)
            self.store.save_session(s)
            self.store.log_event(fb["session_id"], "refined" if new_plans else "not_converged",
                                 feedback_id=fb["feedback_id"], iterations=[log["iteration"] for log in logs],
                                 plan_version=st["plan_version"], llm=self.llm.snapshot())

    # ---------- replies ----------

    def reply(self, fid, body, wait=True):
        comment = (body.get("comment") or "").strip() or None
        with self.store.lock:
            fb = self._feedback(fid)
            if fb["status"] != "awaiting_reply":
                raise ApiError(409, "not_waiting_for_reply", f"feedback {fid} is {fb['status']}")
            s = self.store.get_session(fb["session_id"])
            t = fb["trial"]["t"]
            fb["replies"].append({"iteration": t, "plan_version": fb["trial"]["plan_version"],
                                  "resolved": bool(body["resolved"]), "stop": bool(body.get("stop")),
                                  "comment": comment, "time": now()})
            self.store.log_event(s["session_id"], "reply_received", feedback_id=fid, iteration=t,
                                 resolved=bool(body["resolved"]), stop=bool(body.get("stop")), comment=comment)
            done = True
            if body["resolved"]:
                self._accept(fb, s)
            elif body.get("stop"):
                self._close(fb, s, "stopped_by_user", revert=True)
            else:
                text = comment or FEEDBACK_UNRESOLVED.format(complaint=fb["complaint"])
                fb["trial"]["history"][-1]["feedback"] = text
                fb["last_feedback_text"] = text
                if t >= fb["max_iterations"]:
                    self._close(fb, s, "not_converged", revert=True)
                else:
                    self._set_status(fb, "received")
                    done = False
            self.store.save_feedback(fb)
            self.store.save_session(s)
            if done:
                self.store.log_event(s["session_id"], fb["status"], feedback_id=fid,
                                     current_version=s["current_version"])
                return self.feedback_view(fb), True
        return self._respond(fid, self._submit(fid, lambda f: self._refine(f, "reply"), "refine"), wait)

    def _accept(self, fb, s):
        """The plan the user accepted becomes the session's plan, and its modifications stay in force for every
        later complaint (soft-constraint ids rewritten so they cannot collide with later ones)."""
        n = len(s["accepted_feedback"]) + 1
        s["accepted_modifications"] = s["accepted_modifications"] + with_ids(fb["trial"]["mods"], f"acc{n}")
        s["accepted_feedback"].append(fb["feedback_id"])
        s["current_version"] = fb["trial"]["plan_version"]
        self._close(fb, s, "resolved", revert=False)

    # ---------- views ----------

    def health(self):
        return {"status": "ok", "model": MODEL, "default_config": self.default_config, "configs": list(MAIN),
                "max_iterations": SERVICE_SETTINGS.max_iters, "queued_jobs": self.worker.pending(),
                "engine_thread_alive": bool(self.worker.thread and self.worker.thread.is_alive()),
                "sessions": len(self.store.sessions), "recovered_at_startup": self.recovered,
                **self.startup_checks}

    def session_view(self, s):
        return {"session_id": s["session_id"], "label": s["label"], "config": s["config"],
                "max_iterations": s["max_iterations"], "created_at": s["created_at"],
                "model_modifications": s["model_modifications"],
                "accepted_modifications": s["accepted_modifications"], "initial_plan": s["initial_plan"],
                "current_plan": s["plans"][s["current_version"]],
                "plans": [{"version": p["version"], "source": p["source"],
                           "total_distance": p["metrics"]["total_distance"]} for p in s["plans"]],
                "open_feedback": s["open_feedback"],
                "feedback": [{"feedback_id": f, "status": self.store.feedback[f]["status"],
                              "complaint": self.store.feedback[f]["complaint"]} for f in s["feedback_ids"]
                             if f in self.store.feedback]}

    def get_session(self, sid):
        return self.session_view(self._session(sid))

    def list_sessions(self):
        return [{"session_id": s["session_id"], "label": s["label"], "config": s["config"],
                 "current_version": s["current_version"], "open_feedback": s["open_feedback"],
                 "feedback": len(s["feedback_ids"])} for s in self.store.list_sessions()]

    def feedback_view(self, fb):
        s = self.store.get_session(fb["session_id"])
        st = fb["trial"] or {}
        loc = fb["localization"]
        nxt = {"needs_clarification": f"POST /feedback/{fb['feedback_id']}/clarification {{answer}}",
               "awaiting_reply": f"POST /feedback/{fb['feedback_id']}/reply {{resolved, comment?, stop?}}",
               "received": f"GET /feedback/{fb['feedback_id']}", "processing": f"GET /feedback/{fb['feedback_id']}"}
        return {"feedback_id": fb["feedback_id"], "session_id": fb["session_id"], "status": fb["status"],
                "complaint": fb["complaint"], "received_at": fb["received_at"], "solution": fb["solution"],
                "config": fb["config"], "iteration": st.get("t", 0), "max_iterations": fb["max_iterations"],
                "clarification": {"question": loc["question"], "answer": loc["answer"]}
                if loc and loc["asked"] else None,
                "localization": self.processor.summary(loc) if loc else None,
                "critique": fb["critique"],
                "plan": s["plans"][st["plan_version"]] if st else None,
                "modifications_in_force": st.get("mods"),
                "latest_iteration": fb["iterations"][-1] if fb["iterations"] else None,
                "iterations": fb["iterations"], "replies": fb["replies"], "usage": fb["usage"],
                "error": fb["error"], "session_current_version": s["current_version"],
                "next": nxt.get(fb["status"], f"POST /sessions/{fb['session_id']}/feedback for a new complaint")}

    def get_feedback(self, fid):
        return self.feedback_view(self._feedback(fid))

    def iterations(self, sid, feedback_id=None):
        self._session(sid)
        return [r for r in self.store.iterations(sid) if feedback_id in (None, r["feedback_id"])]

    def events(self, sid):
        self._session(sid)
        return self.store.events(sid)


def default_components(base, llm):
    from tpo.components import Task2Components
    return Task2Components(base, llm, run_label="t4")


def build_service(data_dir, llm=None, components_factory=default_components, new_id=random_id,
                  default_config=DEFAULT_CONFIG, settings=SERVICE_SETTINGS, startup_checks=None):
    """llm=None uses Task 2's LLMClient (needs DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL in the environment) with
    its redacted request log in <data_dir>/logs/llm_requests.jsonl."""
    base = t2.load_frozen_instance()
    store = Store(data_dir, new_id)
    if llm is None:
        from tpo.llm import real_client
        llm = real_client(store.llm_log_path())
    counting = CountingLLM(llm)
    engine = Engine(base, components_factory(base, counting), counting, settings)
    return FeedbackService(store, engine, counting, default_config=default_config, startup_checks=startup_checks)
