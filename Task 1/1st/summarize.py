"""Validate and summarize all five stages and paired differences against one reference."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
STAGES = ['baseline', 'step0', 'step1', 'step2', 'bon15']
JUDGE_NOTE = ('The judge is Qwen (`qwen3.8-max`), not the official AlpacaEval GPT-4 Turbo judge. '
              'Absolute win rates are therefore not comparable to the AlpacaEval leaderboard or the TPO paper; '
              'they measure relative change across stages of this run only.')


def paired_summary(left, right, column):
    a = left.set_index('instruction')[column].sort_index()
    b = right.set_index('instruction')[column].reindex(a.index)
    assert b.notna().all() and len(a) == 100
    diff = (a - b).to_numpy() * 100
    se = diff.std(ddof=1) / np.sqrt(len(diff))
    return {'difference_pp': float(diff.mean()), 'paired_se_pp': float(se),
            'exceeds_one_paired_se': bool(abs(diff.mean()) > se)}


def main():
    rm = json.loads((ROOT / 'stages/rm_summary.json').read_text())['rm_of_selected_response']
    rm['bon15'] = json.loads((ROOT / 'stages/bon15_rm_summary.json').read_text())['mean_selected_rm_score']
    expected = {r['instruction'] for r in json.loads((ROOT / 'data/reference100.json').read_text())}
    rows, annotations, usage = [], {}, {}
    for stage in STAGES:
        directory = ROOT / f'eval_out/{stage}'
        r = pd.read_csv(directory / 'leaderboard.csv', index_col=0).loc[f'tulu3-8b-sft-{stage}']
        frame = pd.read_json(directory / 'annotations.json')
        assert len(frame) == frame['instruction'].nunique() == r['n_total'] == 100
        assert set(frame['instruction']) == expected
        assert frame['preference'].between(1, 2).all() and frame['glm_preference'].notna().all()
        frame['judge_score'] = frame['preference'] - 1
        annotations[stage] = frame
        path = directory / 'usage.jsonl'
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        assert all(e['model'] == 'qwen3.8-max' and e['enable_thinking'] is False
                   and not e['reasoning_content_present'] and e['reasoning_tokens'] in (None, 0) for e in events)
        totals = {key: sum((e['usage'].get(key) or 0) for e in events)
                  for key in ['prompt_tokens', 'completion_tokens', 'total_tokens']}
        usage[stage] = {'successful_api_requests': len(events), **totals,
                        'note': 'Actual successful requests. Cached annotations and identical-answer ties need no new request.'}
        rows.append({'Stage': stage, 'LC (%)': float(r['length_controlled_winrate']),
                     'WR (%)': float(r['win_rate']), 'WR SE (pp)': float(r['standard_error']),
                     'LC SE (pp)': float(r['lc_standard_error']), 'RM': rm[stage],
                     'Avg length (chars)': int(r['avg_length']), 'Judged': int(r['n_total']),
                     'Judge requests': len(events), 'Judge tokens': totals['total_tokens']})
    ordered = ['baseline', 'step1', 'step2']
    indexed = {r['Stage']: r for r in rows}
    monotonic = {metric: all(indexed[a][metric] <= indexed[b][metric]
                            for a, b in zip(ordered, ordered[1:])) for metric in ['WR (%)', 'LC (%)']}
    comparisons = {}
    for left, right in [('step1', 'baseline'), ('step2', 'step1'), ('step2', 'step0'), ('step2', 'bon15')]:
        comparisons[f'{left} - {right}'] = {
            'WR': paired_summary(annotations[left], annotations[right], 'judge_score'),
            'LC': paired_summary(annotations[left], annotations[right], 'glm_preference')}
    smoke = ROOT / 'eval_smoke/usage.jsonl'
    smoke_events = [json.loads(line) for line in smoke.read_text().splitlines()] if smoke.exists() else []
    totals = {'smoke_requests': len(smoke_events),
              'smoke_tokens': sum(e['usage']['total_tokens'] for e in smoke_events),
              'full_stage_requests': sum(v['successful_api_requests'] for v in usage.values()),
              'full_stage_tokens': sum(v['total_tokens'] for v in usage.values())}
    result = {'judge_model': 'qwen3.8-max', 'annotator': 'weighted_qwen3_8_max',
              'rows': rows, 'monotonic_baseline_step1_step2': monotonic,
              'paired_comparisons': comparisons, 'judge_usage': usage, 'usage_totals': totals,
              'uncertainty_note': 'SEs of differences use paired per-instruction scores. LC SEs condition on the fitted GLM; they do not include refitting uncertainty. Exceeding one SE is not a 95% significance test.'}
    (ROOT / 'results_task1.json').write_text(json.dumps(result, indent=2) + '\n')
    df = pd.DataFrame(rows)
    lines = ['# Five-stage Qwen-judged results', '', '> ' + JUDGE_NOTE, '',
             df.to_markdown(index=False, floatfmt='.4f'), '',
             f"Monotonic baseline → step1 → step2: WR **{monotonic['WR (%)']}**, LC **{monotonic['LC (%)']}**.",
             '', '| Comparison | WR Δ (pp) | Paired SE | Δ exceeds SE | LC Δ (pp) | Paired SE | Δ exceeds SE |',
             '|---|---:|---:|---|---:|---:|---|']
    for label, value in comparisons.items():
        w, l = value['WR'], value['LC']
        lines.append(f"| {label} | {w['difference_pp']:.4f} | {w['paired_se_pp']:.4f} | {w['exceeds_one_paired_se']} | {l['difference_pp']:.4f} | {l['paired_se_pp']:.4f} | {l['exceeds_one_paired_se']} |")
    lines += ['', result['uncertainty_note'], '',
              'Lengths are characters, as reported by AlpacaEval. Token totals count successful API requests; '
              'cached judgments are reused across stages. No price estimate is inferred for this endpoint.', '',
              f"Fresh full-run requests: {totals['full_stage_requests']}; tokens: {totals['full_stage_tokens']}. "
              f"Smoke requests: {totals['smoke_requests']}; tokens: {totals['smoke_tokens']}. Full usage: results_task1.json.", '']
    (ROOT / 'results_task1.md').write_text('\n'.join(lines))
    print(df.to_markdown(index=False, floatfmt='.4f'))
    print('PHASE3_ACCEPT_PASS: all five stages have 100 valid judged examples; results_task1.md regenerated.')


if __name__ == '__main__':
    main()
