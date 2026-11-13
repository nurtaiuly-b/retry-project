"""Sanity tests: do the results have the shape the paper predicts?  Run: python -m pytest -q"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrysim import SCENARIOS, SimConfig, make_policy, run

CFG = SimConfig(duration=300.0)


def avg(scn, pol, seeds=range(3), key="retries_per_request", **kw):
    return float(np.mean([run(SCENARIOS[scn], make_policy(pol, **kw), s, CFG)[0][key] for s in seeds]))


def test_requests_are_conserved():
    m, _ = run(SCENARIOS["heavy"], make_policy("backoff"), 0, CFG)
    # everything that arrived is either finished or still waiting for a retry at the end
    assert m["finished"] <= m["total_requests"]
    assert m["finished"] >= 0.99 * m["total_requests"]


def test_stable_load_has_few_retries_and_retryguard_stays_quiet():
    assert avg("stable", "backoff") < 0.05
    # RetryGuard must not change anything when the system is balanced
    assert abs(avg("stable", "retryguard") - avg("stable", "backoff")) < 0.02


def test_retries_explode_under_overload():
    assert avg("heavy", "backoff") > 20 * max(avg("stable", "backoff"), 1e-3)


def test_retryguard_cuts_retry_storm():
    assert avg("heavy", "retryguard") < 0.5 * avg("heavy", "backoff")
    assert avg("mild", "retryguard") <= avg("mild", "backoff")


def test_retryguard_does_not_hurt_success():
    # some failures are unavoidable (capacity); RetryGuard should not make them much worse
    f_rg = avg("heavy", "retryguard", key="failure_rate")
    f_bo = avg("heavy", "backoff", key="failure_rate")
    assert f_rg <= f_bo + 0.05


def test_no_retry_has_zero_retries():
    assert avg("heavy", "no_retry") == 0.0


if __name__ == "__main__":      # run without pytest:  python tests/test_sanity.py
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)
