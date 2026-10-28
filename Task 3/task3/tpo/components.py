"""Adapters for the three Task 2 components, normalized to what the loop consumes.

- Task2Components: the real Task 2 components (interface checked at G2, plan 2.1).
- ReferenceComponents: brute-force attribution, a full-solve probe and scripted localization, in the same
  normalized shapes. Used by pytest and the toy smoke only; it is a stand-in, not the ablated component.

Normalized shapes (prompt-facing fields; anything under "raw" is logged but never prompted)
  attribute(mods, sol, decision) -> {"decision", "conclusion", "constraint_ids", "variable_ids",
        "objective_increase_if_forbidden", "increase_by_term", "edges_only_in_current_plan",
        "edges_only_in_alternative", "customers_switching_vehicle", "raw"}
  probe(case_mods, sol, mods) -> {"feasible", "level", "objective", "delta_objective", "distance_before",
        "distance_after", "metric_changes", "change_set", "solution", "raw"}
  localize(case_mods, sol, complaint, clarification, run, case_id) -> {"confidence", "clarification_question",
        "critique", "raw"}            clarification is None or {"question", "answer"}
  refresh_critique(critique, mods, sol) -> critique with evidence (and text) recomputed on the current plan"""
import json

from .commit import commit_solve
from .task2_bridge import INSTANCE, apply_data_mods, canon, oracle_for

CONCLUSION_FORCED = "hard_constraint_forced"
CONCLUSION_PREFERRED = "objective_preferred"


def decision_text(d):
    return f"{d['type']}({d['i']},{d['j']})"


def _edges(pairs, c):
    return [{"edge": f"e[{a},{b}]", "distance": c[a][b]} for a, b in pairs]


class ReferenceComponents:
    def __init__(self, base, localizations=None):
        self.base = base
        self.localizations = localizations or {}   # case_id -> {"first": flat, "clarified": flat}

    def attribute(self, mods, sol, decision):
        base = self.base
        data = apply_data_mods(base, mods)
        o = oracle_for(base, mods)
        prim = canon.forbid_decision(decision)
        r = o.solve(mods, [prim])
        out = {"decision": decision_text(decision)}
        if not r["feasible"]:
            needed = [f"cap[{k}]" for k in (1, 2)
                      if o.solve(mods, [prim], capacity=tuple(v for v in (1, 2) if v != k))["feasible"]]
            out.update(conclusion=CONCLUSION_FORCED, constraint_ids=needed, variable_ids=[])
            return out
        new = r["optimal"][0]
        cs = canon.change_set(sol, new)
        ids_ = sorted({f"e[{a},{b}]" for a, b in cs["added_edges"] + cs["removed_edges"]})
        out.update(conclusion=CONCLUSION_PREFERRED, constraint_ids=[], variable_ids=ids_,
                   objective_increase_if_forbidden=round(r["objective"] - canon.objective(sol, data, mods), 6),
                   edges_only_in_current_plan=_edges(cs["removed_edges"], data["c"]),
                   edges_only_in_alternative=_edges(cs["added_edges"], data["c"]),
                   customers_switching_vehicle=cs["moved"])
        return out

    def probe(self, case_mods, sol, mods):
        r = commit_solve(self.base, case_mods, sol, mods)
        all_mods = list(case_mods) + list(mods)
        data = apply_data_mods(self.base, all_mods)
        out = {"feasible": r["status"] == "optimal", "level": "reference_full"}
        if out["feasible"]:
            before, after = canon.metrics(sol, data), r["metrics"]
            cs = canon.change_set(sol, r["solution"])
            cur = canon.objective(sol, data, all_mods)
            out.update(objective=r["objective"], delta_objective=r["objective"] - cur,
                       distance_before=before["total_distance"], distance_after=after["total_distance"],
                       metric_changes={k: [before[k], after[k]] for k in after if before.get(k) != after[k]},
                       change_set={k: cs[k] for k in ("moved", "added_edges", "removed_edges")},
                       solution=r["solution"])
        return out

    def localize(self, case_mods, sol, complaint, clarification, run, case_id):
        flat = self.localizations[case_id]["clarified" if clarification else "first"]
        high = flat["confidence"] == "high"
        critique = ({k: flat.get(k) for k in ("target", "aspect", "direction", "modification_type", "evidence")}
                    | {"confidence": "high", "complaint": complaint}) if high else None
        return {"confidence": flat["confidence"], "clarification_question": flat.get("clarification_question"),
                "critique": critique, "raw": flat}

    def refresh_critique(self, critique, mods, sol):
        m = canon.metrics(sol, apply_data_mods(self.base, mods))
        return {**critique, "evidence": {k: m.get(k, v) for k, v in (critique.get("evidence") or {}).items()}}


class Task2Components:
    """The real components; the instance is always the frozen Task 2 instance."""

    def __init__(self, base, llm, run_label="t3-{run}", probe="v2"):
        """probe: "v2" = Task 3's escalation rule (decision ④); "task2_frozen" = Task 2's local method as frozen."""
        from components import attribution, counterfactual, localization   # Task 2 package
        from . import counterfactual_v2
        self.att, self.loc = attribution, localization
        self.cf = (counterfactual_v2.counterfactual if probe == "v2" else
                   lambda state, q: counterfactual.counterfactual(state, q, method="local"))
        self.base, self.llm, self.run_label, self.probe_version = base, llm, run_label, probe
        with open(INSTANCE) as f:
            self.instance = json.load(f)

    def _state(self, mods, sol):
        return {"instance": self.instance, "modifications": list(mods), "solution": sol}

    def attribute(self, mods, sol, decision):
        a = self.att.attribute(self._state(mods, sol), decision)
        out = {"decision": a["decision_text"], "conclusion": a["conclusion"],
               "constraint_ids": a.get("attribution_set", {}).get("constraints", []),
               "variable_ids": a.get("attribution_set", {}).get("variables", [])}
        if a["conclusion"] == CONCLUSION_PREFERRED:
            terms = {k: v for k, v in a["objective_increase_by_term"].items() if v}
            out.update(objective_increase_if_forbidden=a["objective_increase_if_forbidden"],
                       increase_by_term=terms if set(terms) - {"distance"} else None,
                       edges_only_in_current_plan=a["edges_only_in_current_plan"],
                       edges_only_in_alternative=a["edges_only_in_alternative"],
                       customers_switching_vehicle=a["customers_on_other_vehicle_in_alternative"])
        out["raw"] = {k: v for k, v in a.items() if k not in ("lp_relaxation", "constraint_activity")}
        return out

    def probe(self, case_mods, sol, mods):
        q = {"type": "APPLY_MODIFICATIONS", "mods": list(mods)}
        r = self.cf(self._state(case_mods, sol), q)
        out = {"feasible": r["feasible"], "level": r.get("level"), "probe_version": self.probe_version,
               "raw": {k: v for k, v in r.items() if k not in ("solution", "query")}}
        if r["feasible"]:
            out.update(objective=r["objective"], delta_objective=r["delta_objective"],
                       distance_before=r["current_distance"], distance_after=r["total_distance"],
                       metric_changes={k: [v["before"], v["after"]] for k, v in r["metric_changes"].items()},
                       change_set=r["change_set"], solution=r["solution"])
        return out

    def localize(self, case_mods, sol, complaint, clarification, run, case_id):
        r = self.loc.localize(self._state(case_mods, sol), complaint, self.llm, case_id,
                              self.run_label.format(run=run), clarification=clarification)
        return {"confidence": r["confidence"], "clarification_question": r.get("clarifying_question"),
                "critique": r.get("critique"), "raw": r}

    def refresh_critique(self, critique, mods, sol):
        c = {**critique, "evidence": self.loc.evidence(critique["target"], self._state(mods, sol))}
        c["critique_text"] = self.loc.critique_text(c)
        return c
