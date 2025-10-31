"""Динамические метрики, вычисляемые на основе changelog JIRA."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .base import Metric, MetricResult
from . import registry
from ..config import get_settings
from ..services.jira_changelog_metrics import ChangelogMetricSpec, JiraChangelogMetricsService

_CHANGELOG_FILE = Path(os.getenv("CUSTOM_JIRA_CHANGELOG_METRICS_FILE", "custom_jira_changelog_metrics.json"))
_REGISTERED_KEYS: Set[str] = set()


def _ensure_list(raw: Optional[Any]) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p]
    return []


def _load_specs() -> List[Dict[str, Any]]:
    if not _CHANGELOG_FILE.exists():
        return []
    try:
        data = json.loads(_CHANGELOG_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if isinstance(data, list):
        return data
    return []


def _parse_spec(raw: Dict[str, Any]) -> Optional[ChangelogMetricSpec]:
    key = str(raw.get("key") or "").strip()
    label = str(raw.get("label") or key).strip()
    jql = str(raw.get("jql") or "").strip()
    if not key or not jql:
        return None
    from_statuses = _ensure_list(raw.get("from_statuses"))
    to_statuses = _ensure_list(raw.get("to_statuses"))
    if not from_statuses or not to_statuses:
        return None
    aggregation = str(raw.get("aggregation") or "avg").strip()
    unit = str(raw.get("unit") or "days").strip()
    description = raw.get("description")
    max_results = int(raw.get("max_results") or 200)
    return ChangelogMetricSpec(
        key=key,
        label=label or key,
        jql=jql,
        from_statuses=tuple(from_statuses),
        to_statuses=tuple(to_statuses),
        aggregation=aggregation,
        unit=unit,
        description=str(description) if description else None,
        max_results=max_results,
    )


def _metric_class(spec: ChangelogMetricSpec):
    class JiraChangelogCustomMetric(Metric):
        key = spec.key
        label = spec.label
        description = spec.description or "JIRA changelog metric"
        source = "jira"
        _spec = spec

        def compute(self) -> MetricResult:  # noqa: D401
            settings = get_settings().jira
            if not (settings.enabled and settings.base_url and settings.api_token):
                return MetricResult(self.key, self.label, None, "JIRA отключена", {"note": "JIRA disabled"})
            service = JiraChangelogMetricsService()
            data = service.compute(self._spec)
            return MetricResult(self.key, self.label, data.get("value"), data.get("note"), data)

    return JiraChangelogCustomMetric


def register_custom_changelog_metrics():
    specs = _load_specs()
    for key in list(_REGISTERED_KEYS):
        registry._REGISTRY.pop(key, None)  # type: ignore[attr-defined]
    _REGISTERED_KEYS.clear()
    for raw in specs:
        spec = _parse_spec(raw)
        if not spec:
            continue
        metric_cls = _metric_class(spec)
        registry.register(metric_cls)
        _REGISTERED_KEYS.add(spec.key)


def reload_custom_changelog_metrics():  # noqa: D401
    register_custom_changelog_metrics()


# Регистрация при импорте модуля, чтобы метрики подхватывались и вне UI.
register_custom_changelog_metrics()

__all__ = ["reload_custom_changelog_metrics", "register_custom_changelog_metrics"]
