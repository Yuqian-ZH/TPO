"""CPU checks for monotonicity, judge orientation, and paired WR uncertainty.

Run in the aeval environment; reads saved artifacts and writes methodology_checks.json.
No model generation, network access, or judge calls.
"""
import collections
import json
import math
from pathlib import Path
import statistics

import numpy as np
from alpaca_eval import utils
from alpaca_eval.completion_parsers import logprob_parser

from task_paths import ROOT
STAGES = ['baseline', 'step0', 'step1', 'step2', 'bon15']


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    queries = [r['instruction'] for r in read('data/reference100.json')]
    annotations = {s: {r['instruction']: r for r in read(f'eval_out/{s}/annotations.json')}
                   for s in STAGES}
    raw = collections.defaultdict(list)
    for row in read(next((ROOT / 'run100').glob('*.json')).relative_to(ROOT)):
        for key, score in row.items():
            iteration, query, answer = key.split('<SEP>', 2)
            raw[query].append((int(iteration[5:]), answer, score))
    selected = {s: {} for s in STAGES[:4]}
    for q in queries:
        selected['baseline'][q] = next(r[2] for r in raw[q] if r[0] == -1)
        for s, last in [('step0', -1), ('step1', 0), ('step2', 1)]:
            selected[s][q] = max(r[2] for r in raw[q] if r[0] <= last)
    violations = {
        f'{left} -> {right}': sum(selected[left][q] > selected[right][q] for q in queries)
        for left, right in zip(STAGES[:3], STAGES[1:4])}
    assert not any(violations.values())
    means = {}
    for i, name in [(-1, 'init'), (0, 'iter1'), (1, 'iter2')]:
        by_prompt = [[r[2] for r in raw[q] if r[0] == i] for q in queries]
        means[name] = {
            'prompts_with_retained_candidates': sum(bool(v) for v in by_prompt),
            'retained_unique_candidate_mean': statistics.mean(s for v in by_prompt for s in v),
            'equal_prompt_weight_mean': statistics.mean(statistics.mean(v) for v in by_prompt if v)}
    parsing = {}
    for s in STAGES:
        counts = collections.Counter()
        masses = []
        for q in queries:
            row = annotations[s][q]
            completion = row['preference_raw_completion']
            if not isinstance(completion, dict):
                assert row['output_1'] == row['output_2'] and row['preference'] == 1.5
                counts['identical_reference_auto_ties'] += 1
                continue
            flipped = utils.random_seeded_choice(
                seed='is_switched_outputs' + q + '0', choices=[False, True])
            preference = logprob_parser(completion, 'm', ['m', 'M'], is_binarize=False)[0]
            expected = 3 - preference if flipped else preference
            assert math.isclose(expected, row['preference'], abs_tol=1e-9)
            counts['raw_preferences_and_orientation_verified'] += 1
            logps = completion['logprobs']['content'][0]['top_logprobs']
            labels = [t for t in logps if t['token'] in ['m', 'M']]
            counts['both_labels_present_in_top5'] += len(labels) == 2
            masses.append(sum(math.exp(t['logprob']) for t in labels))
        parsing[s] = {**counts, 'min_valid_label_probability_mass': min(masses)}
    indices = np.random.default_rng(42).integers(0, 100, (10000, 100))
    intervals = {}
    for left, right in [('step0', 'baseline'), ('step1', 'baseline'), ('step1', 'step0'),
                        ('step2', 'step1'), ('step2', 'baseline'),
                        ('step2', 'step0'), ('step2', 'bon15'), ('bon15', 'baseline')]:
        differences = np.array([
            (annotations[left][q]['preference'] - annotations[right][q]['preference']) * 100
            for q in queries])
        lo, hi = np.quantile(differences[indices].mean(axis=1), [.025, .975])
        intervals[f'{left} - {right}'] = {
            'WR_difference_pp': float(differences.mean()), 'paired_95_percentile_CI_pp': [float(lo), float(hi)]}
    result = {
        'selected_stored_RM_monotonicity_violations': violations,
        'candidate_reward_means': means, 'judge_parsing': parsing,
        'WR_paired_comparisons': intervals,
        'bootstrap': {'unit': 'prompt', 'resamples': 10000, 'seed': 42,
                      'limits': 'Conditional on saved generations and judge outputs; does not include repeat-run variability.'},
        'LC_uncertainty': 'Existing SEs use fitted per-prompt predictions and omit GLM-refitting uncertainty; descriptive only.'}
    (ROOT / 'methodology_checks.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
