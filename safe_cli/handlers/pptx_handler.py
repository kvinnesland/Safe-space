from pathlib import Path
from typing import Dict, List, Optional

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Pt

from ..column_rules import placeholder_for_header
from ..engine import AnonymizerCore
from ..media import PLACEHOLDER_IMAGE, PLACEHOLDER_VIDEO, PLACEHOLDER_AUDIO, PLACEHOLDER_MEDIA

# python-pptx media type constants (from pptx.enum.shapes PP_MEDIA_TYPE)
_AUDIO_MIME_PREFIXES = ("audio/",)
_VIDEO_MIME_PREFIXES = ("video/",)


def _media_label(shape) -> str:
    """Return the right placeholder label for a media shape."""
    try:
        mime = shape.media_format.mime_type or ""
        if mime.startswith("audio/"):
            return PLACEHOLDER_AUDIO
        if mime.startswith("video/"):
            return PLACEHOLDER_VIDEO
    except Exception:
        pass
    return PLACEHOLDER_MEDIA


def _replace_with_placeholder(slide, shape, label: str, stats: Dict[str, int]) -> None:
    """Remove a shape and insert a grey text box with the placeholder label."""
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    shape._element.getparent().remove(shape._element)

    txBox = slide.shapes.add_textbox(left, top, width, height)
    txBox.fill.solid()
    txBox.fill.fore_color.rgb = RGBColor(0xCC, 0xCC, 0xCC)

    tf = txBox.text_frame
    tf.word_wrap = True
    run = tf.paragraphs[0].add_run()
    run.text = label
    run.font.size = Pt(8)

    stats[label] = stats.get(label, 0) + 1


def _remove_media_shapes(slide, stats: Dict[str, int]) -> None:
    """Replace all image, GIF, video, and audio shapes with grey placeholders."""
    to_replace: List = []
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            to_replace.append((shape, PLACEHOLDER_IMAGE))
        elif shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            to_replace.append((shape, _media_label(shape)))

    for shape, label in to_replace:
        _replace_with_placeholder(slide, shape, label, stats)


def _anonymize_text_frame(
    tf,
    engine: AnonymizerCore,
    stats: Dict[str, int],
    forced: Optional[str] = None,
) -> None:
    for para in tf.paragraphs:
        if not para.runs:
            continue
        full_text = "".join(run.text for run in para.runs)
        if not full_text.strip():
            continue

        if forced:
            anonymized = forced
            stats[forced] = stats.get(forced, 0) + 1
        else:
            anonymized, cell_stats = engine.anonymize_text(full_text)
            for k, v in cell_stats.items():
                stats[k] = stats.get(k, 0) + v

        if anonymized == full_text:
            continue

        para.runs[0].text = anonymized
        for run in para.runs[1:]:
            run.text = ""


def _process_table(table, engine: AnonymizerCore, stats: Dict[str, int]) -> None:
    rows = list(table.rows)
    if not rows:
        return

    col_forced: Dict[int, Optional[str]] = {}
    for col_idx, cell in enumerate(rows[0].cells):
        col_forced[col_idx] = placeholder_for_header(cell.text_frame.text.strip())

    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row.cells):
            forced = col_forced.get(col_idx) if row_idx > 0 else None
            _anonymize_text_frame(cell.text_frame, engine, stats, forced=forced)


def process(input_path: Path, output_path: Path, engine: AnonymizerCore) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    prs = Presentation(str(input_path))

    for slide in prs.slides:
        # Snapshot shapes before media removal; _remove_media_shapes adds new
        # placeholder textboxes that must not be passed through anonymization.
        original_shapes = list(slide.shapes)
        _remove_media_shapes(slide, stats)

        for shape in original_shapes:
            if shape.has_text_frame:
                _anonymize_text_frame(shape.text_frame, engine, stats)
            if shape.has_table:
                _process_table(shape.table, engine, stats)

    prs.save(str(output_path))
    return stats
