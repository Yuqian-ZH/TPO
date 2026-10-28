"""FeedbackService with the task4_v2.1 state-change rule and the v2.1 components.

v2 showed a plan whenever the routes or the data in force changed, and every same-routes plan carried "Your data
correction is applied". Two cases were wrong: (a) the user rejects a corrected plan and the next proposal drops the
correction (each list replaces the last), so the data reverts and the plan the user complained about is shown again
with a notice that the correction is in force; (b) the LLM changes data nobody asked for and the routes stay, so the
invented change is shown as the user's correction.

v2.1: an iteration has something to show when its (routes, data in force) is a state the user has not seen in this
complaint, i.e. neither the plan complained about nor a plan shown since; otherwise the loop runs on, as v1 does for
unchanged routes. A plan whose data differs from the plan the iteration started from lists the changed values in its
notice and asks the user to check them; it does not say whose correction they are."""
from feedback_service.bridge import t2
from feedback_service.engine import SERVICE_SETTINGS, Engine, thread_mods
from feedback_service.service import DEFAULT_CONFIG, _usage_add, _usage_diff
from feedback_service.store import Store, random_id
from feedback_service.worker import CountingLLM
from feedback_service_v2.service import FeedbackServiceV2

PROTOCOL = "task4_v2.1"


def data_key(data):
    """The data items a modification can change (modification.schema.json), in JSON form."""
    return {"Q": data["Q"], "q": list(data["q"]), "coords": [list(c) for c in data["coords"]]}


def seen_state(routes, data):
    return {"routes": [list(r) for r in routes], "data": data_key(data)}


def data_changes(before, after):
    """The changed data items in the user's words, e.g. "customer 4's order size 12 -> 13"."""
    out = []
    if before["Q"] != after["Q"]:
        out.append(f"vehicle capacity {before['Q']} -> {after['Q']}")
    for i in range(1, len(before["q"])):
        if before["q"][i] != after["q"][i]:
            out.append(f"customer {i}'s order size {before['q'][i]} -> {after['q'][i]}")
        if before["coords"][i] != after["coords"][i]:
            out.append(f"customer {i}'s location {before['coords'][i]} -> {after['coords'][i]}")
    return out


def notice(change, changes):
    lead = ("The routes stay as they are, but the data the plan uses changed" if change == "data" else
            "The data the plan uses also changed")
    return (f"{lead}: {'; '.join(changes)}. The plan is the best one on this data. Please check that these values "
            f"are correct before you confirm.")


def state_change(engine, fb, rec, trial, seen):
    """('routes' | 'data' | None, the iteration's state): None if it did not commit or the user has seen its state."""
    if rec["status"] != "committed":
        return None, None
    after = seen_state(rec["solution_after"]["routes"], engine.data(trial.model_mods()))
    if after in seen:
        return None, after
    return ("routes" if after["routes"] != rec["input_solution"]["routes"] else "data"), after


class FeedbackServiceV21(FeedbackServiceV2):
    def _refine(self, fb, trigger):
        """v2's loop (a copy of v1's) with state_change() above; the states the user has seen are kept with the
        trial."""
        if fb["critique"] is None:
            fb["critique"] = self.processor.critique(fb)
            self.store.log_event(fb["session_id"], "critique_ready", feedback_id=fb["feedback_id"],
                                 critique=fb["critique"],
                                 localization=self.processor.summary(fb["localization"])
                                 if fb["localization"] else None)
        trial = self.engine.trial(fb)
        st = fb["trial"] or {"t": 0, "plan_version": fb["solution"]["version"]}
        seen = st.get("seen") or [seen_state(fb["solution"]["routes"], self.engine.data(thread_mods(fb)))]
        s = self.store.get_session(fb["session_id"])
        new_plans, logs = [], []
        while True:
            t = st["t"] + 1
            before = self.llm.snapshot()
            critique = self.engine.critique_on(fb, trial)
            rec = trial.step(t)
            self.llm.raise_if_failed(f"iteration {t}")
            in_v = st["plan_version"]
            change, after = state_change(self.engine, fb, rec, trial, seen)
            changes = []
            out_v = len(s["plans"]) + len(new_plans) if change else in_v
            if change:
                seen = seen + [after]
                changes = data_changes(data_key(self.engine.data(thread_mods(fb) + rec["mods_before"])),
                                       after["data"])
                source = {"kind": "refined" if change == "routes" else "data_corrected",
                          "feedback_id": fb["feedback_id"], "iteration": t, "data_changes": changes}
                if changes:
                    source["notice"] = notice(change, changes)
                new_plans.append(self.engine.plan_record(trial.sol, trial.model_mods(), out_v, source))
            st = {"t": t, "plan_version": out_v, "sol": trial.sol, "mods": trial.mods, "history": trial.history,
                  "seen": seen}
            log = self.engine.iteration_record(fb, rec, trial, trigger, critique, (in_v, out_v),
                                               _usage_diff(self.llm.snapshot(), before))
            log["refined_solution"]["state_change"] = change
            log["refined_solution"]["data_changes"] = changes
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

    def health(self):
        return {**super().health(), "protocol": PROTOCOL}


def default_components_v21(base, llm):
    from tpo_v21.components import Task2ComponentsV21
    return Task2ComponentsV21(base, llm, run_label="t4")


def build_service_v21(data_dir, llm=None, components_factory=default_components_v21, new_id=random_id,
                      default_config=DEFAULT_CONFIG, settings=SERVICE_SETTINGS, startup_checks=None):
    """As feedback_service_v2.service.build_service_v2, with FeedbackServiceV21 and the v2.1 components."""
    base = t2.load_frozen_instance()
    store = Store(data_dir, new_id)
    if llm is None:
        from tpo.llm import real_client
        llm = real_client(store.llm_log_path())
    counting = CountingLLM(llm)
    engine = Engine(base, components_factory(base, counting), counting, settings)
    return FeedbackServiceV21(store, engine, counting, default_config=default_config, startup_checks=startup_checks)
