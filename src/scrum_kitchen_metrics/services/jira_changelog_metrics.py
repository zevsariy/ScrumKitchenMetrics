"""Сервис для вычисления метрик по changelog задач JIRA."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..api.jira_client import JiraClient
from ..config import get_settings

SECONDS_IN_HOUR = 3600.0
SECONDS_IN_DAY = 86400.0


@dataclass
class ChangelogMetricSpec:
    """Параметры вычисления метрики по changelog."""

    key: str
    label: str
    jql: str
    from_statuses: Sequence[str]
    to_statuses: Sequence[str]
    aggregation: str = "avg"
    unit: str = "days"
    description: Optional[str] = None
    max_results: int = 200


class JiraChangelogMetricsService:
    """Компонент, который собирает данные changelog и агрегирует длительности."""

    def __init__(self, client_factory=JiraClient):
        self._settings = get_settings().jira
        self._client_factory = client_factory

    # ---------------------- helpers ----------------------
    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        value = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def _status_timeline(self, issue: Dict[str, Any]) -> List[Tuple[datetime, Optional[str]]]:
        fields = issue.get("fields", {}) or {}
        created = self._parse_dt(fields.get("created"))
        histories = issue.get("changelog", {}).get("histories", []) or []
        events: List[Tuple[datetime, Optional[str]]] = []
        initial_status: Optional[str] = None
        for history in histories:
            ts = self._parse_dt(history.get("created"))
            if not ts:
                continue
            for item in history.get("items", []) or []:
                if item.get("field") != "status":
                    continue
                if initial_status is None:
                    initial_status = item.get("fromString") or item.get("from")
                events.append((ts, item.get("toString") or item.get("to")))
        if initial_status is None:
            status_field = fields.get("status")
            if isinstance(status_field, dict):
                initial_status = status_field.get("name")
            elif status_field is not None:
                initial_status = str(status_field)
        if created:
            events.append((created, initial_status))
        events.sort(key=lambda x: x[0])
        return events

    def _find_duration(
        self,
        timeline: List[Tuple[datetime, Optional[str]]],
        from_statuses: Iterable[str],
        to_statuses: Iterable[str],
    ) -> Optional[float]:
        from_set = {s.strip() for s in from_statuses if s}
        to_set = {s.strip() for s in to_statuses if s}
        if not from_set or not to_set:
            return None
        start: Optional[datetime] = None
        for ts, status in timeline:
            if status and status in from_set:
                if start is None:
                    start = ts
                continue
            if start and status and status in to_set and ts >= start:
                return (ts - start).total_seconds()
        return None

    @staticmethod
    def _convert_duration(seconds: float, unit: str) -> float:
        if unit == "hours":
            return seconds / SECONDS_IN_HOUR
        # fallback days
        return seconds / SECONDS_IN_DAY

    @staticmethod
    def _aggregate(values: Sequence[float], method: str) -> Optional[float]:
        if not values:
            return None
        method = (method or "avg").lower()
        if method in {"avg", "average", "mean"}:
            return sum(values) / len(values)
        if method in {"median", "p50"}:
            return median(values)
        if method in {"min"}:
            return min(values)
        if method in {"max"}:
            return max(values)
        if method in {"sum"}:
            return sum(values)
        # percentiles
        if method.startswith("p") and method[1:].isdigit():
            percentile = int(method[1:])
            if not (0 < percentile <= 100):
                raise ValueError(f"Unsupported percentile: {method}")
            ordered = sorted(values)
            index = max(0, min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1))))
            return ordered[index]
        raise ValueError(f"Unknown aggregation method: {method}")

    # ---------------------- public API ----------------------
    def compute(self, spec: ChangelogMetricSpec) -> Dict[str, Any]:
        if not self._settings.enabled:
            return {
                "value": None,
                "unit": spec.unit,
                "details": [],
                "note": "JIRA выключена — расчёт недоступен",
            }
        issues_data: List[Dict[str, Any]] = []
        with self._client_factory() as client:
            stubs = client.search_issues_all(spec.jql, max_results=spec.max_results)
            for stub in stubs:
                key = stub.get("key")
                if not key:
                    continue
                issue = client.get_issue(
                    key,
                    fields="key,summary,status,created,assignee,issuetype",
                    expand="changelog",
                )
                issues_data.append(issue)
        durations: List[Dict[str, Any]] = []
        for issue in issues_data:
            timeline = self._status_timeline(issue)
            seconds = self._find_duration(timeline, spec.from_statuses, spec.to_statuses)
            fields = issue.get("fields", {}) or {}
            entry = {
                "issue": issue.get("key"),
                "summary": fields.get("summary"),
                "assignee": (fields.get("assignee") or {}).get("displayName") if isinstance(fields.get("assignee"), dict) else fields.get("assignee"),
                "issuetype": (fields.get("issuetype") or {}).get("name") if isinstance(fields.get("issuetype"), dict) else fields.get("issuetype"),
                "duration_seconds": seconds,
                "duration_unit": None,
            }
            if seconds is not None:
                converted = self._convert_duration(seconds, spec.unit)
                entry["duration_unit"] = round(converted, 2)
            durations.append(entry)
        valid = [d for d in durations if d["duration_seconds"] is not None]
        converted_values = [self._convert_duration(d["duration_seconds"], spec.unit) for d in valid]
        aggregated = None
        if converted_values:
            aggregated = self._aggregate(converted_values, spec.aggregation)
            if aggregated is not None:
                aggregated = round(aggregated, 2)
        note = (
            f"JQL: {spec.jql}; переходы {', '.join(spec.from_statuses)} -> {', '.join(spec.to_statuses)};"
            f" aggregation={spec.aggregation}"
        )
        stats = {
            "count_total": len(durations),
            "count_with_duration": len(valid),
            "min": round(min(converted_values), 2) if converted_values else None,
            "max": round(max(converted_values), 2) if converted_values else None,
        }
        return {
            "value": aggregated,
            "unit": spec.unit,
            "details": durations,
            "note": note,
            "stats": stats,
        }

__all__ = ["JiraChangelogMetricsService", "ChangelogMetricSpec"]
