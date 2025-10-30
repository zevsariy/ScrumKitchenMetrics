"""Simplified entrypoint to run the API server and basic actions without package install."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn
import threading
import time
import webbrowser

# Local imports via src path
BASE_DIR = Path(__file__).parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scrum_kitchen_metrics.config import get_settings  # noqa: E402
from scrum_kitchen_metrics.cli import collect_metrics  # noqa: E402
from scrum_kitchen_metrics.reporting.renderer import render_template  # noqa: E402
from scrum_kitchen_metrics.reporting.pdf_exporter import html_to_pdf  # noqa: E402
from scrum_kitchen_metrics.reporting.xlsx_exporter import metrics_to_xlsx  # noqa: E402
from scrum_kitchen_metrics.logging_config import configure_logging  # noqa: E402


def cmd_server(args):  # noqa: D401
    configure_logging()
    url = f"http://{args.host}:{args.port}/ui"

    def _open():  # open after short delay to ensure server binds
        time.sleep(0.5)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(
        "scrum_kitchen_metrics.api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def cmd_metrics(args):  # noqa: D401
    configure_logging()
    results = collect_metrics()
    for r in results:
        print(f"{r.key:30} | {r.value:10} | {r.description}")


def cmd_report(args):  # noqa: D401
    configure_logging()
    settings = get_settings()
    results = collect_metrics()
    context = {
        "generated_at": "manual",
        "app_name": settings.core.app_name,
        "metrics": results,
    }
    html = render_template(settings.report.template_name, context)
    ts = args.name or "manual_report"
    output_dir = settings.report.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    if "PDF" in settings.report.formats:
        created.append(html_to_pdf(html, output_dir / f"{ts}.pdf"))
    if "XLSX" in settings.report.formats:
        created.append(metrics_to_xlsx(results, output_dir / f"{ts}.xlsx"))
    print("Created:")
    for p in created:
        print(" -", p)


def build_parser():  # noqa: D401
    p = argparse.ArgumentParser(description="Simplified runner for ScrumKitchenMetrics")
    sub = p.add_subparsers(dest="command", required=True)

    srv = sub.add_parser("server", help="Run FastAPI server (UI at /ui)")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--reload", action="store_true")
    srv.set_defaults(func=cmd_server)

    met = sub.add_parser("metrics", help="Print metrics")
    met.set_defaults(func=cmd_metrics)

    rep = sub.add_parser("report", help="Generate report files")
    rep.add_argument("--name", default=None, help="Base name for output")
    rep.set_defaults(func=cmd_report)

    return p


def main(argv=None):  # noqa: D401
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
