"""Load scenarios. Service B starts with capacity mu0 = 100 req/s (see SimConfig).

Each scenario gives the NEW-request arrival rate lambda(t) in req/s.
rho = lambda / mu0 is the load relative to Service B's starting capacity.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    rate: Callable[[float], float]


SCENARIOS = {
    "stable": Scenario(
        "stable",
        "Balanced system: 80 req/s into capacity 100 (rho = 0.8). Retries should be harmless.",
        lambda t: 80.0,
    ),
    "mild": Scenario(
        "mild",
        "Mild overload: load jumps 80 -> 120 req/s at t=30s (rho = 1.2). B scales late.",
        lambda t: 80.0 if t < 30 else 120.0,
    ),
    "heavy": Scenario(
        "heavy",
        "Heavy overload: load jumps 80 -> 250 req/s at t=30s (rho = 2.5). B scales late.",
        lambda t: 80.0 if t < 30 else 250.0,
    ),
    "burst": Scenario(
        "burst",
        "Short DDoS-like burst: +400 req/s for 10s at t=30s, then back to 80 req/s.",
        lambda t: 480.0 if 30 <= t < 40 else 80.0,
    ),
}
