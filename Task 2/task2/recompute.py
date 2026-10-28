"""Recompute every metric from the saved artifacts in <out>/raw/ (no network, no LLM, no solver) and
compare with <out>/task2_results.json.   python recompute.py [--out results]"""
import argparse
import json
import os
import sys

import metrics

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    out_dir = os.path.join(ROOT, args.out)
    raw = {k: json.load(open(os.path.join(out_dir, "raw", f"{k}.json")))
           for k in ("attribution", "counterfactual_main", "counterfactual_supplementary", "localization", "meta")}
    meta = raw.pop("meta")
    cases = json.load(open(os.path.join(ROOT, "cases", f"{meta['split']}_cases.json")))["cases"]
    recomputed = metrics.compute_all(cases, raw, meta["runs"])
    saved = json.load(open(os.path.join(out_dir, "task2_results.json")))["metrics"]
    same = json.loads(json.dumps(recomputed)) == saved
    print(json.dumps({"identical_to_saved": same}))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
