"""run_trial and the shared localization of task3_v1 (tpo/loop.py), for task3_v3.

Two changes (DESIGN_V3.md sections 4 and 9):
1. The user is SimulatedUserV3; a trial whose prompt shows the clarification (condition C after a question) starts
   with a user who has already explained.
2. Every iteration starts from the plan the user complained about, under the session's model (TrialV3). task3_v1
   started iteration t+1 from the plan committed at t, which the user had just rejected; the user's conditions
   "at most two customers may change trucks" and "vehicle 1 keeps its route" refer to the plan complained about,
   so from iteration 2 on the plan in the prompt, the decisions A attributes, the changes B's probe reports and the
   commit's anchor all referred to a different plan than the user (found in the pilot, section 9). Earlier attempts
   stay in the history block with their modifications, resulting plans and the user's feedback. A proposal replaces
   all modifications anyway, so the solver's answer depends on the starting plan only through the anchor.
The trial record also gets the distance above the shortest plan that meets every condition (section 5)."""
from dataclasses import asdict

from tpo.llm import PROTOCOL
from tpo.loop import Settings, Trial, _strip_ids, needs_localization
from tpo.public_case import public_view
from tpo.task2_bridge import canon

from v3.conditions import real_data

from .user_sim import SimulatedUserV3


class TrialV3(Trial):
    """task3_v1's Trial, reset after every iteration to the plan complained about and the session's model."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.last_sol, self.last_mods = self.sol, self.mods

    def step(self, t):
        rec = super().step(t)
        self.last_sol, self.last_mods = self.sol, self.mods
        self.sol, self.mods = self.pc.solution, []
        return rec


def localize_with_clarification(case, base, comps, run):
    """Shared by every configuration of the same (case, run): one localization, one clarification at most."""
    pc, user = public_view(case), SimulatedUserV3(case, base)
    args = (list(pc.model_modifications), pc.solution, pc.complaint)
    first = comps.localize(*args, None, run, pc.id)
    rec = {"case_id": pc.id, "run": run, "initial": first, "asked": False, "question": None, "answer": None,
           "after_clarification": None, "final": first}
    if first.get("confidence") == "high":
        return rec
    q = first.get("clarification_question") or "Could you say more precisely what is wrong with the plan?"
    ans = user.clarify(q)
    second = comps.localize(*args, {"question": q, "answer": ans}, run, pc.id)
    rec.update(asked=True, question=q, answer=ans, after_clarification=second, final=second)
    return rec


def run_trial(case, base, flags, config, run, comps, llm, settings=Settings(), loc=None):
    pc = public_view(case)
    user = SimulatedUserV3(case, base, explained=bool(flags.C and loc and loc["asked"]))
    rec = {"protocol": "task3_v3", "seed_protocol": PROTOCOL, "case_id": pc.id, "stratum": case["stratum"],
           "config": config, "run": run, "flags": asdict(flags), "settings": asdict(settings),
           "localization": loc if needs_localization(flags) else None, "user_explained_at_start": user.explained,
           "iterations": []}
    if needs_localization(flags) and loc is None:
        raise ValueError(f"{config} needs the shared localization of ({pc.id}, run {run})")
    if flags.C and loc["final"].get("confidence") != "high":
        rec.update(outcome="stopped_low_confidence", converged=False, converged_at=None,
                   final_solution=pc.solution, final_mods=[])
        return rec
    trial = TrialV3(pc, base, user, flags, config, run, comps, llm, settings, loc)
    for t in range(1, settings.max_iters + 1):
        it = trial.step(t)
        rec["iterations"].append(it)
        if it["verdict"]["resolved"]:
            rec.update(outcome="converged", converged=True, converged_at=t)
            break
    else:
        rec.update(outcome="not_converged", converged=False, converged_at=None)
    rec.update(final_solution=trial.last_sol, final_mods=_strip_ids(trial.last_mods))
    if rec["converged"]:
        dist = canon.metrics(trial.last_sol, real_data(case, base))["total_distance"]
        rec["excess_distance"] = dist - case["min_compliant_distance"]
    return rec
