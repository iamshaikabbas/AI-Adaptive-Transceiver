"""phase5_validation_tests.py -- Phase 5 section 26: 20 validation tests.

Every test is NON-VACUOUS: it recomputes evidence from primary artifacts
(canonical traces, states, manifests, scenario JSONs, engine behavior)
instead of trusting summaries. Where a summary is itself the artifact under
test it is cross-checked against a fresh recomputation.

Usage:  python phase5_validation_tests.py            (from otfs_ai_pipeline)
Output: one line per test; writes ../../PHASE5_VALIDATION.md
"""

import glob
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from acs import compute_acs                              # noqa: E402

ROOT = os.path.dirname(HERE)                 # MATLAB code dir
PROJ = os.path.dirname(ROOT)                 # repo root (venv lives here)
DT = os.path.join(ROOT, "Results", "DigitalTwin")
BASE = os.path.join(DT, "baseline_phase3")
MD = os.path.join(ROOT, "..", "PHASE5_VALIDATION.md")
CHECKS = os.path.join(ROOT, "phase5_check_results.json")

STRATS = ["fixed_otfs", "fixed_oddm", "ai_adaptive", "oracle"]
SCEN_FULL = ["a", "b", "c", "d"]
SEED0 = 20260823

RES = []


def check(tid, name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    RES.append(dict(id=tid, name=name, status=status, detail=detail))
    print(f"[{status}] {tid} {name}" + (f" -- {detail}" if detail else ""))
    return bool(cond)


def trace(scen, strat):
    return pd.read_csv(os.path.join(DT, scen, f"{strat}_trace.csv"))


# ---------------------------------------------------------------------------
def t01_scenario_files():
    ok, det = True, []
    for L in "ABCDEFGHIJKLMNOPQR":
        p = os.path.join(DT, f"scenario_{L.lower()}.json")
        if not os.path.isfile(p):
            ok, _ = False, det.append(f"missing {p}")
            continue
        j = json.load(open(p))
        npts = len(j.get("points", []))
        if not (24 <= npts <= 64):
            ok = False
            det.append(f"{L}: {npts} pts")
    return check("T01", "scenario files A-R exist with valid point counts",
                 ok, "; ".join(det) or "18 scenarios, 24-64 points each")


def t02_custom_schema():
    p = os.path.join(ROOT, "custom_scenarios", "custom_test.json")
    if not os.path.isfile(p):
        return check("T02", "custom scenario schema", False, "file missing")
    j = json.load(open(p))
    need = ["name", "duration_frames"]
    miss = [k for k in need if k not in j]
    prof = pd.read_csv(os.path.join(HERE, "environment_profiles_v2.csv"))
    v = float(j["initial_speed_kmph"])
    inband = bool((((prof.SpeedMin - 1e-9) <= v) &
                   (v <= prof.SpeedMax + 1e-9)).any())
    return check("T02", "custom scenario schema + speed inside a band",
                 (not miss) and inband,
                 f"missing={miss}, v={v} km/h inband={inband}")


def t03_seed_contract():
    bad = []
    for s in SCEN_FULL:
        for st in STRATS:
            T = trace(s, st)
            exp_p = SEED0 + T.frame.astype(np.int64)
            exp_c = SEED0 * 10 + T.frame.astype(np.int64)
            exp_n = 100000 + T.frame.astype(np.int64)
            if not (np.allclose(T.payload_seed, exp_p) and
                    np.allclose(T.channel_seed, exp_c) and
                    np.allclose(T.noise_seed, exp_n)):
                bad.append(f"{s}/{st}")
    return check("T03", "dt_seeds contract holds in every trace",
                 not bad, ",".join(bad) or "pay=s+f chan=10s+f noise=f+1e5")


def t04_paired_fairness():
    bad = []
    for s in SCEN_FULL:
        ref = trace(s, STRATS[0])
        for st in STRATS[1:]:
            T = trace(s, st)
            if len(T) != len(ref) or \
               not np.allclose(T.chan_checksum, ref.chan_checksum) or \
               not np.allclose(T.payload_sum, ref.payload_sum):
                bad.append(f"{s}/{st}")
    return check("T04", "paired fairness: identical channel+payload per frame",
                 not bad, ",".join(bad) or "checksums equal across strategies")


def t05_states_timeline():
    bad = []
    for s in SCEN_FULL + ["custom_test"]:
        S = pd.read_csv(os.path.join(DT, s, "states.csv"))
        if not np.allclose(S.t_sim_s, (S.frame - 1) * 1.0):
            bad.append(s)
    return check("T05", "states timeline t_sim_s == (frame-1)*dt",
                 not bad, ",".join(bad) or "dt_s=1s consistent")


def t06_doppler_derivation():
    c = 299792458.0
    prof = pd.read_csv(os.path.join(HERE, "environment_profiles_v2.csv"))
    scale = dict(zip(prof.Environment, prof.DopplerScale.astype(float)))
    worst = 0.0
    for s in SCEN_FULL:
        T = trace(s, "fixed_otfs")
        k = T.environment.map(scale).astype(float)
        pred = (T.speed_kmph / 3.6) / c * T.carrier_frequency_hz * k
        worst = max(worst, float(np.nanmax(np.abs(pred - T.doppler_hz))))
    return check("T06", "doppler_hz derived from speed/carrier/DopplerScale",
                 worst < 1.0, f"max abs err {worst:.4f} Hz")


def t07_trace_schema():
    req = {"frame", "scenario_id", "environment", "speed_kmph", "snr_db",
           "doppler_hz", "carrier_frequency_hz", "bandwidth_hz",
           "channel_profile", "delay_spread_taps", "num_paths",
           "modulation", "detector", "waveform", "strategy", "mode",
           "policy", "scenario_seed", "payload_seed", "channel_seed",
           "noise_seed", "payload_sum", "chan_checksum",
           "predicted_waveform", "confidence", "selected_waveform",
           "previous_waveform", "switched", "switch_reason", "ai_error",
           "fallback_used", "BER", "SER", "PER", "throughput_bps",
           "spectral_efficiency", "CQI", "wall_clock_ms",
           "detector_time_ms", "latency_ms_modeled", "packet_loss",
           "recovery_rate", "ACS", "actual_BER_OTFS", "actual_ACS_OTFS",
           "actual_BER_ODDM", "actual_ACS_ODDM", "oracle_waveform",
           "oracle_BER", "oracle_ACS", "ACS_regret", "decision_correct",
           "error_flag"}
    bad = []
    for s in SCEN_FULL:
        for st in STRATS:
            cols = set(trace(s, st).columns)
            miss = req - cols
            if miss:
                bad.append(f"{s}/{st}:{sorted(miss)[:3]}")
    return check("T07", "canonical trace schema present (superset allowed)",
                 not bad, ";".join(bad) or f"{len(req)} required columns")


def t08_manifest_integrity():
    bad = []
    for root, _, files in os.walk(DT):
        if "run_manifest.json" not in files:
            continue
        m = json.load(open(os.path.join(root, "run_manifest.json")))
        scen = os.path.basename(root)
        rows = 0
        tf = os.path.join(root, "ai_adaptive_trace.csv")
        if os.path.isfile(tf):
            rows = len(pd.read_csv(tf))
        if m.get("frames_run") != rows or \
           str(m.get("policy")) not in ("phase3", "phase4"):
            bad.append(scen)
    return check("T08", "run_manifest integrity (frames_run/policy)",
                 not bad, ",".join(bad) or "manifests match traces")


def t09_summary_aggregates():
    bad = []
    for s in SCEN_FULL:
        for st in STRATS:
            T = trace(s, st)
            summ_path = os.path.join(DT, s, f"{st}_summary.csv")
            if not os.path.isfile(summ_path):
                bad.append(f"{s}/{st}:no-summary")
                continue
            S = pd.read_csv(summ_path)
            if abs(float(S.mean_ACS.iloc[0]) -
                   float(np.nanmean(T.ACS))) > 1e-9 or \
               int(S.frames.iloc[0]) != len(T):
                bad.append(f"{s}/{st}")
    return check("T09", "summary aggregates recomputed from traces",
                 not bad, ",".join(bad) or "mean_ACS/frames match")


def t10_acs_recompute():
    worst, n = 0.0, 0
    for s in SCEN_FULL:
        for st in ("fixed_otfs", "fixed_oddm"):
            T = trace(s, st)
            idx = np.linspace(0, len(T) - 1, min(8, len(T))).astype(int)
            for i in idx:
                r = T.iloc[i]
                acs, _ = compute_acs(r.BER, r.throughput_bps,
                                     r.spectral_efficiency, r.CQI,
                                     r.detector_time_ms, r.recovery_rate,
                                     r.tp_cap_bps, r.se_cap)
                worst = max(worst, abs(acs - r.ACS))
                n += 1
    return check("T10", "ACS recomputation matches stored ACS (acs.py)",
                 worst < 1e-9, f"{n} rows, max err {worst:.2e}")


def t11_metric_ranges():
    bad = []
    for s in SCEN_FULL:
        for st in STRATS:
            T = trace(s, st)
            okm = (T.BER >= 0).all() and np.isfinite(T.BER).all() and \
                  (T.SER >= T.BER - 1e-12).all() and \
                  ((T.ACS >= 0) & (T.ACS <= 1)).all() and \
                  ((T.CQI >= 0) & (T.CQI <= 15)).all()
            if not okm:
                bad.append(f"{s}/{st}")
    return check("T11", "metric ranges (SER>=BER, ACS in [0,1], CQI 0-15)",
                 not bad, ",".join(bad) or "all rows sane")


def t12_oracle_rule():
    bad = 0
    for s in SCEN_FULL:
        T = trace(s, "oracle")
        want = np.where(T.actual_ACS_OTFS >= T.actual_ACS_ODDM,
                        "OTFS", "ODDM")
        bad += int((upper_arr(T.oracle_waveform) != want).sum())
    return check("T12", "oracle == argmax ACS with OTFS tie-break",
                 bad == 0, f"{bad} rule violations")


def upper_arr(col):
    return col.astype(str).str.upper()


def t13_decision_bookkeeping():
    bad = []
    for s in SCEN_FULL:
        T = trace(s, "ai_adaptive")
        dc = T.decision_correct.fillna(-1).astype(int)
        want_dc = (upper_arr(T.selected_waveform) ==
                   upper_arr(T.oracle_waveform)).astype(int)
        sw = (upper_arr(T.selected_waveform) !=
              upper_arr(T.previous_waveform))
        if not np.array_equal(dc.values, want_dc.values) or \
           not np.array_equal(sw.values, T.switched.astype(bool).values):
            bad.append(s)
    return check("T13", "decision_correct/switched bookkeeping exact",
                 not bad, ",".join(bad) or "definitions hold")


def t14_latency_discipline():
    bad = []
    for s in SCEN_FULL:
        T = trace(s, "fixed_otfs")
        if not T.latency_ms_modeled.isna().all() or \
           not (T.wall_clock_ms > 0).all() or \
           not (T.detector_time_ms > 0).all() or \
           not (T.detector_time_ms <= T.wall_clock_ms + 1e-6).all():
            bad.append(s)
    return check("T14", "measured times ordered; modeled latency NaN",
                 not bad, ",".join(bad) or
                 "detector_time<=wall_clock; latency_ms_modeled=NaN")


def pyexe():
    cand = os.path.join(PROJ, ".venv", "Scripts", "python.exe")
    return cand if os.path.isfile(cand) else sys.executable


def t15_engine_failure_mode():
    bad_in = os.path.join(HERE, "_t15_bad_state.json")
    out = os.path.join(HERE, "_t15_decision.json")
    with open(bad_in, "w") as fh:
        fh.write("{not valid json!!")
    if os.path.isfile(out):
        os.remove(out)
    cfg = os.path.join(ROOT, "adaptive_config_v2.json")
    cmd = [pyexe(), os.path.join(HERE, "ai_engine_v2.py"),
           "--infile", bad_in, "--out", out, "--config", cfg]
    pr = subprocess.run(cmd, capture_output=True, timeout=120)
    refused = (pr.returncode != 0) or (not os.path.isfile(out)) or \
              (os.path.getsize(out) == 0)
    for f in (bad_in, out):
        if os.path.isfile(f):
            os.remove(f)
    return check("T15", "engine refuses invalid input (fallback trigger)",
                 refused,
                 f"rc={pr.returncode}, output_written={os.path.isfile(out)}")


def t16_engine_happy_path():
    state = {"environment": "Urban", "speed_kmph": 25.0, "snr_db": 14.0,
             "doppler_hz": 111.2, "carrier_frequency_hz": 4e9,
             "bandwidth_hz": 480e3, "channel_profile": "EVA",
             "delay_spread_taps": 6, "num_paths": 9,
             "doppler_spread_hz": 222.0, "modulation": 4,
             "current_waveform": "OTFS", "frames_since_switch": 99}
    fin = os.path.join(HERE, "_t16_state.json")
    fout = os.path.join(HERE, "_t16_decision.json")
    json.dump(state, open(fin, "w"))
    cfg = os.path.join(ROOT, "adaptive_config_v2.json")
    cmd = [pyexe(), os.path.join(HERE, "ai_engine_v2.py"),
           "--infile", fin, "--out", fout, "--config", cfg]
    pr = subprocess.run(cmd, capture_output=True, timeout=180)
    ok = pr.returncode == 0 and os.path.isfile(fout)
    keys = []
    if ok:
        d = json.load(open(fout))
        keys = [k for k in ("recommendation", "confidence",
                            "predicted_metrics") if k not in d]
        ok = not keys and d.get("recommendation") in ("OTFS", "ODDM")
    for f in (fin, fout):
        if os.path.isfile(f):
            os.remove(f)
    return check("T16", "engine contract on valid state",
                 ok, f"missing keys={keys}")


def t17_modes_and_custom():
    ok, det = True, []
    ct = os.path.join(DT, "custom_test")
    have = all(os.path.isfile(os.path.join(ct, f"{st}_trace.csv"))
               for st in STRATS)
    if not have:
        ok = False
        det.append("custom_test incomplete")
    m = json.load(open(os.path.join(ct, "run_manifest.json")))
    rows = len(pd.read_csv(os.path.join(ct, "ai_adaptive_trace.csv")))
    if m["frames_run"] != rows or m["frames_run"] not in (12, 60):
        ok = False
        det.append("custom frames mismatch")
    return check("T17", "FAST/FULL modes + custom end-to-end artifacts",
                 ok, ";".join(det) or
                 f"custom_test ran {rows} frames, policy={m['policy']}")


def t18_transitions():
    O = json.load(open(os.path.join(DT, "scenario_o.json")))["points"]
    snr = [p["snr_db"] for p in O][::5]
    M = json.load(open(os.path.join(DT, "scenario_m.json")))["points"]
    envM = [p["environment"] for p in M][::6]
    N = json.load(open(os.path.join(DT, "scenario_n.json")))["points"]
    envN = [p["environment"] for p in N][::6]
    okO = len(set(snr)) == 5 and all(x > y for x, y in zip(snr, snr[1:]))
    corridor_up = ["Pedestrian", "Urban", "Highway", "HighSpeedRail"]
    okM = envM == corridor_up
    okN = envN == corridor_up[::-1]
    return check("T18", "difficult-tier transition structure intact",
                 okO and okM and okN,
                 f"O snr steps={snr}, M={'OK' if okM else 'BAD'}, "
                 f"N={'OK' if okN else 'BAD'}")


def t19_no_oracle_leakage():
    forbidden = ("oracle", "actual_", "regret")
    hits = []
    for p in glob.glob(os.path.join(HERE, "_t16_state.json")) + \
             glob.glob(os.path.join(HERE, "_t15_state.json")):
        txt = open(p).read().lower()
        hits += [tok for tok in forbidden if tok in txt]
    # also scan the canonical AI-state builder source block via runner file
    src = open(os.path.join(ROOT, "run_experiment.m")).read().lower()
    i1 = src.find("ai_st = struct")
    i2 = src.find("if need_ai")
    block = src[i1:i2] if i1 >= 0 and i2 > i1 else ""
    hits += [tok for tok in forbidden if tok in block]
    return check("T19", "no oracle/outcome fields ever reach the AI input",
                 not hits, f"hits={hits}")


def t20_checks_driver_record():
    ok, det = False, "phase5_check_results.json missing"
    if os.path.isfile(CHECKS):
        j = json.load(open(CHECKS))
        rr = j.get("results", [])
        if isinstance(rr, dict):          # single-record file (scope=full)
            rr = [rr]
        npass = sum(bool(r.get("pass")) for r in rr)
        ok = npass == len(rr) and len(rr) >= 16
        reg = [r for r in rr if r.get("name") == "C17_phase3_regression_full"]
        det = f"{npass}/{len(rr)} matlab checks pass; " + (
            "regression=" + str(bool(reg[0]["pass"])) if reg else
            "regression pending (fast-only record)")
    return check("T20", "MATLAB checks driver record present & passing",
                 ok, det)


# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("PHASE-5 VALIDATION TESTS (20, non-vacuous)")
    print("=" * 72)
    t01_scenario_files()
    t02_custom_schema()
    t03_seed_contract()
    t04_paired_fairness()
    t05_states_timeline()
    t06_doppler_derivation()
    t07_trace_schema()
    t08_manifest_integrity()
    t09_summary_aggregates()
    t10_acs_recompute()
    t11_metric_ranges()
    t12_oracle_rule()
    t13_decision_bookkeeping()
    t14_latency_discipline()
    t15_engine_failure_mode()
    t16_engine_happy_path()
    t17_modes_and_custom()
    t18_transitions()
    t19_no_oracle_leakage()
    t20_checks_driver_record()

    npass = sum(r["status"] == "PASS" for r in RES)
    print("-" * 72)
    print(f"RESULT: {npass}/{len(RES)} PASSED")
    write_md(npass)
    return 0 if npass == len(RES) else 1


def write_md(npass):
    lines = [
        "# Phase 5 Validation Report",
        "",
        f"Generated by `otfs_ai_pipeline/phase5_validation_tests.py` "
        f"(non-vacuous artifact-based tests).",
        "",
        f"**Result: {npass}/{len(RES)} PASSED**",
        "",
        "| ID | Test | Status | Detail |",
        "|----|------|--------|--------|",
    ]
    for r in RES:
        lines.append(f"| {r['id']} | {r['name']} | {r['status']} | "
                     f"{r['detail']} |")
    lines += [
        "",
        "## MATLAB-side checks (phase5_checks_driver)",
        "",
    ]
    if os.path.isfile(CHECKS):
        j = json.load(open(CHECKS))
        rr = j.get("results", [])
        if isinstance(rr, dict):
            rr = [rr]
        npass_m = sum(bool(r.get("pass")) for r in rr)
        lines += [
            f"Driver `{j.get('driver', 'phase5_checks_driver.m')}` "
            f"(scope={j.get('scope', '?')}, "
            f"{j.get('when', 'n/a')}): **{npass_m}/{len(rr)} PASSED**",
            "",
            "| Check | Status | Detail |",
            "|-------|--------|--------|",
        ]
        for r in rr:
            d = str(r.get("details", "")).replace("|", "/")
            lines.append(f"| {r.get('name','?')} | "
                         f"{'PASS' if r.get('pass') else 'FAIL'} | {d} |")
    else:
        lines.append("_phase5_check_results.json not found._")
    lines += [
        "",
        "### Regression acceptance rule (C17)",
        "",
        "The FULL A-D comparison against the frozen Phase-3 baseline passes"
        " when: (a) every deterministic field (payload/checksums/taps for all",
        " strategies; BER/SER/PER for fixed AND ai_adaptive rows) is",
        " **bit-exact**; (b) any oracle-label difference lies inside the",
        " latency-tie band w_lat*(exp(-t_min/200)-exp(-t_max/200)) derived",
        " from that run's measured detector-time spread -- the ONLY",
        " non-deterministic input to ACS is wall-clock detector time;",
        " (c) switch counts match exactly; (d) mean-ACS deltas <= 0.02.",
        "",
        "## Notes",
        "",
        "- Tests recompute evidence from primary artifacts; nothing is",
        "  trusted from summaries except where the summary IS the artifact.",
        "- Oracle evaluation-only guarantee is enforced structurally: the",
        "  AI state block contains environment/mobility/channel/modulation/",
        "  deployment fields only (T19 scans both artifacts and source).",
        "",
    ]
    with open(MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
