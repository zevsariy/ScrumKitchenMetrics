"""Optional FastAPI server exposing metrics and report generation."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException

from .config import get_settings
from .logging_config import configure_logging
from .metrics.registry import get_metric_classes
from .metrics.base import MetricResult
from .reporting.renderer import render_template
from .reporting.pdf_exporter import html_to_pdf
from .reporting.xlsx_exporter import metrics_to_xlsx

app = FastAPI(title="ScrumKitchenMetrics API")

def _collect() -> List[MetricResult]:
    results: List[MetricResult] = []
    for cls in get_metric_classes():
        try:
            metric = cls()
            results.append(metric.compute())
        except Exception as e:  # noqa: BLE001
            results.append(MetricResult(cls.__name__, cls.__name__, None, f"Error: {e}"))
    return results

@app.on_event("startup")
def _startup():  # noqa: D401
    configure_logging()

@app.get("/health")
def health():  # noqa: D401
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.get("/metrics")
def metrics():  # noqa: D401
    res = _collect()
    return [r.__dict__ for r in res]

@app.post("/report")
def generate_report():  # noqa: D401
    settings = get_settings()
    res = _collect()
    context = {
        "generated_at": datetime.utcnow().isoformat(),
        "app_name": settings.core.app_name,
        "metrics": res,
    }
    html = render_template(settings.report.template_name, context)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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