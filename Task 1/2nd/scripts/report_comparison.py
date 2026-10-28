"""Report a fresh Tulu/FsfairX replication, judged by Qwen, against the saved run."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STAGES = ['baseline', 'step0', 'step1', 'step2', 'bon15']


def read(path):
    return json.loads(path.read_text())


def paired(values):
    values = np.asarray(values, dtype=float)
    assert values.shape == (100,) and np.isfinite(values).all()
    indices = np.random.default_rng(42).integers(0, 100, (10000, 100))
    low, high = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return dict(mean=float(values.mean()), se=float(values.std(ddof=1) / 10),
                bootstrap_95_ci=[float(low), float(high)])


def parse(folder):
    parsed = {}
    for row in read(ROOT / folder / 'results.json'):
        for key, reward in row.items():
            index, query, answer = key.split('<SEP>', 2)
            parsed.setdefault(query, []).append((int(index.replace('INDEX', '')), answer, reward))
    assert len(parsed) == 100
    return parsed


def interval(record):
    low, high = record['bootstrap_95_ci']
    return f"{record['mean']:+.2f} [{low:+.2f}, {high:+.2f}]"


def main():
    measured = read(ROOT / 'results_task1.json')
    historical = read(ROOT / 'llama_reference/results_task1.json')
    config = read(ROOT / 'run_config.json')
    queries = [r['instruction'] for r in read(ROOT / 'data/reference100.json')]
    assert len(set(queries)) == 100
    for name in ['alpaca100.json', 'reference100.json', 'slice_ids.json', 'alpaca100_meta.json']:
        assert (ROOT / 'data' / name).read_bytes() == (ROOT / 'llama_reference/data' / name).read_bytes()
    scores, outputs = {}, {}
    for label, base in [('new', ROOT), ('current', ROOT / 'llama_reference')]:
        scores[label], outputs[label] = {}, {}
        for stage in STAGES:
            rows = read(base / f'eval_out/{stage}/annotations.json')
            mapping = {r['instruction']: r for r in rows}
            assert len(rows) == len(mapping) == 100 and set(mapping) == set(queries)
            scores[label][stage] = dict(
                WR=np.array([(float(mapping[q]['preference']) - 1) * 100 for q in queries]),
                LC=np.array([float(mapping[q]['glm_preference']) * 100 for q in queries]))
            outputs[label][stage] = {r['instruction']: r['output'] for r in read(base / f'stages/{stage}.json')}
    current = {r['Stage']: r for r in historical['rows']}
    new = {r['Stage']: r for r in measured['rows']}
    differences = {}
    within, improvement_contrasts = {}, {}
    for stage in STAGES:
        differences[stage] = dict(
            WR=paired(scores['new'][stage]['WR'] - scores['current'][stage]['WR']),
            LC_descriptive=paired(scores['new'][stage]['LC'] - scores['current'][stage]['LC']),
            rm_difference=new[stage]['RM'] - current[stage]['RM'],
            identical_outputs=sum(outputs['new'][stage][q] == outputs['current'][stage][q] for q in queries))
    for control in ['baseline', 'step0', 'step1', 'bon15']:
        key = f'step2 - {control}'
        within[key] = {metric: paired(scores['new']['step2'][metric] - scores['new'][control][metric]) for metric in ['WR', 'LC']}
        improvement_contrasts[key] = paired(
            (scores['new']['step2']['WR'] - scores['new'][control]['WR']) -
            (scores['current']['step2']['WR'] - scores['current'][control]['WR']))
    raw, bon = parse('run100'), parse('bon15')
    counts, mean_rewards = {}, {}
    for index, label in [(-1, 'initial'), (0, 'step1'), (1, 'step2')]:
        values = [reward for q in queries for i, answer, reward in raw[q] if i == index]
        counts[label] = len(values)
        mean_rewards[label] = float(np.mean(values)) if values else None
    events = [json.loads(line) for line in (ROOT / 'policy_requests.jsonl').read_text().splitlines()]
    assert all(r['request']['model'] == config['policy_model'] for r in events)
    finishes = Counter(c['finish_reason'] for r in events for c in r['choices'])
    local_usage = {k: sum((r.get('usage') or {}).get(k, 0) or 0 for r in events)
                   for k in ['prompt_tokens', 'completion_tokens', 'total_tokens']}
    rounds = {'initial': Counter(), 'refinement': Counter(), 'bon15': Counter()}
    for event in events:
        request = event['request']
        if request['n'] == 1:
            continue
        kind = 'bon15' if event['phase'] == 'bon15' else ('initial' if request['messages'][0]['content'] == 'You are a helpful, creative, and smart assistant.' else 'refinement')
        rounds[kind]['returned'] += len(event['choices'])
        if kind == 'refinement':
            for choice in event['choices']:
                try:
                    choice['content'].split('<IMPROVED_VARIABLE>')[1].split('</IMPROVED_VARIABLE>')[0].strip()
                    rounds[kind]['valid_tags'] += 1
                except IndexError:
                    rounds[kind]['missing_tags'] += 1
    status = read(ROOT / 'generation_status.json')
    assert all(status[p]['state'] == 'complete' and status[p]['completed'] == 100 for p in ['run100', 'bon15'])
    before = read(ROOT / 'tpo_before.sha256.json')
    protected = ROOT.parent / 'TPO'
    after = {str(p.relative_to(protected)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in protected.rglob('*') if p.is_file() and not p.is_symlink()}
    preservation = dict(unchanged=before == after, before_files=len(before), after_files=len(after),
        changed=[p for p in before if p in after and before[p] != after[p]],
        added=sorted(set(after) - set(before)), removed=sorted(set(before) - set(after)))
    assert preservation['unchanged'], 'Protected TPO content changed'
    (ROOT / 'tpo_preservation.json').write_text(json.dumps(preservation, indent=2) + '\n')
    summary = dict(new_minus_current=differences, new_within_run=within,
        difference_in_WR_improvement=improvement_contrasts, unique_candidate_counts=counts,
        candidate_mean_rm=mean_rewards, local_policy_tokens=local_usage,
        policy_finish_reasons=finishes, raw_candidate_diagnostics=rounds,
        source_preservation=preservation, bootstrap=dict(seed=42, resamples=10000, unit='matched instruction'),
        excluded='discarded_qwen_policy/ was stopped after model-role clarification and contributes no reported data.')
    (ROOT / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
    config.update(run_status='Tulu generation, Qwen judging, and paired comparison complete',
        completed_prompts=100, completed_at=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
        generation_timing=status, local_policy_tokens=local_usage, judge_usage=measured['usage_totals'])
    (ROOT / 'run_config.json').write_text(json.dumps(config, indent=2) + '\n')
    conclusion = (
        f"The baseline → step1 → step2 WR point estimates are monotonic in this rerun "
        f"({new['baseline']['WR (%)']:.2f} → {new['step1']['WR (%)']:.2f} → {new['step2']['WR (%)']:.2f}%), "
        f"whereas the saved experiment was not monotonic. LC is not monotonic. "
        f"Step2 minus baseline WR is {interval(within['step2 - baseline']['WR'])} pp, "
        f"step2 minus Best-of-5 is {interval(within['step2 - step0']['WR'])} pp, "
        f"and step2 minus Best-of-15 is {interval(within['step2 - bon15']['WR'])} pp. "
        'All three intervals contain zero. The rerun therefore shows monotonic point estimates, '
        'but does not establish a reliable TPO benefit over the controls. '
        f"The new final WR is {interval(differences['step2']['WR'])} pp above the saved final WR; "
        'that interval also contains zero.')
    empty_candidates = {label: sum(not answer.strip() for items in value.values() for i, answer, reward in items)
                        for label, value in [('tpo', raw), ('bon15', bon)]}
    lines = ['# Experiment results: Tulu policy, FsfairX RM, Qwen judge', '',
        '**Policy:** `allenai/Llama-3.1-Tulu-3-8B-SFT` for sampling, critique, textual gradient and refinement. '
        '**RM:** `sfairXC/FsfairX-LLaMA3-RM-v0.1`. **Qwen is the judge only:** `qwen3.8-max`, thinking disabled.', '',
        'Fresh measurements on the same fixed 100 AlpacaEval-2 prompts and GPT-4 Turbo reference answers as the current experiment. '
        'D=2, N=5, candidate seed 7, temperature .7, top_p .95, response cap 2048. '
        'Critique/gradient: temperature .7, top_p .99, cap 8192, unset seed. vLLM context 16384; eight prompt workers; policy GPU 2 and RM GPU 3.', '',
        pd.DataFrame(measured['rows']).to_markdown(index=False, floatfmt='.4f'), '',
        f"Monotonic baseline → step1 → step2: WR **{measured['monotonic_baseline_step1_step2']['WR (%)']}**; LC **{measured['monotonic_baseline_step1_step2']['LC (%)']}**.", '',
        conclusion, '',
        'Baseline is the first initial sample. Step0 is Best-of-5; step1/step2 select the best reward in the cumulative cache. '
        'Best-of-15 matches TPO’s answer-candidate count but excludes critique/gradient compute. '
        'Cumulative selection guarantees nondecreasing selected RM; independent win-rate improvement is an empirical question.', '',
        '| New-run comparison | WR Δ pp [paired 95% CI] | LC Δ pp [descriptive CI] |', '|---|---:|---:|']
    for key, value in within.items():
        lines.append(f"| {key} | {interval(value['WR'])} | {interval(value['LC'])} |")
    lines += ['', f'All-candidate mean RM: {json.dumps(mean_rewards)}.',
        f'Unique cached candidates: {json.dumps(counts)}; 500 requested per TPO round.',
        f'Raw candidate extraction diagnostics: {json.dumps(rounds)}.',
        f'Raw policy response finish reasons: {json.dumps(finishes)}. Length indicates a raw response hit its cap.',
        f'Empty unique cached candidates: {json.dumps(empty_candidates)}; none of the 500 selected stage outputs is empty.',
        f'Local policy token usage: {json.dumps(local_usage)}. These are local vLLM counts, not hosted Qwen generation usage.',
        f'Generation timing excluding model loading: TPO {status["run100"]["elapsed_seconds"]:.1f}s; Best-of-15 {status["bon15"]["elapsed_seconds"]:.1f}s.', '',
        'Judge settings match the current experiment: weighted AlpacaEval prompt and soft logprob parser, '
        'temperature 1, max_tokens 1, top_logprobs 5, thinking disabled, answer-order seed 0. '
        'WR is mean weighted preference against the reference, not an integer win fraction. '
        'Uncertainty uses 10,000 paired prompt bootstrap resamples, seed 42. '
        'LC intervals condition on fitted GLMs and omit fit uncertainty; GPT-4-derived calibration is unvalidated for Qwen, so LC is descriptive.', '',
        'The paper Table 1 uses a 70B SFT policy: FsfairX D2-N5 yields WR 16.8→40.5 and LC 27.8→33.0. '
        'There is no equivalent 8B AlpacaEval WR table; §7.4 discusses 8B-Instruct on HH-RLHF. '
        'Model size, subset and judge differ, so these are context, not comparable targets. '
        '[Published paper](https://proceedings.mlr.press/v267/li25ac.html).', '',
        'Evidence: `run_config.json`, `results_task1.json`, `comparison.json`, `robustness.json`, '
        '`policy_requests.jsonl`, `stages/` and `eval_out/`. The discarded Qwen-policy run contributes no results.', '']
    (ROOT / 'EXPERIMENT_RESULTS.md').write_text('\n'.join(lines))
    rows = []
    for stage in STAGES:
        rows.append({'Stage': stage, 'Current WR %': current[stage]['WR (%)'], 'New WR %': new[stage]['WR (%)'],
            'WR Δ pp [95% CI]': interval(differences[stage]['WR']),
            'Current LC %': current[stage]['LC (%)'], 'New LC %': new[stage]['LC (%)'],
            'Current RM': current[stage]['RM'], 'New RM': new[stage]['RM'],
            'Identical outputs /100': differences[stage]['identical_outputs']})
    lines = ['# Comparison with the current experiment', '',
        '**Both runs use the same roles: Tulu-3-8B-SFT policy, FsfairX-LLaMA3 reward model, Qwen judge.** '
        'This compares a fresh replication with the saved experiment; it is not a Qwen-policy versus Llama-policy comparison.', '',
        f"New WR baseline → step1 → step2: **{new['baseline']['WR (%)']:.2f} → {new['step1']['WR (%)']:.2f} → {new['step2']['WR (%)']:.2f}%**. "
        f"Current: **{current['baseline']['WR (%)']:.2f} → {current['step1']['WR (%)']:.2f} → {current['step2']['WR (%)']:.2f}%**.", '',
        conclusion, '',
        pd.DataFrame(rows).to_markdown(index=False, floatfmt='.4f'), '',
        'Every difference pairs the same instruction and reference. These are changes in reference-relative soft preference scores, '
        'not direct matches between the two runs. Intervals containing zero do not establish a difference.', '',
        '| Improvement contrast | New change minus current change, WR pp [95% CI] |', '|---|---:|']
    for key, value in improvement_contrasts.items():
        lines.append(f'| {key} | {interval(value)} |')
    lines += ['', 'Held fixed: policy and reward model identifiers and cached checkpoints, all TPO/TextGrad algorithm code and prompts, '
        '100 exact questions and references, D/N, candidate seed, temperature/top_p, token limits, eight workers, '
        'vLLM context, stage definitions, judge prompt/parser/settings, and bootstrap method. '
        'The rerun uses a persistent eight-worker pool and per-prompt checkpoints; the historical launcher recreated its pool every 32 prompts. Fresh generation differs because critique/gradient requests are unseeded and server batching/scheduling can vary. '
        'The judge alias has no dated snapshot, and judging occurs at a later time. '
        'This single-seed rerun assesses observed repeatability, not a multi-seed estimate of the method’s general performance.', '',
        'Both runs replace the official GPT-4 judge with Qwen; their absolute scores are not directly comparable to the paper or leaderboard. '
        'LC retains historical GPT-4 calibration and is descriptive. Reward increases alone do not establish improved answer quality.', '',
        f'`TPO/` preservation: **{preservation["unchanged"]}**; {preservation["before_files"]} file contents match, with no additions/removals. '
        'See `tpo_preservation.json`. Current artifacts are copied in `llama_reference/`; stopped Qwen-policy artifacts are excluded.', '',
        'See [experiment results](EXPERIMENT_RESULTS.md), [full paired statistics](comparison.json), '
        '[configuration](run_config.json), and [within-run robustness](robustness.md).', '']
    (ROOT / 'COMPARISON.md').write_text('\n'.join(lines))
    print('Reports written; model roles, matched prompts and unchanged TPO contents verified.')


if __name__ == '__main__':
    main()
