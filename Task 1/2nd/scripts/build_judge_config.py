"""Copy the installed weighted annotator and its exact prompt; configure the env client."""
from importlib.metadata import version
from importlib.util import find_spec
import hashlib
import json
from pathlib import Path
import shutil

import yaml

from task_paths import ROOT
PACKAGE = Path(find_spec('alpaca_eval').origin).parent


def main():
    destination = ROOT / 'judge_config'
    destination.mkdir(exist_ok=True)
    source = PACKAGE / 'evaluators_configs/weighted_alpaca_eval_gpt4_turbo/configs.yaml'
    original = yaml.safe_load(source.read_text())['weighted_alpaca_eval_gpt4_turbo']
    prompt = PACKAGE / 'evaluators_configs' / original['prompt_template']
    shutil.copy2(prompt, destination / 'alpaca_eval_clf.txt')
    adapted = json.loads(json.dumps(original))
    adapted['prompt_template'] = 'judge_config/alpaca_eval_clf.txt'
    adapted['completions_kwargs'].update(
        model_name='qwen3.8-max',
        client_config_path='client_configs.yaml',
        extra_body={'enable_thinking': False})
    assert adapted['completion_parser_kwargs'] == original['completion_parser_kwargs']
    for parameter in ['max_tokens', 'temperature', 'logprobs', 'top_logprobs']:
        assert adapted['completions_kwargs'][parameter] == original['completions_kwargs'][parameter]
    (destination / 'configs.yaml').write_text(yaml.safe_dump({'weighted_qwen3_8_max': adapted}, sort_keys=False))
    client = {'qwen3.8-max': [{'client_class': 'judge_client.DashScopeClient',
                            'api_key_env': 'DASHSCOPE_API_KEY',
                            'base_url_env': 'DASHSCOPE_BASE_URL',
                            'timeout': 120, 'max_retries': 2}]}
    (destination / 'client_configs.yaml').write_text(yaml.safe_dump(client, sort_keys=False))
    provenance = {'alpaca_eval_version': version('alpaca-eval'),
                  'original_annotator': 'weighted_alpaca_eval_gpt4_turbo',
                  'adapted_annotator': 'weighted_qwen3_8_max',
                  'judge_model': 'qwen3.8-max',
                  'source_prompt_sha256': hashlib.sha256(prompt.read_bytes()).hexdigest(),
                  'copied_prompt_sha256': hashlib.sha256((destination / 'alpaca_eval_clf.txt').read_bytes()).hexdigest(),
                  'original_config': original,
                  'client_config_mechanism': 'alpaca_eval.utils.get_all_clients imports client_class and passes YAML kwargs; DashScopeClient resolves the named environment variables at runtime.'}
    (destination / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print('Weighted judge config created; prompt, temperature, and parser match the installed original.')


if __name__ == '__main__':
    main()
