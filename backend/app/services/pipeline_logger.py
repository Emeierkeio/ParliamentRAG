"""
Per-query pipeline run logger.

Captures timing, metrics, and diagnostics for every pipeline run.
Saves each run as a timestamped JSON file in logs/pipeline_runs/.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pipeline runs log directory
_LOG_DIR = Path(__file__).parent.parent.parent / "logs" / "pipeline_runs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


class PipelineRunLogger:
    """Tracks and persists a single pipeline run's metrics."""

    def __init__(self, query: str, chamber: str = "both"):
        self.query = query
        self.chamber = chamber
        self.start_time = time.perf_counter()
        self.timestamp = datetime.now()
        self.stages: Dict[str, Dict[str, Any]] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self._current_stage: Optional[str] = None
        self._stage_start: float = 0.0

    def start_stage(self, name: str) -> None:
        """Mark the beginning of a pipeline stage."""
        self._current_stage = name
        self._stage_start = time.perf_counter()
        logger.info(f"[PIPELINE] ── {name} ──")

    def end_stage(self, name: str, **metrics) -> float:
        """Mark the end of a pipeline stage. Returns elapsed seconds."""
        elapsed = time.perf_counter() - self._stage_start
        self.stages[name] = {
            "elapsed_s": round(elapsed, 3),
            **metrics,
        }
        summary_parts = [f"{elapsed:.1f}s"]
        for k, v in metrics.items():
            summary_parts.append(f"{k}={v}")
        logger.info(f"[PIPELINE]    ✓ {name}: {', '.join(summary_parts)}")
        self._current_stage = None
        return elapsed

    def warn(self, msg: str) -> None:
        """Record a warning."""
        self.warnings.append(msg)
        logger.warning(f"[PIPELINE]    ⚠ {msg}")

    def error(self, msg: str) -> None:
        """Record an error."""
        self.errors.append(msg)
        logger.error(f"[PIPELINE]    ✗ {msg}")

    def save(self) -> Path:
        """Persist the run log as a JSON file. Returns the file path."""
        total_elapsed = time.perf_counter() - self.start_time
        ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
        # Sanitize query for filename (first 40 chars, alphanumeric + underscore)
        q_slug = "".join(c if c.isalnum() else "_" for c in self.query[:40]).strip("_")
        filename = f"run_{ts}_{q_slug}.json"
        filepath = _LOG_DIR / filename

        run_data = {
            "timestamp": self.timestamp.isoformat(),
            "query": self.query,
            "chamber": self.chamber,
            "total_elapsed_s": round(total_elapsed, 3),
            "stages": self.stages,
            "warnings": self.warnings,
            "errors": self.errors,
        }

        try:
            filepath.write_text(json.dumps(run_data, indent=2, default=str), encoding="utf-8")
            logger.info(f"[PIPELINE] Run log saved: {filepath.name} ({total_elapsed:.1f}s total)")
        except Exception as e:
            logger.error(f"[PIPELINE] Failed to save run log: {e}")

        return filepath

    def summary_line(self) -> str:
        """One-line summary for console output."""
        total = time.perf_counter() - self.start_time
        stage_times = " → ".join(
            f"{name}:{info['elapsed_s']:.1f}s" for name, info in self.stages.items()
        )
        return f"[PIPELINE] {self.query[:50]}… | {total:.1f}s total | {stage_times}"
