"""
ai_engine_v3.py -- AI decision layer v3 (Phase 4, sections 3-7, 15).

Same prediction core as ai_engine_v2.py (models/metric_models_v2 kept --
the Phase-4 studies found no justification for retraining; see
phase4_model_studies.md / phase4_policy_sweep.md). What changes is the
DECISION POLICY:

  Uncertainty-aware confidence banding (section 6/7):
    agreement = |dACS| / (|dACS| + k_unc * mean(tree-spread ACS))
    HIGH   (>= tau_high): normal switch margins apply
    MEDIUM (>= tau_low ): doubled switch margins required
    LOW    (otherwise  ): fallback -> keep previous waveform,
                          fallback=true recorded (never fabricated)

  tau_low / tau_high are empirical tertiles of the agreement score over
  the TUNING scenarios (E-H); they are documented inputs, not claims of
  optimality. Margins use strict > comparisons (v2 convention).

The two-part BER study did NOT clearly beat log10-clipping (zero-BER rows
remain hard for both), so BER handling is unchanged (clip floor 1e-12).

CLI: python ai_engine_v3.py --infile state.json --out decision.json
              [--config adaptive_config_v4.json]
"""

import argparse
import json
import os

from ai_engine_v2 import AIEngineV2, DEFAULT_POLICY

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(os.path.dirname(HERE),
                           "adaptive_config_v4.json")

V3_POLICY_DEFAULTS = dict(DEFAULT_POLICY, **{
    "conf_mode": "band",       # 'band' | 'none'
    "k_unc": 1.0,              # uncertainty weight in agreement score
    "tau_low": 0.305,          # below -> LOW  (fallback hold)
    "tau_high": 0.585,         # above -> HIGH (normal margins)
})


class AIEngineV3(AIEngineV2):
    """v2 predictions + banded-confidence decision policy."""

    def __init__(self, config_file=None):
        super().__init__(config_file=config_file or CONFIG_FILE)
        for k, v in V3_POLICY_DEFAULTS.items():
            self.policy.setdefault(k, v)

    # ---------------------------------------------------------------- #
    def _uncertainty(self, waveform, state):
        """tree-spread std for ACS and Log10BER of one waveform"""
        import numpy as np
        X = self.design_row(waveform, state)
        out = {}
        for tgt in ("ACS", "Log10BER"):
            model = self.targets[tgt]
            pre = model.named_steps.get("pre") \
                if hasattr(model, "named_steps") else None
            Xt = pre.transform(X) if pre is not None else X
            reg = model.named_steps["reg"] \
                if hasattr(model, "named_steps") else model
            preds = [e.predict(Xt) for e in reg.estimators_]
            out[tgt] = float(np.std(preds))
        return out

    # ---------------------------------------------------------------- #
    def decide(self, state):
        pol = self.policy
        m_o = self.predict_metrics("OTFS", state)
        m_d = self.predict_metrics("ODDM", state)
        u_o = self._uncertainty("OTFS", state)
        u_d = self._uncertainty("ODDM", state)

        gain = m_d["ACS"] - m_o["ACS"]          # ACS objective (max)
        rel = gain / max(abs(m_o["ACS"]), 1e-9)
        u = pol["k_unc"] * 0.5 * (u_o["ACS"] + u_d["ACS"])
        agr = abs(gain) / (abs(gain) + max(u, 1e-9))

        if str(pol.get("conf_mode", "none")).lower() == "band":
            band = ("HIGH" if agr >= pol["tau_high"] else
                    "MEDIUM" if agr >= pol["tau_low"] else "LOW")
        else:
            band = "HIGH"
        m_abs = pol["switch_margin_acs"] * (2.0 if band == "MEDIUM" else 1.0)
        m_rel = pol["switch_margin_rel"] * (2.0 if band == "MEDIUM" else 1.0)

        cur = state.get("current_waveform")
        if cur not in ("OTFS", "ODDM"):
            cur = "OTFS" if m_o["ACS"] >= m_d["ACS"] else "ODDM"
        alt = "ODDM" if cur == "OTFS" else "OTFS"
        dwell = int(state.get("frames_since_switch", 999))

        rec, switched, fallback, reason = cur, False, False, ""
        if dwell < pol["min_dwell_frames"]:
            reason = (f"hold {cur}: min-dwell "
                      f"({dwell}/{pol['min_dwell_frames']})")
        elif gain <= 0:
            reason = f"keep {cur}: already best by ACS"
        elif not (gain > m_abs or rel > m_rel):
            reason = (f"keep {cur}: margin below threshold "
                      f"(gain {gain:+.4f} / {100*rel:.1f}%)")
        elif band == "LOW":
            fallback = True     # documented low-confidence fallback: HOLD
            reason = (f"fallback hold {cur}: LOW agreement {agr:.2f} "
                      f"< tau_low {pol['tau_low']}")
        else:
            rec, switched = alt, True
            reason = (f"switch to {alt}: ACS improvement {gain:+.4f} abs "
                      f"/ {100*rel:.1f}% rel, band {band}, "
                      f"agreement {agr:.2f}")

        best = "OTFS" if m_o["ACS"] >= m_d["ACS"] else "ODDM"
        from ai_engine_v2 import DEFAULT_DET
        return {
            "recommendation": rec,
            "best_by_objective": best,
            "detector": DEFAULT_DET[rec],
            "switched": switched,
            "fallback": fallback,
            "reason": reason,
            "confidence": float(min(1.0, agr)),
            "confidence_band": band,
            "objective": "ACS",
            "predicted_ACS": {"OTFS": m_o["ACS"], "ODDM": m_d["ACS"]},
            "predicted_BER": {"OTFS": m_o["BER"], "ODDM": m_d["BER"]},
            "predicted_metrics": {"OTFS": m_o, "ODDM": m_d},
            "uncertainty": {
                "OTFS": {"ACS": u_o["ACS"],
                         "Log10BER": u_o["Log10BER"]},
                "ODDM": {"ACS": u_d["ACS"],
                         "Log10BER": u_d["Log10BER"]}},
            "policy": pol,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    eng = AIEngineV3(config_file=args.config)
    st = json.load(open(args.infile))
    dec = eng.decide(st)
    with open(args.out, "w") as fh:
        json.dump(dec, fh, indent=1)
    print(f"{dec['recommendation']} ({dec['detector']}) "
          f"band={dec['confidence_band']} conf={dec['confidence']:.2f} "
          f":: {dec['reason']}")


if __name__ == "__main__":
    main()
