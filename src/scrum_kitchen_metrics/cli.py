"""Command line interface for Scrum Kitchen Metrics."""
from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import List

import typer
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .logging_config import configure_logging
from .metrics.base import Metric, MetricResult
from .metrics.registry import get_metric_classes
from .reporting.renderer import render_template
from .reporting.pdf_exporter import html_to_pdf
from .reporting.xlsx_exporter import metrics_to_xlsx
from .email.gmail_sender import GmailSender
from .email.exchange_sender import ExchangeSender
try:
    from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
    from apscheduler.triggers.cron import CronTrigger  # type: ignore
except Exception:  # noqa: BLE001
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None  # type: ignore

app = typer.Typer(help="Metrics aggregation and reporting")
console = Console()

def collect_metrics() -> List[MetricResult]:
    results: List[MetricResult] = []
    for cls in get_metric_classes():
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
                res = metric.compute()
                results.append(res)
            except Exception as e:  # noqa: BLE001
                results.append(MetricResult(cls.__name__, cls.__name__, None, f"Error: {e}"))
        return results

@app.command()
def fetch_metrics(json_output: bool = typer.Option(False, help="Output metrics as JSON")):
    """Fetch metrics and optionally print as JSON."""
    configure_logging()
    res = collect_metrics()
    if json_output:
        console.print_json(json.dumps([r.__dict__ for r in res], default=str))
    else:
        table = Table(title="Metrics")
        table.add_column("Key")
        table.add_column("Label")
        table.add_column("Value")
        table.add_column("Description")
        for r in res:
            table.add_row(r.key, r.label, str(r.value), r.description or "")
        console.print(table)

@app.command()
def generate_report():
    """Generate reports (HTML->PDF/XLSX) based on configured formats."""
    configure_logging()
    settings = get_settings()
    res = collect_metrics()
    context = {
        "generated_at": datetime.now(UTC).isoformat(),
        "app_name": settings.core.app_name,
        "metrics": res,
    }
    html = render_template(settings.report.template_name, context)
    saved_files: List[Path] = []
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base_name = f"metrics_{ts}"
    if "PDF" in settings.report.formats:
        pdf_path = settings.report.output_dir / f"{base_name}.pdf"
        html_to_pdf(html, pdf_path)
        saved_files.append(pdf_path)
    if "XLSX" in settings.report.formats:
        xlsx_path = settings.report.output_dir / f"{base_name}.xlsx"
        metrics_to_xlsx(res, xlsx_path)
        saved_files.append(xlsx_path)
    console.print("Generated files:")
    for p in saved_files:
        console.print(f" - {p}")

@app.command()
def send_report(latest: bool = typer.Option(True, help="Send latest generated report files")):
    """Send report files via configured email provider."""
    configure_logging()
    settings = get_settings()
    if not settings.email.enabled:
        console.print("[red]Email disabled[/red]")
        raise typer.Exit(code=1)
    out_dir = settings.report.output_dir
    attachments: List[Path] = []
    if latest:
        # pick latest by timestamp prefix
        files = sorted(out_dir.glob("metrics_*.pdf")) + sorted(out_dir.glob("metrics_*.xlsx"))
        # simple heuristic: take last of each extension
        if settings.email.send_pdf:
            pdfs = sorted(out_dir.glob("metrics_*.pdf"))
            if pdfs:
                attachments.append(pdfs[-1])
        if settings.email.send_xlsx:
            xlsxs = sorted(out_dir.glob("metrics_*.xlsx"))
            if xlsxs:
                attachments.append(xlsxs[-1])
    else:
        # all files
        if settings.email.send_pdf:
            attachments.extend(out_dir.glob("metrics_*.pdf"))
        if settings.email.send_xlsx:
            attachments.extend(out_dir.glob("metrics_*.xlsx"))

    subject = f"{settings.email.subject_prefix} {settings.core.app_name}"
    body_lines = ["Metrics report attached."]
    for a in attachments:
        body_lines.append(f" - {a.name}")
    body = "\n".join(body_lines)

    if settings.email.provider == "gmail":
        sender = GmailSender()
    elif settings.email.provider == "exchange":
        sender = ExchangeSender()
    else:
        console.print(f"[red]Unknown provider {settings.email.provider}[/red]")
        raise typer.Exit(code=2)

    sender.send(subject, body, settings.email.to, attachments)
    console.print("Email sent.")

@app.command()
def run_all():
    """Fetch metrics, generate report and send email (if enabled)."""
    fetch_metrics()
    generate_report()
    if get_settings().email.enabled:
        send_report()

@app.command()
def start_scheduler():  # noqa: D401
    """Запустить планировщик cron из SCHEDULER_CRON для run_all."""
    settings = get_settings()
    if not settings.scheduler.enabled:
        console.print("[red]Scheduler disabled[/red]")
        raise typer.Exit(1)
    if BackgroundScheduler is None:
        console.print("[red]APScheduler not installed[/red]")
        raise typer.Exit(2)
    configure_logging()
    sched = BackgroundScheduler()
    expr = settings.scheduler.cron.split()
    if len(expr) != 5:
        console.print("[red]Invalid SCHEDULER_CRON expression (need 5 fields)\n[/red]")
        raise typer.Exit(3)
    minute, hour, day, month, dow = expr
    trigger = CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)
    sched.add_job(run_all, trigger, name="run_all")
    sched.start()
    console.print("Scheduler started. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:  # pragma: no cover
        sched.shutdown()
        console.print("Scheduler stopped")

if __name__ == "__main__":  # pragma: no cover
    app()
