"""File storage (plan 3.9). JSON documents are written atomically (temp file + os.replace), logs are append-only
JSONL. Files are the only source of truth; the dicts held here are a cache rebuilt at start-up.

  <root>/sessions/<sid>/session.json
  <root>/sessions/<sid>/feedback/<fid>.json
  <root>/sessions/<sid>/iterations.jsonl     logging layer, one line per TPO iteration
  <root>/sessions/<sid>/events.jsonl         audit trail of every API action and state change
  <root>/logs/llm_requests.jsonl             Task 2's LLMClient log (credentials redacted)"""
import copy
import datetime
import glob
import json
import os
import secrets
import threading


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def random_id(prefix):
    return f"{prefix}_{secrets.token_hex(4)}"


class Store:
    def __init__(self, root, new_id=random_id):
        self.root = root
        self.lock = threading.RLock()
        self.sessions, self.feedback = {}, {}
        self._new_id = new_id
        os.makedirs(os.path.join(root, "sessions"), exist_ok=True)
        os.makedirs(os.path.join(root, "logs"), exist_ok=True)
        for path in sorted(glob.glob(os.path.join(root, "sessions", "*", "session.json"))):
            with open(path) as f:
                s = json.load(f)
            self.sessions[s["session_id"]] = s
            for fpath in sorted(glob.glob(os.path.join(os.path.dirname(path), "feedback", "*.json"))):
                with open(fpath) as f:
                    fb = json.load(f)
                self.feedback[fb["feedback_id"]] = fb

    # ---------- paths ----------

    def session_dir(self, sid):
        return os.path.join(self.root, "sessions", sid)

    def llm_log_path(self):
        return os.path.join(self.root, "logs", "llm_requests.jsonl")

    # ---------- documents ----------

    def new_id(self, prefix):
        with self.lock:
            while True:
                i = self._new_id(prefix)
                if i not in self.sessions and i not in self.feedback:
                    return i

    def get_session(self, sid):
        """A deep copy: callers change it and hand it back to save_session()."""
        with self.lock:
            s = self.sessions.get(sid)
            return copy.deepcopy(s) if s is not None else None

    def get_feedback(self, fid):
        with self.lock:
            fb = self.feedback.get(fid)
            return copy.deepcopy(fb) if fb is not None else None

    def save_session(self, s):
        with self.lock:
            _write_json(os.path.join(self.session_dir(s["session_id"]), "session.json"), s)
            self.sessions[s["session_id"]] = copy.deepcopy(s)

    def save_feedback(self, fb):
        with self.lock:
            _write_json(os.path.join(self.session_dir(fb["session_id"]), "feedback", f"{fb['feedback_id']}.json"),
                        fb)
            self.feedback[fb["feedback_id"]] = copy.deepcopy(fb)

    def list_sessions(self):
        with self.lock:
            return [copy.deepcopy(self.sessions[k]) for k in sorted(self.sessions)]

    # ---------- logs ----------

    def _append(self, path, rec):
        with self.lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def log_event(self, sid, event, **fields):
        self._append(os.path.join(self.session_dir(sid), "events.jsonl"),
                     {"time": now(), "session_id": sid, "event": event, **fields})

    def log_iteration(self, sid, rec):
        self._append(os.path.join(self.session_dir(sid), "iterations.jsonl"), rec)

    def iterations(self, sid):
        with self.lock:
            return _read_jsonl(os.path.join(self.session_dir(sid), "iterations.jsonl"))

    def events(self, sid):
        with self.lock:
            return _read_jsonl(os.path.join(self.session_dir(sid), "events.jsonl"))
