"""
_regen_cmp_csvs_from_raw.py
===========================
Phase 1 one-off repair: the seven cmp_*.csv files written by the OLD
save_compare_results.m are malformed -- each data row accidentally embeds
the full per-trial metric VECTORS (fprintf expands vector arguments over
every row), so a 14-name header sits on top of 68..188-field rows.

The measured data is still fully recoverable: every raw row contains, in
order,

    <xval>, label, waveform, detector,
    BER[nT], SER[nT], PER_mean,
    Throughput_bps[nT], SpectralEfficiency[nT],
    CQI_mean, SINR_mean,
    EVM_percent[nT], Latency_ms[nT], Run_mean          (nT = n_trials)

This script parses those vectors and rewrites each file with EXACTLY the
schema produced by the FIXED save_compare_results.m (scalars only):

    <xname>,label,waveform,detector,
    BER_total,SER_total,PER_mean,Thr_mean,SE_mean,EVM_mean,
    CQI_mean,SINR_mean,Lat_mean,Run_mean

Aggregation formulas mirror run_paired_trials.m verbatim:

    BER_total = round(sum(BER) * N_bits) / (N_bits * nT)
    SER_total = round(sum(SER) * N_syms) / (N_syms * nT)
    *_mean    = arithmetic mean

N_bits/N_syms come from each compare_otfs_oddm_*.m configuration:
N_syms = (M - Lg)*N with Lg = max(max_delay_tap+1, ceil(M/16)) and the
realized profile max delay tap (authoritative values verified against
waveform_dataset.csv DelaySpread column; tap rule round(delay_ns*M*df)):
    EPA/EVA/RayleighFlat @32x32 -> 960   ETU -> 928
multipath: max_tap = P-1 (P>=2), 0 for P=1  -> 960,960,928,...,704
runtime (EVA): M=16->tap 1,Lg2->224 | M=32->960 | M=48->tap 2,Lg3->2160

Nothing is fabricated: all aggregates derive from the stored measurements.
Run from this directory:  python _regen_cmp_csvs_from_raw.py
"""

import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "Results", "WaveformComparison")

# ---- per-experiment payload sizing (see module docstring) -----------------
NSYM_32 = {"RayleighFlat": 960, "EPA": 960, "EVA": 960, "ETU": 928}
EXPERIMENTS = {
    #  tag            xname           N_bits(xrow-index j)                n_rows  n_x
    "cmp_snr":       ("SNR_dB",       lambda j: 1920,                     11),
    "cmp_velocity":  ("Speed_kmph",   lambda j: 1920,                     11),
    "cmp_doppler":   ("DopplerScale", lambda j: 1920,                     11),
    "cmp_channel":   ("ProfileIdx",   lambda j: 2 * NSYM_32[
                     ["RayleighFlat", "EPA", "EVA", "ETU"][j]],           4),
    "cmp_multipath": ("NumPaths",     lambda j: 2 * [960, 960, 928, 896,
                                     864, 832, 800, 768, 736, 704][j],   10),
    "cmp_detector":  ("CondIdx",      lambda j: 1920,                      2),
    "cmp_runtime":   ("NM",           lambda j: [448, 1920, 4320][j],      3),
}

NEW_COLS = ["BER_total", "SER_total", "PER_mean", "Thr_mean", "SE_mean",
            "EVM_mean", "CQI_mean", "SINR_mean", "Lat_mean", "Run_mean"]


def parse_row(fields):
    """Split one malformed data row into labels + ordered metric fields."""
    xval, label, wf, det = fields[:4]
    vals = [float(v) for v in fields[4:]]
    n = (len(vals) - 4) // 6                      # trials per point
    assert len(vals) == 6 * n + 4, f"unexpected field count {len(vals)}"
    return xval, label, wf, det, vals, n


def main():
    for tag, (xname, nbits_of, n_x) in EXPERIMENTS.items():
        path = os.path.join(RES, tag + ".csv")
        with open(path) as fh:
            lines = [ln.rstrip("\n") for ln in fh if ln.strip()]
        old_header = lines[0].split(",")
        assert len(old_header) == 14, f"{tag}: unexpected header"

        out_lines = [",".join([xname, "label", "waveform", "detector"]
                              + NEW_COLS)]
        for r, ln in enumerate(lines[1:]):
            j = r % n_x          # writer loops combos-outer / points-inner
            xval, label, wf, det, v, n = parse_row(ln.split(","))
            ber, ser = v[0:n], v[n:2 * n]
            per_mean = v[2 * n]
            tp = v[2 * n + 1:3 * n + 1]
            se = v[3 * n + 1:4 * n + 1]
            cqi_mean, sinr_mean = v[4 * n + 1], v[4 * n + 2]
            evm = v[4 * n + 3:5 * n + 3]
            lat = v[5 * n + 3:6 * n + 3]
            run_mean = v[6 * n + 3]

            nbits = nbits_of(j)
            nsyms = nbits // 2   # all seven sweeps use QPSK (log2(M)=2)
            ber_total = round(sum(ber) * nbits) / (nbits * n)
            ser_total = round(sum(ser) * nsyms) / (nsyms * n)
            row = [xval, label, wf, det,
                   f"{ber_total:.10g}", f"{ser_total:.10g}",
                   f"{per_mean:.10g}", f"{sum(tp)/n:.10g}",
                   f"{sum(se)/n:.10g}", f"{sum(evm)/n:.10g}",
                   f"{cqi_mean:.10g}", f"{sinr_mean:.10g}",
                   f"{sum(lat)/n:.10g}", f"{run_mean:.10g}"]
            out_lines.append(",".join(row))

        with open(path, "w") as fh:
            fh.write("\n".join(out_lines) + "\n")

        df = pd.read_csv(path)                    # immediate parse check
        assert list(df.columns) == out_lines[0].split(",")
        print(f"fixed {tag}.csv: {len(df)} rows x {len(df.columns)} cols "
              f"(nTrials/point recovered from raw vectors)")

    print("\nAll seven CSVs rewritten with scalar-aggregate schema.")


if __name__ == "__main__":
    main()
