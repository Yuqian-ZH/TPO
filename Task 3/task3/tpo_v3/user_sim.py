"""Simulated user of task3_v3 (DESIGN_V3.md section 4).

The verdict is Task 2's v3 conditions: feasible on the real data and every condition the user stated holds. The
user's words are the same in every configuration: a clarifying question gets the case's explanation; a plan that
does not resolve the complaint gets the explanation the first time (unless the user already gave it as a
clarification) and, every time, the conditions still unmet with the plan's values."""
from tpo import task2_bridge  # noqa: F401  (puts Task 2 on sys.path)

from v3 import conditions     # Task 2's task2_v3 package


class SimulatedUserV3:
    def __init__(self, case, base, explained=False):
        self.case, self.base, self.explained = case, base, explained

    def verdict(self, sol):
        return conditions.verdict(self.case, sol, self.base)

    def resolved(self, sol):
        return self.verdict(sol)["resolved"]

    def feedback(self, verdict):
        text = conditions.feedback(self.case, verdict, self.explained)
        self.explained = True
        return text

    def clarify(self, question):
        self.explained = True
        return self.case["explanation"]

    def label_swap_resolved(self, sol):
        """Diagnostic: would the verdict change if the two vehicle labels were swapped?"""
        return self.resolved({"routes": [list(r) for r in sol["routes"][::-1]]})

    def illegal_data_mods(self, mods):
        allowed = [(m["field"], m["value"]) for m in self.case.get("allowed_data_corrections", [])]
        return [m for m in mods if m["op"] == "modify_data" and (m["field"], m["value"]) not in allowed]
