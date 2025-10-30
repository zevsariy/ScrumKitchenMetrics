"""UI routes for local management."""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..metrics.registry import get_metric_classes, register as register_metric
from ..reporting.pdf_exporter import html_to_pdf
from ..reporting.xlsx_exporter import metrics_to_xlsx
from ..reporting.renderer import render_template
from ..logging_config import configure_logging
from ..cli import collect_metrics, send_report as cli_send_report

# Resolve templates directory relative to repository root to avoid dependency on CWD
try:
    _REPO_ROOT = Path(__file__).resolve().parents[3]
except IndexError:  # fallback if unexpected structure
    _REPO_ROOT = Path.cwd()
_TEMPLATES_DIR = _REPO_ROOT / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
router = APIRouter(prefix="/ui", tags=["ui"])

def _read_overrides() -> dict:
    data = {}
    p = Path('overrides.env')
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip()
    return data

def _write_overrides(mapping: dict):
    lines = [f"{k}={v}" for k, v in sorted(mapping.items())]
    Path('overrides.env').write_text('\n'.join(lines) + '\n', encoding='utf-8')

CUSTOM_METRICS_FILE = Path('custom_metrics.json')

def _load_custom_metrics() -> List[Dict[str, Any]]:
    if not CUSTOM_METRICS_FILE.exists():
        return []
    import json
    try:
        data = json.loads(CUSTOM_METRICS_FILE.read_text(encoding='utf-8'))
        if isinstance(data, list):
            return data
    except Exception:  # noqa: BLE001
        return []
    return []

def _save_custom_metrics(metrics: List[Dict[str, Any]]):
    import json
    CUSTOM_METRICS_FILE.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding='utf-8')

def _safe_eval(expr: str, variables: Dict[str, Any]) -> Any:
    allowed_names = {
        'len': len,
        'sum': sum,
        'min': min,
        'max': max,
        'round': round,
    }
    code = compile(expr, '<expr>', 'eval')
    for name in code.co_names:
        if name not in allowed_names and name not in variables:
            raise ValueError(f"Name '{name}' not allowed")
    return eval(code, {'__builtins__': {}}, {**allowed_names, **variables})

def _register_dynamic_metrics():
    from ..metrics.base import Metric, MetricResult
    settings = get_settings()
    custom = _load_custom_metrics()
    variables = {}
    # Provide access to settings for simple expressions (e.g., app_name)
    variables['settings'] = settings

    class DynamicMetric(Metric):  # base for dynamic instances
        source = 'custom'
        expression: str
        def compute(self) -> MetricResult:  # noqa: D401
            try:
                value = _safe_eval(self.expression, variables)
                return MetricResult(self.key, self.label, value, self.description or 'Dynamic metric')
            except Exception as e:  # noqa: BLE001
                return MetricResult(self.key, self.label, None, f"Dynamic error: {e}")

    for spec in custom:
        key = spec.get('key')
        if not key:
            continue
        label = spec.get('label', key)
        expr = spec.get('expression', 'None')
        desc = spec.get('description')
        # Create metric subclass dynamically
        attrs = {'key': key, 'label': label, 'description': desc, 'expression': expr}
        cls = type(f"DynMetric_{key}", (DynamicMetric,), attrs)
        register_metric(cls)

_register_dynamic_metrics()

@router.get('/', response_class=HTMLResponse)
def dashboard(request: Request):  # noqa: D401
    settings = get_settings()
    metrics = collect_metrics()
    reports_dir = settings.report.output_dir
    reports_dir.mkdir(exist_ok=True, parents=True)
    pdfs = sorted(reports_dir.glob('metrics_*.pdf'))[-5:]
    xlsxs = sorted(reports_dir.glob('metrics_*.xlsx'))[-5:]
    return templates.TemplateResponse('ui/index.html', {
        'request': request,
        'settings': settings,
        'metrics': metrics,
        'pdfs': list(reversed(pdfs)),
        'xlsxs': list(reversed(xlsxs)),
    })

@router.get('/metrics', response_class=HTMLResponse)
def metrics_page(request: Request):  # noqa: D401
    classes = get_metric_classes()
    overrides = _read_overrides()
    disabled = set(overrides.get('DISABLED_METRICS', '').split(',')) if overrides.get('DISABLED_METRICS') else set()
    custom_specs = _load_custom_metrics()
    return templates.TemplateResponse('ui/metrics.html', {
        'request': request,
        'metrics': classes,
        'disabled': disabled,
        'custom_specs': custom_specs,
    })

@router.post('/metrics/toggle')
def toggle_metric(request: Request, key: str = Form(...)):
    overrides = _read_overrides()
    disabled_raw = overrides.get('DISABLED_METRICS', '')
    disabled = {x for x in disabled_raw.split(',') if x}
    if key in disabled:
        disabled.remove(key)
    else:
        disabled.add(key)
    overrides['DISABLED_METRICS'] = ','.join(sorted(disabled))
    _write_overrides(overrides)
    from functools import lru_cache
    from .. import config as config_module
    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    return RedirectResponse('/ui/metrics', status_code=303)

@router.post('/metrics/add')
def add_custom_metric(
    request: Request,
    key: str = Form(...),
    label: str = Form(...),
    expression: str = Form(...),
    description: str = Form(''),
):
    specs = _load_custom_metrics()
    # prevent duplicates
    if any(s.get('key') == key for s in specs):
        return RedirectResponse('/ui/metrics', status_code=303)
    specs.append({'key': key, 'label': label, 'expression': expression, 'description': description})
    _save_custom_metrics(specs)
    # Register just-added metric dynamically
    from ..metrics.base import Metric, MetricResult
    from ..metrics import registry as reg
    class DynamicMetric(Metric):  # type: ignore[no-redef]
        source = 'custom'
        def compute(self) -> MetricResult:  # noqa: D401
            try:
                settings = get_settings()
                value = _safe_eval(self.expression, {'settings': settings})
                return MetricResult(self.key, self.label, value, self.description or 'Dynamic metric')
            except Exception as e:  # noqa: BLE001
                return MetricResult(self.key, self.label, None, f"Dynamic error: {e}")
    # assign attributes after class creation to avoid NameError shadowing
    DynamicMetric.key = key  # type: ignore[attr-defined]
    DynamicMetric.label = label  # type: ignore[attr-defined]
    DynamicMetric.description = description  # type: ignore[attr-defined]
    DynamicMetric.expression = expression  # type: ignore[attr-defined]
    reg.register(DynamicMetric)
    return RedirectResponse('/ui/metrics', status_code=303)

@router.post('/metrics/delete')
def delete_custom_metric(request: Request, key: str = Form(...)):
    specs = _load_custom_metrics()
    specs = [s for s in specs if s.get('key') != key]
    _save_custom_metrics(specs)
    # Remove from registry if present
    from ..metrics import registry as reg
    if key in getattr(reg, '_REGISTRY', {}):  # type: ignore[attr-defined]
        reg._REGISTRY.pop(key, None)  # type: ignore[attr-defined]
    return RedirectResponse('/ui/metrics', status_code=303)

@router.get('/report', response_class=HTMLResponse)
def report_editor(request: Request):  # noqa: D401
    settings = get_settings()
    template_path = settings.report.template_dir / settings.report.template_name
    if template_path.exists():
        content = template_path.read_text(encoding='utf-8')
    else:
        content = '<html><body><h2>{{ app_name }} Metrics</h2></body></html>'
    overrides = _read_overrides()
    return templates.TemplateResponse('ui/report.html', {
        'request': request,
        'template_content': content,
        'formats': ','.join(settings.report.formats),
        'pdf_engine': overrides.get('REPORT_PDF_ENGINE', settings.report.pdf_engine),
    })

@router.post('/report/save')
def report_save(
    request: Request,
    template_content: str = Form(...),
    formats: str = Form('PDF,XLSX'),
    pdf_engine: str = Form('reportlab'),
):
    settings = get_settings()
    template_path = settings.report.template_dir / settings.report.template_name
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text(template_content, encoding='utf-8')
    overrides = _read_overrides()
    overrides['REPORT_FORMATS'] = formats
    overrides['REPORT_PDF_ENGINE'] = pdf_engine
    _write_overrides(overrides)
    from .. import config as config_module
    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    return RedirectResponse('/ui/report', status_code=303)

@router.get('/config', response_class=HTMLResponse)
def config_page(request: Request):  # noqa: D401
    settings = get_settings()
    overrides = _read_overrides()
    editable_keys = [
        'JIRA_ENABLED', 'GITLAB_ENABLED', 'REPORT_FORMATS', 'EMAIL_ENABLED', 'EMAIL_PROVIDER',
        'LOG_LEVEL', 'LOG_FORMAT'
    ]
    current = {}
    env_map = {
        'JIRA_ENABLED': settings.jira.enabled,
        'GITLAB_ENABLED': settings.gitlab.enabled,
        'REPORT_FORMATS': ','.join(settings.report.formats),
        'EMAIL_ENABLED': settings.email.enabled,
        'EMAIL_PROVIDER': settings.email.provider,
        'LOG_LEVEL': settings.core.log_level,
        'LOG_FORMAT': settings.core.log_format,
    }
    for k in editable_keys:
        current[k] = overrides.get(k, env_map[k])
    return templates.TemplateResponse('ui/config.html', {
        'request': request,
        'config_values': current,
    })

@router.post('/config/save')
def save_config(
    request: Request,
    jira_enabled: str = Form('false'),
    gitlab_enabled: str = Form('false'),
    report_formats: str = Form('PDF,XLSX'),
    email_enabled: str = Form('false'),
    email_provider: str = Form('gmail'),
    log_level: str = Form('INFO'),
    log_format: str = Form('text'),
):
    overrides = _read_overrides()
    overrides.update({
        'JIRA_ENABLED': str(jira_enabled.lower() in {'true', '1', 'on'}),
        'GITLAB_ENABLED': str(gitlab_enabled.lower() in {'true', '1', 'on'}),
        'REPORT_FORMATS': report_formats,
        'EMAIL_ENABLED': str(email_enabled.lower() in {'true', '1', 'on'}),
        'EMAIL_PROVIDER': email_provider,
        'LOG_LEVEL': log_level.upper(),
        'LOG_FORMAT': log_format.lower(),
    })
    _write_overrides(overrides)
    from .. import config as config_module
    config_module.get_settings.cache_clear()  # type: ignore[attr-defined]
    return RedirectResponse('/ui/config', status_code=303)

@router.post('/action/generate')
def action_generate():  # noqa: D401
    settings = get_settings()
    configure_logging()
    metrics = collect_metrics()
    context = {
        'generated_at': 'UI',
        'app_name': settings.core.app_name,
        'metrics': metrics,
    }
    html = render_template(settings.report.template_name, context)
    from datetime import datetime, UTC
    ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
    base_name = f"ui_metrics_{ts}"
    created: List[str] = []
    if 'PDF' in settings.report.formats:
        created.append(str(html_to_pdf(html, settings.report.output_dir / f"{base_name}.pdf")))
    if 'XLSX' in settings.report.formats:
        created.append(str(metrics_to_xlsx(metrics, settings.report.output_dir / f"{base_name}.xlsx")))
    return RedirectResponse('/ui', status_code=303)

@router.post('/action/send')
def action_send():  # noqa: D401
    settings = get_settings()
    if not settings.email.enabled:
        return RedirectResponse('/ui', status_code=303)
    configure_logging()
    # Reuse CLI send_report logic
    try:
        cli_send_report()  # will use latest files
    except SystemExit:
        pass
    return RedirectResponse('/ui', status_code=303)

__all__ = ["router"]