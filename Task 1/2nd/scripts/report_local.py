"""Validate the completed run and report local rewards, without inventing judge results."""
import json
from pathlib import Path

from task_paths import ROOT
STAGES = ("baseline", "step0", "step1", "step2")


def main():
    config = json.loads((ROOT / "run_config.json").read_text())
    prompts = json.loads((ROOT / "data/alpaca100.json").read_text())
    expected = set(prompts)
    outputs = {}
    for stage in STAGES:
        outputs[stage] = json.loads((ROOT / f"stages/{stage}.json").read_text())
        assert len(outputs[stage]) == len(prompts) == 100, stage
        assert {r["instruction"] for r in outputs[stage]} == expected, stage
        assert all(r["output"].strip() for r in outputs[stage]), stage

    summary = json.loads((ROOT / "stages/rm_summary.json").read_text())
    raw = json.loads(next((ROOT / "run100").glob("*.json")).read_text())
    counts = {i: [] for i in (-1, 0, 1)}
    for prompt_result in raw:
        n = {i: 0 for i in counts}
        for key in prompt_result:
            stage, query, _ = key.split("<SEP>", 2)
            assert query in expected
            n[int(stage.replace("INDEX", ""))] += 1
        for i in counts:
            counts[i].append(n[i])
    assert len(raw) == 100
    assert all(v > 0 for v in counts[-1]), "Missing initial responses"
    sampling = {
        ("init" if i == -1 else f"iter{i+1}"): {
            "scored_candidates": sum(v),
            "min_per_prompt": min(v),
            "max_per_prompt": max(v),
            "prompts_with_fewer_than_5": sum(n < 5 for n in v),
        }
        for i, v in counts.items()
    }
    (ROOT / "stages/candidate_counts.json").write_text(json.dumps(sampling, indent=2) + "\n")
    selected = summary["rm_of_selected_response"]
    means = summary["mean_rm_of_all_samples_per_iter"]
    lines = [
        "# Task 1 run report",
        "",
        "Completed 100 AlpacaEval-2 prompts with D=2 and N=5 requested candidates per step.",
        "",
        f"Policy: `{config['policy_model']}` via vLLM on the configured vLLM server. "
        f"Reward model: `{config['reward_model']}` on the configured reward-model device.",
        "",
        "PyTorch 2.4.0+cu121; vLLM 0.6.3; bfloat16. Sampling temperature 0.7, "
        "top_p 0.95, seed 7. Slice seed 42; exact indices: `data/slice_ids.json`. "
        "Response cap 2048 tokens, critique/gradient cap 8192, server context 16384. "
        "Full configuration and data hashes: `run_config.json`.",
        "",
        "## Results",
        "",
        "| Stage | Mean selected RM score | AlpacaEval LC win rate | AlpacaEval win rate |",
        "|---|---:|---|---|",
    ]
    for stage in STAGES:
        lines.append(f"| {stage} | {selected[stage]:.4f} | Pending external judge | Pending external judge |")
    lines += [
        "",
        "Baseline is the first initial sample; step0 is Best-of-5; step1 and step2 "
        "select the best cached answer after each refinement. Selected reward scores "
        "are nondecreasing by construction and do not establish independent win-rate improvement.",
        "",
        "Mean reward of all scored candidates, including less successful refinements:",
        "",
        "| Iteration | Mean RM score | Scored candidates | Prompts with fewer than 5 stored candidates |",
        "|---|---:|---:|---:|",
    ]
    for iteration, score in means.items():
        count = sampling[iteration]
        lines.append(f"| {iteration} | {score:.4f} | {count['scored_candidates']} | {count['prompts_with_fewer_than_5']} |")
    lines += [
        "",
        "The official optimizer discards refinements missing its required response tags; "
        "identical responses within an iteration also share a cache key. Candidate counts "
        "therefore describe stored scored answers, not necessarily all requested generations.",
        "",
        "## Independent evaluation",
        "",
        "A dummy API key suffices for the local server. This RM-only report does not perform external judging. Credentials may be "
        "configured separately in the aeval environment. "
        "Read results_task1.md for any completed independent evaluation. "
        "With an AlpacaEval environment and valid judge credentials, run "
        "`bash run_alpaca_eval.sh stages data/reference100.json`, then `python summarize.py` "
        "from this directory. The reference contains the same 100 GPT-4 Turbo responses.",
        "",
        "## Comparison with the paper",
        "",
        "The [published ICML paper](https://proceedings.mlr.press/v267/li25ac.html) "
        "does not report an 8B-policy AlpacaEval win-rate table. Table 1 reports 70B-SFT "
        "LC 27.8% / WR 16.8%, rising to LC 33.0% / WR 40.5% with FsfairX and D2-N5. "
        "These are context, not directly comparable targets for this 8B, 100-prompt run. "
        "Section 7.4 and Figure 7 show declining reward for 8B-Instruct on HH-RLHF, "
        "attributed to instruction-following limitations. Improvement on this setup "
        "must therefore be measured rather than assumed.",
        "",
        "## Environment repair",
        "",
        "The existing vLLM process initially returned HTTP 500 because its lazy outlines "
        "import could not find pyairports. Replaced the installed nonfunctional 0.0.1 "
        "package with original NICTA/pyairports 2.1.1 at commit "
        "`9699eae8c6b03c97239018dea92e01daa8594936`. Actual text generation then succeeded. "
        "Existing repository modifications were preserved. The policy server was reused.",
        "",
    ]
    (ROOT / "rm_report.md").write_text("\n".join(lines))
    print("Validated all four stages: 100 nonempty, matching prompts each.")
    print(json.dumps(sampling, indent=2))
    print("Report:", ROOT / "rm_report.md")


if __name__ == "__main__":
    main()
