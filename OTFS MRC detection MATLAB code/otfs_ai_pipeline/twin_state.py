"""
twin_state.py -- central Digital Twin state object (spec section 9).

One dataclass instance is updated after every simulated frame and serialized
to the live state file consumed by the dashboard / MATLAB runtime.
"""

from dataclasses import dataclass, field, asdict
import time


def _clean(v):
    try:
        import numpy as np
        if isinstance(v, (np.floating, np.integer)):
            return v.item()
    except Exception:
        pass
    return v


@dataclass
class TwinState:
    # --- identity/time -----------------------------------------------------
    timestamp: str = ""
    frame: int = -1
    t_s: float = 0.0
    scenario_id: str = "drive60"
    strategy: str = "ai_adaptive"          # fixed_otfs | fixed_oddm | ai_adaptive

    # --- environment / mobility ---------------------------------------------
    environment: str = ""
    speed_kmph: float = 0.0
    snr_db: float = 0.0
    doppler_hz: float = 0.0
    doppler_category: str = ""
    carrier_frequency_hz: float = 4e9
    bandwidth_hz: float = 480e3            # M * delta_f (N=M=32, df=15 kHz)
    delay_profile: str = ""
    delay_spread_taps: int = 0
    num_paths: int = 0

    # --- link configuration ---------------------------------------------------
    modulation: int = 4
    waveform: str = ""                     # currently selected
    detector: str = ""

    # --- measured frame metrics -------------------------------------------------
    BER: float = None
    SER: float = None
    PER: float = None
    throughput_bps: float = None
    spectral_efficiency: float = None
    CQI: float = None
    latency_ms: float = None
    packet_loss: float = None
    recovery_rate: float = None
    ACS: float = None

    # --- AI layer ------------------------------------------------------------------
    ai_recommendation: str = ""
    ai_confidence: float = None
    predicted_ACS_otfs: float = None
    predicted_ACS_oddm: float = None
    predicted_waveform_metrics: dict = field(default_factory=dict)
    switch_reason: str = ""
    previous_waveform: str = ""
    switched: bool = False

    def update_environment(self, point) -> None:
        """Apply a scenario.ScenarioPoint."""
        from mobility_model import doppler_hz, doppler_category
        self.t_s = point.t_s
        self.frame = point.frame
        self.environment = point.environment
        self.speed_kmph = point.speed_kmph
        self.snr_db = point.snr_db
        self.delay_profile = point.delay_profile
        self.doppler_scale = point.doppler_scale
        self.doppler_hz = doppler_hz(point.speed_kmph,
                                     self.carrier_frequency_hz) \
            * point.doppler_scale
        self.doppler_category = doppler_category(self.doppler_hz)
        self.modulation = point.modulation

    def apply_result(self, res: dict) -> None:
        """Merge one waveform run's metrics (dict from JSON row)."""
        for k in ("BER", "SER", "PER", "throughput_bps", "spectral_efficiency",
                  "CQI", "latency_ms", "packet_loss", "recovery_rate", "ACS"):
            if k in res:
                setattr(self, k, _clean(res[k]))

    def to_dict(self) -> dict:
        return {k: _clean(v) for k, v in asdict(self).items()}

    @staticmethod
    def now_stamp() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")
