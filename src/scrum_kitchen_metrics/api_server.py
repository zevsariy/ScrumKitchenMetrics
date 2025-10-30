"""Optional FastAPI server exposing metrics and report generation."""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .logging_config import configure_logging
from .metrics.registry import get_metric_classes
from .config import get_settings
from .metrics.base import MetricResult
from .reporting.renderer import render_template
from .reporting.pdf_exporter import html_to_pdf
from .reporting.xlsx_exporter import metrics_to_xlsx
from .ui.router import router as ui_router

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: D401
    configure_logging()
    settings = get_settings()
    if settings.report.output_dir.exists():
        app.mount("/reports", StaticFiles(directory=str(settings.report.output_dir)), name="reports")
    yield

app = FastAPI(title="ScrumKitchenMetrics API", lifespan=lifespan)
app.include_router(ui_router)

def _collect() -> List[MetricResult]:
    settings = get_settings()
    results: List[MetricResult] = []
    for cls in get_metric_classes():
        src = getattr(cls, 'source', None)
        if src == 'jira' and not settings.jira.enabled:
            continue
        if src == 'gitlab' and not settings.gitlab.enabled:
            continue
        try:
            metric = cls()
            results.append(metric.compute())
        except Exception as e:  # noqa: BLE001
            results.append(MetricResult(cls.__name__, cls.__name__, None, f"Error: {e}"))
    return results


@app.get("/health")
def health():  # noqa: D401
    return {"status": "ok", "ts": datetime.now(UTC).isoformat()}

@app.get("/metrics")
def metrics():  # noqa: D401
    res = _collect()
    return [r.__dict__ for r in res]

@app.post("/report")
def generate_report():  # noqa: D401
    settings = get_settings()
    res = _collect()
    context = {
        "generated_at": datetime.now(UTC).isoformat(),
        "app_name": settings.core.app_name,
        "metrics": res,
    }
    html = render_template(settings.report.template_name, context)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base_name = f"api_metrics_{ts}"
    saved = []
    if "PDF" in settings.report.formats:
        pdf_path = settings.report.output_dir / f"{base_name}.pdf"
        html_to_pdf(html, pdf_path)
        saved.append(str(pdf_path))
    if "XLSX" in settings.report.formats:
        xlsx_path = settings.report.output_dir / f"{base_name}.xlsx"
        metrics_to_xlsx(res, xlsx_path)
        saved.append(str(xlsx_path))
    return {"files": saved}

__all__ = ["app"]