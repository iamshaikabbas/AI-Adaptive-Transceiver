"""
generate_synthetic_dataset.py
==============================
NOT part of the real Phase-1/Phase-2 pipeline. This only exists so you can
smoke-test train_model.py / predict.py / dashboard.py before your MATLAB
script has produced a real Results/OTFS_Dataset.csv.

Once you have the real CSV from MATLAB, delete/ignore this and just point
train_model.py at Results/OTFS_Dataset.csv as usual.

Usage: python generate_synthetic_dataset.py
"""

import numpy as np
import pandas as pd

from config import DATASET_FILE, RANDOM_STATE

rng = np.random.default_rng(RANDOM_STATE)

environments = pd.read_csv("environment_profiles.csv")
detectors = ["MRC", "LMMSE", "MPA"]
modulations = {"QPSK": 4, "16QAM": 16, "64QAM": 64}
snr_list = list(range(0, 31, 5))

# rough relative detector quality (lower factor -> lower BER for same SNR)
detector_quality = {"MRC": 1.0, "LMMSE": 0.6, "MPA": 0.35}
mod_penalty = {"QPSK": 1.0, "16QAM": 2.2, "64QAM": 4.5}

rows = []
for _, env in environments.iterrows():
    for scen_id in range(1, 6):  # 5 scenarios per environment
        speed = rng.uniform(env.SpeedMin, env.SpeedMax)
        delay_spread = rng.integers(1, 8)
        num_paths = rng.integers(2, 6)
        doppler_spread = env.DopplerScale * rng.uniform(0.8, 1.2)

        for mod_name, mod_order in modulations.items():
            for det in detectors:
                for snr in snr_list:
                    snr_lin = 10 ** (snr / 10)
                    q = detector_quality[det] * mod_penalty[mod_name]
                    ber = np.clip(0.5 * np.exp(-snr_lin / (2 * q)) + rng.normal(0, 0.001), 1e-7, 0.5)
                    ser = np.clip(ber * np.log2(mod_order), 1e-7, 1.0)
                    per = np.clip(1 - (1 - ber) ** 200, 0, 1)
                    evm_pct = np.clip(100 * np.sqrt(ber) * 2, 0.1, 100)
                    sinr_est = -20 * np.log10(max(evm_pct, 1e-6) / 100)

                    thresholds = [-6.7,-4.7,-2.3,0.2,2.4,4.3,5.9,8.1,10.3,11.7,14.1,16.3,18.7,21.0,22.7]
                    cqi = sum(1 for t in thresholds if sinr_est >= t)

                    n_bits = 64 * 60 * int(np.log2(mod_order))
                    throughput = n_bits * (1 - per) / (64 / 15e3)
                    bw = 64 * 15e3
                    se = throughput / bw
                    runtime = rng.uniform(0.05, 0.5) * (2 if det != "MRC" else 1)
                    avg_iter = {"MRC": rng.uniform(5, 50), "LMMSE": 1, "MPA": 10}[det]

                    rows.append({
                        "Environment": env.Environment, "Speed_kmh": round(speed),
                        "DelayProfile": env.DelayProfile, "DelaySpread": delay_spread,
                        "NumPaths": num_paths, "DopplerSpread": doppler_spread,
                        "Modulation": mod_name, "Detector": det, "SNR_dB": snr,
                        "BER": ber, "SER": ser, "PER": per, "EVM_percent": evm_pct,
                        "SINR_est_dB": sinr_est, "CQI": cqi, "Throughput_bps": throughput,
                        "SpectralEfficiency_bps_per_Hz": se, "Runtime_sec": runtime,
                        "AvgIterations": avg_iter, "ScenarioID": scen_id,
                        "Category": env.Category, "FocusMode": False,
                        "Timestamp": pd.Timestamp.now(),
                    })

df = pd.DataFrame(rows)
df.to_csv(DATASET_FILE, index=False)
print(f"Synthetic dataset written -> {DATASET_FILE} ({len(df)} rows)")
