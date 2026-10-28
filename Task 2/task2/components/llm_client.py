"""DashScope (OpenAI-compatible) client with seed derivation, retry policy and redacted request logs."""
import datetime
import hashlib
import json
import os
import time

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

PROTOCOL = "task2_v1"
MODEL = "qwen3.8-max"
RETRY_WAITS = (2, 8)  # 3 attempts in total; only connection failures and rate limits are retried


def derive_seed(case_id, component, run, sample_index):
    payload = f"{PROTOCOL}|{case_id}|{component}|{run}|{sample_index}"
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big") & 0x7FFFFFFF


def _secrets():
    return [v for v in (os.environ.get("DASHSCOPE_API_KEY"), os.environ.get("DASHSCOPE_BASE_URL")) if v]


def redact(text):
    for s in _secrets():
        text = text.replace(s, "<redacted>")
    return text


class LLMClient:
    def __init__(self, log_path, model=MODEL):
        self.model = model
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.client = OpenAI(api_key=os.environ["DASHSCOPE_API_KEY"],
                             base_url=os.environ["DASHSCOPE_BASE_URL"], max_retries=0, timeout=120)

    def chat(self, messages, *, temperature, seed, json_mode=False, max_tokens=None, meta=None):
        """One logical request. Returns a dict with content, parsed JSON (if json_mode) and parse status."""
        params = {"model": self.model, "messages": messages, "temperature": temperature, "seed": seed,
                  "extra_body": {"enable_thinking": False}}
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        if max_tokens:
            params["max_tokens"] = max_tokens
        rec = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), **(meta or {}),
               "params": {k: v for k, v in params.items() if k != "messages"}, "messages": messages,
               "attempts": []}
        resp, t0 = None, time.perf_counter()
        for attempt in range(len(RETRY_WAITS) + 1):
            try:
                resp = self.client.chat.completions.create(**params)
                rec["attempts"].append({"ok": True})
                break
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                rec["attempts"].append({"ok": False, "error": type(e).__name__, "detail": str(e)[:500]})
                if attempt < len(RETRY_WAITS):
                    time.sleep(RETRY_WAITS[attempt])
            except Exception as e:  # not retried
                rec["attempts"].append({"ok": False, "error": type(e).__name__, "detail": str(e)[:1000]})
                break
        rec["latency_s"] = round(time.perf_counter() - t0, 3)
        out = {"ok": resp is not None, "content": None, "parsed": None, "parse_status": "no_response"}
        if resp is not None:
            raw = resp.model_dump()
            rec["raw_response"] = raw
            rec["usage"] = raw.get("usage")
            rec["returned_model"] = raw.get("model")
            msg = resp.choices[0].message
            out["content"] = msg.content
            out["reasoning_present"] = bool(getattr(msg, "reasoning_content", None) or
                                            (raw["choices"][0]["message"].get("reasoning_content")))
            out["returned_model"] = raw.get("model")
            out["usage"] = raw.get("usage")
            out["parse_status"] = "text"
            if json_mode:
                try:
                    out["parsed"] = json.loads(msg.content)
                    out["parse_status"] = "json_ok"
                except (TypeError, json.JSONDecodeError):
                    out["parse_status"] = "json_error"
        rec["parse_status"] = out["parse_status"]
        with open(self.log_path, "a") as f:
            f.write(redact(json.dumps(rec, ensure_ascii=False, default=str)) + "\n")
        out["latency_s"] = rec["latency_s"]
        out["attempts"] = len(rec["attempts"])
        return out
