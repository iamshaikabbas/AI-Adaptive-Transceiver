"""
communication_quality.py
=========================
Single shared definition of "Communication Quality" (Excellent / Good /
Moderate / Poor), derived from BER, CQI and Throughput_bps.

Kept as its own tiny module (rather than duplicated in predict.py,
dashboard.py and graphs.py) so the classification rule is defined in exactly
one place -- see config.QUALITY_THRESHOLDS to tune it.

Throughput is judged *relative* to the best throughput achieved for the same
Modulation in the reference table passed in (typically the training
dataset), since "good throughput" means something different for QPSK vs
64QAM. If no reference table is available, an absolute Throughput_bps value
can be passed via `throughput_ref_bps` instead.
"""

import numpy as np
import pandas as pd

from config import QUALITY_LABELS, QUALITY_THRESHOLDS


def build_throughput_reference(df: pd.DataFrame) -> dict:
    """Per-Modulation 95th-percentile throughput, used as the 'near-ideal'
    denominator for throughput_frac. 95th percentile (not max) so a single
    noisy outlier row can't silently deflate every quality label."""
    if "Modulation" not in df.columns or "Throughput_bps" not in df.columns:
        return {}
    ref = df.groupby("Modulation")["Throughput_bps"].quantile(0.95).to_dict()
    return {k: float(v) if v and v > 0 else 1.0 for k, v in ref.items()}


def classify_quality_row(ber, cqi, throughput_bps, modulation=None,
                          throughput_ref: dict = None, throughput_ref_bps: float = None) -> str:
    """Classify a single (BER, CQI, Throughput_bps) triple into one of
    config.QUALITY_LABELS. Returns 'Poor' for anything malformed/NaN."""
    try:
        ber = float(ber)
        cqi = float(cqi)
        throughput_bps = float(throughput_bps)
    except (TypeError, ValueError):
        return "Poor"
    if not np.isfinite(ber) or not np.isfinite(cqi) or not np.isfinite(throughput_bps):
        return "Poor"

    if throughput_ref_bps and throughput_ref_bps > 0:
        denom = throughput_ref_bps
    elif throughput_ref and modulation in throughput_ref and throughput_ref[modulation] > 0:
        denom = throughput_ref[modulation]
    else:
        denom = max(throughput_bps, 1.0)  # degrade gracefully -> frac ~1.0

    throughput_frac = max(throughput_bps, 0.0) / denom

    for label, max_ber, min_cqi, min_frac in QUALITY_THRESHOLDS:
        if ber <= max_ber and cqi >= min_cqi and throughput_frac >= min_frac:
            return label
    return "Poor"


def classify_quality_frame(df: pd.DataFrame, ber_col="BER", cqi_col="CQI",
                            throughput_col="Throughput_bps", modulation_col="Modulation",
                            throughput_ref: dict = None) -> pd.Series:
    """Vectorised (row-wise) version of classify_quality_row for a whole
    DataFrame. Builds its own throughput reference from `df` if none given."""
    if throughput_ref is None:
        throughput_ref = build_throughput_reference(df)

    def _row(r):
        mod = r[modulation_col] if modulation_col in df.columns else None
        return classify_quality_row(
            r.get(ber_col, np.nan), r.get(cqi_col, np.nan), r.get(throughput_col, np.nan),
            modulation=mod, throughput_ref=throughput_ref,
        )

    return df.apply(_row, axis=1)


QUALITY_ORDER = {label: i for i, label in enumerate(QUALITY_LABELS)}  # Excellent=0 ... Poor=3
