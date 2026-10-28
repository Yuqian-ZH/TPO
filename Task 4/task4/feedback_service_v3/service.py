"""FeedbackServiceV21 with task3_v3's loop: each iteration starts from the plan complained about.

EngineV3.trial() restores only the trial's history; the plan and modifications of the last iteration stay in the
feedback record (the plan shown, the modifications accepted with it) but are not the next iteration's start. Within
one refinement, _refine resets the trial to the plan complained about before every further iteration.

Difference to Task 3 that remains (README section 12): when an iteration returns a state the user has already seen,
the service does not show it and runs on with the user's last words; Task 3's simulated user comments on every
committed plan. The two coincide whenever every iteration produces a new plan."""
from feedback_service.bridge import CONFIGS, PublicCase, t2
from feedback_service.engine import SERVICE_SETTINGS, DeferredUser, Engine, ServiceTrial, thread_mods
from feedback_service.service import DEFAULT_CONFIG, _usage_add, _usage_diff
from feedback_service.store import Store, random_id
from feedback_service.worker import CountingLLM
from feedback_service_v21.service import (FeedbackServiceV21, data_changes, data_key, default_components_v21, notice,
                                          seen_state, state_change)

PROTOCOL = "task4_v3"


class EngineV3(Engine):
    def trial(self, fb):
        """As Engine.trial, but the trial starts from the plan complained about; only the history is restored."""
        pc = PublicCase(id=fb["feedback_id"], solution={"routes": [list(r) for r in fb["solution"]["routes"]]},
                        complaint=fb["complaint"], model_modifications=tuple(thread_mods(fb)))
        tr = ServiceTrial(pc, self.base, DeferredUser(), CONFIGS[fb["config"]], fb["config"], 1, self.comps,
                          self.llm, self.settings, loc=fb.get("localization"),
                          accepted=fb["accepted_modifications"])
        st = fb.get("trial")
        if st:
            tr.history = st["history"]
        return tr


class FeedbackServiceV3(FeedbackServiceV21):
    def _refine(self, fb, trigger):
        """FeedbackServiceV21._refine with the input of every iteration being the plan complained about."""
        if fb["critique"] is None:
            fb["critique"] = self.processor.critique(fb)
            self.store.log_event(fb["session_id"], "critique_ready", feedback_id=fb["feedback_id"],
                                 critique=fb["critique"],
                                 localization=self.processor.summary(fb["localization"])
                                 if fb["localization"] else None)
        trial = self.engine.trial(fb)
        start_v = fb["solution"]["version"]
        st = fb["trial"] or {"t": 0, "plan_version": start_v}
        seen = st.get("seen") or [seen_state(fb["solution"]["routes"], self.engine.data(thread_mods(fb)))]
        s = self.store.get_session(fb["session_id"])
        new_plans, logs = [], []
        while True:
            t = st["t"] + 1
            before = self.llm.snapshot()
            critique = self.engine.critique_on(fb, trial)
            rec = trial.step(t)
            self.llm.raise_if_failed(f"iteration {t}")
            change, after = state_change(self.engine, fb, rec, trial, seen)
            changes = []
            out_v = len(s["plans"]) + len(new_plans) if change else st["plan_version"]
            if change:
                seen = seen + [after]
                changes = data_changes(data_key(self.engine.data(thread_mods(fb) + rec["mods_before"])),
                                       after["data"])
                source = {"kind": "refined" if change == "routes" else "data_corrected",
                          "feedback_id": fb["feedback_id"], "iteration": t, "data_changes": changes}
                if changes:
                    source["notice"] = notice(change, changes)
                new_plans.append(self.engine.plan_record(trial.sol, trial.model_mods(), out_v, source))
                shown = {"sol": trial.sol, "mods": trial.mods}
            else:
                shown = {"sol": st.get("sol", {"routes": fb["solution"]["routes"]}), "mods": st.get("mods", [])}
            st = {"t": t, "plan_version": out_v, **shown, "history": trial.history, "seen": seen}
            log = self.engine.iteration_record(fb, rec, trial, trigger, critique, (start_v, out_v),
                                               _usage_diff(self.llm.snapshot(), before))
            log["refined_solution"]["state_change"] = change
            log["refined_solution"]["data_changes"] = changes
            logs.append(log)
            fb["iterations"].append({k: log[k] for k in ("iteration", "trigger", "status", "note", "rationale",
                                                          "committed_modifications", "feasibility", "time")}
                                    | {"input_version": start_v, "plan_version": out_v, "new_plan": bool(change),
                                       "state_change": change, "changes": log["refined_solution"]["changes"]})
            if change or t >= fb["max_iterations"]:
                break
            trial.history[-1]["feedback"] = fb["last_feedback_text"]
            trial.sol, trial.mods = trial.pc.solution, []          # task3_v3: start again from the plan complained about
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

    def health(self):
        return {**super().health(), "protocol": PROTOCOL}


def build_service_v3(data_dir, llm=None, components_factory=default_components_v21, new_id=random_id,
                     default_config=DEFAULT_CONFIG, settings=SERVICE_SETTINGS, startup_checks=None):
    """As build_service_v21, with EngineV3 and FeedbackServiceV3."""
    base = t2.load_frozen_instance()
    store = Store(data_dir, new_id)
    if llm is None:
        from tpo.llm import real_client
        llm = real_client(store.llm_log_path())
    counting = CountingLLM(llm)
    engine = EngineV3(base, components_factory(base, counting), counting, settings)
    return FeedbackServiceV3(store, engine, counting, default_config=default_config, startup_checks=startup_checks)
