"""Construct the original Tulu engine and record responses without changing calls."""
import json
import os
from pathlib import Path
import threading
import time
import uuid
import textgrad as tg


def create_engine(root):
    engine = tg.get_engine('server-allenai/Llama-3.1-Tulu-3-8B-SFT',
        base_url=f"http://127.0.0.1:{os.environ.get('TASK1_POLICY_PORT', '8002')}/v1",
        api_key='token-abc123', max_tokens=8192)
    engine.phase = 'unset'
    original = engine.client.chat.completions.create
    lock = threading.Lock()

    def recorded(**request):
        started = time.monotonic()
        response = original(**request)
        row = dict(id=uuid.uuid4().hex, phase=engine.phase, request=request,
            response_model=response.model, response_id=response.id,
            elapsed_seconds=time.monotonic() - started,
            usage=response.usage.model_dump() if response.usage else {},
            choices=[dict(index=c.index, content=c.message.content, finish_reason=c.finish_reason) for c in response.choices])
        with lock, (Path(root) / 'policy_requests.jsonl').open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        return response

    engine.client.chat.completions.create = recorded
    return engine
