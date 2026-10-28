"""Task 3's adapter over the Task 2 components, with Task 2's task2_v2 attribution and localization.

Attribution (audit F1): anchored to the current plan, no relabelling, direction flipped only on ties; a decision
whose removal lowers the objective is reported as "cheaper_without" and carries the same fields as an
objective-preferred one, so the prompt shows the (negative) change.
Localization (audit F5): task2_v2's rule. The formal run re-uses task3_v1's shared localizations only after
checking that the v2 rule reaches the same decision and question on their samples (run_experiment_v2.py)."""
from tpo.components import Task2Components

from v2 import attribution as attribution_v2    # Task 2's task2_v2 package (on sys.path via task2_bridge)
from v2 import localization as localization_v2

ALTERNATIVE_CONCLUSIONS = (attribution_v2.PREFERRED, attribution_v2.CHEAPER)


class Task2ComponentsV2(Task2Components):
    def __init__(self, base, llm, run_label="t3-{run}", probe="v2"):
        super().__init__(base, llm, run_label, probe)
        self.att, self.loc = attribution_v2, localization_v2

    def attribute(self, mods, sol, decision):
        a = self.att.attribute(self._state(mods, sol), decision)
        out = {"decision": a["decision_text"], "conclusion": a["conclusion"],
               "constraint_ids": a.get("attribution_set", {}).get("constraints", []),
               "variable_ids": a.get("attribution_set", {}).get("variables", [])}
        if a["conclusion"] in ALTERNATIVE_CONCLUSIONS:
            terms = {k: v for k, v in a["objective_increase_by_term"].items() if v}
            out.update(objective_increase_if_forbidden=a["objective_increase_if_forbidden"],
                       increase_by_term=terms if set(terms) - {"distance"} else None,
                       edges_only_in_current_plan=a["edges_only_in_current_plan"],
                       edges_only_in_alternative=a["edges_only_in_alternative"],
                       customers_switching_vehicle=a["customers_on_other_vehicle_in_alternative"])
        out["raw"] = {k: v for k, v in a.items() if k not in ("lp_relaxation", "constraint_activity")}
        return out
