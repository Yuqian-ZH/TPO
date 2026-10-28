"""Seed derivation for Task 3 and a scripted stand-in for tests. Real requests go through Task 2's LLMClient
(same model, enable_thinking=false, retry policy and redacted logs)."""
import hashlib
import json

PROTOCOL = "task3_v1"


def derive_seed(case_id, config, run, iteration, role, sample):
    payload = f"{PROTOCOL}|{case_id}|{config}|{run}|{iteration}|{role}|{sample}"
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big") & 0x7FFFFFFF


def real_client(log_path):
    from components.llm_client import LLMClient  # Task 2 package, on sys.path via task2_bridge
    return LLMClient(log_path)


class StubLLM:
    """Answers from a script: a callable (messages, meta) -> dict | str, or a list consumed in order."""

    def __init__(self, script):
        self.script = script
        self.calls = []

    def chat(self, messages, *, temperature, seed, json_mode=False, max_tokens=None, meta=None):
        self.calls.append({"messages": messages, "temperature": temperature, "seed": seed, "meta": meta or {}})
        ans = self.script(messages, meta or {}) if callable(self.script) else self.script.pop(0)
        content = ans if isinstance(ans, str) else json.dumps(ans)
        try:
            parsed, status = json.loads(content), "json_ok"
        except json.JSONDecodeError:
            parsed, status = None, "json_error"
        return {"ok": True, "content": content, "parsed": parsed if json_mode else None,
                "parse_status": status if json_mode else "text", "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                "returned_model": "stub", "latency_s": 0.0, "attempts": 1, "reasoning_present": False}
