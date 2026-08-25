"""
ai_engine.py -- AI decision layer of the Digital Twin (spec sections 11-13, 17).

Given the twin's current wireless state, the engine

    1. predicts OTFS performance   (log10BER -> BER, Throughput, CQI,
                                    derived PER/SE, median latency)
    2. predicts ODDM performance   (same pipeline)
    3. converts both to a predicted Adaptive Communication Score (ACS)
    4. recommends the higher-ACS waveform, GATED by
         - a minimum absolute ACS-improvement threshold and
         - a minimum dwell time since the last switch
       so the transceiver does not chatter between waveforms.

Nothing is hard-coded about which waveform wins where -- everything comes
from the regression models trained on real simulation data
(models/metric_reg_*.joblib, see train_metric_regressors.py).

CLI (used by the MATLAB digital-twin runtime):
    python ai_engine.py --infile state.json --out decision.json

state.json needs: Environment, Speed_kmh, DelayProfile, DelaySpread(taps),
NumPaths, DopplerSpread(normalized), Modulation, SNR_dB,
current_waveform, frames_since_switch [, N, M, delta_f]
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd

import acs as acs_mod

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")

TARGETS = {"Log10BER", "Throughput", "CQI"}
DEFAULT_DET = {"OTFS": "MRC", "ODDM": "LMMSE"}

# Adaptive-switching policy defaults (overridable via adaptive_config.json)
DEFAULT_POLICY = {
    "switch_threshold_acs": 0.01,     # need >=1 pt ACS advantage to switch
    "switch_threshold_rel": 0.02,     # ...or >=2 % relative improvement
    "min_dwell_frames": 3,            # never switch twice within N frames
}


class AIEngine:
    def __init__(self):
        self.meta = json.load(open(
            os.path.join(MODELS_DIR, "metric_regressors_meta.json")))
        self.models = {t: joblib.load(
            os.path.join(MODELS_DIR, f"metric_reg_{t}.joblib"))
            for t in TARGETS}
        self.features = self.meta["features"]
        self.runtime_ms = {(r["Waveform"], r["Detector"]):
                           1000 * r["runtime_median_s"]
                           for r in self.meta["runtime_table_s"]}
        pol_path = os.path.join(HERE, "..", "adaptive_config.json")
        self.policy = dict(DEFAULT_POLICY)
        if os.path.isfile(pol_path):
            try:
                self.policy.update(json.load(open(pol_path)))
            except ValueError:
                pass
        self._lat_med = float(np.median(list(self.runtime_ms.values())))

    # ------------------------------------------------------------------ #
    def _row(self, waveform, detector, f):
        row = {c: f.get(c, 0) for c in self.features}
        row["Waveform"] = waveform
        row["Detector"] = detector
        return pd.DataFrame([row], columns=self.features)

    def predict_metrics(self, waveform, detector, f):
        """Predicted metrics dict for one candidate configuration."""
        X = self._row(waveform, detector, f)
        log10ber = float(self.models["Log10BER"].predict(X)[0])
        ber = float(np.clip(10 ** log10ber, 0.0, 1.0))
        tp = float(max(self.models["Throughput"].predict(X)[0], 0.0))
        cqi = float(np.clip(self.models["CQI"].predict(X)[0], 0, 15))
        n_bits = int(f.get("N_bits_nominal", 1920))
        per_hat = float(1 - (1 - ber) ** max(n_bits, 1)) if ber > 0 else 0.0
        lat = self.runtime_ms.get((waveform, detector), self._lat_med)
        return {"Waveform": waveform, "Detector": detector,
                "Log10BER": log10ber, "BER": ber, "Throughput_bps": tp,
                "CQI": cqi, "PER_hat": per_hat, "Latency_ms": lat}

    def predict_acs(self, waveform, f, tp_cap, se_cap, weights=None):
        det = DEFAULT_DET[waveform]
        m = self.predict_metrics(waveform, det, f)
        bw = float(f.get("bandwidth_hz", 480e3))
        se = m["Throughput_bps"] / bw
        acs_v, parts = acs_mod.compute_acs(
            m["BER"], m["Throughput_bps"], se, m["CQI"], m["Latency_ms"],
            1.0 - m["PER_hat"], tp_cap, se_cap, weights)
        return acs_v, parts, m

    # ------------------------------------------------------------------ #
    def decide(self, f, current_waveform=None, frames_since_switch=999,
               weights=None, policy=None):
        """Full adaptive decision. `f` = feature dict of the CURRENT state."""
        pol = dict(self.policy)
        if policy:
            pol.update(policy)
        N = int(f.get("N", 32)); M = int(f.get("M", 32))
        mod = int(f.get("Modulation", 4))
        mbits = int(np.log2(mod))
        m_data = M - max(2, int(np.ceil(M / 16)))      # nominal guard band
        frame_T = N / float(f.get("delta_f", 15e3))
        n_bits = m_data * N * mbits
        tp_cap = n_bits / frame_T
        se_cap = mbits
        f = dict(f); f["N_bits_nominal"] = n_bits

        acs_o, parts_o, m_o = self.predict_acs("OTFS", f, tp_cap, se_cap,
                                               weights)
        acs_d, parts_d, m_d = self.predict_acs("ODDM", f, tp_cap, se_cap,
                                               weights)

        best = "OTFS" if acs_o >= acs_d else "ODDM"
        cand = {"OTFS": (acs_o, m_o), "ODDM": (acs_d, m_d)}
        rec, reason, switched = current_waveform, "", False

        if current_waveform not in ("OTFS", "ODDM"):
            rec, switched = best, True
            reason = f"initial selection (predicted ACS {cand[best][0]:.3f})"
        else:
            cur_acs = cand[current_waveform][0]
            alt = "ODDM" if current_waveform == "OTFS" else "OTFS"
            alt_acs = cand[alt][0]
            gain = alt_acs - cur_acs
            rel = gain / max(cur_acs, 1e-9)
            if frames_since_switch < pol["min_dwell_frames"]:
                reason = (f"hold {alt}: min-dwell "
                          f"({frames_since_switch}/{pol['min_dwell_frames']})")
            elif gain >= pol["switch_threshold_acs"] or \
                    rel >= pol["switch_threshold_rel"]:
                rec, switched = alt, True
                reason = (f"predicted ACS improvement = "
                          f"{100*rel:.1f}% ({gain:+.4f} abs)")
            else:
                reason = (f"keep {current_waveform}: predicted gain "
                          f"{100*rel:.1f}% below threshold")

        conf = abs(acs_o - acs_d) / max(max(acs_o, acs_d), 1e-9)
        return {
            "recommendation": rec,
            "detector": DEFAULT_DET[rec],
            "switched": switched,
            "reason": reason,
            "confidence": float(min(1.0, conf)),
            "predicted_ACS": {"OTFS": acs_o, "ODDM": acs_d},
            "predicted_ACS_parts": {"OTFS": parts_o, "ODDM": parts_d},
            "predicted_metrics": {"OTFS": m_o, "ODDM": m_d},
            "policy": pol,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    eng = AIEngine()
    st = json.load(open(args.infile))
    dec = eng.decide(st, st.get("current_waveform"),
                     st.get("frames_since_switch", 999))
    with open(args.out, "w") as fh:
        json.dump(dec, fh, indent=1)
    print(f"{dec['recommendation']} ({dec['detector']}) "
          f"ACS_OTFS={dec['predicted_ACS']['OTFS']:.3f} "
          f"ACS_ODDM={dec['predicted_ACS']['ODDM']:.3f} :: {dec['reason']}")


if __name__ == "__main__":
    main()
