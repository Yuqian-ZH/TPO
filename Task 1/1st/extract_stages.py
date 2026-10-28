"""Step 7: turn TPO run.py output into per-stage AlpacaEval files + RM-score table.

run.py saves a list of dicts, one per prompt: {"INDEX{i}<SEP>{query}<SEP>{answer}": rm_score}
  INDEX-1 = the N initial samples, INDEX0 = samples from TPO iter 1, INDEX1 = iter 2, ...

Stages written (each = the response AlpacaEval will judge for that prompt):
  baseline : first initial sample (a single plain draw from the SFT policy, no selection, no TPO)
  step0    : best-RM response among the N initial samples (= Best-of-N, no textual feedback)
  step1    : best-RM response in the cache after TPO iteration 1
  step2    : best-RM response in the cache after TPO iteration 2 (paper's final output rule)
"""
import argparse, json, os, statistics as st

def parse(results):
    per_q = {}
    for d in results:
        for k, score in d.items():
            idx, q, a = k.split("<SEP>", 2)
            it = int(idx.replace("INDEX", ""))
            per_q.setdefault(q, []).append((it, a, score))
    return per_q

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tpo_output", required=True)
    ap.add_argument("--meta", default="data/alpaca100_meta.json")
    ap.add_argument("--out_dir", default="stages")
    ap.add_argument("--generator", default="tulu3-8b-sft")
    ap.add_argument("--max_iters", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    meta = {m["instruction"]: m["dataset"] for m in json.load(open(a.meta, encoding="utf-8"))}
    per_q = parse(json.load(open(a.tpo_output, encoding="utf-8")))
    missing = set(meta) - set(per_q)
    if missing:
        print(f"[warn] {len(missing)} prompts have no TPO output yet (run unfinished?)")

    stages = {"baseline": [], "step0": [], "step1": [], "step2": []}
    best_rm = {s: [] for s in stages}
    mean_rm_by_iter = {}           # paper's test-time-training metric: mean RM of samples at each iter
    for q, items in per_q.items():
        if q not in meta:
            continue
        init = [x for x in items if x[0] == -1]
        pick = {
            "baseline": init[0],
            "step0": max(init, key=lambda x: x[2]),
        }
        for s in range(1, a.max_iters + 1):
            pool = [x for x in items if x[0] <= s - 1]
            pick[f"step{s}"] = max(pool, key=lambda x: x[2])
        for name, (_, ans, sc) in pick.items():
            if name in stages:
                stages[name].append({"instruction": q, "output": ans,
                                     "generator": f"{a.generator}-{name}", "dataset": meta[q]})
                best_rm[name].append(sc)
        for it in sorted({x[0] for x in items}):
            mean_rm_by_iter.setdefault(it, []).extend(x[2] for x in items if x[0] == it)

    for name, rows in stages.items():
        json.dump(rows, open(f"{a.out_dir}/{name}.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    summary = {
        "n_prompts": len(stages["step0"]),
        "rm_of_selected_response": {k: round(st.mean(v), 4) for k, v in best_rm.items() if v},
        "mean_rm_of_all_samples_per_iter": {("init" if k == -1 else f"iter{k+1}"): round(st.mean(v), 4)
                                            for k, v in sorted(mean_rm_by_iter.items())},
    }
    json.dump(summary, open(f"{a.out_dir}/rm_summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))
