import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()


def test_frozen_files_unchanged():
    rec = json.load(open(os.path.join(ROOT, "FROZEN.json")))
    assert sha256(rec["instance"]["file"]) == rec["instance"]["sha256"]
    assert sha256(rec["test_cases"]["file"]) == rec["test_cases"]["sha256"]
