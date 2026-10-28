"""Write protocol.json once (section 7.1). Refuses to overwrite an existing protocol."""
import datetime
import glob
import hashlib
import json
import os
import sys

from components.localization import N_SAMPLES, RULE, TEMPERATURE
from components.llm_client import MODEL, PROTOCOL, RETRY_WAITS
from cvrp.model import PARAMS

ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = ["instance/cvrp_instance.json", "cases/test_cases.json", "evaluate.py", "metrics.py", "recompute.py"]
GLOBS = ["cvrp/*.py", "components/*.py", "components/prompts/*.txt", "cases/*.py", "schemas/*.json"]


def sha256(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()


def main():
    path = os.path.join(ROOT, "protocol.json")
    if os.path.exists(path):
        sys.exit("protocol.json already exists; the protocol is frozen once")
    files = sorted(set(FILES) | {os.path.relpath(p, ROOT) for g in GLOBS for p in glob.glob(os.path.join(ROOT, g))})
    frozen = json.load(open(os.path.join(ROOT, "FROZEN.json")))
    proto = {
        "protocol": PROTOCOL,
        "frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "instance_sha256": frozen["instance"]["sha256"],
        "test_cases_sha256": frozen["test_cases"]["sha256"],
        "file_sha256": {f: sha256(f) for f in files},
        "solver": {"name": "Gurobi", "params": PARAMS},
        "llm": {"model": MODEL, "enable_thinking": False, "api": "DashScope OpenAI-compatible chat completions",
                "explanation": {"temperature": 0.2, "max_attempts": 2, "fallback": "template, counted as failure"},
                "localization": {"temperature": TEMPERATURE, "samples": N_SAMPLES, "response_format": "json_object"},
                "seed_rule": "payload = f'task2_v1|{case_id}|{component}|{run}|{sample_index}'; seed = "
                             "int.from_bytes(sha256(payload)[:4], 'big') & 0x7fffffff; component in "
                             "{explain, localize, localize_clarified}",
                "retry": {"retried_errors": ["APIConnectionError", "APITimeoutError", "RateLimitError"],
                          "max_attempts": len(RETRY_WAITS) + 1, "waits_s": list(RETRY_WAITS),
                          "same_parameters": True, "invalid_outputs_retried": False},
                "runs": 3},
        "confidence_rule": {**RULE, "samples": N_SAMPLES,
                            "definition": "high iff >= min_agree samples share the same (target ID, modification type), "
                                          "the target exists, >= min_non_ambiguous valid samples are not ambiguous, and "
                                          "invalid samples <= max_invalid; otherwise low (clarifying question only, no "
                                          "critique). Invalid = not JSON, fails the sample schema, or (object, aspect) "
                                          "does not map to an existing target ID.",
                            "majority_target": "most frequent target among valid samples; ties broken by sample order"},
        "neighbourhood_rule": {"L0": "query customers may change vehicle; all others fixed to their vehicle; both routes "
                                     "re-sequenced", "L1": "plus each query customer's 2 nearest customers (distance, "
                                                           "ties by index)", "L2": "all customers free",
                               "escalation": "only when the current level is infeasible; infeasible reported only after L2",
                               "anchor": "smallest customer not involved in the query stays on its vehicle (customer 1 if "
                                         "all are involved); same anchor for local and full methods",
                               "modification_queries": "involved customers = customers on the routes of the modified "
                                                       "indicators"},
        "attribution_rule": {"infeasible": "attribution set = business-specific constraints (cap[k]) of the Gurobi IIS",
                             "feasible": "attribution set = undirected edges e[i,j] that differ between the current "
                                         "solution and the optimum with the decision forbidden",
                             "lp": "LP-relaxation duals / reduced costs are reported for reference only"},
        "latency": {"repeats_per_query_per_method": 20, "modes": ["with_model_setup", "solve_only"],
                    "local_with_model_setup": "apply query constraints + warm start + all levels solved + undo "
                                              "(resident model built once at start-up, reported separately)",
                    "full_with_model_setup": "fresh model build + solve, no warm start",
                    "statistics": "median, mean, p95 (nearest rank) over all repeats"},
        "metrics": {
            "attribution": "inclusion = returned set contains every GT element; precision/recall per case (macro) and "
                           "pooled (micro), overall and for the constraint and variable parts; GT set with the best F1 "
                           "when several are acceptable",
            "explanation": "pass = LLM text passes the number and entity checks within 2 attempts",
            "counterfactual": "local vs full: feasibility agreement over all queries; objective within 1% and identical "
                              "change set over queries where both are feasible; each method also against the "
                              "exhaustive ground truth; the reversal flag is reported but not compared",
            "localization": "correct = majority target in the GT target list; overall, among predicted high, among "
                            "predicted low; clarification rate; invalid-sample rate; expected vs predicted confidence; "
                            "re-localization with the simulated clarification answer (generic question when the "
                            "first pass was high)",
            "runs": "LLM parts 3 independent runs, mean and sample std; deterministic parts once"},
        "supplementary_queries": "all MOVE (8) and FIX_ARC (2 x 8 x 7 = 112) queries on the reference optimum",
    }
    with open(path, "w") as f:
        json.dump(proto, f, indent=2)
        f.write("\n")
    print(f"protocol.json written with {len(files)} file hashes")


if __name__ == "__main__":
    main()
