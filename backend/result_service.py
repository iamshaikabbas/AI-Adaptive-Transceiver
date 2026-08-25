"""Result service — persistence for live simulation runs."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import LIVE_SIM_DIR

logger = logging.getLogger(__name__)


class ResultService:
    """Manages persistence for live simulation runs to Results/LiveSimulation/."""

    def __init__(self):
        LIVE_SIM_DIR.mkdir(parents=True, exist_ok=True)

    def create_run(self, run_id: str, config: dict) -> Path:
        run_dir = LIVE_SIM_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        config_path = run_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return run_dir

    def append_frame(self, run_id: str, frame_data: dict) -> None:
        run_dir = LIVE_SIM_DIR / run_id
        frames_csv = run_dir / "frames.csv"
        header_written = frames_csv.exists() and frames_csv.stat().st_size > 0
        try:
            with open(frames_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=sorted(frame_data.keys()))
                if not header_written:
                    writer.writeheader()
                writer.writerow(frame_data)
        except Exception as e:
            logger.error("Failed to append frame: %s", e)

    def write_event(self, run_id: str, event: dict) -> None:
        run_dir = LIVE_SIM_DIR / run_id
        events_path = run_dir / "events.jsonl"
        try:
            with open(events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error("Failed to write event: %s", e)

    def write_manifest(self, run_id: str, manifest: dict) -> None:
        run_dir = LIVE_SIM_DIR / run_id
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def write_results_csv(self, run_id: str, results: list[dict]) -> None:
        if not results:
            return
        run_dir = LIVE_SIM_DIR / run_id
        results_csv = run_dir / "results.csv"
        try:
            with open(results_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=sorted(results[0].keys()))
                writer.writeheader()
                for row in results:
                    writer.writerow(row)
        except Exception as e:
            logger.error("Failed to write results CSV: %s", e)

    def list_runs(self) -> list[str]:
        if not LIVE_SIM_DIR.exists():
            return []
        return sorted(
            [d.name for d in LIVE_SIM_DIR.iterdir() if d.is_dir()],
            reverse=True,
        )

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        p = LIVE_SIM_DIR / run_id
        return p if p.is_dir() else None
