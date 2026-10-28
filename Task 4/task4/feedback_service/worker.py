"""Trigger mechanism (plan 3.6): a FIFO job queue drained by one engine thread.

Every job that touches Gurobi or the LLM runs on that thread: Task 2's model.py shares one Gurobi environment
per process and Task 3's counterfactual_v2 keeps resident models, neither of which is thread-safe."""
import queue
import threading
import traceback


class Job:
    def __init__(self, fn, name):
        self.fn, self.name = fn, name
        self.done = threading.Event()
        self.result = self.error = None


class EngineWorker:
    def __init__(self):
        self.q = queue.Queue()
        self.thread = None
        self.ident = None

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, name="tpo-engine", daemon=True)
            self.thread.start()

    def stop(self, timeout=None):
        if self.thread is not None and self.thread.is_alive():
            self.q.put(None)
            self.thread.join(timeout)
        self.thread = None

    def submit(self, fn, name):
        job = Job(fn, name)
        self.q.put(job)
        return job

    def pending(self):
        return self.q.qsize()

    def _run(self):
        self.ident = threading.get_ident()
        while True:
            job = self.q.get()
            if job is None:
                return
            try:
                job.result = job.fn()
            except Exception as e:  # last resort; service jobs record their own failures
                job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=5)}"
            finally:
                job.done.set()


class LLMUnavailable(RuntimeError):
    """A request got no response (network error, 403, ...). Task 2's client reports this as an empty result
    instead of raising, which would otherwise look like low confidence or a rejected proposal."""


class CountingLLM:
    """Wraps the LLM client given to the components and the TPO loop; counts requests, tokens, latency and
    transport failures since the last reset()."""

    def __init__(self, inner):
        self.inner = inner
        self.reset()

    def reset(self):
        self.calls = self.failures = self.prompt_tokens = self.completion_tokens = 0
        self.latency_s = 0.0

    def chat(self, messages, **kw):
        out = self.inner.chat(messages, **kw)
        self.calls += 1
        if not out.get("ok", True):
            self.failures += 1
        usage = out.get("usage") or {}
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.completion_tokens += usage.get("completion_tokens") or 0
        self.latency_s += out.get("latency_s") or 0.0
        return out

    def snapshot(self):
        return {"requests": self.calls, "failed_requests": self.failures, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "llm_latency_s": round(self.latency_s, 3)}

    def raise_if_failed(self, where):
        if self.failures:
            raise LLMUnavailable(f"{self.failures} of {self.calls} LLM requests got no response during {where}")
