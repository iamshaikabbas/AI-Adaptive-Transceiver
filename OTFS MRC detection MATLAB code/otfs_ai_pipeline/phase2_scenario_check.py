"""phase2_scenario_check.py -- Phase 2 / STEP 8 gate.

Verifies the four generated scenario JSONs load into the v1 ScenarioPoint
schema (field-for-field) and that ranges respect environment_profiles_v2.
"""

import json
import os
import sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DT = os.path.join(ROOT, "Results", "DigitalTwin")
FIELDS = ["t_s", "frame", "environment", "speed_kmph", "snr_db",
          "delay_profile", "doppler_scale", "modulation"]
prof = pd.read_csv(os.path.join(HERE, "environment_profiles_v2.csv"))\
         .set_index("Environment")

fails = []
for name in "abcd":
    p = os.path.join(DT, f"scenario_{name}.json")
    with open(p, encoding="utf-8") as fh:
        obj = json.load(fh)
    pts = obj["points"]
    ok_schema = all(set(FIELDS) <= set(pt) for pt in pts)
    ok_range = all(
        prof.loc[pt["environment"], "SpeedMin"] - 1e-9 <= pt["speed_kmph"]
        <= prof.loc[pt["environment"], "SpeedMax"] + 1e-9 for pt in pts)
    ok_prof = all(pt["delay_profile"] ==
                  prof.loc[pt["environment"], "DelayProfile"] for pt in pts)
    ok_mono = [pt["frame"] for pt in pts] == list(range(len(pts)))
    print(f"scenario_{name}: n={len(pts)} schema={ok_schema} "
          f"speeds_in_bounds={ok_range} profiles_match={ok_prof} "
          f"frames_monotonic={ok_mono}")
    fails += [f"{name}:{k}" for k, v in
              dict(schema=ok_schema, speeds=ok_range,
                   profiles=ok_prof, frames=ok_mono).items() if not v]

print("ALL SCENARIO CHECKS PASSED" if not fails else f"FAILURES: {fails}")
sys.exit(0 if not fails else 1)
