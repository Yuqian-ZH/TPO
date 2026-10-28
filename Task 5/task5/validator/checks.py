"""Solver-backed checks on user feedback (DESIGN.md section 3.4).

Positive feedback ("thanks, now X"): is the praised change real, is it caused by this complaint's modifications, and
is the accepted plan feasible on the data the user has confirmed? If not, the acceptance rests on a misunderstanding
and must not become a positive training example (or, if the plan is infeasible, it is an incident).

Complaints: is the complained-about property caused by the user's own earlier inputs (a fix they accepted, data they
entered), or by a real physical constraint? Then the response is to show the trade-off or the reason, and the
complaint is not evidence that the model erred.

Claims arrive in the structured form the feedback localizer already produces (a target ID and a direction, or a
decision such as SEP(2,5)), so no LLM call is needed here."""
from feedback_service.bridge import apply_data_mods, canon
from tpo.commit import commit_solve

FORCED = "hard_constraint_forced"
TOL = 1e-9


def _better(v0, v1, direction):
    return v1 < v0 - TOL if direction == "decrease" else v1 > v0 + TOL


def _decision_text(d):
    return f"{d['type']}({d['i']},{d['j']})"


class Validator:
    def __init__(self, base, comps):
        """comps: Task 3's adapter over the real Task 2 components; the demo passes tpo_v21's, whose attribution is
        Task 2's task2_v2.1 (IIS for forced decisions, alternatives anchored to the current plan, audit F1; exact
        anchor test and no attribution of a plan over capacity, Task 2 README 8.4)."""
        self.base, self.comps = base, comps

    def data(self, mods):
        return apply_data_mods(self.base, list(mods))

    def check_praise(self, claim, before, after, confirmed_mods, mods_before, mods_after):
        """confirmed_mods: what the user has confirmed (session data and earlier accepted fixes, not this complaint's
        own changes); mods_before / mods_after: the model before and after the complaint's modifications."""
        flags, ev = [], {}
        ev["feasible_on_confirmed_data"] = canon.is_feasible(after, self.data(confirmed_mods))
        if not ev["feasible_on_confirmed_data"]:
            conf = canon.metrics(after, self.data(confirmed_mods))
            ev["loads_on_confirmed_data"] = {k: conf[f"W[{k}]"] for k in (1, 2)}
            ev["capacity_on_confirmed_data"] = self.data(confirmed_mods)["Q"]
            flags.append("infeasible_on_confirmed_data")
        if "target" in claim:
            v0 = canon.target_value(before, self.data(mods_before), claim["target"])
            v1 = canon.target_value(after, self.data(mods_after), claim["target"])
            ev[claim["target"]] = {"before": v0, "after": v1}
            if not _better(v0, v1, claim["direction"]):
                flags.append("praised_change_absent")
        else:
            d = claim["decision"]
            ev["holds_before"], ev["holds_after"] = canon.decision_holds(before, d), canon.decision_holds(after, d)
            if not ev["holds_after"]:
                flags.append("praised_decision_absent")
            elif ev["holds_before"]:
                a = self.comps.attribute(list(mods_before), before, d)
                ev["why_it_held_before"] = {k: a.get(k) for k in ("decision", "conclusion", "constraint_ids",
                                                                  "objective_increase_if_forbidden")}
                flags.append("credit_misattributed")
        verdict = ("incident" if "infeasible_on_confirmed_data" in flags else
                   "exclude_from_training" if flags else "usable_positive")
        return {"verdict": verdict, "flags": flags, "evidence": ev}

    def check_complaint(self, claim, plan, user_data, accepted):
        """user_data: data the user entered for the session; accepted: fixes the user accepted earlier.

        Target claims: re-solve without each user input in turn (a full re-solve with Task 2's single anchor, i.e.
        the control method of the counterfactual component; its query language has no 'remove a modification'
        query). The input is binding if dropping it moves the target the way the user asks. If dropping it leaves
        no feasible plan, that is recorded as evidence (the input is what makes the plan possible), not a cause.
        Decision claims: Task 2's attribution; if capacity forces the decision, attribute again with each
        user-entered data item reverted to see whether the user's own data is what forces it."""
        mods = list(user_data) + list(accepted)
        flags, ev, binding = [], {}, []
        if "target" in claim:
            v0 = canon.target_value(plan, self.data(mods), claim["target"])
            ev[claim["target"]] = v0
            ev["total_distance"] = canon.metrics(plan, self.data(mods))["total_distance"]
            for m in mods:
                rest = [x for x in mods if x is not m]
                r = commit_solve(self.base, rest, plan, [])
                if r["status"] != "optimal":
                    # the input is what makes the model feasible (e.g. a raised capacity): evidence, not a cause
                    ev.setdefault("without_each_user_input", []).append(
                        {"input": m, "feasible_without_it": False, "solver_status_without_it": r["status"]})
                    continue
                v1 = canon.target_value(r["solution"], self.data(rest), claim["target"])
                rec = {"input": m, f"{claim['target']}_without_it": v1, "routes_without_it": r["solution"]["routes"],
                       "total_distance_without_it": r["metrics"]["total_distance"]}
                ev.setdefault("without_each_user_input", []).append(rec)
                if _better(v0, v1, claim["direction"]):
                    binding.append(rec)
            if binding:
                flags.append("conflicts_with_user_input")
            verdict = "self_imposed" if binding else "genuine"
        else:
            d = claim["decision"]
            a = self.comps.attribute(mods, plan, d)
            ev["attribution"] = {"decision": _decision_text(d), "conclusion": a["conclusion"],
                                 "constraint_ids": a["constraint_ids"]}
            verdict = "genuine"
            if a["conclusion"] == FORCED:
                for m in [x for x in user_data if x["op"] == "modify_data"]:
                    rest = [x for x in mods if x is not m]
                    if commit_solve(self.base, rest, plan, [])["status"] != "optimal":
                        # no plan at all without it: an IIS would then "force" every decision
                        ev.setdefault("without_each_user_data_item", []).append({"input": m,
                                                                                 "feasible_without_it": False})
                        continue
                    b = self.comps.attribute(rest, plan, d)
                    rec = {"input": m, "conclusion_without_it": b["conclusion"]}
                    ev.setdefault("without_each_user_data_item", []).append(rec)
                    if b["conclusion"] != FORCED:
                        binding.append(rec)
                flags.append("forced_by_user_data" if binding else "forced_by_physical_constraint")
                verdict = "self_imposed" if binding else "hard_constraint"
        return {"verdict": verdict, "flags": flags, "binding_user_inputs": [b["input"] for b in binding],
                "evidence": ev}
