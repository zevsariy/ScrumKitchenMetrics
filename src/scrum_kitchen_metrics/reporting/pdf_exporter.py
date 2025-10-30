"""Export HTML into PDF using reportlab (basic)."""
from __future__ import annotations

from pathlib import Path
from reportlab.lib.pagesizes import A4  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore

from ..logging_config import get_logger
from ..config import get_settings

logger = get_logger(__name__)

def html_to_pdf(html: str, output_path: Path) -> Path:
    settings = get_settings()
    engine = getattr(settings.report, 'pdf_engine', 'reportlab').lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if engine == 'weasyprint':  # richer rendering if installed
        try:
            from weasyprint import HTML  # type: ignore
            HTML(string=html).write_pdf(str(output_path))
            logger.info("PDF (weasyprint) saved to %s", output_path)
            return output_path
        except Exception as e:  # noqa: BLE001
            logger.warning("WeasyPrint failed (%s); falling back to simple exporter", e)
    # fallback simple exporter
    text = _strip_html(html)
    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    y = height - 40
    for line in text.splitlines():
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(40, y, line[:120])
        y -= 14
    c.save()
    logger.info("PDF (simple) saved to %s", output_path)
    return output_path

def _strip_html(html: str) -> str:
    import re
    # Remove tags
    text = re.sub(r"<[^>]+>", "", html)
    return text
