import json
import os

import pytest

import run_experiment as rx
import stats
from tpo.components import ReferenceComponents
from tpo.llm import StubLLM

from conftest import FIX_STOPS, HIGH, LOW, NO_EFFECT, synthetic_case


def test_runner_is_resumable(base, tmp_path):
    cases = [synthetic_case("X1"), synthetic_case("X2", complaint="Vehicle 2 stops at too many customers.")]
    locs = {"X1": {"first": HIGH, "clarified": HIGH}, "X2": {"first": LOW, "clarified": HIGH}}
    llms = []

    def factory(out_dir, base):
        llm = StubLLM(lambda m, meta: {"choice": 1} if meta["role"] == "select" else
                      (FIX_STOPS if meta["iteration"] == 2 else NO_EFFECT))
        llms.append(llm)
        return ReferenceComponents(base, locs), llm

    configs = ["A0B0C0", "A1B1C1", "S2"]
    rx.run_all(cases, base, configs, [1, 2], str(tmp_path), factory, rx.Settings(tie_diagnostic=False), log=lambda *_: None)
    files = sorted(os.listdir(tmp_path / "trials" / "A1B1C1"))
    assert files == ["X1__r1.json", "X1__r2.json", "X2__r1.json", "X2__r2.json"]
    loc = json.loads((tmp_path / "localization" / "X2__r1.json").read_text())
    assert loc["asked"] and loc["final"]["confidence"] == "high"
    first_calls = len(llms[0].calls)
    assert first_calls > 0
    rx.run_all(cases, base, configs, [1, 2], str(tmp_path), factory, rx.Settings(tie_diagnostic=False), log=lambda *_: None)
    assert len(llms[1].calls) == 0                     # everything already on disk
    trials = [json.loads(p.read_text()) for p in sorted((tmp_path / "trials").rglob("*.json"))]
    assert len(trials) == 12 and all(t["converged_at"] == 2 for t in trials)
    s = stats.summarize(trials, B=200)
    assert s["configs"]["A0B0C0"]["rate_mean_std_over_runs"] == {"mean": 1.0, "std": 0.0}
    assert s["configs"]["A0B0C0"]["cumulative_by_iteration"] == [0.0, 1.0, 1.0]
    assert s["configs"]["A1B1C1"]["llm_calls_mean"] == 8          # 2 iterations x (3 proposals + 1 selection)


def test_test_cases_need_frozen_protocol(tmp_path):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps({"cases": [{"id": "T1", "split": "test"}]}))
    with pytest.raises(SystemExit):
        rx.require_protocol_for_test(str(p), rx.load_cases(str(p)))
    rx.require_protocol_for_test(str(p), [{"id": "D1", "split": "dev"}])   # dev cases are fine


def test_wilson_and_mcnemar():
    assert stats.wilson(5, 10) == [0.2366, 0.7634]
    assert stats.wilson(0, 30)[0] == 0.0
    r = stats.mcnemar_exact([(True, False)] * 6 + [(False, True)] * 1 + [(True, True)] * 3)
    assert r == {"first_only": 6, "second_only": 1, "p_value": 0.125}


def fake_trials(rule, cases=10, runs=3):
    out = []
    for g in stats.MAIN:
        for c in range(cases):
            for r in range(1, runs + 1):
                ok = rule(g, c, r)
                out.append({"config": g, "case_id": f"T{c}", "run": r, "converged": ok, "converged_at": 1 if ok else None,
                            "outcome": "converged" if ok else "not_converged", "iterations": []})
    return out


def test_effects_and_verdict_clear():
    trials = fake_trials(lambda g, c, r: stats.level(g, "B") == 1)
    boot = stats.cluster_bootstrap(trials, B=500)
    assert boot["main_B"]["estimate"] == 1.0 and boot["main_A"]["estimate"] == 0.0
    assert boot["interaction_AB"]["estimate"] == 0.0
    assert stats.verdict_rule(boot)["mechanism"] == "B"


def test_effects_and_verdict_undetermined():
    trials = fake_trials(lambda g, c, r: (c + r) % 2 == 0)
    boot = stats.cluster_bootstrap(trials, B=500)
    assert all(abs(boot[f"main_{f}"]["estimate"]) < 1e-9 for f in "ABC")
    assert stats.verdict_rule(boot)["finding"] == "undetermined"


def test_rates_mean_std_over_runs():
    trials = fake_trials(lambda g, c, r: c < 2 + r)       # runs converge 3, 4, 5 of 10 cases
    t = stats.config_table(trials, "A0B0C0")
    assert t["rate_per_run"] == {"1": 0.3, "2": 0.4, "3": 0.5}
    assert t["rate_mean_std_over_runs"] == {"mean": 0.4, "std": 0.1}
    assert t["cases_converged_all_runs"] == 3
