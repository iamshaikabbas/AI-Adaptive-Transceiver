"""
ai_engine_v2.py -- AI decision layer v2 (Phase 3, sections 3-5).

Same architecture and CLI contract as ai_engine.py (v1), but powered by
the metric regressors RETRAINED on the expanded Phase-2 dataset
(models/metric_models_v2/, see train_metric_regressors_v2.py) and the
v2 feature set (adds doppler_hz / carrier_frequency_hz / bandwidth_hz /
channel_profile vocabulary of environment_profiles_v2).

Pipeline per decision:
    1. predict metrics for OTFS-MRC  (BER, throughput, CQI, ACS, PER, SE)
    2. predict metrics for ODDM-LMMSE (same)
    3. objective = config.objective ('ACS' maximize | 'BER' minimize)
    4. recommendation = argmax pred ACS / argmin pred BER
    5. GATED by adaptive_config_v2.json policy:
         - min_confidence   (normalized margin must exceed it)
         - switch_margin_acs/rel (absolute OR relative advantage)
         - min_dwell_frames (no switch twice within N frames)

Nothing is hard-coded about which waveform wins where. Confidence is the
normalized predicted-objective margin (v1 convention), NOT an accuracy
claim; it is documented as such.

CLI: python ai_engine_v2.py --infile state.json --out decision.json
"""

import argparse
import json
import os

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models", "metric_models_v2")
CONFIG_FILE = os.path.join(HERE, "..", "adaptive_config_v2.json")

DEFAULT_DET = {"OTFS": "MRC", "ODDM": "LMMSE"}

DEFAULT_POLICY = {
    "objective": "ACS",            # 'ACS' | 'BER'
    "min_confidence": 0.0,         # optional gate; 0 = disabled by default
    "switch_margin_acs": 0.01,
    "switch_margin_rel": 0.02,
    "min_dwell_frames": 3,
}


class AIEngineV2:
    def __init__(self, config_file=None):
        self.meta = json.load(open(
            os.path.join(MODELS_DIR, "metric_models_v2_meta.json")))
        self.features = self.meta["features_cat"] + self.meta["features_num"]
        self.targets = {}
        for t, info in self.meta["targets"].items():
            self.targets[t] = joblib.load(
                os.path.join(MODELS_DIR, info["file"]))
        self.lat_ms = {r["waveform"]: float(r["latency_median_ms"])
                       for r in self.meta["latency_lookup_ms"]}
        self.policy = dict(DEFAULT_POLICY)
        cfg_path = config_file or CONFIG_FILE
        if os.path.isfile(cfg_path):
            try:
                cfg = json.load(open(cfg_path))
                for k in DEFAULT_POLICY:
                    if k in cfg:
                        self.policy[k] = cfg[k]
            except ValueError:
                pass

    # ------------------------------------------------------------------ #
    def design_row(self, waveform, state):
        """Exact feature frame fed to the regressors (reused by sims)."""
        row = {c: state.get(c, 0) for c in self.features}
        row["waveform"] = waveform
        return pd.DataFrame([row], columns=self.features)

    def predict_metrics(self, waveform, state):
        X = self.design_row(waveform, state)
        m = {"waveform": waveform, "detector": DEFAULT_DET[waveform]}
        m["Log10BER"] = float(self.targets["Log10BER"].predict(X)[0])
        m["BER"] = float(np.clip(10 ** m["Log10BER"], 0.0, 1.0))
        m["Throughput_bps"] = float(max(
            self.targets["Throughput"].predict(X)[0], 0.0))
        m["CQI"] = float(np.clip(self.targets["CQI"].predict(X)[0], 0, 15))
        m["ACS"] = float(np.clip(self.targets["ACS"].predict(X)[0], 0, 1))
        m["PER"] = float(np.clip(self.targets["PER"].predict(X)[0], 0, 1))
        m["SpectralEfficiency"] = float(max(
            self.targets["SE"].predict(X)[0], 0.0))
        m["Latency_ms"] = self.lat_ms.get(waveform, 100.0)
        return m

    # ------------------------------------------------------------------ #
    def decide(self, state):
        pol = self.policy
        obj = str(pol["objective"]).upper()
        if obj not in ("ACS", "BER"):
            raise ValueError(f"unknown objective {obj}")

        m_o = self.predict_metrics("OTFS", state)
        m_d = self.predict_metrics("ODDM", state)
        cand = {"OTFS": m_o, "ODDM": m_d}

        def score(m):
            return m["BER"] if obj == "BER" else m["ACS"]

        s_o, s_d = score(m_o), score(m_d)
        best = "OTFS" if ((s_o <= s_d) if obj == "BER" else (s_o >= s_d)) \
            else "ODDM"

        cur = state.get("current_waveform")
        dwell = int(state.get("frames_since_switch", 999))
        rec, switched, reason = cur if cur in cand else best, False, ""

        margin_abs_key = "switch_margin_acs"
        gain_best = max(s_o, s_d) if obj == "ACS" else min(s_o, s_d)
        if cur not in cand:
            rec, switched = best, True
            reason = f"initial selection ({obj}={score(cand[best]):.4f})"
        else:
            alt = "ODDM" if cur == "OTFS" else "OTFS"
            cur_s, alt_s = score(cand[cur]), score(cand[alt])
            gain = (cur_s - alt_s) if obj == "BER" else (alt_s - cur_s)
            rel = gain / max(abs(cur_s), 1e-9)
            conf_raw = abs(s_o - s_d) / max(abs(gain_best), 1e-9)
            confidence = float(min(1.0, conf_raw))

            if dwell < pol["min_dwell_frames"]:
                reason = (f"hold {cur}: min-dwell "
                          f"({dwell}/{pol['min_dwell_frames']})")
            elif gain <= 0:
                reason = f"keep {cur}: already best by {obj}"
            elif not (abs(gain) > pol[margin_abs_key] or
                      rel > pol["switch_margin_rel"]):
                reason = (f"keep {cur}: margin below threshold "
                          f"(gain {gain:+.4f} / {100*rel:.1f}%)")
            elif confidence < pol["min_confidence"]:
                reason = (f"hold {cur}: normalized margin confidence "
                          f"{confidence:.2f} < {pol['min_confidence']}")
            else:
                rec, switched = alt, True
                reason = (f"switch to {alt}: {obj} improvement "
                          f"{gain:+.4f} abs / {100*rel:.1f}% rel, "
                          f"confidence {confidence:.2f}")
        conf_raw = abs(s_o - s_d) / max(abs(gain_best), 1e-9)
        confidence = float(min(1.0, conf_raw))

        return {
            "recommendation": rec,
            "best_by_objective": best,
            "detector": DEFAULT_DET[rec],
            "switched": switched,
            "reason": reason,
            "confidence": confidence,
            "objective": obj,
            "predicted_ACS": {"OTFS": m_o["ACS"], "ODDM": m_d["ACS"]},
            "predicted_BER": {"OTFS": m_o["BER"], "ODDM": m_d["BER"]},
            "predicted_metrics": {"OTFS": m_o, "ODDM": m_d},
            "policy": pol,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None,
                    help="policy config JSON (default adaptive_config_v2.json)")
    args = ap.parse_args()

    eng = AIEngineV2(config_file=args.config)
    st = json.load(open(args.infile))
    dec = eng.decide(st)
    with open(args.out, "w") as fh:
        json.dump(dec, fh, indent=1)
    pm = dec["predicted_metrics"][dec["recommendation"]]
    print(f"{dec['recommendation']} ({dec['detector']}) "
          f"conf={dec['confidence']:.2f} :: {dec['reason']}")


if __name__ == "__main__":
    main()
