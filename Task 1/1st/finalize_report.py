"""Assemble the finishing report from validated results, retaining the paper section."""
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    original_path = ROOT / 'run_report_before_finish.md'
    if not original_path.exists():
        original_path.write_text((ROOT / 'run_report.md').read_text())
    original = original_path.read_text()
    comparison = original.split('## Comparison with the paper', 1)[1].split('## Environment repair', 1)[0].strip()
    result = json.loads((ROOT / 'results_task1.json').read_text())
    robustness = json.loads((ROOT / 'robustness.json').read_text())
    endpoint = json.loads((ROOT / 'judge_endpoint_check.json').read_text())
    bon = json.loads((ROOT / 'stages/bon15_rm_summary.json').read_text())
    assert endpoint['acceptance'] == 'PASS' and len(result['rows']) == 5
    assert all(row['Judged'] == 100 for row in result['rows'])
    results_text = (ROOT / 'results_task1.md').read_text().split('\n', 1)[1].strip()
    robustness_text = (ROOT / 'robustness.md').read_text().split('\n', 1)[1].strip()
    lines = [
        '# Task 1 — completed GPU experiment and Qwen evaluation', '',
        'TPO improves the stored RM scores but does **not** monotonically improve Qwen-judged WR or LC. '
        'Step2 has lower point estimates than Best-of-5 and Best-of-15. Paired 95% WR intervals for both '
        'control comparisons include zero, so this run does not establish an independent judge-measured gain.', '',
        '## Experiment and completed checks', '',
        '- Policy: `allenai/Llama-3.1-Tulu-3-8B-SFT` via vLLM on H100 GPU 2, port 8002. '
        'RM: `sfairXC/FsfairX-LLaMA3-RM-v0.1` on H100 GPU 3. Both generation runs completed; '
        'the confirmed user-owned policy server was stopped after Best-of-15. Phase 1 verified no `yuqian` processes remained on GPUs 2 and 3.',
        '- Same 100-prompt AlpacaEval-2 slice and GPT-4 Turbo references for every stage. Slice seed 42; '
        'exact original indices in `data/slice_ids.json`. TPO D=2, N=5; sampling temperature 0.7, top_p 0.95, seed 7.',
        '- Candidate response cap 2048; critique/gradient output cap 8192; vLLM context 16384; '
        '8 worker threads; bfloat16. TPO runtime 347.9887 seconds; Best-of-15 runtime 96.5834 seconds.',
        f'- Best-of-15 acceptance: 100 nonempty matching outputs; mean selected RM {bon["mean_selected_rm_score"]:.4f}; '
        f'{bon["prompts_with_fewer_than_15_stored_samples"]} prompts have fewer than 15 stored answers due to duplicate merging. '
        'It matches the response-candidate budget, not full FLOPs, because TPO also generates critiques/gradients.',
        '- Phase 2: HTTP 200; populated top logprobs; no reasoning content. Reasoning-token detail is absent '
        '(not an explicitly reported zero). Every judge request sends `enable_thinking=false` and is validated '
        'for reasoning content and any exposed reasoning-token count. The response model is the alias `qwen3.8-max`; '
        'no dated snapshot was exposed.',
        '- Phase 3: five-example parsing smoke passed; baseline, step0, step1, step2, and bon15 each have '
        '100 valid annotations and saved LC fits. Phase 4 uses only stored scores and annotations on CPU.',
        '- TPO/optimizer source hashes match their pre-finish values. No TPO generation was rerun during Phases 2–6. '
        'Full configuration: `run_config.json`; deviations and limits: `DEVIATIONS.md`.', '',
        '## Five-stage results', '', results_text, '',
        'Baseline is the first plain SFT sample. Step0 is Best-of-5. Step1 and step2 choose the best cached '
        'answer after each refinement. Selected RM scores are nondecreasing by construction and are not '
        'independent evidence of improved response quality. Both WR and LC monotonicity verdicts are **false**.', '',
        'The adjacent WR change baseline→step1 is smaller than its paired SE; step1→step2 declines by more '
        'than one paired SE. Both adjacent LC changes are negative and exceed their conditional paired SE. '
        'See the comparison table for the exact differences. These one-SE comparisons are descriptive, '
        'not 95% significance tests.', '',
        '## Robustness', '', robustness_text, '',
        'The complete-case subset has rising mean rewards too, so the RM trend persists after restricting '
        'to prompts with five stored candidates in every round. This does not make the subset representative '
        'or turn RM improvement into judge improvement. Improved-prompt percentages count any positive '
        'soft-score change, including very small changes; they can differ from the sign of the mean effect.', '',
        '## Reproducibility', '',
        '`setup_env.sh` creates separate `tpo` and `aeval` environments, installs official requirements and '
        'the two required environment repairs, pins pyairports to its exact source commit, builds the '
        'environment-backed judge config, and provides the vLLM serve command. It was syntax checked; '
        'a clean-machine installation was not executed on this host. It does not rerun either completed experiment.', '',
        'The exact weighted GPT-4-Turbo prompt bytes and soft logprob parser are retained with the judge '
        'model changed to Qwen. Judge temperature is the original **1**, with max_tokens=1; the distinct '
        'Phase 2 connection check used temperature=0/max_tokens=5. Identical pairs share the seeded annotation '
        'cache. The standard LC estimator receives original benchmark indices rather than slice row positions; '
        'its GPT-4-derived calibration is retained, so these LC values also inherit that calibration limitation.', '',
        'Package locks, source patch, prompt hashes, LC calibration, usage, and an exhaustive file list are '
        'available through `FILES_FINISH.md`. Credentials remain in the external mode-600 environment file; '
        'no credential value is embedded in project files.', '',
        '## Comparison with the paper', '', comparison, '',
        'The use of a different judge, a smaller policy, and a 100-prompt slice prevents direct comparison '
        'of this run’s absolute WR/LC with the published 70B numbers. The observed RM/judge divergence '
        'supports reporting the failure to demonstrate the requested monotonic improvement, rather than assuming it.', '',
        '## Final validation', '',
        'All five stages have 100 aligned, finite annotations. Robustness outputs use 10,000 paired bootstrap '
        'resamples with seed 42. Shell scripts pass syntax checks and new Python scripts compile. '
        'The secret-scan result is recorded in `secret_scan_result.json` after the final scan.', '']
    (ROOT / 'run_report.md').write_text('\n'.join(lines))
    config = json.loads((ROOT / 'run_config.json').read_text())
    config['judge_status'] = 'Completed all five stages with user-fixed qwen3.8-max weighted judge; official GPT-4 Turbo judging not used.'
    config['run_status'] = 'TPO, Best-of-15, Qwen judging, and robustness complete'
    config['judge_model'] = result['judge_model']
    config['judge_annotator'] = result['annotator']
    config['judge_settings'] = {'temperature': 1, 'max_tokens': 1, 'logprobs': True,
                                'top_logprobs': 5, 'enable_thinking': False, 'order_randomization_seed': 0}
    config['judge_packages'] = {p: version(p) for p in ['alpaca-eval', 'openai', 'setuptools', 'scikit-learn']}
    config['judge_usage'] = result['usage_totals']
    config['robustness'] = {'bootstrap_seed': 42, 'bootstrap_resamples': 10000,
                            'complete_case_n': robustness['survivorship']['complete_case_n_prompts']}
    (ROOT / 'run_config.json').write_text(json.dumps(config, indent=2) + '\n')
    print('Report and configuration updated; original paper-comparison section preserved verbatim.')


if __name__ == '__main__':
    main()
