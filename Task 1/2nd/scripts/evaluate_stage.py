"""Run AlpacaEval with the fixed Qwen annotator and correct benchmark slice indices."""
import argparse
import hashlib
import json
import logging
import math
import os
from pathlib import Path

import pandas as pd

from task_paths import ROOT, PACKAGE_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True, choices=['baseline', 'step0', 'step1', 'step2', 'bon15'])
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--stages-dir', type=Path, default=ROOT / 'stages')
    parser.add_argument('--reference', type=Path, default=ROOT / 'data/reference100.json')
    args = parser.parse_args()
    assert os.environ.get('JUDGE_MODEL') == 'qwen3.8-max'
    assert os.environ.get('DASHSCOPE_API_KEY') and os.environ.get('DASHSCOPE_BASE_URL')
    # Imports follow credential loading. No client options containing key values are logged.
    from alpaca_eval import evaluate
    from alpaca_eval.metrics import get_length_controlled_winrate
    from alpaca_eval.metrics import glm_winrate

    # Use the exact saved calibration without a fresh Hugging Face download.
    calibration = PACKAGE_DIR / 'judge_config/df_gamed.csv'
    provenance = json.loads((PACKAGE_DIR / 'judge_config/calibration_provenance.json').read_text())
    assert hashlib.sha256(calibration.read_bytes()).hexdigest() == provenance['sha256']

    def local_calibration(**kwargs):
        assert kwargs['repo_id'] == 'tatsu-lab/alpaca_eval' and kwargs['filename'] == 'df_gamed.csv'
        return str(calibration)

    glm_winrate.hf_hub_download = local_calibration

    logging.basicConfig(level=logging.INFO)
    reference = json.loads(args.reference.read_text())
    ids = json.loads((ROOT / 'data/slice_ids.json').read_text())
    index_for_instruction = {r['instruction']: i for r, i in zip(reference, ids)}
    assert len(index_for_instruction) == 100
    outputs = json.loads((args.stages_dir / f'{args.stage}.json').read_text())
    assert len(outputs) == 100 and {r['instruction'] for r in outputs} == set(index_for_instruction)
    if args.smoke:
        outputs = outputs[:5]
        queries = {r['instruction'] for r in outputs}
        reference = [r for r in reference if r['instruction'] in queries]
    output_dir = ROOT / ('eval_smoke' if args.smoke else f'eval_out/{args.stage}')
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ['JUDGE_USAGE_PATH'] = str(output_dir / 'usage.jsonl')
    # AlpacaEval resolves prompts from the config parent; client YAML uses the cwd.
    config_dir = ROOT / 'judge_config'
    os.chdir(config_dir)

    def indexed_metric(annotations, **kwargs):
        # The standard GLM reads original benchmark IDs from the DataFrame index.
        # A sliced dataset's row positions (0..99) are not those IDs.
        frame = pd.DataFrame(annotations)
        frame.index = [index_for_instruction[q] for q in frame['instruction']]
        frame.index.name = None
        metrics = get_length_controlled_winrate(
            frame, save_weights_dir=output_dir / 'glm_weights', **kwargs)
        if isinstance(annotations, list):
            for row, preference in zip(annotations, frame['glm_preference']):
                row['glm_preference'] = float(preference)
                row['benchmark_index'] = index_for_instruction[row['instruction']]
        return metrics

    # Smoke checks parsing only; a five-example LC fit is not a meaningful acceptance test.
    options = dict(fn_metric='get_winrate', sort_by='win_rate') if args.smoke else dict(fn_metric=indexed_metric)
    leaderboard, annotations = evaluate(
        model_outputs=outputs, reference_outputs=reference,
        annotators_config=ROOT / 'judge_config/configs.yaml',
        base_dir=config_dir,
        output_path=output_dir, precomputed_leaderboard=None,
        is_cache_leaderboard=False, is_return_instead_of_print=True,
        other_input_keys_to_keep=['generator_1', 'generator_2', 'dataset'],
        **options)
    records = annotations.to_dict('records') if isinstance(annotations, pd.DataFrame) else annotations
    expected = 5 if args.smoke else 100
    assert len(records) == expected
    assert all(math.isfinite(float(r['preference'])) and 1 <= r['preference'] <= 2 for r in records)
    assert any(abs(r['preference'] - 1.5) > 1e-8 for r in records), 'All preferences are ties'
    assert {r['instruction'] for r in records} == {r['instruction'] for r in outputs}
    print(leaderboard.to_markdown())
    print(f'PHASE3_{"SMOKE" if args.smoke else args.stage.upper()}_PASS: {expected} valid judged examples.')


if __name__ == '__main__':
    main()
