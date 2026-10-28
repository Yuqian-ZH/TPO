"""Validate measured selections, judge alignment, and artifact isolation."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text())


def parse(folder):
    rows = load(ROOT / folder / 'results.json')
    parsed = {}
    for row in rows:
        queries = set()
        for key, reward in row.items():
            index, query, answer = key.split('<SEP>', 2)
            # The original optimizer may extract an empty tagged candidate.
            # Validate all stored scores; require nonempty selected outputs below.
            assert math.isfinite(reward)
            queries.add(query)
            parsed.setdefault(query, []).append((int(index.replace('INDEX', '')), answer, reward))
        assert len(queries) == 1
    assert len(rows) == len(parsed) == 100
    return parsed


def main():
    expected = set(load(ROOT / 'data/alpaca100.json'))
    assert len(expected) == 100
    tpo, bon = parse('run100'), parse('bon15')
    assert set(tpo) == set(bon) == expected
    diagnostics = {}
    for stage in ['baseline', 'step0', 'step1', 'step2', 'bon15']:
        rows = load(ROOT / f'stages/{stage}.json')
        assert len(rows) == 100 and {r['instruction'] for r in rows} == expected
        for row in rows:
            assert row['output'].strip()
            query = row['instruction']
            items = tpo[query]
            if stage == 'bon15':
                selected = max(bon[query], key=lambda x: x[2])
            elif stage == 'baseline':
                selected = next(x for x in items if x[0] == -1)
            else:
                limit = {'step0': -1, 'step1': 0, 'step2': 1}[stage]
                selected = max((x for x in items if x[0] <= limit), key=lambda x: x[2])
            assert row['output'] == selected[1]
            assert row['generator'] == f'tulu3-8b-sft-{stage}'
        annotations = load(ROOT / f'eval_out/{stage}/annotations.json')
        assert len(annotations) == 100 and {r['instruction'] for r in annotations} == expected
        outputs = {r['instruction']: r['output'] for r in rows}
        for row in annotations:
            assert row['output_2'] == outputs[row['instruction']]
            assert 1 <= float(row['preference']) <= 2
            assert math.isfinite(float(row['glm_preference']))
        diagnostics[stage] = dict(valid_outputs=100, valid_judgments=100,
            outputs_with_residual_tags=sum(any(tag in r['output'] for tag in ['<IMPROVED_VARIABLE>', '</IMPROVED_VARIABLE>']) for r in rows),
            mean_characters=sum(len(r['output']) for r in rows) / 100,
            max_characters=max(len(r['output']) for r in rows))
    for relative in ['tpo_utils.py', 'reward_model.py', 'textgrad-main/textgrad/optimizer/optimizer.py', 'textgrad-main/textgrad/autograd/llm_ops.py']:
        assert (ROOT / 'source/TPO' / relative).read_bytes() == (ROOT.parent / 'TPO' / relative).read_bytes()
    before = load(ROOT / 'tpo_before.sha256.json')
    protected = ROOT.parent / 'TPO'
    after = {str(p.relative_to(protected)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in protected.rglob('*') if p.is_file() and not p.is_symlink()}
    assert before == after
    for p in (ROOT / 'scripts').glob('*.py'):
        ast.parse(p.read_text(), filename=str(p))
    # Exact credential scan; output only paths, never credential values.
    credential = os.environ.get('DASHSCOPE_API_KEY', '').encode()
    matches = [str(p.relative_to(ROOT)) for p in ROOT.rglob('*')
               if p.is_file() and credential and credential in p.read_bytes()]
    assert not matches, f'Credential material found in files: {matches}'
    result = dict(status='PASS', prompts=100, stages=diagnostics,
        empty_cached_candidates={name: sum(not answer.strip() for items in values.values() for i, answer, reward in items)
                                 for name, values in [('tpo', tpo), ('bon15', bon)]},
        original_algorithms_unchanged=True, protected_TPO_unchanged=True,
        protected_file_count=len(before), syntax='PASS',
        exact_credential_scan='PASS' if credential else 'not run; credential not in environment')
    (ROOT / 'audit_results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
