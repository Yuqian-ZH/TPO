"""Stage 3 checks on DESIGN.md: every measured number is found in its source, the validator table matches the
demonstration output, every sub-question of the task is covered, and no dash joins sentences.
Writes results/checks.json. RLUF quotes were checked by hand against arXiv 2505.14946v1."""
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
USC = os.path.dirname(os.path.dirname(ROOT))


def read(*parts):
    with open(os.path.join(USC, *parts)) as f:
        return f.read()


DOC = read("Task 5", "task5", "DESIGN.md")

# (number as written in DESIGN.md, source file, string that must appear in the source)
SOURCES = [
    ("298 of 300", ("Task 3", "task3", "README.md"), "298 of 300"),
    ("12 percentage points [+2, +22]", ("Task 3", "task3", "README.md"), "**+12.0 pp [+2.0, +22.0]**"),
    ("+62 percentage points at iteration 1", ("Task 3", "task3", "README.md"), "**+61.7 pp [+5.0, +100.0]**"),
    ("+5 [−6, +17] in v3.1", ("Task 3", "task3", "README.md"), "side: A +5 [−1, +11], B +5 [−6, +17]"),
    ("18 percentage points [+2, +34]", ("Task 3", "task3", "README.md"), "side cases +18 [+2, +34]"),
    ("80 to 83%", ("Task 3", "task3", "README.md"), "80 to 83%"),
    ("3.7 to 9.0 km", ("Task 3", "task3", "README.md"), "3.7 to 9.0 km"),
    ("RM +0.80", ("Task 1", "1st", "robustness.md"), "| RM            | step2 - bon15 |   0.8046 |"),
    ("RM +0.88 [0.48, 1.28]", ("Task 1", "3rd", "robustness.md"), "| RM | step2 - bon15 | 0.8809 | 68.0000 | [0.4848, 1.2772] |"),
    ("+0.16 pp [−5.51, 5.95]", ("Task 1", "3rd", "robustness.md"), "| WR_pp | step2 - bon15 | 0.1594 | 58.0000 | [-5.5083, 5.9471] |"),
    ("−5.74 pp, 95% CI [−11.92, 0.007]", ("Task 1", "1st", "robustness.md"), "| Judge WR (pp) | step2 - bon15 |  -5.7442 |                52.0000 | [-11.9185, 0.0072] |"),
    ("95 to 99%", ("Task 4", "task4", "README.md"), "95 to 99%"),
    ("58 to 70 ms", ("Task 4", "task4", "README.md"), "58 to 70 ms"),
    ("11.8k tokens", ("Task 4", "task4", "results", "e2e_test", "e2e_report.md"), "| A0B0C1 | 10/10 | 10/10 | 3 | 75 | 111,502 + 6,777 |"),
    ("10/10", ("Task 2", "task2", "README.md"), "| Returned set contains the ground truth | 10/10 |"),
    ("87 of 101", ("Task 2", "task2", "README.md"), "87/101 (86.1%)"),
    ("3 to 13 of 20 queries", ("Task 2", "task2", "README.md"), "3, 13 and 4 of 20 queries at 12, 16 and 20 customers"),
    ("19 of 20", ("Task 4", "task4", "README.md"), "| `A1B1C1` (full system) | 9/10 |"),
    ("149 of 885", ("Task 2", "task2", "results_v2", "task2_v2_results.md"),
     "| Objective of the alternative correct | 83.2% (736/885) | 100.0% (885/885) |"),
    ("46,500", ("Task 2", "task2", "results_v2", "task2_v2_results.md"), "Largest error: (46500.0,"),
]

TOPICS = {
    "1 distillation: SFT": "**SFT, proposer", "1 distillation: DPO": "**DPO, proposer", "1 data pipeline": "### 2.2 The trajectory record",
    "1 training cadence": "### 2.4 Cadence", "2 filter, weight, validate": "### 3.3 The filtering and weighting pipeline",
    "2 RLUF failure mode": "### 3.2 The Meta RLUF failure mode", "2 misunderstood praise": "**Positive feedback based on a misunderstanding",
    "2 self-imposed constraint": "**A complaint that targets a constraint the user imposed", "3 isolation": "### 4.1 Isolation boundaries",
    "3 shared base from aggregated signals": "### 4.3 Aggregation safeguards", "4 A/B strategy": "### 5.1 Release path",
    "4 metrics": "### 5.2 Metrics", "4 rollback triggers": "### 5.4 Rollback triggers",
}


def validator_numbers():
    with open(os.path.join(ROOT, "results", "validator_demo.json")) as f:
        rows = {r["id"]: r for r in json.load(f)}
    e = {k: rows[k]["evidence"] for k in rows}
    v1 = e["V1"]["without_each_user_input"][0]
    return {
        "V4 60 to 129": (e["V4"]["A[3]"]["before"], e["V4"]["A[3]"]["after"]) == (60, 129) and "from 60 to 129 km" in DOC,
        "V5 124 against 100": e["V5"]["loads_on_confirmed_data"]["1"] == 124 and "124 against a capacity of 100" in DOC,
        "V5 stops 4 to 2": (e["V5"]["S[2]"]["before"], e["V5"]["S[2]"]["after"]) == (4, 2) and "(4 to 2)" in DOC,
        "V6 99 to 91": (e["V6"]["W[1]"]["before"], e["V6"]["W[1]"]["after"]) == (99, 91) and "from 99 to 91" in DOC,
        "V1 235 / 140 / 390 to 351": (e["V1"]["L[1]"], v1["L[1]_without_it"], e["V1"]["total_distance"],
                                     v1["total_distance_without_it"]) == (235, 140, 390, 351)
                                    and "vehicle 1 drives 140 km, total 390 to 351" in DOC,
        "V7 still 4 stops": e["V7"]["without_each_user_input"][0]["S[2]_without_it"] == 4 and "at 4 stops" in DOC,
        "all verdicts as expected": all(r["as_expected"] for r in rows.values()),
    }


def main():
    checks = {}
    checks["numbers_in_doc_and_source"] = {n: (n in DOC, src in read(*path)) for n, path, src in SOURCES}
    checks["validator_table_matches_demo"] = validator_numbers()
    checks["topics_covered"] = {k: v in DOC for k, v in TOPICS.items()}
    checks["no_dash"] = {f: not any(c in read("Task 5", "task5", f) for c in "—–") for f in ("DESIGN.md", "README.md")}
    py = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    checks["pytest"] = {"passed": py.returncode == 0, "tail": py.stdout.strip().splitlines()[-1:]}

    def ok(v):
        if isinstance(v, dict):
            return all(ok(x) for k, x in v.items() if k != "tail")
        if isinstance(v, tuple):
            return all(v)
        return bool(v)
    report = {"checks": checks, "all_passed": ok(checks)}
    with open(os.path.join(ROOT, "results", "checks.json"), "w") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
