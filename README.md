# Retry storms: re-implementing the RetryGuard baseline

Course project (Parallel & Distributed Computing, one semester).

**Baseline paper:** *RetryGuard: Preventing Self-Inflicted and Attack-Driven Retry Storms in Cloud
Applications* (Tavori, Bremler-Barr, Levy, Lavi; arXiv:2511.23278).

**Idea of the paper:** when a downstream service stays overloaded for a long time (for example it
scales slower than the caller), retries make things worse: they multiply the load and the cloud bill.
RetryGuard watches the rejection rate and **turns retries off** while the overload lasts, and back on
when it is over. New requests are never blocked.

**What this project does:** we re-implement the idea in a small simulator (instead of AWS/Istio),
compare it with other retry methods, and run benchmarks.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run_all.sh            # about 30 seconds: tests, benchmarks, sweep, figures
```

Or step by step: `python run_benchmarks.py --seeds 20`, `python run_sweep.py --seeds 10`, `python make_plots.py`.
Tests: `python -m pytest -q` (or `python tests/test_sanity.py`).

## Files

| File | What it is |
|---|---|
| `retrysim/engine.py` | The simulator (Service A calls Service B, B has a slow autoscaler) |
| `retrysim/policies.py` | 6 policies: RetryGuard, exp. backoff, jitter, retry budget, circuit breaker, no retries |
| `retrysim/scenarios.py` | 4 load scenarios: stable, mild, heavy, burst |
| `run_benchmarks.py` | Runs all policies x scenarios x 20 seeds -> `results/summary.md`, `raw.csv` |
| `run_sweep.py` | RetryGuard parameter sweep (threshold, interval) -> `results/sweep.csv` |
| `make_plots.py` | Figures in `results/figures/` |
| `tests/test_sanity.py` | Checks that results have the shape the paper predicts |

## The model (short)

* New requests arrive at A as a Poisson process. A sends each one to B. B can serve `mu` req/s
  (token bucket, starts at 100 req/s); anything above that is **rejected**.
* A rejected request may be retried up to 5 times (the policy decides if and when). After that it **fails**.
* B has an **autoscaler**: every 10 s it looks at all attempts it received in the last 30 s
  (**including retries**) and asks for `offered / 0.9` capacity. New capacity arrives after 60 s. Scale-down needs 120 s of low load.
  So a retry storm makes B ask for too much capacity (over-scaling, the "Denial-of-Wallet" in the paper).
* Cost proxies: peak capacity of B, capacity-seconds of B, and total seconds requests spent waiting in A.

Scenarios (B starts at 100 req/s): **stable** 80 req/s; **mild** 80 -> 120 req/s; **heavy** 80 -> 250 req/s;
**burst** +400 req/s for 10 s (DDoS-like).

## Results (20 seeds, mean)

Full tables with standard deviations: `results/summary.md`. Figures: `results/figures/`.

| Scenario | Policy | Retries / request | Latency during overload (s) | Peak capacity of B | Failed |
|---|---|---|---|---|---|
| stable | all | 0 | 0 | 100 | 0 |
| mild | Exp. backoff | 0.31 | 0.52 | 442 | 2.2% |
| mild | **RetryGuard (30 s)** | **0.13** | **0.22** | **386** | 2.4% |
| mild | Retry budget | 0.05 | 0.02 | 179 | 2.3% |
| heavy | Exp. backoff | 0.57 | 1.26 | 1,340 | 8.4% |
| heavy | **RetryGuard (30 s)** | **0.24** | **0.52** | **1,311** | 8.8% |
| heavy | Retry budget | 0.04 | 0.02 | 354 | 9.3% |
| heavy | No retries | 0 | 0 | 278 | 9.9% |
| burst | Exp. backoff | 0.50 | 0.94 | 1,055 | 8.3% |
| burst | **RetryGuard (30 s)** | 0.50 | 0.94 | 1,055 | 8.3% |

### What we see

1. **The paper's problem is reproduced.** With plain retries, B receives about 5x more attempts than real
   requests during heavy overload, and the autoscaler over-provisions B by about 5x (1,340 vs the 278 req/s
   really needed). In the stable scenario retries are harmless.
2. **RetryGuard works, but only after it reacts.** With the paper's 30 s interval it cuts retries by about 58 %
   in mild and heavy overload and also lowers latency. It does **nothing in the burst scenario**, because the
   burst (10 s) is shorter than the detection time (30 s).
3. **The detection interval matters much more than the threshold** (`fig_retryguard_sweep.png`).
   With a 2-5 s interval, peak capacity in the heavy scenario falls from 1,311 to about 320-420 req/s, and
   it also helps in the burst scenario. The threshold (10/20/40 %) only matters in the mild scenario; in
   heavy and burst the rejection rate is far above all three values. This agrees with the paper's claim that the transition is sharp.
4. **In our simulation, a retry budget is cheaper than RetryGuard (30 s)** (354 vs 1,311 req/s peak in heavy).
   This is different from what the paper suggests (the paper says budgets still allow useless retries). The reason in
   our model: the budget limits retries immediately, while RetryGuard needs 30 s to notice, and the autoscaler
   has already counted the retries by then. Possible causes: our autoscaler is simpler than real ones, and the budget
   settings (20 % + 10 retries/s) are Linkerd's defaults. This is worth discussing, not hiding.
5. **Failures are about the same for all retry methods** (8-9 % in heavy): the capacity limit decides this, not the
   retry method. The circuit breaker fails more requests (13.5 %), because it blocks new requests too.

## Limits (be honest in the report)

* This is a simulation, not AWS or Istio, so absolute numbers are **not comparable** with the paper's
  (98 % fewer retries, 3x fewer replicas). Only the shapes can be compared.
* The autoscaler, the token-bucket service and all parameters are our own simplifications.
* We track counts and mean latency, not full latency distributions, so there is no p95/p99.
* RetryGuard here is the binary ON/OFF version (Algorithm 1). The paper also mentions gradual re-enabling
  and recovery probes; they are not implemented.
* The circuit breaker is a simplified extra baseline; the paper does not test one.

## Ideas for the "own contribution" part

* **RetryGuard + retry budget:** retries limited right away by a budget, plus RetryGuard's full stop when overload lasts.
* **Faster / adaptive detection:** shorten the interval automatically when the rejection rate is very high.
* **Gradual re-enabling** (paper's footnote 11) and its effect on oscillation.
* **Attacker test:** a burst pattern timed to the detection interval (the burst scenario already shows the weak spot).
* **Latency distributions** (p95/p99) by tracking individual requests.
