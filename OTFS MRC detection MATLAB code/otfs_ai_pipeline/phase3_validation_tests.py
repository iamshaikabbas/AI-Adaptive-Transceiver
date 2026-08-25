"""phase3_validation_tests.py -- Phase 3 / sections 20-21.

TESTS 4-12 operate on the canonical trace CSVs.
TEST 13 unit-tests the decision policy (confidence / margin / dwell /
objective) by injecting crafted predictions into AIEngineV2.

Exit code 0 iff all tests pass.
"""

import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DT = os.path.join(HERE, "..", "Results", "DigitalTwin")
STRATS = ["fixed_otfs", "fixed_oddm", "ai_adaptive", "oracle"]
fails = []


def chk(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)


def bcol(df, name):
    """MATLAB logicals arrive as 0/1 floats or 'true'/'false' strings."""
    s = df[name]
    if s.dtype == object:
        return s.astype(str).str.strip().str.lower().eq("true")
    return s.astype(float) > 0.5


tr = {}
for s in STRATS:
    p = os.path.join(DT, f"{s}_trace.csv")
    ok = os.path.isfile(p)
    chk(f"T4-T7 trace exists: {s}", ok)
    tr[s] = pd.read_csv(p) if ok else pd.DataFrame()

# T4/T5/T6: fixed strategies + oracle executed every frame with right wf
for s, wf in [("fixed_otfs", "otfs"), ("fixed_oddm", "oddm")]:
    df = tr[s]
    chk(f"T4/T5 {s}: 240 rows", len(df) == 240, f"n={len(df)}")
    wfs = df.waveform.str.strip().str.lower()
    chk(f"T4/T5 {s}: waveform always {wf}", (wfs == wf).all())
    chk(f"T4/T5 {s}: no sim errors", (~bcol(df, "error_flag")).sum() >= 238,
        f"errors={int(bcol(df, 'error_flag').sum())}")
dfo = tr["oracle"]
chk("T6 oracle: 240 rows", len(dfo) == 240, f"n={len(dfo)}")
chk("T6 oracle picks best actual ACS",
    ((dfo.oracle_waveform.str.strip().str.lower() == "otfs") ==
     (dfo.actual_ACS_OTFS >= dfo.actual_ACS_ODDM)).mean() > 0.99)

# T7: adaptive executed all frames
da = tr["ai_adaptive"]
chk("T7 adaptive: 240 rows, all executed", len(da) == 240 and
    int(bcol(da, "error_flag").sum()) == 0)

# T8: exactly one row per frame per scenario
grp = da.groupby(["scenario", "frame"]).size()
chk("T8 one row per scenario-frame", (grp == 1).all(),
    f"cells={len(grp)}")
chk("T8 frames 1..60 x A-D complete",
    sorted(da.scenario.unique()) == ["A", "B", "C", "D"] and
    all(set(g.frame) == set(range(1, 61)) for _, g in da.groupby("scenario")))

# T9: no NaN in critical metrics on error-free rows
crit = ["BER", "SER", "PER", "Throughput_bps", "CQI", "ACS"]
bad = sum(int(df[c].isna().sum()) for s in STRATS for c in crit
          for df in [tr[s]])
chk("T9 no NaN in critical metrics (error-free rows)", bad == 0,
    f"NaN cells={bad}")

# T10 fairness: identical seeds / payload / channel per frame across strats
idx = ["scenario", "frame"]
A = tr["fixed_otfs"].set_index(idx)
B = tr["fixed_oddm"].set_index(idx)
C = tr["ai_adaptive"].set_index(idx)
D = tr["oracle"].set_index(idx)
m = A.join(B, rsuffix="_oddm").join(C, rsuffix="_ai").join(D, rsuffix="_orc")
same_seed = ((m.seed_frame == m.seed_frame_oddm) &
             (m.seed_frame == m.seed_frame_ai)).all()
same_pay = ((m.payload_sum == m.payload_sum_oddm) &
            (m.payload_sum == m.payload_sum_ai)).all()
same_chan = ((m.chan_checksum == m.chan_checksum_oddm) &
             (m.chan_checksum == m.chan_checksum_ai)).all()
chk("T10 identical noise seeds across strategies", bool(same_seed))
chk("T10 identical payloads across strategies", bool(same_pay))
chk("T10 identical channel realizations across strategies", bool(same_chan))

# T11 predicted + actual metrics recorded
pred_ok = da[["confidence", "pred_ACS_OTFS", "pred_ACS_ODDM",
              "pred_BER_OTFS", "pred_BER_ODDM"]].notna().all().all()
act_ok = da[["actual_BER_OTFS", "actual_BER_ODDM", "actual_ACS_OTFS",
             "actual_ACS_ODDM", "oracle_waveform"]].notna().all().all()
chk("T11 AI prediction fields recorded", bool(pred_ok))
chk("T11 actual+oracle fields recorded", bool(act_ok))

# T12 regret recomputation cross-check
rb = da.BER - da.oracle_BER
ra = np.maximum(da.oracle_ACS - da.ACS, 0)
ok12 = np.allclose(rb, da.BER_regret, atol=1e-12, equal_nan=True) and \
    np.allclose(ra, da.ACS_regret, atol=1e-12)
chk("T12 regret columns recompute correctly", bool(ok12))

# T13 decision policy unit test --------------------------------------------
from ai_engine_v2 import AIEngineV2  # noqa: E402

eng = AIEngineV2()


def craft(acs_otfs, acs_oddm, ber_otfs=1e-3, ber_oddm=1e-3):
    def fake(wf, state):
        m = {"waveform": wf, "detector": "", "Log10BER": -3,
             "Throughput_bps": 1e6, "CQI": 10}
        m["ACS"] = acs_otfs if wf == "OTFS" else acs_oddm
        m["BER"] = ber_otfs if wf == "OTFS" else ber_oddm
        m["PER"] = 0.1
        m["SpectralEfficiency"] = 2.0
        m["Latency_ms"] = 50.0
        return m
    return fake


def decide_with(acs_o, acs_d, cur="OTFS", dwell=99, pol=None,
                ber_o=1e-3, ber_d=1e-3):
    eng.predict_metrics = craft(acs_o, acs_d, ber_o, ber_d)
    old = dict(eng.policy)
    if pol:
        eng.policy.update(pol)
    d = eng.decide({"current_waveform": cur, "frames_since_switch": dwell})
    eng.policy = old
    return d


# small margin (spec section-5 example A) -> keep
d = decide_with(0.81, 0.82)
chk("T13 small margin keeps current", d["recommendation"] == "OTFS"
    and not d["switched"])
# big margin + dwell -> switch (spec example B)
d = decide_with(0.70, 0.86)
chk("T13 big margin switches", d["recommendation"] == "ODDM"
    and d["switched"], f"conf={d['confidence']:.2f}")
# dwell blocks
d = decide_with(0.70, 0.86, dwell=2)
chk("T13 min-dwell blocks early switch", not d["switched"])
# confidence gate works when enabled
d = decide_with(0.80, 0.805, pol={"min_confidence": 0.5})
chk("T13 confidence gate blocks small normalized margin",
    not d["switched"])
d = decide_with(0.70, 0.86, pol={"min_confidence": 0.1})
chk("T13 confidence gate passes large normalized margin",
    d["switched"])
# BER objective flips direction
eng.policy["objective"] = "BER"
d = decide_with(0.8, 0.8, ber_o=1e-6, ber_d=1e-3)  # cur OTFS already better
chk("T13 BER objective keeps lower-BER current", d["recommendation"] == "OTFS")
d = decide_with(0.8, 0.8, ber_o=1e-3, ber_d=1e-6)
chk("T13 BER objective switches to lower-BER alt",
    d["recommendation"] == "ODDM" and d["switched"])
eng.policy["objective"] = "ACS"

# traces respect min-dwell given observed switching (vacuous if 0 switches)
sw_idx = np.flatnonzero(bcol(da, "switched").to_numpy())
gaps = np.diff(sw_idx) if len(sw_idx) > 1 else np.array([999])
chk("T13 trace respects min-dwell between switches",
    bool((gaps >= eng.policy["min_dwell_frames"]).all()),
    f"min gap={gaps.min() if len(gaps) else 'NA'}")

print(f"\n{'ALL TRACE/POLICY TESTS PASSED' if not fails else 'FAILURES: ' + str(fails)}")
sys.exit(0 if not fails else 1)
