"""Extract and validate the Best-of-15 control without changing TPO logic."""
import collections
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parent


def main():
    paths = list((ROOT / 'bon15').glob('*.json'))
    assert len(paths) == 1, f'Expected one BoN result file, found {len(paths)}'
    results = json.loads(paths[0].read_text())
    meta = json.loads((ROOT / 'data/alpaca100_meta.json').read_text())
    expected = {r['instruction'] for r in meta}
    by_query = {}
    for result in results:
        for key, reward in result.items():
            iteration, query, answer = key.split('<SEP>', 2)
            assert iteration == 'INDEX-1' and math.isfinite(reward)
            by_query.setdefault(query, []).append((answer, reward))
    assert len(results) == len(by_query) == len(expected) == 100
    assert set(by_query) == expected
    outputs, scores, counts = [], {}, {}
    for row in meta:
        query = row['instruction']
        answer, reward = max(by_query[query], key=lambda x: x[1])
        assert answer.strip()
        assert 1 <= len(by_query[query]) <= 15
        outputs.append({'instruction': query, 'output': answer,
                        'generator': 'tulu3-8b-sft-bon15', 'dataset': row['dataset']})
        scores[query] = reward
        counts[query] = len(by_query[query])
    summary = {
        'n_prompts': 100,
        'requested_candidates_per_prompt': 15,
        'mean_selected_rm_score': statistics.mean(scores.values()),
        'prompts_with_fewer_than_15_stored_samples': sum(n < 15 for n in counts.values()),
        'stored_sample_count_distribution': dict(sorted(collections.Counter(counts.values()).items())),
        'selected_rm_by_instruction': scores,
        'stored_sample_counts_by_instruction': counts,
        'note': 'Identical answers merge within the official score cache; no textual refinement is performed.'
    }
    (ROOT / 'stages/bon15.json').write_text(json.dumps(outputs, indent=2, ensure_ascii=False) + '\n')
    (ROOT / 'stages/bon15_rm_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print('PHASE1_ACCEPT_PASS: 100 matching prompts, all selected answers nonempty.')
    print(json.dumps({k: v for k, v in summary.items() if not k.endswith('_by_instruction')}, indent=2))


if __name__ == '__main__':
    main()
