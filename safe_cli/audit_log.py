"""GDPR-compliant local audit logging — one JSON file per run."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


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
        detected_language: Optional[str] = None,
        language_warning: bool = False,
        article9_categories: Optional[List[str]] = None,
    ) -> Path:
        ts = datetime.now(timezone.utc)
        log_file = self.log_dir / f"{ts.strftime('%Y%m%d_%H%M%S')}_{input_path.stem}.json"

        entry: Dict = {
            "timestamp": ts.isoformat(),
            "input_file": input_path.name,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "detected_language": detected_language or "unknown",
            "language_warning": language_warning,
            "article9_categories_detected": article9_categories or [],
            "article9_manual_review_required": bool(article9_categories),
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
