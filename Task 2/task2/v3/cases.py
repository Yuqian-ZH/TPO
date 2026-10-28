"""task2_v3 cases: specifications, ground truth and design checks, all by brute force (never by Gurobi).
Run from the Task 2 root:  python -m v3.cases     -> v3/cases/{test_cases,dev_cases}.json and v3/cases/cases.md

Three strata (DESIGN_V3.md section 3), the same recipe for the 10 test and the 10 development cases:
  control    a clear request; the most direct encoding (one soft constraint at the user's limit) resolves it
  ambiguity  a vague complaint whose referent the explanation settles; the most plausible misreading does not
             resolve it
  side       a clear request plus a second condition a dispatcher states (a route that may not change any more,
             at most one exchange of customers between the trucks, a distance budget, an earlier fix that must
             hold); the most direct encoding of the request violates the second condition in every optimum, while
             at most 4 modifications resolve both

Each build checks: the plan complained about fails the case; a plan meeting every condition exists (its distance is
recorded); the reference modification (at most 4, the commit's anchor) resolves the case in every optimum; and the
stratum's property above."""
import json
import os

import numpy as np

from cases.gt import attribution_gt, counterfactual_gt
from cvrp import canon
from cvrp.data import apply_data_mods, load_instance
from cvrp.oracle import oracle_for

from v2.attribution import orient_ties

from .conditions import real_data, verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "v3", "cases")
SOFT, WEIGHT, DATA = "add_soft_constraint", "set_objective_weight", "modify_data"
MAX_MODS = 4


def soft(target, sense, rhs, penalty=100):
    return {"op": SOFT, "target": target, "sense": sense, "rhs": rhs, "penalty": penalty}


def weight(term, w):
    return {"op": WEIGHT, "term": term, "weight": w}


def data(field, value):
    return {"op": DATA, "field": field, "value": value}


def cond(kind, **params):
    return {"kind": kind, "params": params}


def loc(targets, types, confidence):
    return {"targets": targets, "modification_types": types, "confidence": confidence}


R0_NOTE = "Reference instance; the plan complained about is its optimum (351 km)."

TEST = [
    dict(id="U1", stratum="control", object="vehicle", clarity="clear", scenario=R0_NOTE,
         complaint="Vehicle 2 is on the road for 211 km today. That is too much for one driver: its route must not "
                   "be longer than 180 km.",
         explanation="I mean the total length of vehicle 2's route: it should be 180 km or less.",
         conditions=[cond("max", target="L[2]", max=180)],
         direct=[soft("L[2]", "<=", 180)], reference=[soft("L[2]", "<=", 180)],
         localization=loc(["L[2]"], [SOFT], "high"),
         why_question="Customer 3 is only 20 km from customer 1. Why is it on vehicle 2 and not with customer 1?",
         why_decision={"type": "SEP", "i": 1, "j": 3},
         what_if_question="What if vehicle 2's route were limited to 180 km?",
         what_if={"type": "APPLY_MODIFICATIONS", "mods": [soft("L[2]", "<=", 180, 10)]}),
    dict(id="U2", stratum="control", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="The direct road between customers 6 and 8 is closed today, so no truck may drive straight from "
                   "one to the other.",
         explanation="No truck may drive directly from customer 6 to customer 8 or back.",
         conditions=[cond("not_adjacent", i=6, j=8)],
         direct=[soft("e[6,8]", "<=", 0)], reference=[soft("e[6,8]", "<=", 0)],
         localization=loc(["e[6,8]"], [SOFT], "high"),
         why_question="Why does vehicle 2 drive from customer 6 straight to customer 8?",
         why_decision={"type": "ADJ", "i": 6, "j": 8},
         what_if_question="What if vehicle 2 went to customer 8 first?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 8}),
    dict(id="U3", stratum="ambiguity", object="vehicle", clarity="ambiguous", scenario=R0_NOTE,
         complaint="Vehicle 1 is doing too much work.",
         explanation="I mean the load: vehicle 1 leaves the depot with 99 units, which is practically full. It should "
                     "carry at most 92 units.",
         conditions=[cond("max", target="W[1]", max=92)],
         misreading=[soft("load_balance", "<=", 5)], reference=[soft("W[1]", "<=", 92)],
         localization=loc(["W[1]"], [SOFT], "low"),
         why_question="Why are customers 1 and 2 both served by vehicle 1?",
         why_decision={"type": "SAME", "i": 1, "j": 2},
         what_if_question="What if customer 7 were moved to vehicle 2?",
         what_if={"type": "MOVE", "i": 7, "k": 2}),
    dict(id="U4", stratum="ambiguity", object="data", clarity="ambiguous", scenario=R0_NOTE,
         complaint="One of the numbers you have for customer 7 is wrong. It should be 18.",
         explanation="I mean the order size: customer 7 now orders 18 units, not 11.",
         conditions=[], allowed_data_corrections=[data("demand[7]", 18)],
         misreading=[data("coord[7]", [6, 18])], reference=[data("demand[7]", 18)],
         localization=loc(["demand[7]"], [DATA], "low"),
         why_question="Why does vehicle 1 go from customer 7 to customer 2?",
         why_decision={"type": "ADJ", "i": 2, "j": 7},
         what_if_question="What if customers 2 and 7 were on different vehicles?",
         what_if={"type": "FORCE_SEP", "i": 2, "j": 7}),
    dict(id="U5", stratum="ambiguity", object="global", clarity="ambiguous", scenario=R0_NOTE,
         complaint="The drivers are unhappy with how the work is split between the two vehicles.",
         explanation="It is about the loads: one truck carries 99 units and the other 90. The two loads should differ "
                     "by at most 5 units, even if that costs some extra distance.",
         conditions=[cond("max", target="load_balance", max=5)],
         misreading=[soft("balance", "<=", 50)], reference=[soft("load_balance", "<=", 5)],
         localization=loc(["load_balance"], [WEIGHT, SOFT], "low"),
         why_question="Why are customers 2 and 7 on the same vehicle?",
         why_decision={"type": "SAME", "i": 2, "j": 7},
         what_if_question="What if customers 1 and 8 swapped vehicles?",
         what_if={"type": "SWAP", "i": 1, "j": 8}),
    dict(id="U6", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customer 6 is only 47 km from the depot, but it is reached after 95 km of driving. It should be "
                   "reached within the first 70 km. Vehicle 1 has already left the depot, so its route cannot change "
                   "any more.",
         explanation="Customer 6 must be reached within 70 km, and vehicle 1 keeps its route 0 -> 1 -> 4 -> 7 -> 2 "
                     "-> 0 exactly.",
         conditions=[cond("max", target="A[6]", max=70), cond("route_kept", k=1)],
         direct=[soft("A[6]", "<=", 70)],
         reference=[soft("A[6]", "<=", 70), soft("same[1,4]", ">=", 1), soft("same[1,7]", ">=", 1),
                    soft("same[1,2]", ">=", 1)],
         localization=loc(["A[6]"], [SOFT], "high"),
         why_question="Why does vehicle 2 go from customer 3 to customer 6?",
         why_decision={"type": "ADJ", "i": 3, "j": 6},
         what_if_question="What if vehicle 2 went to customer 6 first?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 6}),
    dict(id="U7", stratum="side", object="vehicle", clarity="clear", scenario=R0_NOTE,
         complaint="Vehicle 1 is loaded with 99 of its 100 units, which its driver finds too risky: it should carry "
                   "at most 94 units. Both trucks are already half loaded, so at most two customers may change "
                   "trucks.",
         explanation="Vehicle 1 should carry at most 94 units, and at most two customers may move to the other truck.",
         conditions=[cond("max", target="W[1]", max=94), cond("max_moved", max=2)],
         direct=[soft("W[1]", "<=", 94)],
         reference=[soft("W[1]", "<=", 94), soft("same[1,7]", ">=", 1)],
         localization=loc(["W[1]"], [SOFT], "high"),
         why_question="Why are customers 2 and 5 on different vehicles?",
         why_decision={"type": "SEP", "i": 2, "j": 5},
         what_if_question="What if vehicle 1 also served customer 3?",
         what_if={"type": "MOVE", "i": 3, "k": 1}),
    dict(id="U8", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customers 2, 4, 5 and 7 are all in the south-west. If possible, one truck should serve all four. "
                   "If the trucks are too small for that, at least customers 4 and 5 should share a truck, and the "
                   "total distance must not go above 370 km.",
         explanation="Ideally customers 2, 4, 5 and 7 share one truck; if that cannot be done, customers 4 and 5 "
                     "share a truck and the total distance stays at or below 370 km.",
         conditions=[cond("same", i=4, j=5), cond("total_max", max=370)],
         impossible_wish=[cond("same", i=2, j=4), cond("same", i=4, j=5), cond("same", i=5, j=7)],
         direct=[soft("same[2,4]", ">=", 1), soft("same[4,5]", ">=", 1), soft("same[5,7]", ">=", 1)],
         reference=[soft("same[4,5]", ">=", 1)],
         localization=loc(["same[4,5]", "sep[4,5]"], [SOFT], "high"),
         why_question="Why are customers 2 and 5 not on the same vehicle?",
         why_decision={"type": "SEP", "i": 2, "j": 5},
         what_if_question="What if customers 2 and 5 had to share a vehicle?",
         what_if={"type": "FORCE_SAME", "i": 2, "j": 5}),
    dict(id="U9", stratum="side", object="customer", clarity="clear",
         scenario="Earlier in this session the user reported that the road between customers 4 and 7 is closed; the "
                  "fix was accepted and stays in force.",
         model_modifications=[soft("e[4,7]", "<=", 0)],
         complaint="Customers 5 and 7 order from the same supplier and should be served by one truck. At most two "
                   "customers may change trucks, and remember that the road between customers 4 and 7 is still "
                   "closed.",
         explanation="Customers 5 and 7 on one truck, at most two customers moving to the other truck, and no truck "
                     "driving directly between customers 4 and 7.",
         conditions=[cond("same", i=5, j=7), cond("max_moved", max=2), cond("not_adjacent", i=4, j=7)],
         direct=[soft("same[5,7]", ">=", 1)],
         reference=[soft("same[5,7]", ">=", 1), soft("same[1,4]", ">=", 1), soft("same[3,8]", ">=", 1)],
         localization=loc(["same[5,7]", "sep[5,7]"], [SOFT], "high"),
         why_question="Customers 1 and 3 are only 20 km apart. Why are they on different trucks?",
         why_decision={"type": "SEP", "i": 1, "j": 3},
         what_if_question="What if customers 1 and 3 had to share a truck?",
         what_if={"type": "FORCE_SAME", "i": 1, "j": 3}),
    dict(id="U10", stratum="side", object="customer", clarity="clear",
         scenario="Earlier in this session the user asked for customers 4 and 5 to share a truck; the fix was "
                  "accepted and stays in force.",
         model_modifications=[soft("same[4,5]", ">=", 1)],
         complaint="The direct road between customers 2 and 7 is closed today. Vehicle 2 has already left the depot, "
                   "so its route cannot change any more, and customers 4 and 5 still have to share a truck.",
         explanation="No truck may drive directly between customers 2 and 7, vehicle 2 keeps its route exactly, and "
                     "customers 4 and 5 stay on one truck.",
         conditions=[cond("not_adjacent", i=2, j=7), cond("route_kept", k=2), cond("same", i=4, j=5)],
         direct=[soft("e[2,7]", "<=", 0)],
         reference=[soft("e[2,7]", "<=", 0), soft("same[3,4]", ">=", 1), soft("same[3,6]", ">=", 1)],
         localization=loc(["e[2,7]"], [SOFT], "high"),
         why_question="Why does vehicle 1 drive from customer 7 straight to customer 2?",
         why_decision={"type": "ADJ", "i": 2, "j": 7},
         what_if_question="What if customer 2 were the first stop of vehicle 1?",
         what_if={"type": "FIX_ARC", "k": 1, "i": 0, "j": 2}),
]

DEV = [
    dict(id="P1", stratum="control", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customer 3 needs its delivery early in the route: the truck should reach it within the first 30 "
                   "km, not after 60 km as it does now.",
         explanation="Customer 3 should be reached within the first 30 km of driving.",
         conditions=[cond("max", target="A[3]", max=30)],
         direct=[soft("A[3]", "<=", 30)], reference=[soft("A[3]", "<=", 30)],
         localization=loc(["A[3]"], [SOFT], "high"),
         why_question="Customer 3 is only 20 km from customer 1. Why are they not on the same vehicle?",
         why_decision={"type": "SEP", "i": 1, "j": 3},
         what_if_question="What if vehicle 1 also served customer 3?",
         what_if={"type": "MOVE", "i": 3, "k": 1}),
    dict(id="P2", stratum="control", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customers 4 and 5 are only 14 km apart, but they are served by different trucks. Please serve them "
                   "with the same truck.",
         explanation="Customers 4 and 5 should be on the same truck.",
         conditions=[cond("same", i=4, j=5)],
         direct=[soft("same[4,5]", ">=", 1)], reference=[soft("same[4,5]", ">=", 1)],
         localization=loc(["same[4,5]", "sep[4,5]"], [SOFT], "high"),
         why_question="Why are customers 4 and 5 on different vehicles?",
         why_decision={"type": "SEP", "i": 4, "j": 5},
         what_if_question="What if customers 4 and 5 had to share a vehicle?",
         what_if={"type": "FORCE_SAME", "i": 4, "j": 5}),
    dict(id="P3", stratum="ambiguity", object="vehicle", clarity="ambiguous", scenario=R0_NOTE,
         complaint="The driver of vehicle 2 says today's plan is exhausting.",
         explanation="He means the number of stops: four stops are too many for him today. Vehicle 2 should make at "
                     "most three stops.",
         conditions=[cond("max", target="S[2]", max=3)],
         misreading=[soft("L[2]", "<=", 180)], reference=[soft("S[2]", "<=", 3)],
         localization=loc(["S[2]"], [SOFT], "low"),
         why_question="Why does vehicle 2 start its route at customer 5?",
         why_decision={"type": "ADJ", "i": 0, "j": 5},
         what_if_question="What if customer 5 were moved to vehicle 1?",
         what_if={"type": "MOVE", "i": 5, "k": 1}),
    dict(id="P4", stratum="ambiguity", object="customer", clarity="ambiguous", scenario=R0_NOTE,
         complaint="Customer 8 is not happy with our service.",
         explanation="Customer 8 is reached only after 167 km of driving. It should be reached within the first 100 "
                     "km.",
         conditions=[cond("max", target="A[8]", max=100)],
         misreading=[soft("L[2]", "<=", 180)], reference=[soft("A[8]", "<=", 100)],
         localization=loc(["A[8]"], [SOFT], "low"),
         why_question="Why are customers 5 and 8 on the same vehicle?",
         why_decision={"type": "SAME", "i": 5, "j": 8},
         what_if_question="What if customers 7 and 8 were visited one right after the other?",
         what_if={"type": "FORCE_ADJ", "i": 7, "j": 8}),
    dict(id="P5", stratum="ambiguity", object="data", clarity="ambiguous", scenario=R0_NOTE,
         complaint="The number you have for customer 2 is out of date. It is 30 now.",
         explanation="I mean customer 2's order size: 30 units, not 24.",
         conditions=[], allowed_data_corrections=[data("demand[2]", 30)],
         misreading=[data("coord[2]", [30, 26])], reference=[data("demand[2]", 30)],
         localization=loc(["demand[2]"], [DATA], "low"),
         why_question="Why does vehicle 1 start its route at customer 1?",
         why_decision={"type": "ADJ", "i": 0, "j": 1},
         what_if_question="What if customer 2 were moved to vehicle 2?",
         what_if={"type": "MOVE", "i": 2, "k": 2}),
    dict(id="P6", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="The direct road between customers 3 and 5 is closed today. Vehicle 1 has already left the depot, "
                   "so its route cannot change any more.",
         explanation="No truck may drive directly between customers 3 and 5, and vehicle 1 keeps its route "
                     "0 -> 1 -> 4 -> 7 -> 2 -> 0 exactly.",
         conditions=[cond("not_adjacent", i=3, j=5), cond("route_kept", k=1)],
         direct=[soft("e[3,5]", "<=", 0)],
         reference=[soft("e[3,5]", "<=", 0), soft("same[1,4]", ">=", 1), soft("same[1,7]", ">=", 1),
                    soft("same[1,2]", ">=", 1)],
         localization=loc(["e[3,5]"], [SOFT], "high"),
         why_question="Why does vehicle 2 go from customer 5 to customer 3?",
         why_decision={"type": "ADJ", "i": 3, "j": 5},
         what_if_question="What if vehicle 2 went to customer 3 first?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 3}),
    dict(id="P7", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customers 2 and 5 are served from the same loading bay and should be on one truck. Both trucks "
                   "are already half loaded, so at most two customers may change trucks.",
         explanation="Customers 2 and 5 on one truck, and at most two customers moving to the other truck.",
         conditions=[cond("same", i=2, j=5), cond("max_moved", max=2)],
         direct=[soft("same[2,5]", ">=", 1)],
         reference=[soft("same[2,5]", ">=", 1), soft("same[5,8]", ">=", 1)],
         localization=loc(["same[2,5]", "sep[2,5]"], [SOFT], "high"),
         why_question="Why are customers 2 and 5 on different vehicles?",
         why_decision={"type": "SEP", "i": 2, "j": 5},
         what_if_question="What if customers 2 and 6 swapped vehicles?",
         what_if={"type": "SWAP", "i": 2, "j": 6}),
    dict(id="P8", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customers 1 and 3 are only 20 km apart; serve them with the same truck if you can. If that is "
                   "impossible, customer 3 must at least be reached within the first 30 km, without the total distance "
                   "going above 375 km.",
         explanation="Customers 1 and 3 on one truck if possible; otherwise customer 3 reached within 30 km and the "
                     "total distance at most 375 km.",
         conditions=[cond("max", target="A[3]", max=30), cond("total_max", max=375)],
         impossible_wish=[cond("same", i=1, j=3)],
         direct=[soft("same[1,3]", ">=", 1)],
         reference=[soft("A[3]", "<=", 30)],
         localization=loc(["A[3]"], [SOFT], "high"),
         why_question="Customer 3 is only 20 km from customer 1. Why are they not on the same vehicle?",
         why_decision={"type": "SEP", "i": 1, "j": 3},
         what_if_question="What if customers 1 and 3 had to share a vehicle?",
         what_if={"type": "FORCE_SAME", "i": 1, "j": 3}),
    dict(id="P9", stratum="side", object="customer", clarity="clear", scenario=R0_NOTE,
         complaint="Customers 5 and 7 order from the same supplier, so one truck should serve both. Both trucks are "
                   "already half loaded, so at most two customers may change trucks.",
         explanation="Customers 5 and 7 on one truck, and at most two customers moving to the other truck.",
         conditions=[cond("same", i=5, j=7), cond("max_moved", max=2)],
         direct=[soft("same[5,7]", ">=", 1)],
         reference=[soft("same[5,7]", ">=", 1), soft("same[1,4]", ">=", 1), soft("same[3,6]", ">=", 1)],
         localization=loc(["same[5,7]", "sep[5,7]"], [SOFT], "high"),
         why_question="Why are customers 5 and 7 on different vehicles?",
         why_decision={"type": "SEP", "i": 5, "j": 7},
         what_if_question="What if customers 2 and 5 swapped vehicles?",
         what_if={"type": "SWAP", "i": 2, "j": 5}),
    dict(id="P10", stratum="side", object="customer", clarity="clear",
         scenario="Earlier in this session the user corrected customer 4's order to 20 units; the correction stays "
                  "in force.",
         model_modifications=[data("demand[4]", 20)],
         complaint="The direct road between customers 4 and 5 is closed today. Vehicle 1 has already left the depot, "
                   "so its route cannot change any more.",
         explanation="No truck may drive directly between customers 4 and 5, and vehicle 1 keeps its current route "
                     "exactly.",
         conditions=[cond("not_adjacent", i=4, j=5), cond("route_kept", k=1)],
         direct=[soft("e[4,5]", "<=", 0)],
         reference=[soft("e[4,5]", "<=", 0), soft("same[1,7]", ">=", 1), soft("same[1,2]", ">=", 1),
                    soft("same[1,8]", ">=", 1)],
         localization=loc(["e[4,5]"], [SOFT], "high"),
         why_question="Why does vehicle 2 go from customer 4 to customer 5?",
         why_decision={"type": "ADJ", "i": 4, "j": 5},
         what_if_question="What if vehicle 2 went to customer 5 first?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 5}),
]


# ---------------- brute force ----------------

def start_plan(base, mods):
    """Optimum of the session model (unique up to relabelling and reversal), in canonical form."""
    r = oracle_for(base, mods).solve(mods)
    keys = {canon.unlabeled_key(s) for s in r["optimal"]}
    assert len(keys) == 1, f"session optimum is not unique: {keys}"
    return canon.canonical(r["optimal"][0]), r["objective"]


def anchored_optima(base, session_mods, start, mods):
    """Every optimum of session model + mods as Task 3's commit would return it: under the commit's anchor
    (commit.anchor_for), and with a route reversed into the canonical direction when that ties (commit.orient_ties,
    the same rule as v2.attribution.orient_ties)."""
    _, _, involved = canon.compile_query({"type": "APPLY_MODIFICATIONS", "mods": list(mods)}, start)
    anchor = canon.anchor(involved, start, base["n"])
    allm = list(session_mods) + list(mods)
    r = oracle_for(base, allm).solve(allm, [anchor])
    if not r["feasible"]:
        return []
    d = apply_data_mods(base, allm)
    out = []
    for s in r["optimal"]:
        o, _ = orient_ties(s, d, allm)
        if o not in out:
            out.append(o)
    return out


def outcome(case, base, mods):
    """Resolution of every anchored optimum of the case model with these modifications."""
    sols = anchored_optima(base, case["model_modifications"], case["solution"], mods)
    vs = [verdict(case, s, base) for s in sols]
    return {"modifications": mods, "optima": len(vs), "resolving": sum(v["resolved"] for v in vs),
            "first_plan": sols[0] if sols else None,
            "first_distance": canon.metrics(sols[0], real_data(case, base))["total_distance"] if sols else None,
            "first_unmet": vs[0]["unmet"] if vs else ["no feasible plan"]}


def compliant_plans(case, base, conds=None):
    """Every labelled plan, feasible on the real data, that meets the conditions (default: the case's), except a
    plan that only exchanges the two vehicles' routes: the commit always keeps one customer on its vehicle (its
    anchor), so the system can never return such a plan."""
    d = real_data(case, base)
    o = oracle_for(d)
    L1, L2 = o._pair(o.rlen)
    W1, W2 = o._pair(o.rload)
    ok = (W1 <= d["Q"]) & (W2 <= d["Q"])
    total = L1 + L2
    cand = np.flatnonzero(ok)
    # vectorized prefilters where they are exact; the rest is checked per plan with conditions.verdict
    for c in case["conditions"] if conds is None else conds:
        k, p = c["kind"], c["params"]
        if k == "max" and p["target"] != "avg_arrival":
            cand = cand[o.target(p["target"])[cand] <= p["max"] + 1e-9]
        elif k in ("same", "separate"):
            s = o.target(f"same[{p['i']},{p['j']}]")[cand] > 0.5
            cand = cand[s if k == "same" else ~s]
        elif k == "not_adjacent":
            cand = cand[o.target(f"e[{min(p['i'], p['j'])},{max(p['i'], p['j'])}]")[cand] < 0.5]
        elif k == "total_max":
            cand = cand[total[cand] <= p["max"] + 1e-9]
    probe = dict(case, conditions=case["conditions"] if conds is None else conds)
    veh = canon.vehicle_of(case["solution"])
    keep = []
    for i in cand:
        s = o.solution(int(i))
        if all(canon.vehicle_of(s)[c] != veh[c] for c in veh):
            continue
        if verdict(probe, s, base)["resolved"]:
            keep.append(int(i))
    return keep, total, o


def build(spec, base, split):
    mm = spec.get("model_modifications", [])
    sol, obj = start_plan(base, mm)
    session_data = apply_data_mods(base, mm)
    case = {"id": spec["id"], "split": split, "stratum": spec["stratum"], "scenario": spec["scenario"],
            "model_modifications": mm, "solution": sol, "solution_objective": obj,
            "solution_metrics": canon.metrics(sol, session_data),
            "complaint": spec["complaint"], "explanation": spec["explanation"],
            "clarification_answer": spec["explanation"], "clarity": spec["clarity"],
            "complaint_object": spec["object"], "conditions": spec["conditions"],
            "allowed_data_corrections": spec.get("allowed_data_corrections", []),
            "reference_modification": spec["reference"],
            "why_question": spec["why_question"], "why_decision": spec["why_decision"],
            "what_if_question": spec["what_if_question"], "what_if": spec["what_if"]}
    v0 = verdict(case, sol, base)
    assert not v0["resolved"], (spec["id"], "the plan complained about already resolves the case")
    case["initial_verdict"] = {"feasible": v0["feasible"], "unmet": v0["unmet"]}
    assert len(spec["reference"]) <= MAX_MODS, spec["id"]
    keep, total, _ = compliant_plans(case, base)
    assert keep, (spec["id"], "no plan meets every condition")
    best = min(total[i] for i in keep)
    case["min_compliant_distance"] = float(best)
    case["compliant_plans"] = len(keep)
    ref = outcome(case, base, spec["reference"])
    assert ref["optima"] and ref["resolving"] == ref["optima"], (spec["id"], "reference", ref)
    design = {"reference": ref}
    if spec["stratum"] == "control":
        d = outcome(case, base, spec["direct"])
        assert d["resolving"] == d["optima"] > 0, (spec["id"], "control: direct encoding must resolve", d)
        design["direct"] = d
    elif spec["stratum"] == "ambiguity":
        m = outcome(case, base, spec["misreading"])
        assert m["resolving"] == 0, (spec["id"], "ambiguity: the misreading must not resolve", m)
        design["misreading"] = m
    else:
        d = outcome(case, base, spec["direct"])
        assert d["optima"] and d["resolving"] == 0, (spec["id"], "side: direct encoding must fail in every optimum", d)
        design["direct"] = d
    if spec.get("impossible_wish"):
        none, _, _ = compliant_plans(case, base, spec["impossible_wish"])
        assert not none, (spec["id"], "the wish stated as impossible is feasible")
        design["impossible_wish"] = {"conditions": spec["impossible_wish"], "feasible_plans": 0}
    case["design"] = design
    att = attribution_gt(base, mm, sol, spec["why_decision"])
    att["part"] = "constraints" if att["conclusion"] != "objective_preferred" else "variables"
    cf = counterfactual_gt(base, mm, sol, spec["what_if"])
    case["gt"] = {"localization": spec["localization"], "attribution": att, "counterfactual": cf}
    return case


def _cond_str(c):
    p = c["params"]
    if c["kind"] == "max":
        return f"{p['target']} <= {p['max']:g}"
    if c["kind"] in ("same", "separate", "not_adjacent"):
        return f"{c['kind']}({p['i']},{p['j']})"
    if c["kind"] == "max_moved":
        return f"moved <= {p['max']}"
    if c["kind"] == "total_max":
        return f"total <= {p['max']:g}"
    return f"route of vehicle {p['k']} kept"


def summary_md(cases):
    rows = ["| ID | Stratum | Complaint | Conditions | Start | Min compliant | Reference fix | Direct / misreading "
            "(first optimum) | Attribution GT | Counterfactual GT |", "|---" * 10 + "|"]
    for c in cases:
        d = c["design"]
        probe = d.get("direct") or d.get("misreading")
        pm = "; ".join(json.dumps(m) for m in probe["modifications"])
        po = ("resolves" if probe["resolving"] == probe["optima"] else
              f"{probe['first_distance']} km, fails: {'; '.join(probe['first_unmet'])}")
        a = c["gt"]["attribution"]
        att = (f"{c['why_decision']['type']}({c['why_decision']['i']},{c['why_decision']['j']}): "
               + (f"forced, {'/'.join(a['acceptable_sets'][0])}" if a["conclusion"] != "objective_preferred"
                  else f"objective-preferred, Δ={a['delta']:.0f}"))
        cf = c["gt"]["counterfactual"]
        cft = cf["outcome"] + (f", Δdist={cf['delta_distance']:+.0f}" if cf["feasible"] else "")
        conds = ", ".join(_cond_str(x) for x in c["conditions"]) or "feasible on corrected data"
        if c["allowed_data_corrections"]:
            conds += " (real data: " + ", ".join(f"{m['field']}={m['value']}" for m in c["allowed_data_corrections"]) + ")"
        rows.append(f"| {c['id']} | {c['stratum']} | {c['complaint']} | {conds} | {c['solution_objective']:.0f} | "
                    f"{c['min_compliant_distance']:.0f} | `{'; '.join(json.dumps(m) for m in c['reference_modification'])}`"
                    f" | `{pm}` → {po} | {att} | {cft} |")
    return "\n".join(rows)


def main():
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
    tests = [build(s, base, "test") for s in TEST]
    devs = [build(s, base, "dev") for s in DEV]
    os.makedirs(OUT, exist_ok=True)
    sha = json.load(open(os.path.join(ROOT, "FROZEN.json")))["instance"]["sha256"]
    for name, cases in (("test_cases.json", tests), ("dev_cases.json", devs)):
        with open(os.path.join(OUT, name), "w") as f:
            json.dump({"protocol": "task2_v3", "instance_sha256": sha, "cases": cases}, f, indent=1)
            f.write("\n")
    with open(os.path.join(OUT, "cases.md"), "w") as f:
        f.write("# task2_v3 cases (review table)\n\nGenerated by `v3/cases.py`; the JSON files are authoritative. "
                "Every number here is computed by brute force.\n\n## Test cases\n\n" + summary_md(tests) +
                "\n\n## Development cases (pilot only)\n\n" + summary_md(devs) + "\n")
    print(f"built {len(tests)} test and {len(devs)} dev cases")


if __name__ == "__main__":
    main()
