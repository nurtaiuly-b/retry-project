"""Simulation engine: Service A (caller) -> Service B (slow-to-scale callee).

Model (simple on purpose, easy to explain to a teacher):

* Time moves in small steps (dt = 0.1 s).
* Each step, Poisson(lambda(t) * dt) NEW requests arrive at Service A.
* Service B is a token bucket: it gains mu * dt tokens per step (mu = capacity in
  req/s) and can store at most `bucket_s` seconds of capacity. Every attempt that
  reaches B needs one token; attempts without a token are REJECTED.
* A rejected request may be retried (the policy decides if and when), at most
  `max_retries` times. After that it FAILS.
* B has a slow autoscaler (like the paper's DynamoDB / Reviews service). Every
  `eval_every_s` it looks at the attempts offered to it in the last `window_s`
  (INCLUDING retries) and asks for capacity = offered / target_util. New capacity
  arrives only after `provision_delay_s`. Scale-down is slow (`scale_down_after_s`).
  Because retries inflate "offered", retry storms cause OVER-SCALING (= wasted money).

We track counts per attempt number instead of single requests, so a run takes ~1 s.
Latency of a request = (time it finishes) - (time it arrived), so back-off waits count.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimConfig:
    dt: float = 0.1               # step length (s)
    duration: float = 500.0       # simulated time (s)
    mu0: float = 100.0            # starting capacity of B (req/s)
    bucket_s: float = 0.5         # burst tolerance of B, in seconds of capacity
    max_retries: int = 5          # retries per request (Istio allows up to 5)
    # autoscaler of Service B
    eval_every_s: float = 10.0
    window_s: float = 30.0
    target_util: float = 0.9
    provision_delay_s: float = 60.0
    scale_down_after_s: float = 120.0
    # window used for the 'during overload' latency metric (requests that FINISH inside it)
    event_start_s: float = 30.0
    event_len_s: float = 120.0


def _clean(x: float) -> float:
    """Remove float rounding noise (e.g. -1e-18) from sums of latencies."""
    return 0.0 if abs(x) < 1e-9 else float(x)


def run(scenario, policy, seed: int = 0, cfg: SimConfig | None = None):
    """Run one simulation. Returns (metrics: dict, timeseries: dict of 1-second arrays)."""
    cfg = cfg or SimConfig()
    rng = np.random.default_rng(seed)
    policy.reset(cfg)

    K = cfg.max_retries
    steps = int(round(cfg.duration / cfg.dt))
    spb = int(round(1.0 / cfg.dt))                      # steps per second
    win_steps = int(round(cfg.window_s / cfg.dt))
    eval_steps = int(round(cfg.eval_every_s / cfg.dt))
    delay_steps = int(round(cfg.provision_delay_s / cfg.dt))

    mu = cfg.mu0
    latest_target = cfg.mu0
    pending_scale: list[tuple[int, float]] = []
    low_since = None
    tokens = mu * cfg.bucket_s
    pending: dict[int, list] = {}   # step -> [counts per attempt, sum of origin times per attempt]

    ts_off = np.zeros(steps)
    ts_retry = np.zeros(steps)
    ts_rej = np.zeros(steps)
    ts_mu = np.zeros(steps)
    ts_on = np.zeros(steps)

    total_new = 0
    succeeded = 0
    failed = 0
    lat_steps = 0.0
    ev_lo = int(round(cfg.event_start_s / cfg.dt))
    ev_hi = ev_lo + int(round(cfg.event_len_s / cfg.dt))
    ev_cnt = 0
    ev_lat = 0.0
    attempts = 0
    retry_attempts = 0
    cap_seconds = 0.0

    for s in range(steps):
        t = s * cfg.dt

        # 1) capacity that finished provisioning
        while pending_scale and pending_scale[0][0] <= s:
            cap = pending_scale.pop(0)[1]
            if cap > mu:
                mu = cap

        # 2) arrivals: new requests + retries that are due now
        new = int(rng.poisson(scenario.rate(t) * cfg.dt))
        total_new += new
        policy.on_new(new, cfg.dt)
        n = np.zeros(K + 1, dtype=np.int64)
        so = np.zeros(K + 1)          # sum of the original arrival STEP numbers of the requests in n
        n[0] = new
        so[0] = new * s
        due = pending.pop(s, None)
        if due is not None:
            n += due[0]
            so += due[1]

        offered = 0
        rejected = 0
        fin_cnt = 0
        fin_lat = 0.0     # latency in steps, summed over requests finishing now
        tokens = min(tokens + mu * cfg.dt, max(mu * cfg.bucket_s, 1.0))
        total_here = int(n.sum())

        if total_here > 0:
            if policy.blocking():
                # circuit breaker is open: everything fails immediately
                failed += total_here
                fin_cnt += total_here
                fin_lat += total_here * s - so.sum()
            else:
                offered = total_here
                attempts += offered
                retry_attempts += offered - int(n[0])
                take = min(offered, int(tokens))
                if take >= offered:
                    acc = n.copy()
                elif take <= 0:
                    acc = np.zeros_like(n)
                else:
                    acc = rng.multivariate_hypergeometric(n, take)
                tokens -= take

                frac = np.divide(acc, n, out=np.zeros(K + 1), where=n > 0)
                so_acc = so * frac
                n_acc = int(acc.sum())
                succeeded += n_acc
                fin_cnt += n_acc
                fin_lat += n_acc * s - so_acc.sum()

                rej = n - acc
                so_rej = so - so_acc
                rejected = int(rej.sum())
                for i in range(K + 1):
                    r = int(rej[i])
                    if r == 0:
                        continue
                    mean_origin = so_rej[i] / r
                    allowed = policy.allow(r, i + 1) if i < K else 0
                    allowed = int(min(max(allowed, 0), r))
                    denied = r - allowed
                    if denied:
                        failed += denied
                        fin_cnt += denied
                        fin_lat += denied * (s - mean_origin)
                    if allowed:
                        for d, c in policy.schedule(i + 1, allowed, rng, cfg.dt):
                            if c <= 0:
                                continue
                            s2 = s + max(1, int(d))
                            slot = pending.get(s2)
                            if slot is None:
                                slot = [np.zeros(K + 1, dtype=np.int64), np.zeros(K + 1)]
                                pending[s2] = slot
                            slot[0][i + 1] += c
                            slot[1][i + 1] += c * mean_origin

        lat_steps += fin_lat
        if ev_lo <= s < ev_hi:
            ev_cnt += fin_cnt
            ev_lat += fin_lat

        policy.observe(offered, rejected, cfg.dt)

        # 3) autoscaler of B
        ts_off[s] = offered
        if s > 0 and s % eval_steps == 0:
            lo = max(0, s - win_steps)
            avg = ts_off[lo:s].sum() / ((s - lo) * cfg.dt)
            desired = max(cfg.mu0, avg / cfg.target_util)
            if desired > latest_target * 1.05:
                pending_scale.append((s + delay_steps, desired))
                latest_target = desired
                low_since = None
            elif not pending_scale and desired < mu * 0.95:
                if low_since is None:
                    low_since = t
                elif t - low_since >= cfg.scale_down_after_s:
                    mu = desired
                    latest_target = desired
                    low_since = None
            else:
                low_since = None

        cap_seconds += mu * cfg.dt
        ts_retry[s] = (offered - int(n[0])) if total_here > 0 and not policy.blocking() else 0
        ts_rej[s] = rejected
        ts_mu[s] = mu
        ts_on[s] = 1.0 if getattr(policy, "retries_on", True) and not getattr(policy, "is_open", False) else 0.0

    finished = succeeded + failed
    lat_sum = lat_steps * cfg.dt
    metrics = {
        "total_requests": total_new,
        "finished": finished,
        "succeeded": succeeded,
        "failed": failed,
        "failure_rate": failed / finished if finished else 0.0,
        "retry_attempts": retry_attempts,
        "retries_per_request": retry_attempts / total_new if total_new else 0.0,
        "total_attempts": attempts,
        "avg_latency_s": _clean(lat_sum / finished) if finished else 0.0,
        "avg_latency_event_s": _clean(ev_lat * cfg.dt / ev_cnt) if ev_cnt else 0.0,
        "wait_seconds_billed": _clean(lat_sum),               # proxy for Service A (Lambda-like) billing
        "capacity_seconds": cap_seconds,              # proxy for Service B (DB / replicas) billing
        "peak_capacity": float(ts_mu.max()),
        "peak_retries_per_s": float(ts_retry.reshape(-1, spb).sum(axis=1).max()),
    }
    series = {
        "offered_per_s": ts_off.reshape(-1, spb).sum(axis=1),
        "retries_per_s": ts_retry.reshape(-1, spb).sum(axis=1),
        "rejected_per_s": ts_rej.reshape(-1, spb).sum(axis=1),
        "capacity": ts_mu.reshape(-1, spb).mean(axis=1),
        "retries_on": ts_on.reshape(-1, spb).mean(axis=1),
    }
    return metrics, series
