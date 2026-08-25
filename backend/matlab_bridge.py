"""MATLAB bridge — subprocess communication with the canonical MATLAB runtime.

Phase 9.1 fix: Uses subprocess.Popen instead of subprocess.run to enable
cancellation of MATLAB processes during PAUSE/STOP. Tracks per-run
subprocess handles and supports safe termination.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .config import MATLAB_EXECUTABLE, MATLAB_DIR

logger = logging.getLogger(__name__)


class MATLABBridge:
    """Communicates with MATLAB via subprocess calls.

    Phase 9.1: Added Popen-based frame execution with process tracking
    so that PAUSE and STOP can terminate the active MATLAB subprocess.
    """

    def __init__(self, matlab_exe: Optional[str] = None):
        self.matlab_exe = matlab_exe or MATLAB_EXECUTABLE
        self._available: Optional[bool] = None
        self._work_dir = Path(tempfile.mkdtemp(prefix="dt8_matlab_"))
        self._current_process: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                [self.matlab_exe, "-batch", "disp('ok')"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(MATLAB_DIR),
            )
            self._available = result.returncode == 0 and "ok" in result.stdout
        except Exception as e:
            logger.warning("MATLAB availability check failed: %s", e)
            self._available = False
        return self._available

    def check_available_async(self):
        """Start availability check in background (non-blocking)."""
        import threading

        def _check():
            try:
                result = subprocess.run(
                    [self.matlab_exe, "-batch", "disp('ok')"],
                    capture_output=True, text=True, timeout=60,
                    cwd=str(MATLAB_DIR),
                )
                self._available = result.returncode == 0 and "ok" in result.stdout
            except Exception:
                self._available = False

        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def run_frame(
        self,
        scenario_json: str,
        frame: int,
        strategy: str,
        policy: str,
        seed0: int = 20260823,
    ) -> dict:
        """Execute one frame via dt_step_frame.m.

        Phase 9.1: Uses Popen and stores the process handle so
        terminate_current() can kill it during PAUSE/STOP.
        """
        state_in = self._work_dir / "_state_in.json"
        result_out = self._work_dir / "_result_out.json"

        state_in.write_text(scenario_json, encoding="utf-8")

        matlab_cmd = (
            f"cd('{MATLAB_DIR.as_posix()}'); "
            f"scenario_json = fileread('{state_in.as_posix()}'); "
            f"result_json = dt_step_frame(scenario_json, {frame}, "
            f"'{strategy}', '{policy}', {seed0}); "
            f"fid = fopen('{result_out.as_posix()}', 'w'); "
            f"fwrite(fid, result_json); fclose(fid);"
        )

        try:
            proc = subprocess.Popen(
                [self.matlab_exe, "-batch", matlab_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(MATLAB_DIR),
            )
            self._current_process = proc
            try:
                stdout, stderr = proc.communicate(timeout=120)
            finally:
                if self._current_process is proc:
                    self._current_process = None

            if proc.returncode != 0:
                logger.error("MATLAB stderr: %s", stderr[:2000] if stderr else "")
                return {"error": True, "error_message": (stderr[:500] if stderr else "unknown error")}
            if not result_out.exists():
                return {"error": True, "error_message": "No output file produced"}
            return json.loads(result_out.read_text(encoding="utf-8"))
        except subprocess.TimeoutExpired:
            if self._current_process is proc:
                self._current_process = None
            proc.kill()
            proc.wait()
            return {"error": True, "error_message": "MATLAB timeout (120s)"}
        except Exception as e:
            if self._current_process is proc:
                self._current_process = None
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
            return {"error": True, "error_message": str(e)}

    def terminate_current(self):
        """Phase 9.1: Kill the active MATLAB subprocess, if any.

        Only terminates the process created by the current run.
        Does NOT use taskkill /IM matlab.exe or kill all MATLAB processes.
        """
        proc = self._current_process
        if proc is not None:
            try:
                logger.info("Terminating MATLAB subprocess PID=%s", proc.pid)
                proc.kill()
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("MATLAB process did not terminate in 10s, force kill")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            except Exception as e:
                logger.warning("Error terminating MATLAB process: %s", e)
            finally:
                if self._current_process is proc:
                    self._current_process = None

    def cleanup(self):
        """Clean up temporary files and any remaining process."""
        self.terminate_current()
        try:
            for p in self._work_dir.iterdir():
                p.unlink(missing_ok=True)
            self._work_dir.rmdir()
        except Exception:
            pass
