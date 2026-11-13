#!/usr/bin/env bash
# Reproduce everything: tests -> benchmarks -> sweep -> figures
set -e
python3 tests/test_sanity.py
python3 run_benchmarks.py --seeds 20
python3 run_sweep.py --seeds 10
python3 make_plots.py
