"""AlpacaEval client-config class; credentials stay in the process environment."""
import hashlib
import json
import os
from pathlib import Path
import threading

from openai import OpenAI

_LOCK = threading.Lock()


class DashScopeClient(OpenAI):
    def __init__(self, api_key_env='DASHSCOPE_API_KEY',
                 base_url_env='DASHSCOPE_BASE_URL', **kwargs):
        super().__init__(api_key=os.environ[api_key_env],
                         base_url=os.environ[base_url_env], **kwargs)
        original_create = self.chat.completions.create

        def recorded_create(**request):
            assert request['model'] == os.environ['JUDGE_MODEL'] == 'qwen3.8-max'
            assert request.get('extra_body', {}).get('enable_thinking') is False
            assert request['temperature'] == 1 and request['max_tokens'] == 1
            assert request['logprobs'] is True and request['top_logprobs'] == 5
            try:
                response = original_create(**request)
            except Exception as exc:
                # Avoid provider exception bodies that could echo credential material.
                raise RuntimeError(f'Judge request failed: {type(exc).__name__}; '
                                   f'HTTP {getattr(exc, "status_code", "unavailable")}') from None
            usage = response.usage.model_dump() if response.usage else {}
            reasoning = any(bool(getattr(c.message, 'reasoning_content', None))
                            for c in response.choices)
            reasoning_tokens = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
            assert not reasoning and reasoning_tokens in (None, 0), 'Unexpected reasoning in judge response'
            path = os.environ.get('JUDGE_USAGE_PATH')
            if path:
                row = {'model': response.model, 'usage': usage,
                       'reasoning_content_present': reasoning,
                       'reasoning_tokens': reasoning_tokens,
                       'enable_thinking': False, 'temperature': request['temperature'],
                       'max_tokens': request['max_tokens'],
                       'request_sha256': hashlib.sha256(json.dumps(request['messages'], sort_keys=True).encode()).hexdigest()}
                target = Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                with _LOCK, target.open('a') as stream:
                    stream.write(json.dumps(row) + '\n')
            return response

        self.chat.completions.create = recorded_create
