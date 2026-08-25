"""
make_scenario.py -- CLI: write a Digital-Twin scenario JSON for the MATLAB
runtime / strategy comparator.

Usage:
    python make_scenario.py [duration_s] [outfile] [--seed N]
"""

import sys
import os

from scenario import build_scenario, write_scenario_json

if __name__ == "__main__":
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        "..", "Results", "DigitalTwin", "scenario.json")
    seed = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == "--seed" else 7
    pts = build_scenario(duration_s=dur, seed=seed)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    write_scenario_json(pts, out)
    print(f"wrote {len(pts)} frames -> {os.path.abspath(out)}")
