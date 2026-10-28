"""Step 4: sample a fixed 100-prompt slice of AlpacaEval 2 + matching GPT-4 Turbo reference outputs.

Outputs (in --out_dir):
  alpaca100.json        list[str]  -> input for TPO run.py
  alpaca5.json          list[str]  -> smoke test (first 5 of the 100)
  alpaca100_meta.json   list[dict] -> instruction + dataset field (needed by AlpacaEval)
  reference100.json     list[dict] -> AlpacaEval 2 reference outputs for the same 100 prompts
  slice_ids.json        list[int]  -> indices into the 805-prompt eval set (for reproducibility)
"""
import argparse, json, os, random

def load_reference():
    # AlpacaEval 2 default reference = GPT-4 Turbo outputs on all 805 prompts.
    try:
        from huggingface_hub import hf_hub_download
        p = hf_hub_download("tatsu-lab/alpaca_eval", "alpaca_eval_gpt4_baseline.json",
                            repo_type="dataset")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[warn] direct download failed ({e}); falling back to datasets.load_dataset")
        from datasets import load_dataset
        ds = load_dataset("tatsu-lab/alpaca_eval", "alpaca_eval_gpt4_baseline",
                          trust_remote_code=True)["eval"]
        return [dict(r) for r in ds]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out_dir", default="data")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    ref = load_reference()
    assert len(ref) == 805, f"expected 805 prompts, got {len(ref)}"
    ids = sorted(random.Random(a.seed).sample(range(len(ref)), a.n))
    sub = [ref[i] for i in ids]
    assert len({r["instruction"] for r in sub}) == a.n, "duplicate instructions in slice"

    dump = lambda name, obj: json.dump(obj, open(os.path.join(a.out_dir, name), "w",
                                                  encoding="utf-8"), indent=2, ensure_ascii=False)
    dump("alpaca100.json", [r["instruction"] for r in sub])
    dump("alpaca5.json", [r["instruction"] for r in sub[:5]])
    dump("alpaca100_meta.json", [{"instruction": r["instruction"], "dataset": r.get("dataset", "")} for r in sub])
    dump("reference100.json", sub)
    dump("slice_ids.json", ids)
    print(f"wrote {a.n} prompts (seed={a.seed}) to {a.out_dir}/")
