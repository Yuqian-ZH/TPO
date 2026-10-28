"""FeedbackService with the task4_v2 state-change rule and the v2 components.

An iteration has something to show the user when the routes changed or the data in force changed. Same routes on
corrected data is a new plan version of kind "data_corrected": the view carries a notice that the correction is
applied and the plan is still optimal on it, and the user confirms it like any other plan (accepting keeps the
correction in force). Same routes on the same data, i.e. a soft constraint or weight that changed nothing, still
runs the next iteration at once, as in v1."""
from feedback_service.bridge import t2
from feedback_service.engine import SERVICE_SETTINGS, Engine, thread_mods
from feedback_service.service import DEFAULT_CONFIG, FeedbackService, _usage_add, _usage_diff
from feedback_service.store import Store, random_id
from feedback_service.worker import CountingLLM

PROTOCOL = "task4_v2"
DATA_NOTICE = ("Your data correction is applied. On the corrected data the current routes are still the best "
               "plan, so they stay as they are. Please confirm.")


def state_change(engine, fb, rec, trial):
    """'routes', 'data' or None: what an iteration changed compared with the plan it started from."""
    if rec["status"] != "committed":
        return None
    if rec["solution_after"]["routes"] != rec["input_solution"]["routes"]:
        return "routes"
    before = engine.data(thread_mods(fb) + rec["mods_before"])
    after = engine.data(trial.model_mods())
    return "data" if before != after else None


class FeedbackServiceV2(FeedbackService):
    def _refine(self, fb, trigger):
        """v1's loop with one change: whether an iteration produced a plan to show is state_change(), not a
        comparison of routes."""
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
            change = state_change(self.engine, fb, rec, trial)
            out_v = len(s["plans"]) + len(new_plans) if change else in_v
            if change:
                source = {"kind": "refined" if change == "routes" else "data_corrected",
                          "feedback_id": fb["feedback_id"], "iteration": t}
                if change == "data":
                    source["notice"] = DATA_NOTICE
                new_plans.append(self.engine.plan_record(trial.sol, trial.model_mods(), out_v, source))
            st = {"t": t, "plan_version": out_v, "sol": trial.sol, "mods": trial.mods, "history": trial.history}
            log = self.engine.iteration_record(fb, rec, trial, trigger, critique, (in_v, out_v),
                                               _usage_diff(self.llm.snapshot(), before))
            log["refined_solution"]["state_change"] = change
            logs.append(log)
            fb["iterations"].append({k: log[k] for k in ("iteration", "trigger", "status", "note", "rationale",
                                                          "committed_modifications", "feasibility", "time")}
                                    | {"input_version": in_v, "plan_version": out_v, "new_plan": bool(change),
                                       "state_change": change, "changes": log["refined_solution"]["changes"]})
            if change or t >= fb["max_iterations"]:
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
                                 plan_version=st["plan_version"], state_change=[log["refined_solution"]
                                                                                ["state_change"] for log in logs],
                                 llm=self.llm.snapshot())

    def feedback_view(self, fb):
        v = super().feedback_view(fb)
        plan = v.get("plan") or {}
        v["notice"] = plan.get("source", {}).get("notice") if fb["status"] == "awaiting_reply" else None
        return v

    def health(self):
        return {**super().health(), "protocol": PROTOCOL}


def default_components_v2(base, llm):
    from tpo_v2.components import Task2ComponentsV2
    return Task2ComponentsV2(base, llm, run_label="t4")


def build_service_v2(data_dir, llm=None, components_factory=default_components_v2, new_id=random_id,
                     default_config=DEFAULT_CONFIG, settings=SERVICE_SETTINGS, startup_checks=None):
    """As feedback_service.service.build_service, with FeedbackServiceV2 and the v2 components."""
    base = t2.load_frozen_instance()
    store = Store(data_dir, new_id)
    if llm is None:
        from tpo.llm import real_client
        llm = real_client(store.llm_log_path())
    counting = CountingLLM(llm)
    engine = Engine(base, components_factory(base, counting), counting, settings)
    return FeedbackServiceV2(store, engine, counting, default_config=default_config, startup_checks=startup_checks)
