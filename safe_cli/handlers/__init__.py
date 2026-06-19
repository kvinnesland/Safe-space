from pathlib import Path
from typing import Callable, Dict, Optional

from ..engine import AnonymizerCore
from . import txt, csv_handler, xlsx, docx_handler, pdf

Handler = Callable[[Path, Path, "AnonymizerCore"], Dict[str, int]]

_HANDLERS: Dict[str, Handler] = {
    ".txt": txt.process,
    ".csv": csv_handler.process,
    ".xlsx": xlsx.process,
    ".docx": docx_handler.process,
    ".pdf": pdf.process,
}


def get_handler(extension: str) -> Optional[Handler]:
    return _HANDLERS.get(extension.lower())
