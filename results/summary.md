# Benchmark summary (20 seeds per cell, mean ± std)

## stable
Balanced system: 80 req/s into capacity 100 (rho = 0.8). Retries should be harmless.

| Policy | Retries / request | Latency during overload (s) | Latency, whole run (s) | Failed requests (fraction) | Peak capacity of B (req/s) | B capacity-seconds (cost proxy) |
|---|---|---|---|---|---|---|
| RetryGuard | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |
| Exp. backoff | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |
| Backoff + jitter | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |
| Retry budget | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |
| Circuit breaker | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |
| No retries | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0 ± 0 | 100 ± 0 | 50,000 ± 0 |

## mild
Mild overload: load jumps 80 -> 120 req/s at t=30s (rho = 1.2). B scales late.

| Policy | Retries / request | Latency during overload (s) | Latency, whole run (s) | Failed requests (fraction) | Peak capacity of B (req/s) | B capacity-seconds (cost proxy) |
|---|---|---|---|---|---|---|
| RetryGuard | 0.128 ± 0.0077 | 0.215 ± 0.019 | 0.0527 ± 0.0045 | 0.0235 ± 0.0015 | 386 ± 19 | 95,469 ± 2,507 |
| Exp. backoff | 0.306 ± 0.011 | 0.524 ± 0.022 | 0.128 ± 0.0062 | 0.0218 ± 0.0015 | 442 ± 13 | 106,532 ± 3,242 |
| Backoff + jitter | 0.303 ± 0.0084 | 0.322 ± 0.011 | 0.0791 ± 0.0027 | 0.0219 ± 0.0011 | 436 ± 14 | 105,756 ± 3,918 |
| Retry budget | 0.0454 ± 0.0017 | 0.0247 ± 0.0013 | 0.00605 ± 0.00032 | 0.023 ± 0.0012 | 179 ± 3 | 68,907 ± 632 |
| Circuit breaker | 0.0727 ± 0.01 | 0.109 ± 0.015 | 0.0268 ± 0.0037 | 0.0923 ± 0.0048 | 151 ± 15 | 66,095 ± 1,905 |
| No retries | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0.0268 ± 0.0013 | 135 ± 2.5 | 63,077 ± 724 |

## heavy
Heavy overload: load jumps 80 -> 250 req/s at t=30s (rho = 2.5). B scales late.

| Policy | Retries / request | Latency during overload (s) | Latency, whole run (s) | Failed requests (fraction) | Peak capacity of B (req/s) | B capacity-seconds (cost proxy) |
|---|---|---|---|---|---|---|
| RetryGuard | 0.237 ± 0.0035 | 0.519 ± 0.0081 | 0.13 ± 0.0021 | 0.0875 ± 0.00081 | 1,311 ± 18 | 252,872 ± 2,191 |
| Exp. backoff | 0.566 ± 0.0053 | 1.26 ± 0.0099 | 0.315 ± 0.0033 | 0.0839 ± 0.00093 | 1,340 ± 31 | 260,976 ± 8,937 |
| Backoff + jitter | 0.567 ± 0.0054 | 0.744 ± 0.0078 | 0.186 ± 0.0021 | 0.0855 ± 0.0011 | 1,344 ± 28 | 263,208 ± 14,295 |
| Retry budget | 0.0425 ± 0.00017 | 0.018 ± 0.00012 | 0.00452 ± 2.4e-05 | 0.0927 ± 0.00068 | 354 ± 3.7 | 129,003 ± 937 |
| Circuit breaker | 0.139 ± 0.0029 | 0.305 ± 0.0068 | 0.0764 ± 0.0017 | 0.135 ± 0.0011 | 362 ± 9.7 | 130,828 ± 1,298 |
| No retries | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0.0986 ± 0.00076 | 278 ± 3.5 | 119,343 ± 1,357 |

## burst
Short DDoS-like burst: +400 req/s for 10s at t=30s, then back to 80 req/s.

| Policy | Retries / request | Latency during overload (s) | Latency, whole run (s) | Failed requests (fraction) | Peak capacity of B (req/s) | B capacity-seconds (cost proxy) |
|---|---|---|---|---|---|---|
| RetryGuard | 0.502 ± 0.0078 | 0.941 ± 0.012 | 0.291 ± 0.005 | 0.083 ± 0.0016 | 1,055 ± 16 | 172,832 ± 2,111 |
| Exp. backoff | 0.502 ± 0.0078 | 0.941 ± 0.012 | 0.291 ± 0.005 | 0.083 ± 0.0016 | 1,055 ± 16 | 172,832 ± 2,111 |
| Backoff + jitter | 0.493 ± 0.0079 | 0.546 ± 0.0092 | 0.169 ± 0.0029 | 0.0837 ± 0.0014 | 1,040 ± 17 | 171,359 ± 2,176 |
| Retry budget | 0.0306 ± 0.00026 | 0.0114 ± 0.0002 | 0.00352 ± 5.5e-05 | 0.0854 ± 0.0011 | 286 ± 2.8 | 72,342 ± 337 |
| Circuit breaker | 0.179 ± 0.0045 | 0.348 ± 0.0093 | 0.108 ± 0.0029 | 0.106 ± 0.0014 | 439 ± 8.9 | 90,714 ± 1,068 |
| No retries | 0 ± 0 | 0 ± 0 | 0 ± 0 | 0.0856 ± 0.001 | 237 ± 2.1 | 66,464 ± 251 |

