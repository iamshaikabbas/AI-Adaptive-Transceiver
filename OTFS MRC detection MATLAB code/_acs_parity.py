"""_acs_parity.py -- Phase 1 certification helper (temporary).

Runs three metric vectors through BOTH canonical ACS implementations
(MATLAB compute_acs.m and otfs_ai_pipeline/acs.py) and asserts agreement
to <1e-12 on the composite score and every component score.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "otfs_ai_pipeline"))

from acs import compute_acs, load_weights

VECTORS = [
    # ber      tp_bps    se    cqi  lat_ms  rec   tp_cap    se_cap
    [1e-4, 1.2e6, 2.5, 12, 45, 0.97, 1.92e6, 6],
    [5e-2, 3.0e5, 1.2, 6, 120, 0.50, 1.92e6, 6],
    [1.0, 10.0, 0.05, 1, 400, 0.00, 1.92e6, 2],
]

ML_CMD = (
    "T = [" + ";".join(" ".join(repr(x) for x in v) for v in VECTORS) + "];\n"
    "for t = 1:size(T,1)\n"
    "  v = T(t,:);\n"
    "  [a,p] = compute_acs(v(1),v(2),v(3),v(4),v(5),v(6),v(7),v(8));\n"
    "  fprintf('%.17g %.17g %.17g %.17g %.17g %.17g %.17g\\n', a, "
    "p.BER, p.Throughput, p.SE, p.CQI, p.Latency, p.Recovery);\n"
    "end"
)

ml = subprocess.run(
    [r"C:\MY DATA ANALYTICS FILES AND PROJECTS\Matlab\bin\matlab.exe",
     "-batch", ML_CMD],
    cwd=HERE, capture_output=True, text=True, timeout=600)
lines = [ln for ln in ml.stdout.splitlines() if ln and ln[0].isdigit()]
assert len(lines) == len(VECTORS), f"MATLAB output parse failed:\n{ml.stdout}\n{ml.stderr}"

w = load_weights()
ok = True
for i, (line, v) in enumerate(zip(lines, VECTORS)):
    mvals = [float(x) for x in line.split()]
    py_acs, s = compute_acs(*v[:6], *v[6:], w)
    pyvals = [py_acs, s["BER"], s["Throughput"], s["SE"],
              s["CQI"], s["Latency"], s["Recovery"]]
    diffs = [abs(a - b) for a, b in zip(mvals, pyvals)]
    status = "OK" if max(diffs) < 1e-12 else "MISMATCH"
    ok &= max(diffs) < 1e-12
    print(f"vector {i+1}: ACS_ml={mvals[0]:.15f} ACS_py={pyvals[0]:.15f} "
          f"max|diff|={max(diffs):.3g} {status}")

print("ACS PARITY:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
