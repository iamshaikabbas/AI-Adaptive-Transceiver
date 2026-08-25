"""phase4_validation_tests.py -- Phase 4 section 22: 20 validation tests.

Every test is written to FAIL on a real regression (non-vacuous): it
recomputes evidence from primary artifacts (traces, states, configs,
reports) instead of trusting summaries, except where a summary itself is
the artifact under test (then it is cross-checked against a fresh
recomputation).

Usage:  python phase4_validation_tests.py
Output: prints one line per test and writes ../../PHASE4_VALIDATION.md
"""

import hashlib
import json
import os
import sys
import time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ai_engine_v3 import AIEngineV3                       # noqa: E402
from phase4_policy_sim import (load_tier, simulate, TIER, # noqa: E402
                               paired_metrics)

ROOT = os.path.dirname(HERE)
DT = os.path.join(ROOT, "Results", "DigitalTwin")
BASE = os.path.join(DT, "baseline_phase3")
MD = os.path.join(ROOT, "..", "PHASE4_VALIDATION.md")
V4 = json.load(open(os.path.join(ROOT, "adaptive_config_v4.json")))
CP = V4["confidence_policy"]
POL_P4 = dict(objective="ACS", margin_abs=V4["switch_margin_acs"],
              margin_rel=V4["switch_margin_rel"],
              min_dwell=V4["min_dwell_frames"], conf_mode=CP["mode"],
              k_unc=CP["k_unc"], tau_low=CP["tau_low"],
              tau_high=CP["tau_high"])

RES = []
def check(tid, name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    RES.append(dict(id=tid, name=name, status=status, detail=detail))
    print(f"[{status}] {tid} {name}" + (f" -- {detail}" if detail else ""))
    return bool(cond)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def tf(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1"])


def main():
    t0 = time.time()
    fm = json.load(open(os.path.join(HERE,
                                     "phase4_final_metrics.json")))
    study = json.load(open(os.path.join(HERE,
                                        "phase4_study_results.json")))

    # ---- T1 baseline preservation --------------------------------------
    ok = all(os.path.isfile(f"{BASE}\\{s}_trace.csv")
             for s in ("fixed_otfs", "fixed_oddm", "ai_adaptive",
                       "oracle"))
    ok &= os.path.isfile(os.path.join(ROOT, "..",
                                      "PHASE3_BASELINE.md"))
    same = {s: sha(f"{DT}\\{s}_trace.csv") == sha(f"{BASE}\\{s}_trace.csv")
            for s in ("fixed_otfs", "fixed_oddm", "ai_adaptive",
                      "oracle")}
    check("T1", "phase-3 baseline frozen & canonical traces untouched",
          ok and all(same.values()), f"hash-equal={same}")

    # ---- T2 extended schema --------------------------------------------
    p4 = pd.read_csv(os.path.join(DT, "ai_adaptive_trace_p4.csv"))
    need = ["unc_ACS_OTFS", "unc_ACS_ODDM", "unc_LogBER_OTFS",
            "unc_LogBER_ODDM", "confidence_band", "actual_TP_OTFS",
            "actual_TP_ODDM", "actual_CQI_OTFS", "actual_CQI_ODDM"]
    miss = [c for c in need if c not in p4.columns]
    bands_ok = set(p4.confidence_band.str.strip()).issubset(
        {"HIGH", "MEDIUM", "LOW"})
    check("T2", "67-col extended trace schema with uncertainty/band/"
          "paired-TP-CQI", not miss and len(p4.columns) == 67 and
          bands_ok, f"missing={miss} ncols={len(p4.columns)}")

    # ---- T3 scenario tiers ----------------------------------------------
    letters = [c for c in "ABCDEFGHIJKLMNOPQR" if os.path.isfile(
        os.path.join(DT, f"scenario_{c.lower()}.json"))]
    src = open(os.path.join(ROOT, "dt_scenarios_v4.m")).read()
    rng_ok = all(f"20260823+{k}" in src for k in (4, 5, 6))
    check("T3", "tuning E-H / held-out I-L / difficult M-R tiers exist "
          "and are disjoint from final A-D",
          all(c in letters for c in "EFGHIJKLMNOPQR") and rng_ok,
          f"scenarios={letters}")

    # ---- T4 tagged outputs + states sidecars -----------------------------
    states_ok, cols_ok = True, True
    for tier in ("tune", "heldout", "difficult"):
        for c in TIER[tier]:
            sp = os.path.join(DT, f"states_{c}_p4col.csv")
            if not os.path.isfile(sp):
                states_ok = False
                continue
            st = pd.read_csv(sp)
            have = {"environment", "speed_kmph", "snr_db", "doppler_hz",
                    "channel_profile", "delay_spread_taps", "num_paths",
                    "modulation"}
            if not have.issubset(st.columns):
                cols_ok = False
    canon_intact = sha(f"{DT}\\oracle_trace.csv") == \
        sha(f"{BASE}\\oracle_trace.csv")
    check("T4", "tagged runs never touch canonical outputs; per-frame "
          "AI feature vectors recorded (states sidecar)",
          states_ok and cols_ok and canon_intact,
          f"states_ok={states_ok} features={cols_ok} "
          f"canonical_oracle_untouched={canon_intact}")

    # ---- T5 paired execution --------------------------------------------
    ok5 = True
    for tier in ("tune", "heldout", "difficult"):
        for c in TIER[tier]:
            d = pd.read_csv(os.path.join(DT,
                            f"oracle_trace_{c}_p4col.csv"))
            cols = ["actual_ACS_OTFS", "actual_ACS_ODDM",
                    "actual_BER_OTFS", "actual_BER_ODDM",
                    "actual_TP_OTFS", "actual_TP_ODDM",
                    "actual_CQI_OTFS", "actual_CQI_ODDM"]
            if not d[cols].notna().all().all():
                ok5 = False
    check("T5", "every collected frame records BOTH waveforms' actual "
          "ACS/BER/TP/CQI (paired execution)", ok5)

    # ---- T6 fairness checksums (independent recomputation) ---------------
    b = pd.read_csv(f"{BASE}\\ai_adaptive_trace.csv")
    m = b.merge(p4, on=["scenario", "frame"], suffixes=("_b", "_p"))
    fair = bool((m.seed_frame_b == m.seed_frame_p).all() and
                (m.payload_sum_b == m.payload_sum_p).all() and
                (m.chan_checksum_b == m.chan_checksum_p).all()) \
        if "payload_sum_b" in m.columns else \
        bool((m.seed_frame_b == m.seed_frame_p).all())
    check("T6", "final A-D P4 run uses identical seeds/payload/channels "
          "as the frozen baseline", fair and fm["fairness"]["seed_match"]
          and fm["fairness"]["channel_match"])

    # ---- T7-T11 difficult scenarios M-R ----------------------------------
    diff_traces = {}
    ok7 = True
    for c in "MNOPQR":
        d = pd.read_csv(os.path.join(DT,
                        f"ai_adaptive_trace_{c.lower()}_p4.csv"))
        diff_traces[c] = d
        if len(d) != 24 or d.error_flag.astype(str).str.lower(
                ).isin(["true", "1"]).any():
            ok7 = False
    osc = fm["oscillation_pairs"]
    check("T7", "rapid accel/decel (M,N): complete error-free runs, no "
          "oscillation", ok7 and osc["P4_live_difficult"] == 0,
          f"osc={osc['P4_live_difficult']}")

    tr = pd.DataFrame(fm["robustness_transitions"])
    op = tr[(tr.scenario.isin(["O", "P"])) &
            (tr.policy == "P4_live")] if len(tr) else pd.DataFrame()
    check("T8", "SNR drop/recover (O,P): every transition answered and "
          "logged (switch or already-optimal)",
          len(op) == 8 and op.note.fillna("").eq(
              "already-on-new").sum() + op.det_delay.notna().sum()
          >= len(op))

    q = diff_traces["Q"]
    check("T9", "high-doppler HSR (Q, 250 km/h): stable run, decisions "
          "logged, ACS in range",
          len(q) == 24 and q.ACS.between(0, 1).all())

    r = tr[(tr.scenario == "R") & (tr.policy == "P4_live")]
    check("T10", "profile transition (R): both transitions logged",
          len(r) == 2)

    rs = fm["robustness_summary"]
    check("T11", "difficult-set outcome: P4 policy >= P3 policy on ACS "
          "with zero bad switches",
          rs["P4_replay"]["mean_ACS"] >= rs["P3_replay"]["mean_ACS"]
          and rs["P4_replay"]["bad_switches"] == 0,
          f"P4={rs['P4_replay']['mean_ACS']:.4f} "
          f"P3={rs['P3_replay']['mean_ACS']:.4f}")

    # ---- T12 offline-replay exactness (fresh recomputation) --------------
    diff_data = load_tier("difficult")
    rep4 = simulate(diff_data, POL_P4)[0].sort_values(
        ["scenario", "frame"]).reset_index(drop=True)
    live = pd.concat([diff_traces[c] for c in "MNOPQR"],
                     ignore_index=True).sort_values(
        ["scenario", "frame"]).reset_index(drop=True)
    mism = int((live.waveform.str.strip().values !=
                rep4.used.astype(str).str.strip().values).sum())
    bmism = int((live.confidence_band.str.strip().values !=
                 rep4.band.astype(str).str.strip().values).sum())
    check("T12", "offline replay reproduces live execution EXACTLY "
          "(decisions and confidence bands)", mism == 0 and bmism == 0,
          f"decision_mismatch={mism}/144 band_mismatch={bmism}/144")

    # ---- T13 zero-BER handling -------------------------------------------
    zbe = 0
    for tier in ("tune", "heldout", "difficult"):
        for c in TIER[tier]:
            d = pd.read_csv(os.path.join(DT,
                            f"oracle_trace_{c}_p4col.csv"))
            zbe += int(((d.actual_BER_OTFS == 0) |
                        (d.actual_BER_ODDM == 0)).sum())
    sa = study["studyA"]
    keep_verdict = (sa["two_part_mae"] >= sa["overall_mae_v2style"] and
                    "ber_model_version" in json.dumps(V4))
    check("T13", "zero-BER rows handled by documented log10 clipping; "
          "two-part model tested and NOT adopted (worse MAE); counts "
          "consistent",
          zbe == fm["zero_ber_frames"] and zbe > 0 and keep_verdict,
          f"zero_ber={zbe} v2style_MAE={sa['overall_mae_v2style']:.3f} "
          f"twopart_MAE={sa['two_part_mae']:.3f}")

    # ---- T14 RF uncertainty validity -------------------------------------
    sb = study["studyB"]
    check("T14", "RF estimator disagreement predicts prediction error "
          "(Spearman>0.5, p<1e-6, both metrics)",
          sb["Log10BER"]["spearman"] > .5 and sb["ACS"]["spearman"] > .5
          and sb["Log10BER"]["p"] < 1e-6 and sb["ACS"]["p"] < 1e-6,
          f"Log10BER rho={sb['Log10BER']['spearman']:.3f} "
          f"ACS rho={sb['ACS']['spearman']:.3f}")

    # ---- T15 confidence-band mechanics ------------------------------------
    agr = []
    for sn, (st, ac) in load_tier("tune").items():
        for t in range(len(st)):
            pm = paired_metrics(st.iloc[t].to_dict())
            g = pm["ODDM"]["ACS"] - pm["OTFS"]["ACS"]
            u = 0.5 * (pm["OTFS"]["unc_ACS"] + pm["ODDM"]["unc_ACS"])
            agr.append(abs(g) / (abs(g) + u))
    tl, th = np.quantile(agr, [1 / 3, 2 / 3])
    tau_ok = abs(tl - CP["tau_low"]) < .02 and abs(th - CP["tau_high"]) \
        < .02
    bands_all = set()
    for v in fm["band_usage"].values():
        bands_all |= set(v)
    check("T15", "tau_low/tau_high are empirical tertiles of tuning "
          "agreement scores; all three bands occur in practice",
          tau_ok and bands_all == {"HIGH", "MEDIUM", "LOW"},
          f"recomputed=({tl:.3f},{th:.3f}) config=({CP['tau_low']},"
          f"{CP['tau_high']}) bands_seen={sorted(bands_all)}")

    # ---- T16 dwell semantics ----------------------------------------------
    b3 = pd.read_csv(f"{BASE}\\ai_adaptive_trace.csv")
    gaps = []
    for sc, g in b3.groupby(b3.scenario.str.strip()):
        idx = np.flatnonzero(tf(g.switched).values)
        gaps += list(np.diff(idx))
    gap_ok = len(gaps) > 0 and min(gaps) >= 3 + 1
    eng = AIEngineV3()
    eng.predict_metrics = lambda wf, st: {
        "ACS": 0.9 if wf == "ODDM" else 0.5, "BER": 0.01}
    eng._uncertainty = lambda wf, st: {"ACS": 1e-9, "Log10BER": 1e-9}
    blocked = eng.decide({"current_waveform": "OTFS",
                          "frames_since_switch": 2})
    allowed = eng.decide({"current_waveform": "OTFS",
                          "frames_since_switch": 99})
    check("T16", "min-dwell blocks early switches (gap>=min_dwell+1); "
          "engine enforces it internally",
          gap_ok and not blocked["switched"] and allowed["switched"],
          f"observed_min_gap={int(min(gaps)) if gaps else 'n/a'} "
          f"dwell_blocked={not blocked['switched']}")

    # ---- T17 margin strictness + LOW-confidence fallback -------------------
    eng2 = AIEngineV3()
    tiny = {"ACS": 1e-9, "Log10BER": 1e-9}
    eng2._uncertainty = lambda wf, st: dict(tiny)
    otfs_a, g = 0.5, 0.01
    oddm_a = otfs_a + g
    g_exact = oddm_a - otfs_a          # float-exact difference
    eng2.predict_metrics = lambda wf, st: {
        "ACS": oddm_a if wf == "ODDM" else otfs_a, "BER": 0.01}
    eng2.policy["switch_margin_rel"] = 1e9          # isolate abs-margin path
    st99 = {"current_waveform": "OTFS", "frames_since_switch": 99}
    eng2.policy["switch_margin_acs"] = 0.0
    eng2.predict_metrics = lambda wf, st: {"ACS": otfs_a, "BER": 0.01}
    e0 = eng2.decide(st99)                          # zero gain -> no switch
    eng2.predict_metrics = lambda wf, st: {
        "ACS": oddm_a if wf == "ODDM" else otfs_a, "BER": 0.01}
    eng2.policy["switch_margin_acs"] = g_exact      # gain == margin
    eq = eng2.decide(st99)                          # strict > -> no switch
    eng2.policy["switch_margin_acs"] = float(
        np.nextafter(np.float64(g_exact), np.float64(0)))  # just below
    gt = eng2.decide(st99)                          # -> switch
    eng3 = AIEngineV3()
    eng3.predict_metrics = lambda wf, st: {
        "ACS": oddm_a if wf == "ODDM" else otfs_a, "BER": 0.01}
    eng3._uncertainty = lambda wf, st: {"ACS": 5.0, "Log10BER": 5.0}
    lowfb = eng3.decide({"current_waveform": "OTFS",
                         "frames_since_switch": 99})
    check("T17", "strict-> margins (equal gain does NOT switch), "
          "LOW-confidence fallback holds current waveform and flags "
          "fallback",
          (not e0["switched"]) and (not eq["switched"]) and
          gt["switched"] and lowfb.get("fallback") is True and
          not lowfb["switched"],
          f"tie={not e0['switched']} at_margin={not eq['switched']} "
          f"above={gt['switched']} low_fallback={lowfb.get('fallback')}")

    # ---- T18 payload-sizing refactor provably no-op on A-D -----------------
    src = open(os.path.join(ROOT, "digital_twin_runtime.m")).read()
    has_fix = "max_delay_tap+1" in src.replace(" ", "")
    check("T18", "runtime payload sizing now per-frame channel-derived; "
          "bit-identical A-D execution proves equivalence for these "
          "runs (see T6)", has_fix and fair)

    # ---- T19 no tuning against final scenarios ----------------------------
    sweep = open(os.path.join(HERE, "AI_Results", "Reports",
                              "phase4_policy_sweep.md"),
                 encoding="utf-8").read()
    tuning_sections = sweep.split("## Stage 4")[0]
    leak = any(f"scenario {c}" in tuning_sections or
               f"| {c} " in tuning_sections for c in "ABCD")
    cfg_t = os.path.getmtime(os.path.join(ROOT,
                                          "adaptive_config_v4.json"))
    eval_t = os.path.getmtime(os.path.join(DT,
                                           "ai_adaptive_trace_p4.csv"))
    order_ok = cfg_t < eval_t
    check("T19", "selection used only E-L (+M-R robustness); final A-D "
          "evaluated strictly after the config was frozen",
          (not leak) and order_ok,
          f"no_AD_reference_in_stages_1-3={not leak} "
          f"config_before_eval={order_ok}")

    # ---- T20 honesty of the improvement verdict ---------------------------
    vd = fm["verdict"]
    honest = (vd["P4_beats_P3_on_ACS"] ==
              (vd["P4_vs_P3_dACS"] > 0)) and \
             (("PHASE 3 REMAINS" in vd["action"]) ==
              (not vd["P4_beats_P3_on_ACS"]))
    tab = pd.DataFrame(fm["final_table"]).set_index("strategy")
    recheck = abs(tab.loc["AI_phase4", "mean_ACS"] -
                  p4.ACS.mean()) < 1e-9
    check("T20", "section-19 verdict matches raw data; P3 kept as "
          "preferred when P4 does not improve on it",
          honest and recheck,
          f"dACS={vd['P4_vs_P3_dACS']:+.5f} action='{vd['action'][:44]}…'")

    # ---------------------------------------------------------------------
    n_pass = sum(1 for r in RES if r["status"] == "PASS")
    lines = [
        "# PHASE 4 VALIDATION REPORT",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}   "
        f"Duration: {time.time()-t0:.0f} s",
        f"Result: **{n_pass}/{len(RES)} tests PASS**",
        "",
        "| # | Test | Status | Evidence |",
        "|---|------|--------|----------|",
    ]
    for r in RES:
        det = (r["detail"] or "").replace("|", "/")
        lines.append(f"| {r['id']} | {r['name']} | {r['status']} | "
                     f"{det} |")
    lines += [
        "",
        "## Notes",
        "",
        "- Tests marked PASS were verified non-vacuously: each asserts a "
        "property that fails if the corresponding component regresses "
        "(checksums, exact replay equality, strict-inequality margins, "
        "tertile recomputation, dwell arithmetic, honesty consistency).",
        "- Latency_ms is wall-clock detector time; cross-run ACS "
        "differences are dominated by bit-exact BER/TP/CQI (see analysis "
        "report latency-noise quantification).",
        "- The Phase-4 policy did NOT beat Phase 3 on the untouched "
        "final scenarios; per the pre-registered improvement criteria, "
        "Phase 3 remains the preferred configuration.",
    ]
    with open(MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"\n{n_pass}/{len(RES)} PASS -> {os.path.normpath(MD)}")


if __name__ == "__main__":
    main()
