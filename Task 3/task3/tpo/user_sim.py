"""Simulated user (plan 3.4): verdicts come from Task 2's checkers; feedback uses fixed templates that never
reveal the checker, its threshold or its value."""
from .task2_bridge import checkers

FEEDBACK_INFEASIBLE = ("This plan can't be used: with the real customer demands, a vehicle would be over capacity. "
                       "My original complaint: {complaint}")
FEEDBACK_UNRESOLVED = "The new plan still doesn't fix my complaint: {complaint}"
NOTE_NO_PLAN = "No feasible plan exists with the proposed changes; the previous plan is kept."
NOTE_REJECTED = "The proposed modifications were rejected: {errors}"


class SimulatedUser:
    def __init__(self, case, base):
        self.case = case
        self.base = base

    def verdict(self, sol):
        return checkers.complaint_resolved(self.case, sol, self.base)

    def resolved(self, sol):
        return self.verdict(sol)["resolved"]

    def feedback(self, verdict):
        tpl = FEEDBACK_UNRESOLVED if verdict["feasible"] else FEEDBACK_INFEASIBLE
        return tpl.format(complaint=self.case["complaint"])

    def clarify(self, question):
        return self.case["clarification_answer"]

    def label_swap_resolved(self, sol):
        """Diagnostic: would the verdict change if the two vehicle labels were swapped?"""
        return self.resolved({"routes": [list(r) for r in sol["routes"][::-1]]})

    def illegal_data_mods(self, mods):
        allowed = [(m["field"], m["value"]) for m in self.case.get("allowed_data_corrections", [])]
        return [m for m in mods if m["op"] == "modify_data" and (m["field"], m["value"]) not in allowed]
