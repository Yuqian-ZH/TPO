"""Canonical IDs and their categories. Gurobi names are identical to canonical IDs, so the mapping is
the identity; everything that evaluates IDs goes through this module."""
import re

CONSTRAINT_FAMILIES = {
    "visit": "business_general",       # visit[i]: each customer served by exactly one vehicle
    "depot_out": "business_general",   # depot_out[k]: each vehicle leaves the depot exactly once
    "cap": "business_specific",        # cap[k]: vehicle capacity
    "flow_out": "structural", "flow_in": "structural",
    "mtz": "structural",               # load-based MTZ subtour elimination (does not imply capacity)
    "arr": "structural",               # arrival-mileage lower bounds
    "def_L": "structural", "def_W": "structural", "def_S": "structural",
    "def_balance": "structural", "def_makespan": "structural", "def_load_balance": "structural",
    "anchor": "convention",            # single anchor of counterfactual queries
    "perturbation": "perturbation",    # constraint forbidding the decision under attribution
    "query": "query",                  # counterfactual query constraints
    "soft": "soft", "soft_aux": "soft",  # soft constraints added by modifications
}
VARIABLE_FAMILIES = ("x", "y", "u", "L", "W", "S", "A", "balance", "makespan", "load_balance")
OBJECTIVE_TERMS = ("distance", "balance", "makespan", "load_balance", "sum_arrival")
DATA_FIELDS = ("demand", "coord", "capacity")


def family(name):
    return name.split("[", 1)[0]


def category(cid):
    return CONSTRAINT_FAMILIES.get(family(cid), "unknown")


def constraint_ids(n, K=2):
    C, Ks = range(1, n + 1), range(1, K + 1)
    ids = [f"visit[{i}]" for i in C] + [f"cap[{k}]" for k in Ks] + [f"depot_out[{k}]" for k in Ks]
    ids += [f"flow_out[{k},{i}]" for k in Ks for i in C] + [f"flow_in[{k},{i}]" for k in Ks for i in C]
    ids += [f"mtz[{i},{j}]" for i in C for j in C if i != j]
    ids += [f"arr[{i},{j}]" for i in range(n + 1) for j in C if i != j]
    ids += [f"def_L[{k}]" for k in Ks] + [f"def_W[{k}]" for k in Ks] + [f"def_S[{k}]" for k in Ks]
    ids += ["def_balance[1]", "def_balance[2]", "def_load_balance[1]", "def_load_balance[2]"]
    ids += [f"def_makespan[{k}]" for k in Ks]
    return ids


def variable_ids(n, K=2):
    N, C, Ks = range(n + 1), range(1, n + 1), range(1, K + 1)
    ids = [f"x[{k},{i},{j}]" for k in Ks for i in N for j in N if i != j]
    ids += [f"y[{k},{i}]" for k in Ks for i in C] + [f"u[{i}]" for i in C]
    ids += [f"{v}[{k}]" for v in ("L", "W", "S") for k in Ks] + [f"A[{i}]" for i in C]
    ids += ["balance", "makespan", "load_balance"]
    return ids


_IDX = re.compile(r"^([A-Za-z_]+)(?:\[([0-9,]+)\])?$")


def target_exists(tid, n, K=2):
    """Localization / soft-constraint targets and data fields."""
    m = _IDX.match(tid)
    if not m:
        return False
    head, idx = m.group(1), m.group(2)
    nums = [int(t) for t in idx.split(",")] if idx else []
    if head in ("balance", "makespan", "load_balance", "sum_arrival", "capacity"):
        return not nums
    if head in ("L", "W", "S"):
        return len(nums) == 1 and 1 <= nums[0] <= K
    if head in ("A", "demand", "coord"):
        return len(nums) == 1 and 1 <= nums[0] <= n
    if head in ("e", "same", "sep"):
        lo = 0 if head == "e" else 1
        return len(nums) == 2 and nums[0] != nums[1] and all(lo <= v <= n for v in nums)
    return False


def id_exists(any_id, n, K=2):
    return (any_id in constraint_ids(n, K) or any_id in variable_ids(n, K) or target_exists(any_id, n, K)
            or any_id in OBJECTIVE_TERMS)


def gurobi_name(cid):
    return cid


def canonical_id(gname):
    return gname
