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
    ) -> Path:
        ts = datetime.now(timezone.utc)
        log_file = self.log_dir / f"{ts.strftime('%Y%m%d_%H%M%S')}_{input_path.stem}.json"

        entry = {
            "timestamp": ts.isoformat(),
            "input_file": input_path.name,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "pii_found": stats,
            "total_replacements": sum(stats.values()),
            "status": status,
        }
        if error:
            entry["error"] = error

        log_file.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return log_file
