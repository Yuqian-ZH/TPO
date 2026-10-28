"""Parsing and validation of TPO proposals and selector answers (plan 3.3 step 3, 3.8)."""
import json
import os
import re

import jsonschema

from .task2_bridge import TASK2_ROOT

MAX_MODS = 4
MAX_PENALTY = 1000.0
MAX_WEIGHT = 100.0
ONLY_LE = ("A", "balance", "makespan", "load_balance", "sum_arrival")
TERMS = ("balance", "makespan", "load_balance", "sum_arrival")

_T2_SCHEMA = os.path.join(TASK2_ROOT, "schemas", "modification.schema.json")
_TARGET = re.compile(r"^(?:(L|W|S)\[(\d+)\]|A\[(\d+)\]|(balance|makespan|load_balance|sum_arrival)"
                     r"|(e|same|sep)\[(\d+),(\d+)\])$")
_FIELD = re.compile(r"^(?:(demand|coord)\[(\d+)\]|capacity)$")


def _task2_schema():
    try:
        with open(_T2_SCHEMA) as f:
            return json.load(f)
    except OSError:
        return None


def check_modification(mod, n, K):
    """Errors of one modification (empty list = valid). Task 2's schema is hard-wired to n = 8, K = 2,
    so it is applied only there; the semantic checks below hold for any size."""
    if not isinstance(mod, dict):
        return ["modification is not an object"]
    errs = []
    schema = _task2_schema() if (n, K) == (8, 2) else None
    if schema is not None:
        try:
            jsonschema.validate(mod, schema)
        except jsonschema.ValidationError as e:
            errs.append(f"schema: {e.message[:200]}")
    op = mod.get("op")
    if op == "add_soft_constraint":
        allowed = {"op", "id", "target", "sense", "rhs", "penalty"}
        m = _TARGET.match(str(mod.get("target", "")))
        if not m:
            errs.append(f"unknown soft-constraint target {mod.get('target')!r}")
        else:
            if m.group(1) and not 1 <= int(m.group(2)) <= K:
                errs.append(f"no vehicle in {mod['target']}")
            if m.group(3) and not 1 <= int(m.group(3)) <= n:
                errs.append(f"no customer in {mod['target']}")
            if m.group(5):
                i, j, lo = int(m.group(6)), int(m.group(7)), 0 if m.group(5) == "e" else 1
                if i == j or not (lo <= i <= n and lo <= j <= n):
                    errs.append(f"invalid pair in {mod['target']}")
            head = mod["target"].split("[")[0]
            if head in ONLY_LE and mod.get("sense") != "<=":
                errs.append(f"{mod['target']} only accepts '<='")
        if mod.get("sense") not in ("<=", ">=", "=="):
            errs.append(f"invalid sense {mod.get('sense')!r}")
        if not _num(mod.get("rhs")):
            errs.append("rhs must be a number")
        p = mod.get("penalty")
        if not _num(p) or not 0 < p <= MAX_PENALTY:
            errs.append(f"penalty must be in (0, {MAX_PENALTY:g}]")
    elif op == "set_objective_weight":
        allowed = {"op", "term", "weight"}
        if mod.get("term") not in TERMS:
            errs.append(f"unknown objective term {mod.get('term')!r}")
        w = mod.get("weight")
        if not _num(w) or not 0 <= w <= MAX_WEIGHT:
            errs.append(f"weight must be in [0, {MAX_WEIGHT:g}]")
    elif op == "modify_data":
        allowed = {"op", "field", "value"}
        m = _FIELD.match(str(mod.get("field", "")))
        v = mod.get("value")
        if not m:
            errs.append(f"unknown data field {mod.get('field')!r}")
        elif m.group(1) and not 1 <= int(m.group(2)) <= n:
            errs.append(f"no customer in {mod['field']}")
        elif m.group(1) == "coord":
            if not (isinstance(v, list) and len(v) == 2 and all(_int(t) and 0 <= t <= 100 for t in v)):
                errs.append("coord value must be two integers in [0, 100]")
        elif not (_int(v) and v >= 0):
            errs.append(f"{mod['field']} value must be a non-negative integer")
    else:
        return [f"unknown op {op!r}"]
    extra = set(mod) - allowed
    if extra:
        errs.append(f"unexpected keys {sorted(extra)}")
    return sorted(set(errs))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_proposal(llm_out, n, K):
    """-> {"valid", "modifications", "rationale", "errors"}; soft-constraint ids are assigned by the caller."""
    if llm_out.get("parse_status") != "json_ok" or not isinstance(llm_out.get("parsed"), dict):
        return {"valid": False, "modifications": [], "rationale": None,
                "errors": [f"response is not a JSON object ({llm_out.get('parse_status')})"]}
    obj = llm_out["parsed"]
    mods = obj.get("modifications")
    errs = []
    if not isinstance(mods, list):
        errs.append("'modifications' must be a list")
        mods = []
    elif len(mods) > MAX_MODS:
        errs.append(f"at most {MAX_MODS} modifications")
    for idx, m in enumerate(mods):
        errs += [f"modification {idx + 1}: {e}" for e in check_modification(m, n, K)]
    clean = [{k: v for k, v in m.items() if k != "id"} for m in mods if isinstance(m, dict)]
    return {"valid": not errs, "modifications": clean if not errs else [],
            "raw_modifications": mods, "rationale": obj.get("rationale"), "errors": errs}


def assign_ids(mods, tag):
    out, s = [], 0
    for m in mods:
        if m["op"] == "add_soft_constraint":
            s += 1
            m = {**m, "id": f"tpo_{tag}_{s}"}
        out.append(m)
    return out


def parse_choice(llm_out, n_candidates):
    obj = llm_out.get("parsed") if llm_out.get("parse_status") == "json_ok" else None
    c = obj.get("choice") if isinstance(obj, dict) else None
    if _int(c) and 1 <= c <= n_candidates:
        return {"ok": True, "index": c - 1, "reason": obj.get("reason")}
    return {"ok": False, "index": 0, "reason": None}
