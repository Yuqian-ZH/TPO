"""Phase 2: validate the fixed judge, recording no credentials or headers."""
import json
import os
from pathlib import Path
import stat
import sys

from openai import OpenAI

ROOT = Path(__file__).resolve().parent


def main():
    result = {'phase': 2, 'requested_model': 'qwen3.8-max',
              'api': 'chat.completions', 'temperature': 0, 'max_tokens': 5,
              'requested_logprobs': True, 'top_logprobs': 5,
              'enable_thinking': False}
    try:
        credentials = Path.home() / '.dashscope_env'
        assert stat.S_IMODE(credentials.stat().st_mode) == 0o600
        assert credentials.stat().st_uid == os.getuid()
        assert os.environ.get('JUDGE_MODEL') == 'qwen3.8-max'
        client = OpenAI(api_key=os.environ['DASHSCOPE_API_KEY'],
                        base_url=os.environ['DASHSCOPE_BASE_URL'],
                        timeout=60, max_retries=0)
        raw = client.chat.completions.with_raw_response.create(
            model=os.environ['JUDGE_MODEL'],
            messages=[{'role': 'user', 'content': 'Reply with OK.'}],
            temperature=0, max_tokens=5, logprobs=True, top_logprobs=5,
            extra_body={'enable_thinking': False})
        result['http_status'] = raw.status_code
        response = raw.parse()
        choice = response.choices[0]
        message = choice.message
        result['response_model'] = response.model
        result['short_answer'] = message.content
        result['reasoning_content_present'] = bool(getattr(message, 'reasoning_content', None))
        result['usage'] = response.usage.model_dump() if response.usage else None
        details = getattr(response.usage, 'completion_tokens_details', None)
        result['reasoning_tokens'] = getattr(details, 'reasoning_tokens', None)
        logprobs = choice.logprobs.content if choice.logprobs else None
        result['top_logprobs_populated'] = bool(logprobs and all(t.top_logprobs for t in logprobs))
        assert message.content and message.content.strip(), 'No short answer'
        assert not result['reasoning_content_present'], 'Thinking content returned'
        assert result['reasoning_tokens'] in (None, 0), 'Reasoning tokens returned'
        result['acceptance'] = 'PASS'
    except Exception as exc:
        result['acceptance'] = 'FAIL'
        result['error_type'] = type(exc).__name__
        result['http_status'] = getattr(exc, 'status_code', result.get('http_status'))
        # Exception messages/HTTP bodies may echo input; do not persist them.
    output = json.dumps(result, indent=2) + '\n'
    (ROOT / 'judge_endpoint_check.json').write_text(output)
    (ROOT / 'phase2_endpoint_check.log').write_text(output)
    print(output, end='')
    return 0 if result['acceptance'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
