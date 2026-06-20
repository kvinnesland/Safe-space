"""GDPR-compliant local audit logging — one JSON file per run."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


class AuditLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        input_path: Path,
        output_path: Path,
        stats: Dict[str, int],
        status: str = "success",
        error: str = "",
        detected_language: str = "",
        language_warning: bool = False,
    ) -> Path:
        ts = datetime.now(timezone.utc)
        log_file = self.log_dir / f"{ts.strftime('%Y%m%d_%H%M%S')}_{input_path.stem}.json"

        entry = {
            "timestamp": ts.isoformat(),
            "input_file": input_path.name,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "detected_language": detected_language or "unknown",
            "language_warning": language_warning,
            "pii_found": stats,
            "total_replacements": sum(stats.values()),
            "status": status,
        }
        if error:
            entry["error"] = error
        if language_warning:
            entry["manual_review_required"] = True

        log_file.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return log_file
