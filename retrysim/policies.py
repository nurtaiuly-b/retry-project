"""Retry policies. Every policy answers four questions for the engine:

  blocking()        -> should ALL calls to B fail fast right now? (circuit breaker only)
  allow(n, attempt) -> of n rejected requests, how many may retry?
  schedule(...)     -> when do the allowed retries go out again?
  observe(...)      -> look at what happened this step (used by controllers)

Policies work on COUNTS of requests (not single requests) so the simulation is fast.
"""
from __future__ import annotations

import math

import numpy as np


class Policy:
    name = "base"
    label = "base"

    def reset(self, cfg):
        self.cfg = cfg

    def on_new(self, n: int, dt: float):
        pass

    def blocking(self) -> bool:
        return False

    def allow(self, n: int, attempt: int) -> int:
        return n

    def schedule(self, attempt: int, n: int, rng, dt: float):
        """Return a list of (delay_in_steps, count)."""
        return [(1, n)]

    def observe(self, offered: int, rejected: int, dt: float):
        pass


class NoRetry(Policy):
    name = "no_retry"
    label = "No retries"

    def allow(self, n, attempt):
        return 0


class ExponentialBackoff(Policy):
    """Wait base * 2^(attempt-1) seconds before each retry (0.1, 0.2, 0.4, ... capped)."""

    name = "backoff"
    label = "Exp. backoff"

    def __init__(self, base_s=0.1, cap_s=5.0):
        self.base_s, self.cap_s = base_s, cap_s

    def _delay_s(self, attempt):
        return min(self.cap_s, self.base_s * 2 ** (attempt - 1))

    def schedule(self, attempt, n, rng, dt):
        return [(max(1, math.ceil(self._delay_s(attempt) / dt)), n)]


class BackoffWithJitter(ExponentialBackoff):
    """'Full jitter': wait a random time in [0, base * 2^(attempt-1)]."""

    name = "jitter"
    label = "Backoff + jitter"

    def schedule(self, attempt, n, rng, dt):
        d = max(1, math.ceil(self._delay_s(attempt) / dt))
        counts = rng.multinomial(n, np.full(d, 1.0 / d))
        return [(j + 1, int(c)) for j, c in enumerate(counts) if c > 0]


class RetryBudget(ExponentialBackoff):
    """Linkerd-style retry budget: retries may add at most `ratio` extra load
    (plus `min_per_s` retries/s), measured with a token bucket."""

    name = "retry_budget"
    label = "Retry budget"

    def __init__(self, ratio=0.2, min_per_s=10.0, max_tokens=300.0, **kw):
        super().__init__(**kw)
        self.ratio, self.min_per_s, self.max_tokens = ratio, min_per_s, max_tokens

    def reset(self, cfg):
        super().reset(cfg)
        self.tokens = self.max_tokens

    def on_new(self, n, dt):
        self.tokens = min(self.max_tokens, self.tokens + self.ratio * n + self.min_per_s * dt)

    def allow(self, n, attempt):
        a = int(min(n, math.floor(self.tokens)))
        self.tokens -= a
        return a


class RetryGuard(ExponentialBackoff):
    """Rejection-based productive-retry controller (Algorithm 1 of the paper).

    Every `sample_s` seconds we measure the rejection rate of calls to B.
    If it stays above `threshold` for `interval_s` seconds -> retries OFF.
    If it stays below `threshold` for `interval_s` seconds -> retries ON.
    New (first) requests are never touched.
    """

    name = "retryguard"
    label = "RetryGuard"

    def __init__(self, threshold=0.20, interval_s=30.0, sample_s=1.0, **kw):
        super().__init__(**kw)
        self.threshold, self.interval_s, self.sample_s = threshold, interval_s, sample_s

    def reset(self, cfg):
        super().reset(cfg)
        self.retries_on = True
        self.low = self.high = 0
        self._off = self._rej = 0
        self._t = 0.0
        self.need = max(1, int(round(self.interval_s / self.sample_s)))

    def allow(self, n, attempt):
        return n if self.retries_on else 0

    def observe(self, offered, rejected, dt):
        self._off += offered
        self._rej += rejected
        self._t += dt
        if self._t + 1e-9 < self.sample_s:
            return
        rate = self._rej / self._off if self._off > 0 else 0.0
        self._off = self._rej = 0
        self._t = 0.0
        # --- Algorithm 1 ---
        if rate < self.threshold:
            self.low += 1
            self.high = 0
        elif rate > self.threshold:
            self.high += 1
            self.low = 0
        else:
            self.low = self.high = 0
        if self.low >= self.need:
            self.retries_on = True
        elif self.high >= self.need:
            self.retries_on = False


class CircuitBreaker(ExponentialBackoff):
    """Simplified circuit breaker (extra baseline, NOT tested in the paper).

    Opens when the rejection rate is above `threshold` for `trip_s` seconds.
    While open, ALL calls to B (new requests and retries) fail fast for `open_s` seconds.
    """

    name = "circuit_breaker"
    label = "Circuit breaker"

    def __init__(self, threshold=0.5, trip_s=5.0, open_s=10.0, sample_s=1.0, **kw):
        super().__init__(**kw)
        self.threshold, self.trip_s, self.open_s, self.sample_s = threshold, trip_s, open_s, sample_s

    def reset(self, cfg):
        super().reset(cfg)
        self.is_open = False
        self.timer = 0.0
        self.high = 0
        self._off = self._rej = 0
        self._t = 0.0
        self.need = max(1, int(round(self.trip_s / self.sample_s)))

    def blocking(self):
        return self.is_open

    def observe(self, offered, rejected, dt):
        if self.is_open:
            self.timer -= dt
            if self.timer <= 0:
                self.is_open = False
                self.high = 0
            return
        self._off += offered
        self._rej += rejected
        self._t += dt
        if self._t + 1e-9 < self.sample_s:
            return
        rate = self._rej / self._off if self._off > 0 else 0.0
        self._off = self._rej = 0
        self._t = 0.0
        self.high = self.high + 1 if rate > self.threshold else 0
        if self.high >= self.need:
            self.is_open = True
            self.timer = self.open_s


# name -> factory (fresh object per run). Order = plotting order.
POLICIES = {
    "retryguard": RetryGuard,
    "backoff": ExponentialBackoff,
    "jitter": BackoffWithJitter,
    "retry_budget": RetryBudget,
    "circuit_breaker": CircuitBreaker,
    "no_retry": NoRetry,
}


def make_policy(name: str, **kwargs) -> Policy:
    return POLICIES[name](**kwargs)
