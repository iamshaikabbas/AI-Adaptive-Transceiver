"""
acs.py -- Adaptive Communication Score (canonical Python definition).

Mirrors MATLAB compute_acs.m EXACTLY and reads the SAME acs_weights.json:

    ACS = w_ber*BER_score + w_throughput*Throughput_score + w_se*SE_score
        + w_cqi*CQI_score + w_latency*Latency_score + w_recovery*Recovery_score

All scores are normalized to [0,1] (see acs_weights.json "_normalization").
Edit the weights in the json file only -- never in either code path.
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_FILE = os.path.join(os.path.dirname(HERE), "acs_weights.json")

DEFAULT_WEIGHTS = {
    "w_ber": 0.25,
    "w_throughput": 0.20,
    "w_se": 0.10,
    "w_cqi": 0.15,
    "w_latency": 0.10,
    "w_recovery": 0.20,
}

LATENCY_REF_MS = 200.0


def load_weights(path: str = None) -> dict:
    """Load + normalize ACS weights (shared json with MATLAB)."""
    w = dict(DEFAULT_WEIGHTS)
    src = path or WEIGHTS_FILE
    if os.path.isfile(src):
        try:
            with open(src) as fh:
                j = json.load(fh)
            for k in w:
                if isinstance(j.get(k), (int, float)):
                    w[k] = float(j[k])
        except (OSError, ValueError):
            pass
    tot = sum(w.values()) or 1.0
    return {k: v / tot for k, v in w.items()}


def acs_scores(ber: float, throughput_bps: float, se_bps_per_hz: float,
               cqi: float, latency_ms: float, recovery: float,
               tp_cap: float, se_cap: float) -> dict:
    """Normalized component scores, each clamped to [0,1]."""
    s_ber = min(1.0, max(0.0, -math.log10(max(ber, 1e-6)) / 6.0))
    s_tp = min(1.0, max(0.0, throughput_bps) / max(tp_cap, 1e-12))
    s_se = min(1.0, max(0.0, se_bps_per_hz) / max(se_cap, 1e-12))
    s_cqi = min(1.0, max(0.0, cqi) / 15.0)
    s_lat = math.exp(-max(latency_ms, 0.0) / LATENCY_REF_MS)
    s_rec = min(1.0, max(0.0, recovery))
    return {"BER": s_ber, "Throughput": s_tp, "SE": s_se,
            "CQI": s_cqi, "Latency": s_lat, "Recovery": s_rec}


def compute_acs(ber: float, throughput_bps: float, se_bps_per_hz: float,
                cqi: float, latency_ms: float, recovery: float,
                tp_cap: float, se_cap: float, weights: dict = None):
    """Return (ACS in [0,1], component-score dict). tp_cap/se_cap come from
    the frame itself: tp_cap = N_bits/frame_T, se_cap = log2(M_mod)."""
    w = weights or load_weights()
    s = acs_scores(ber, throughput_bps, se_bps_per_hz, cqi, latency_ms,
                   recovery, tp_cap, se_cap)
    acs = (w["w_ber"] * s["BER"] + w["w_throughput"] * s["Throughput"]
           + w["w_se"] * s["SE"] + w["w_cqi"] * s["CQI"]
           + w["w_latency"] * s["Latency"] + w["w_recovery"] * s["Recovery"])
    return min(1.0, max(0.0, acs)), s


if __name__ == "__main__":
    a, parts = compute_acs(1e-6, 1e6, 2.0, 15, 0, 1, 1024, 2)
    print(f"perfect frame ACS={a:.4f} parts={parts}")
    assert abs(a - 1.0) < 1e-9
    a, _ = compute_acs(1.0, 0, 0, 0, 500, 0, 1024, 2)
    assert 0 <= a < 0.2, a
    print(f"dead frame   ACS={a:.4f}")
