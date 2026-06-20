"""CLI entrypoint for `safe` — anonymize files before passing to Claude."""

import sys
from datetime import datetime
from pathlib import Path

import click

from .audit_log import AuditLogger
from .engine import AnonymizerCore
from .handlers import get_handler
from .language import detect as detect_language, is_supported as lang_is_supported

DEFAULT_OUTPUT_DIR = Path("/app/safe-output")
DEFAULT_LOG_DIR = DEFAULT_OUTPUT_DIR / "logs"


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
    handler = get_handler(suffix)
    if handler is None:
        click.echo(
            f"Unsupported format '{suffix}'. Supported: .txt .csv .xlsx .docx .pdf .pptx",
            err=True,
        )
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = input_path.stem
    output_path = out_dir / f"{stem}_anonymized_{timestamp}{suffix}"

    click.echo("Detecting language ...", err=True)
    detected_lang = detect_language(input_path, suffix)
    lang_warning = not lang_is_supported(detected_lang)

    if lang_warning:
        click.echo(
            f"\nADVARSEL: Filen ser ut til å være på '{detected_lang}', "
            "som ikke er fullt dekket av anonymiseringsmotoren.\n"
            "Anonymisering gjennomføres, men output-filen MA sjekkes manuelt "
            "for PII før den deles med Claude.\n",
            err=True,
        )

    click.echo("Loading engine ...", err=True)
    engine = AnonymizerCore()

    click.echo(f"Anonymizing {input_path.name} ...", err=True)
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
            detected_language=detected_lang, language_warning=lang_warning,
        )
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    AuditLogger(log_dir).log(
        input_path, output_path, stats,
        status=status,
        detected_language=detected_lang,
        language_warning=lang_warning,
    )

    total = sum(stats.values())
    click.echo(f"\nReplaced {total} PII item(s):")
    for label, count in sorted(stats.items()):
        click.echo(f"  {label}: {count}")

    click.echo(f"\nAnonymized file: {output_path}")

    if lang_warning:
        click.echo(
            f"\nHUSK: Filen var pa '{detected_lang}' — sjekk output manuelt for PII."
        )


if __name__ == "__main__":
    cli()
