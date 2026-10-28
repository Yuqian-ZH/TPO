"""run_trial of task3_v3 (tpo_v3/loop.py), for task3_v31.

One change to the loop (DESIGN_V31.md section 2): the session's modifications (U9, U10: soft constraints set before
the complaint) were always in the model the solver re-optimizes, but task3_v3's prompt said "Modifications currently
in force: none" and the system prompt says an empty answer returns to the plain distance optimum, so the LLM often
wrote them again and lost one of its 4 modifications. A block before "Modifications currently in force" now lists
them, worded like Task 4's "Modifications accepted earlier". Cases without session modifications get task3_v3's
prompt byte for byte.

Supplementary configurations (section 3): S1a and S1b are A0B1C0 and A1B1C1 with blind selection (tpo/loop.py's
Flags.blind: three candidates and the selector, no probe); S2a is A0B0C0 with the clarification answer appended to
the complaint (Flags.clar_text) whenever the shared localization asked, after which the user has explained."""
import json
from dataclasses import asdict

from tpo.llm import PROTOCOL
from tpo.loop import CONFIGS as V1_CONFIGS, MAIN, Flags, Settings, _strip_ids, needs_localization
from tpo.public_case import public_view
from tpo.task2_bridge import canon

from v3.conditions import real_data

from tpo_v3.loop import TrialV3, localize_with_clarification  # noqa: F401  (task3_v3's shared localization)
from tpo_v3.user_sim import SimulatedUserV3

SUPPLEMENTARY = ("S1a", "S1b", "S2a")
CONFIGS = {**{g: V1_CONFIGS[g] for g in MAIN},
           "S1a": Flags(False, True, False, blind=True),
           "S1b": Flags(True, True, True, blind=True),
           "S2a": Flags(False, False, False, clar_text=True)}
ALL = MAIN + SUPPLEMENTARY
RUNS = (6, 7, 8, 9, 10)            # seeds derive from the run number; task3_v3 used 1-5


def session_block(mods):
    lines = ["## Modifications set earlier in this session (kept in force)",
             "They were in the model before this complaint. They stay in force whatever you answer; do not repeat "
             "them. An empty answer returns the plan to the optimum of the model with them."]
    lines += [f"- {json.dumps(m, separators=(', ', ': '))}" for m in _strip_ids(mods)]
    return "\n".join(lines)


class TrialV31(TrialV3):
    def session_mods(self):
        return list(self.pc.model_modifications)

    def blocks(self):
        b, attr = super().blocks()
        if self.session_mods():
            b["mods_in_force"] = session_block(self.session_mods()) + "\n\n" + b["mods_in_force"]
        return b, attr


def run_trial(case, base, flags, config, run, comps, llm, settings=Settings(), loc=None):
    """tpo_v3.loop.run_trial with TrialV31. The user starts explained whenever the prompt carries the clarification
    answer: condition C after a question, or S2a's appended answer."""
    pc = public_view(case)
    user = SimulatedUserV3(case, base, explained=bool(needs_localization(flags) and loc and loc["asked"]))
    rec = {"protocol": "task3_v31", "seed_protocol": PROTOCOL, "case_id": pc.id, "stratum": case["stratum"],
           "config": config, "run": run, "flags": asdict(flags), "settings": asdict(settings),
           "localization": loc if needs_localization(flags) else None, "user_explained_at_start": user.explained,
           "iterations": []}
    if needs_localization(flags) and loc is None:
        raise ValueError(f"{config} needs the shared localization of ({pc.id}, run {run})")
    if flags.C and loc["final"].get("confidence") != "high":
        rec.update(outcome="stopped_low_confidence", converged=False, converged_at=None,
                   final_solution=pc.solution, final_mods=[])
        return rec
    trial = TrialV31(pc, base, user, flags, config, run, comps, llm, settings, loc)
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
