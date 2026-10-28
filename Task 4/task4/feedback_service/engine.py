"""TPO refinement on top of Task 3's Trial, which stays frozen and unchanged (plan 3.7).

Three seams adapt the experiment loop to a service whose user answers in a later HTTP request:
  1. DeferredUser: every verdict inside a step is "pending"; the real one arrives with the reply.
  2. The reply text replaces the placeholder in the trial history before the next step (service.py).
  3. ServiceTrial.blocks(): modifications accepted with earlier complaints are shown to the LLM. Without
     them the prompt is byte-for-byte Task 3's."""
import json
import re

from .bridge import CONFIGS, CVRPModel, PublicCase, Settings, Trial, apply_data_mods, canon
from .store import now
from tpo.commit import orient_ties  # noqa: E402  (tpo is importable once .bridge has run)

SERVICE_SETTINGS = Settings(tie_diagnostic=False)   # the tie diagnostic needs the user's checker
PENDING = "(awaiting the user's reply)"
CRITIQUE_HEADINGS = ("## User complaint", "## Clarification", "## Structured localization",
                     "## Decision attribution", "## Previous attempts")


class DeferredUser:
    def verdict(self, sol):
        return {"resolved": False, "pending": True}

    def feedback(self, verdict):
        return PENDING

    def illegal_data_mods(self, mods):
        """Task 3 asks the simulated user which data changes were not allowed; a real user confirms them by
        accepting the plan, so here this lists the data changes the plan depends on."""
        return [m for m in mods if m["op"] == "modify_data"]

    def resolved(self, sol):
        raise AssertionError("the service has no checker; tie_diagnostic must stay off")

    def label_swap_resolved(self, sol):
        raise AssertionError("a verdict inside a step is never 'resolved'")


def strip_ids(mods):
    return [{k: v for k, v in m.items() if k != "id"} for m in mods]


def with_ids(mods, tag):
    """Soft constraints get ids unique to their origin (session data, or the n-th accepted complaint), so they
    never collide with the tpo_<t>_<s> ids of a later complaint."""
    out, k = [], 0
    for m in mods:
        if m["op"] == "add_soft_constraint":
            k += 1
            m = {**m, "id": f"{tag}_{k}"}
        out.append(m)
    return out


def accepted_block(mods):
    lines = ["## Modifications accepted earlier (kept in force)",
             "The user accepted these with earlier complaints. They stay in force whatever you answer; "
             "do not repeat them."]
    lines += [f"- {json.dumps(m, separators=(', ', ': '))}" for m in strip_ids(mods)]
    return "\n".join(lines)


def critique_sections(prompt):
    """The part of a proposal prompt that is the textual loss: complaint, clarification, localization,
    attribution and previous attempts (instance, plan and modification blocks are context, not critique)."""
    return "\n\n".join(s for s in re.split(r"\n\n(?=## )", prompt) if s.startswith(CRITIQUE_HEADINGS))


class ServiceTrial(Trial):
    def __init__(self, *args, accepted=(), **kw):
        super().__init__(*args, **kw)
        self.accepted = list(accepted)

    def blocks(self):
        b, attr = super().blocks()
        if self.accepted:
            b["mods_in_force"] = accepted_block(self.accepted) + "\n\n" + b["mods_in_force"]
        return b, attr


def thread_mods(fb):
    """Model modifications every step of this complaint builds on: session data, then accepted fixes."""
    return list(fb["session_modifications"]) + list(fb["accepted_modifications"])


class Engine:
    def __init__(self, base, comps, llm, settings=SERVICE_SETTINGS):
        self.base, self.comps, self.llm, self.settings = base, comps, llm, settings

    def data(self, mods):
        return apply_data_mods(self.base, list(mods))

    # ---------- plans ----------

    def initial_plan(self, mods):
        """Optimal plan of instance + session modifications in Task 2's reference form (customer 1 on vehicle 1,
        tied directions canonical); None if no feasible plan exists."""
        r = CVRPModel(self.base, list(mods)).optimize()
        if r["status"] != "optimal":
            return None
        routes = [list(x) for x in r["solution"]["routes"]]
        if 1 not in routes[0]:
            routes = routes[::-1]
        sol, _ = orient_ties({"routes": routes}, self.data(mods), list(mods))
        return sol, canon.objective(sol, self.data(mods), list(mods))

    def plan_record(self, sol, mods, version, source):
        data = self.data(mods)
        return {"version": version, "routes": [list(r) for r in sol["routes"]],
                "objective": canon.objective(sol, data, list(mods)), "metrics": canon.metrics(sol, data),
                "source": source, "created_at": now()}

    # ---------- complaint processing ----------

    def localize(self, fb, clarification):
        return self.comps.localize(thread_mods(fb), {"routes": fb["solution"]["routes"]}, fb["complaint"],
                                   clarification, 1, fb["feedback_id"])

    def critique_on(self, fb, trial):
        """The structured critique with its evidence recomputed on the trial's current plan (what the
        localization block of this iteration's prompt shows); None when C is off."""
        loc = fb.get("localization")
        if not (CONFIGS[fb["config"]].C and loc and loc["final"].get("critique")):
            return None
        return self.comps.refresh_critique(loc["final"]["critique"], trial.model_mods(), trial.sol)

    # ---------- refinement ----------

    def trial(self, fb):
        pc = PublicCase(id=fb["feedback_id"], solution={"routes": [list(r) for r in fb["solution"]["routes"]]},
                        complaint=fb["complaint"], model_modifications=tuple(thread_mods(fb)))
        tr = ServiceTrial(pc, self.base, DeferredUser(), CONFIGS[fb["config"]], fb["config"], 1, self.comps,
                          self.llm, self.settings, loc=fb.get("localization"),
                          accepted=fb["accepted_modifications"])
        st = fb.get("trial")
        if st:
            tr.sol, tr.mods, tr.history = st["sol"], st["mods"], st["history"]
        return tr

    def feasibility(self, rec, fb, trial):
        """Solver status, plus an independent pure-Python check of the plan on the data in force and on the
        data the user has confirmed (session data and accepted fixes, without this complaint's data changes)."""
        sol = rec["solution_after"]
        data_changes = strip_ids([m for m in trial.mods if m["op"] == "modify_data"])
        return {"iteration_status": rec["status"],
                "solver_status": (rec.get("commit") or {}).get("status", "not_solved"),
                "feasible": canon.is_feasible(sol, self.data(trial.model_mods())),
                "feasible_on_confirmed_data": canon.is_feasible(sol, self.data(thread_mods(fb))),
                "data_modifications_in_force": data_changes,
                "checked_by": "canon.is_feasible: two non-empty routes, every customer exactly once, capacity"}

    def iteration_record(self, fb, rec, trial, trigger, critique, versions, usage):
        """One line of the logging layer (plan 3.8)."""
        mods_before = thread_mods(fb) + rec["mods_before"]
        mods_after = trial.model_mods()
        before, after = rec["input_solution"], rec["solution_after"]
        chosen = next((c for c in rec["candidates"] if c["sample"] == rec.get("chosen_sample")), None)
        return {
            "session_id": fb["session_id"], "feedback_id": fb["feedback_id"], "iteration": rec["t"],
            "config": fb["config"], "time": now(), "trigger": trigger,
            "input_solution": {"version": versions[0], "routes": before["routes"],
                               "metrics": canon.metrics(before, self.data(mods_before))},
            "complaint": fb["complaint"],
            "user_replies_so_far": [r["comment"] for r in fb["replies"]],
            "critique": {"structured": critique, "text": critique_sections(rec["proposal_prompt"]),
                         "blocks": rec["blocks"]},
            "candidates": [{"sample": c["sample"], "valid": c["valid"], "errors": c["errors"],
                            "modifications": c["modifications"], "rationale": c.get("rationale"),
                            "probe": {k: c["probe"].get(k) for k in ("feasible", "level", "objective",
                                                                     "delta_objective", "distance_after")}
                            if c.get("probe") else None} for c in rec["candidates"]],
            "selection": {k: v for k, v in (rec.get("selection") or {}).items() if k != "prompt"} or None,
            "status": rec["status"], "note": rec["note"], "rationale": chosen.get("rationale") if chosen else None,
            "committed_modifications": rec["committed_mods"],
            "refined_solution": {"version": versions[1], "routes": after["routes"],
                                 "metrics": canon.metrics(after, self.data(mods_after)),
                                 "new_plan": versions[1] != versions[0],
                                 "changes": canon.change_set(before, after)},
            "feasibility": self.feasibility(rec, fb, trial),
            "llm": usage, "wall_s": rec["wall_s"],
            "detail": rec,
        }
