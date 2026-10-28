"""Hand-written case specifications + oracle-computed ground truth -> test_cases.json, dev_cases.json,
test_cases.md.  Run from task2/:  python -m cases.build_cases"""
import json
import os

from cvrp import canon
from cvrp.data import apply_data_mods, load_instance
from cvrp.oracle import oracle_for

from .checkers import run_checker
from .gt import attribution_gt, counterfactual_gt, reference_check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "cases")


def soft(target, sense, rhs, penalty):
    return {"op": "add_soft_constraint", "target": target, "sense": sense, "rhs": rhs, "penalty": penalty}


def weight(term, w):
    return {"op": "set_objective_weight", "term": term, "weight": w}


def data(field, value):
    return {"op": "modify_data", "field": field, "value": value}


def loc(targets, types, confidence):
    return {"targets": targets, "modification_types": types, "confidence": confidence}


SOFT, WEIGHT, DATA = "add_soft_constraint", "set_objective_weight", "modify_data"

TEST = [
    dict(id="T1", object="vehicle", clarity="clear",
         complaint="Vehicle 2 is on the road for 211 km today. That is too much for one driver: its route must "
                   "not be longer than 180 km.",
         clarification_answer="I mean the total length of vehicle 2's route: it should be 180 km or less.",
         why_question="Why does vehicle 2 finish its route by driving from customer 8 straight back to the depot?",
         why_decision={"type": "ADJ", "i": 0, "j": 8},
         what_if_question="What if vehicle 2's route were limited to 180 km?",
         what_if={"type": "APPLY_MODIFICATIONS", "mods": [soft("L[2]", "<=", 180, 10)]},
         localization=loc(["L[2]"], [SOFT], "high"),
         checker={"name": "route_length_max", "params": {"k": 2, "max": 180}},
         reference_modification=[soft("L[2]", "<=", 180, 10)]),
    dict(id="T2", object="vehicle", clarity="ambiguous",
         complaint="Vehicle 1 is doing too much work.",
         clarification_answer="I mean the load: vehicle 1 leaves the depot with 99 units, which is practically "
                              "full. It should carry at most 92 units.",
         why_question="Why are customers 1 and 2 both served by vehicle 1?",
         why_decision={"type": "SAME", "i": 1, "j": 2},
         what_if_question="What if customer 7 were moved to vehicle 2?",
         what_if={"type": "MOVE", "i": 7, "k": 2},
         localization=loc(["W[1]"], [SOFT], "low"),
         checker={"name": "max_load", "params": {"k": 1, "max": 92}},
         reference_modification=[soft("W[1]", "<=", 92, 30)]),
    dict(id="T3", object="customer", clarity="clear",
         complaint="Customer 6 is on a long detour. It is only 47 km from the depot, but vehicle 2 drives 95 km "
                   "before it gets there.",
         clarification_answer="Customer 6 should be reached without a big detour: the distance driven before "
                              "reaching it should be at most 1.5 times its direct distance from the depot.",
         why_question="Why does vehicle 2 go from customer 3 to customer 6?",
         why_decision={"type": "ADJ", "i": 3, "j": 6},
         what_if_question="What if vehicle 2 went to customer 6 first?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 6},
         localization=loc(["A[6]"], [SOFT], "high"),
         checker={"name": "detour_ratio", "params": {"i": 6, "max_ratio": 1.5}},
         reference_modification=[soft("A[6]", "<=", 70, 10)]),
    dict(id="T4", object="customer", clarity="clear",
         complaint="Customer 3 needs its delivery early in the route: the truck should reach it within the first "
                   "30 km, not after 60 km as it does now.",
         clarification_answer="Customer 3 should be reached within the first 30 km of driving.",
         why_question="Customer 3 is only 20 km from customer 1. Why are they not on the same vehicle?",
         why_decision={"type": "SEP", "i": 1, "j": 3},
         what_if_question="What if vehicle 1 also served customer 3?",
         what_if={"type": "MOVE", "i": 3, "k": 1},
         localization=loc(["A[3]"], [SOFT], "high"),
         checker={"name": "arrival_max", "params": {"i": 3, "max": 30}},
         reference_modification=[soft("A[3]", "<=", 30, 10)]),
    dict(id="T5", object="data", clarity="clear",
         complaint="Customer 4 has increased its order to 20 units, but your plan still uses the old 12 units. "
                   "With 20 units, vehicle 1 would carry 107 units and be overloaded.",
         clarification_answer="Customer 4's demand is 20 units, not 12.",
         why_question="Why does vehicle 1 drive from customer 4 to customer 7?",
         why_decision={"type": "ADJ", "i": 4, "j": 7},
         what_if_question="What if customer 4 were served by vehicle 2 instead?",
         what_if={"type": "MOVE", "i": 4, "k": 2},
         localization=loc(["demand[4]"], [DATA], "high"),
         checker={"name": "feasible_under", "params": {"corrections": [data("demand[4]", 20)]}},
         allowed_data_corrections=[data("demand[4]", 20)],
         reference_modification=[data("demand[4]", 20)]),
    dict(id="T6", object="data", clarity="ambiguous",
         complaint="One of the numbers you have for customer 7 is wrong. It should be 18.",
         clarification_answer="I mean the order size: customer 7 now orders 18 units, not 11.",
         why_question="Why does vehicle 1 go from customer 7 to customer 2?",
         why_decision={"type": "ADJ", "i": 2, "j": 7},
         what_if_question="What if customers 2 and 7 were on different vehicles?",
         what_if={"type": "FORCE_SEP", "i": 2, "j": 7},
         localization=loc(["demand[7]"], [DATA], "low"),
         checker={"name": "feasible_under", "params": {"corrections": [data("demand[7]", 18)]}},
         allowed_data_corrections=[data("demand[7]", 18)],
         reference_modification=[data("demand[7]", 18)]),
    dict(id="T7", object="global", clarity="clear",
         complaint="Driver 2 drives 211 km and driver 1 only 140 km, but they are paid the same. Please split the "
                   "driving more fairly, even if the total distance goes up a little; a difference of up to 50 km "
                   "is acceptable.",
         clarification_answer="I mean the difference between the two route lengths: it should be at most 50 km.",
         why_question="Why is customer 6 on vehicle 2 rather than on vehicle 1 together with customer 2?",
         why_decision={"type": "SEP", "i": 2, "j": 6},
         what_if_question="What if fairness between the two drivers counted almost as much as total distance "
                          "(weight 0.8)?",
         what_if={"type": "APPLY_MODIFICATIONS", "mods": [weight("balance", 0.8)]},
         localization=loc(["balance"], [WEIGHT, SOFT], "high"),
         checker={"name": "balance_max", "params": {"max": 50}},
         reference_modification=[weight("balance", 0.8)]),
    dict(id="T8", object="global", clarity="ambiguous",
         complaint="The drivers are unhappy with how the work is split between the two vehicles.",
         clarification_answer="It is about the loads: one truck carries 99 units and the other 90. The two loads "
                              "should differ by at most 5 units, even if that costs some extra distance.",
         why_question="Why do customers 2 and 7 share a vehicle?",
         why_decision={"type": "SAME", "i": 2, "j": 7},
         what_if_question="What if customers 1 and 8 swapped vehicles?",
         what_if={"type": "SWAP", "i": 1, "j": 8},
         localization=loc(["load_balance"], [WEIGHT, SOFT], "low"),
         checker={"name": "load_balance_max", "params": {"max": 5}},
         reference_modification=[weight("load_balance", 4)]),
    dict(id="T9", object="customer", clarity="clear",
         scenario="Variant day: customer 3 orders 54 units instead of 49 (part of this case's model).",
         model_modifications=[data("demand[3]", 54)],
         complaint="Customers 4 and 5 are only 14 km apart, but they are served by different trucks. Please serve "
                   "them with the same truck.",
         clarification_answer="Customers 4 and 5 should be on the same vehicle.",
         why_question="Why can't customer 5 ride on the same truck as customer 2?",
         why_decision={"type": "SEP", "i": 2, "j": 5},
         what_if_question="What if customers 2 and 5 were put on the same vehicle?",
         what_if={"type": "FORCE_SAME", "i": 2, "j": 5},
         localization=loc(["same[4,5]", "sep[4,5]"], [SOFT], "high"),
         checker={"name": "same_vehicle", "params": {"i": 4, "j": 5}},
         reference_modification=[soft("same[4,5]", ">=", 1, 30)]),
    dict(id="T10", object="customer", clarity="clear",
         complaint="Vehicle 2 drives 72 km straight from customer 6 to customer 8 through the city centre. Please "
                   "avoid driving directly between customers 6 and 8.",
         clarification_answer="Customers 6 and 8 should not be visited one right after the other.",
         why_question="Why does vehicle 2 drive from customer 6 directly to customer 8?",
         why_decision={"type": "ADJ", "i": 6, "j": 8},
         what_if_question="What if vehicle 2 drove its route the other way round, starting with customer 8?",
         what_if={"type": "FIX_ARC", "k": 2, "i": 0, "j": 8},
         localization=loc(["e[6,8]"], [SOFT], "high"),
         checker={"name": "not_adjacent", "params": {"i": 6, "j": 8}},
         reference_modification=[soft("e[6,8]", "<=", 0, 30)]),
]

DEV = [
    dict(id="D1", object="vehicle", clarity="ambiguous",
         complaint="The driver of vehicle 2 says today's plan is exhausting.",
         clarification_answer="It is the number of stops: the driver can make at most 3 deliveries today, but the "
                              "plan has 4.",
         why_question="Why does vehicle 1 go from customer 1 to customer 4?",
         why_decision={"type": "ADJ", "i": 1, "j": 4},
         what_if_question="What if vehicle 1 drove its route in the opposite direction, visiting customer 4 "
                          "before customer 1?",
         what_if={"type": "FIX_ARC", "k": 1, "i": 4, "j": 1},
         localization=loc(["S[2]"], [SOFT], "low"),
         checker={"name": "max_stops", "params": {"k": 2, "max": 3}},
         reference_modification=[soft("S[2]", "<=", 3, 60)]),
    dict(id="D2", object="customer", clarity="clear",
         scenario="Variant day: customer 4 orders 17 units instead of 12 (part of this case's model).",
         model_modifications=[data("demand[4]", 17)],
         complaint="The direct road between customers 2 and 8 is closed today, so no truck should drive straight "
                   "from one to the other.",
         clarification_answer="Customers 2 and 8 should not be visited one right after the other.",
         why_question="Why can't customers 2 and 4 share a truck?",
         why_decision={"type": "SEP", "i": 2, "j": 4},
         what_if_question="What if customers 2 and 4 were put on the same vehicle?",
         what_if={"type": "FORCE_SAME", "i": 2, "j": 4},
         localization=loc(["e[2,8]"], [SOFT], "high"),
         checker={"name": "not_adjacent", "params": {"i": 2, "j": 8}},
         reference_modification=[soft("e[2,8]", "<=", 0, 30)]),
    dict(id="D3", object="data", clarity="clear",
         complaint="Customer 2 now orders 30 units, not 24, so vehicle 1 cannot carry everything you planned.",
         clarification_answer="Customer 2's demand is 30 units.",
         why_question="Why does vehicle 1 visit customer 1 first?",
         why_decision={"type": "ADJ", "i": 0, "j": 1},
         what_if_question="What if customer 2 were moved to vehicle 2?",
         what_if={"type": "MOVE", "i": 2, "k": 2},
         localization=loc(["demand[2]"], [DATA], "high"),
         checker={"name": "feasible_under", "params": {"corrections": [data("demand[2]", 30)]}},
         allowed_data_corrections=[data("demand[2]", 30)],
         reference_modification=[data("demand[2]", 30)]),
    dict(id="D4", object="customer", clarity="ambiguous",
         complaint="Customer 8 is not happy with our service.",
         clarification_answer="Customer 8 is the last stop and only gets its delivery after 167 km of driving. "
                              "It wants the delivery within the first 100 km.",
         why_question="Why are customers 5 and 8 on the same vehicle?",
         why_decision={"type": "SAME", "i": 5, "j": 8},
         what_if_question="What if customer 8 were visited right after customer 7?",
         what_if={"type": "FORCE_ADJ", "i": 7, "j": 8},
         localization=loc(["A[8]"], [SOFT], "low"),
         checker={"name": "arrival_max", "params": {"i": 8, "max": 100}},
         reference_modification=[soft("A[8]", "<=", 100, 10)]),
    dict(id="D5", object="global", clarity="clear",
         complaint="On average our customers wait for 73.5 km of driving before their delivery arrives. Bring "
                   "that average below 73 km, even if the total distance grows.",
         clarification_answer="The average arrival mileage over all customers should be at most 73 km.",
         why_question="Why are customers 3 and 5 on the same vehicle?",
         why_decision={"type": "SAME", "i": 3, "j": 5},
         what_if_question="What if customers 3 and 5 were on different vehicles?",
         what_if={"type": "FORCE_SEP", "i": 3, "j": 5},
         localization=loc(["sum_arrival"], [WEIGHT, SOFT], "high"),
         checker={"name": "avg_arrival_max", "params": {"max": 73}},
         reference_modification=[weight("sum_arrival", 3)]),
]


def reference_solution(base, model_mods):
    """Optimum of the case model (unique up to relabeling / reversal), in canonical form."""
    r = oracle_for(base, model_mods).solve(model_mods)
    keys = {canon.unlabeled_key(s) for s in r["optimal"]}
    assert len(keys) == 1, f"case model optimum is not unique: {keys}"
    return canon.canonical(r["optimal"][0]), r["objective"]


def build(spec, base, split):
    mm = spec.get("model_modifications", [])
    sol, obj = reference_solution(base, mm)
    case = {
        "id": spec["id"], "split": split, "scenario": spec.get("scenario", "Reference instance."),
        "model_modifications": mm, "solution": sol, "solution_objective": obj,
        "solution_metrics": canon.metrics(sol, apply_data_mods(base, mm)),
        "complaint": spec["complaint"], "clarity": spec["clarity"], "complaint_object": spec["object"],
        "clarification_answer": spec["clarification_answer"],
        "why_question": spec["why_question"], "why_decision": spec["why_decision"],
        "what_if_question": spec["what_if_question"], "what_if": spec["what_if"],
        "checker": spec["checker"], "allowed_data_corrections": spec.get("allowed_data_corrections", []),
        "reference_modification": spec["reference_modification"],
    }
    att = attribution_gt(base, mm, sol, spec["why_decision"])
    att["part"] = "constraints" if att["conclusion"] != "objective_preferred" else "variables"
    cf = counterfactual_gt(base, mm, sol, spec["what_if"])
    case["gt"] = {"localization": spec["localization"], "attribution": att, "counterfactual": cf}
    case["initial_check"] = run_checker(case, sol, base)
    ref = reference_check(base, case)
    case["reference_check"] = ref
    assert not case["initial_check"]["passed"], (spec["id"], "initial solution already passes its checker")
    assert ref["feasible"] and ref["all_optimal_resolve"], (spec["id"], ref)
    return case


def query_str(q):
    t = q["type"]
    if t == "FIX_ARC":
        return f"FIX_ARC(v{q['k']}: {q['i']}→{q['j']})"
    if t == "MOVE":
        return f"MOVE({q['i']}→v{q['k']})"
    if t == "APPLY_MODIFICATIONS":
        return "APPLY_MODIFICATIONS(" + "; ".join(json.dumps(m) for m in q["mods"]) + ")"
    return f"{t}({q['i']},{q['j']})"


def summary_md(cases):
    rows = ["| ID | Object | Clarity | Complaint | Localization GT | Checker (initial value) | Reference fix | "
            "Why → attribution GT | What-if → counterfactual GT |", "|---" * 9 + "|"]
    for c in cases:
        g = c["gt"]
        a = g["attribution"]
        att = (f"{c['why_decision']['type']}({c['why_decision']['i']},{c['why_decision']['j']}): "
               + ("capacity-forced, " + "/".join(a["acceptable_sets"][0]) if a["conclusion"] != "objective_preferred"
                  else f"objective-preferred, Δ={a['delta']:.0f}, {len(a['acceptable_sets'][0])} edges"
                  + ("" if len(a["acceptable_sets"]) == 1 else f" ({len(a['acceptable_sets'])} acceptable sets)")))
        cf = g["counterfactual"]
        qs = query_str(c["what_if"])
        if cf["feasible"]:
            cs = cf["acceptable_change_sets"][0]
            cft = (f"{cf['outcome']}, Δdist={cf['delta_distance']:+.0f}, moved={cs['moved']}, "
                   f"+{len(cs['added_edges'])}/−{len(cs['removed_edges'])} edges"
                   + (f", reversed={cs['reversed']}" if cs["reversed"] else "")
                   + ("" if len(cf["acceptable_change_sets"]) == 1 else
                      f" ({len(cf['acceptable_change_sets'])} acceptable)"))
        else:
            cft = cf["outcome"]
        ch = c["checker"]
        chk = f"{ch['name']}({', '.join(f'{k}={v}' for k, v in ch['params'].items() if k != 'corrections')}) " \
              f"[{c['initial_check']['value']}]"
        ref = "; ".join(json.dumps(m) for m in c["reference_modification"])
        locg = g["localization"]
        rows.append(f"| {c['id']} | {c['complaint_object']} | {c['clarity']} | {c['complaint']} | "
                    f"{', '.join(locg['targets'])} / {', '.join(locg['modification_types'])} / {locg['confidence']} | "
                    f"{chk} | `{ref}` | {att} | {qs} → {cft} |")
    return "\n".join(rows)


def main():
    base = load_instance(os.path.join(ROOT, "instance", "cvrp_instance.json"))
    tests = [build(s, base, "test") for s in TEST]
    devs = [build(s, base, "dev") for s in DEV]
    for name, cases in (("test_cases.json", tests), ("dev_cases.json", devs)):
        with open(os.path.join(HERE, name), "w") as f:
            json.dump({"protocol": "task2_v1", "instance_sha256": json.load(open(os.path.join(ROOT, "FROZEN.json")))
                       ["instance"]["sha256"], "cases": cases}, f, indent=2)
            f.write("\n")
    with open(os.path.join(HERE, "test_cases.md"), "w") as f:
        f.write("# Task 2 test cases (review table)\n\nGenerated by `cases/build_cases.py`; the JSON files are "
                "authoritative.\n\n## Test cases\n\n" + summary_md(tests) + "\n\n## Development cases\n\n"
                + summary_md(devs) + "\n")
    print(f"built {len(tests)} test and {len(devs)} dev cases")


if __name__ == "__main__":
    main()
