"""
mobility_model.py -- physical mobility/Doppler calculations.

fD = (v / c) * fc          (maximum Doppler shift)

Pure software model of the virtual mover; no hardware involved.
"""

C_LIGHT = 299792458.0


def speed_mps(speed_kmph: float) -> float:
    return float(speed_kmph) * 1000.0 / 3600.0


def doppler_hz(speed_kmph: float, carrier_frequency_hz: float) -> float:
    """Maximum Doppler shift fD = v/c * fc."""
    return speed_mps(speed_kmph) / C_LIGHT * float(carrier_frequency_hz)


def doppler_category(fD: float) -> str:
    """Qualitative label used by the dashboard/twin logs."""
    if fD < 25:
        return "Low"
    if fD < 150:
        return "Medium"
    if fD < 600:
        return "High"
    return "VeryHigh"


def timeline(times_s, speeds_kmph, carrier_frequency_hz):
    """Vectorized helper: returns (dopplers, categories) for a whole trace."""
    dop = [doppler_hz(v, carrier_frequency_hz) for v in speeds_kmph]
    return dop, [doppler_category(d) for d in dop]
