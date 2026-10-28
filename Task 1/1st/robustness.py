"""CPU-only paired checks on stored RM and judge scores; no new generations."""
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
BOOTSTRAP_SEED = 42
N_RESAMPLES = 10000


def paired(values):
    values = np.asarray(values, dtype=float)
    assert values.shape == (100,) and np.isfinite(values).all()
    indices = np.random.default_rng(BOOTSTRAP_SEED).integers(0, len(values), (N_RESAMPLES, len(values)))
    lo, hi = np.quantile(values[indices].mean(axis=1), [0.025, 0.975])
    return {'n_prompts': len(values), 'mean_difference': float(values.mean()),
            'percent_prompts_improved': float(np.mean(values > 0) * 100),
            'percent_prompts_unchanged': float(np.mean(values == 0) * 100),
            'bootstrap_95_ci': [float(lo), float(hi)],
            'paired_standard_error': float(values.std(ddof=1) / np.sqrt(len(values)))}


def trace_evidence():
    path = ROOT.parent / 'TPO/logs/2026-10-19_19-50-42.jsonl'
    text = path.read_text()
    decoder, position, counts, raw = json.JSONDecoder(), 0, collections.Counter(), 0
    while position < len(text):
        while position < len(text) and text[position].isspace():
            position += 1
        if position == len(text):
            break
        row, position = decoder.raw_decode(text, position)
        counts[row.get('msg')] += 1
        raw += int('optimizer.response' in row)
    return {'trace': str(path.relative_to(ROOT.parent)), 'message_counts': dict(counts),
            'records_with_raw_optimizer_response': raw}


def main():
    reference = json.loads((ROOT / 'data/reference100.json').read_text())
    queries = [r['instruction'] for r in reference]
    raw = json.loads(next((ROOT / 'run100').glob('*.json')).read_text())
    per_query = {q: {-1: [], 0: [], 1: []} for q in queries}
    for row in raw:
        for key, score in row.items():
            iteration, query, answer = key.split('<SEP>', 2)
            per_query[query][int(iteration.replace('INDEX', ''))].append((answer, score))
    assert len(raw) == 100 and all(per_query[q][-1] for q in queries)
    complete = [q for q in queries if all(len(per_query[q][i]) == 5 for i in [-1, 0, 1])]
    assert complete, 'No prompts with all five stored candidates in all rounds'
    full_means, complete_means = {}, {}
    for i, name in [(-1, 'init'), (0, 'iter1'), (1, 'iter2')]:
        full_means[name] = float(np.mean([s for q in queries for _, s in per_query[q][i]]))
        complete_means[name] = float(np.mean([s for q in complete for _, s in per_query[q][i]]))
    stored_summary = json.loads((ROOT / 'stages/rm_summary.json').read_text())
    assert all(abs(full_means[k] - stored_summary['mean_rm_of_all_samples_per_iter'][k]) < 0.000051
               for k in full_means)
    score0 = {q: max(s for _, s in per_query[q][-1]) for q in queries}
    score2 = {q: max(s for items in per_query[q].values() for _, s in items) for q in queries}
    bon = json.loads((ROOT / 'stages/bon15_rm_summary.json').read_text())['selected_rm_by_instruction']
    rm_differences = {
        'step2 - step0': paired([score2[q] - score0[q] for q in queries]),
        'step2 - bon15': paired([score2[q] - bon[q] for q in queries])}
    annotations = {}
    for stage in ['step0', 'step2', 'bon15']:
        rows = json.loads((ROOT / f'eval_out/{stage}/annotations.json').read_text())
        annotations[stage] = {r['instruction']: float(r['preference']) - 1 for r in rows}
        assert set(annotations[stage]) == set(queries)
    judge_differences = {
        f'step2 - {stage}': paired([(annotations['step2'][q] - annotations[stage][q]) * 100 for q in queries])
        for stage in ['step0', 'bon15']}
    outputs = {stage: {r['instruction']: r['output'] for r in json.loads((ROOT / f'stages/{stage}.json').read_text())}
               for stage in ['step0', 'step2']}
    unchanged = sum(outputs['step0'][q] == outputs['step2'][q] for q in queries)
    discarded = {}
    for i, name in [(-1, 'init'), (0, 'iter1'), (1, 'iter2')]:
        stored = sum(len(per_query[q][i]) for q in queries)
        missing = 500 - stored
        discarded[name] = {'requested': 500, 'unique_stored': stored,
                           'missing_tags_plus_duplicate_merges': missing,
                           'dropped_missing_tags': 0 if i == -1 else None,
                           'merged_duplicates': missing if i == -1 else None,
                           'dropped_missing_tags_bounds': [0, 0] if i == -1 else [0, missing],
                           'merged_duplicates_bounds': [missing, missing] if i == -1 else [0, missing]}
    evidence = trace_evidence()
    assert evidence['records_with_raw_optimizer_response'] == 0
    result = {'bootstrap': {'resamples': N_RESAMPLES, 'seed': BOOTSTRAP_SEED,
                            'method': 'Paired prompt resampling with replacement; percentile 95% interval.'},
              'survivorship': {'full_n_prompts': 100, 'complete_case_n_prompts': len(complete),
                               'full_sample_means': full_means, 'complete_case_means': complete_means,
                               'complete_case_instructions': complete,
                               'weighting': 'Mean across all stored candidates in each iteration; complete cases have five in each round.'},
              'rm_paired_differences': rm_differences,
              'judge_paired_differences_pp': judge_differences,
              'judge_comparison_note': 'Paired differences in weighted preferences against the same GPT-4 reference. These are changes in reference-relative win scores, not direct step2-versus-control head-to-head win rates.',
              'step2_identical_to_step0_count': unchanged,
              'discarded_refinements': discarded,
              'discard_identifiability': 'Initial samples bypass response-tag extraction, so the initial deficit is entirely duplicate merging. For refinements the only identifiable total is 500 minus stored unique answers. The official multi-sample optimizer discards malformed tags and then cache_scores merges identical answers, but neither the raw five outputs nor extraction counts are logged. The two components cannot be separated retrospectively; bounds and the exact combined deficit are reported instead.',
              'trace_evidence': evidence}
    (ROOT / 'robustness.json').write_text(json.dumps(result, indent=2) + '\n')
    survival = pd.DataFrame([
        {'Subset': 'All prompts', 'Prompts': 100, **full_means},
        {'Subset': 'All 5 stored in every iteration', 'Prompts': len(complete), **complete_means}])
    comparisons = []
    for kind, records in [('RM', rm_differences), ('Judge WR (pp)', judge_differences)]:
        for name, record in records.items():
            lo, hi = record['bootstrap_95_ci']
            comparisons.append({'Metric': kind, 'Comparison': name, 'Mean Δ': record['mean_difference'],
                                'Improved prompts (%)': record['percent_prompts_improved'],
                                '95% paired CI': f'[{lo:.4f}, {hi:.4f}]'})
    deficit = pd.DataFrame([{'Iteration': k, 'Requested': v['requested'], 'Stored': v['unique_stored'],
                             'Combined deficit': v['missing_tags_plus_duplicate_merges'],
                             'Missing tags': str(v['dropped_missing_tags']) if k == 'init' else 'Not identifiable',
                             'Duplicate merges': str(v['merged_duplicates']) if k == 'init' else 'Not identifiable'}
                            for k, v in discarded.items()])
    lines = ['# Robustness checks', '', survival.to_markdown(index=False, floatfmt='.4f'), '',
             pd.DataFrame(comparisons).to_markdown(index=False, floatfmt='.4f'), '',
             f'Paired bootstrap: {N_RESAMPLES:,} resamples, fixed seed {BOOTSTRAP_SEED}.', '',
             result['judge_comparison_note'], '',
             f'Step2 is byte-for-byte identical to step0 for **{unchanged}/100** prompts.', '',
             deficit.to_markdown(index=False), '', result['discard_identifiability'], '',
             'Trace evidence: 200 optimizer update prompts were logged, but zero raw optimizer responses. '
             'No extra generations were run to fill in missing historical evidence.', '']
    (ROOT / 'robustness.md').write_text('\n'.join(lines))
    print('\n'.join(lines))
    print('PHASE4_ACCEPT_PASS: paired comparisons aligned on 100 prompts; bootstrap and counts saved.')


if __name__ == '__main__':
    main()
