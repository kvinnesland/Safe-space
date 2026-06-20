"""CLI entrypoint for `safe` — anonymize files before passing to Claude."""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click

from .article9 import scan as scan_article9
from .audit_log import AuditLogger
from .engine import AnonymizerCore
from .handlers import get_handler
from .language import detect as detect_language, is_supported as lang_is_supported
from .media import STANDALONE_MEDIA_EXT, standalone_warning

DEFAULT_OUTPUT_DIR = Path("/app/safe-output")
DEFAULT_LOG_DIR = DEFAULT_OUTPUT_DIR / "logs"


def _article9_warning(categories: List[str]) -> None:
    cats = ", ".join(categories)
    click.echo(
        f"\n{'='*60}\n"
        f"ADVARSEL — GDPR ARTIKKEL 9\n"
        f"{'='*60}\n"
        f"Dokumentet ser ut til å inneholde fritekst om:\n"
        + "".join(f"  • {c}\n" for c in categories)
        + "\n"
        "Under GDPR artikkel 9 er dette spesielt beskyttet persondata.\n"
        "Denne filen MA sjekkes manuelt for gjenvaerende PII\n"
        "for den deles med verktoy som kjorer utenfor EU/EOS.\n"
        f"{'='*60}"
    )


@click.command()
@click.argument("filepath", type=click.Path(exists=True, readable=True, path_type=Path))
@click.option(
    "--output-dir",
    default=str(DEFAULT_OUTPUT_DIR),
    show_default=True,
    help="Directory for anonymized output files.",
)
def cli(filepath: Path, output_dir: str) -> None:
    """Anonymize PII in FILEPATH and write the result to OUTPUT_DIR.

    The original file is never modified. All processing is fully local.
    """
    input_path = filepath.resolve()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "logs"

    suffix = input_path.suffix.lower()

    # Standalone media files cannot be automatically anonymized
    if suffix in STANDALONE_MEDIA_EXT:
        click.echo(standalone_warning(suffix))
        sys.exit(2)

    handler = get_handler(suffix)
    if handler is None:
        click.echo(
            f"Ikke stottet format '{suffix}'. Stottede formater: "
            ".txt .csv .xlsx .docx .pdf .pptx",
            err=True,
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = input_path.stem
    output_path = out_dir / f"{stem}_anonymized_{timestamp}{suffix}"

    # ── Pre-flight checks (fast regex scan — no engine needed) ───────────
    click.echo("Analyserer fil ...", err=True)
    detected_lang = detect_language(input_path, suffix)
    lang_warning = not lang_is_supported(detected_lang)
    article9_categories = scan_article9(input_path, suffix)

    if lang_warning:
        click.echo(
            f"\nADVARSEL: Filen ser ut til a vaere pa '{detected_lang}', "
            "som ikke er fullt dekket av anonymiseringsmotoren.\n"
            "Anonymisering gjennomfores, men output-filen MA sjekkes manuelt "
            "for PII for den deles med Claude.\n",
            err=True,
        )

    # ── Anonymization ─────────────────────────────────────────────────────
    click.echo("Laster anonymiseringsmotor ...", err=True)
    engine = AnonymizerCore()

    click.echo(f"Anonymiserer {input_path.name} ...", err=True)
    try:
        stats = handler(input_path, output_path, engine)
        status = "success"
        error = ""
    except Exception as exc:
        status = "error"
        error = str(exc)
        AuditLogger(log_dir).log(
            input_path, output_path, {},
            status=status, error=error,
            detected_language=detected_lang,
            language_warning=lang_warning,
            article9_categories=article9_categories,
        )
        click.echo(f"Feil: {exc}", err=True)
        sys.exit(1)

    AuditLogger(log_dir).log(
        input_path, output_path, stats,
        status=status,
        detected_language=detected_lang,
        language_warning=lang_warning,
        article9_categories=article9_categories,
    )

    # ── Summary ───────────────────────────────────────────────────────────
    total = sum(stats.values())
    click.echo(f"\nFerdig. {total} PII-element(er) anonymisert:")
    for label, count in sorted(stats.items()):
        click.echo(f"  {label}: {count}")

    click.echo(f"\nAnonymisert fil: {output_path}")

    # ── Post-processing warnings (shown once, after results) ──────────────
    if article9_categories:
        _article9_warning(article9_categories)
    elif lang_warning:
        click.echo(
            f"\nHUSK: Filen var pa '{detected_lang}' — sjekk output manuelt for PII."
        )


if __name__ == "__main__":
    cli()
