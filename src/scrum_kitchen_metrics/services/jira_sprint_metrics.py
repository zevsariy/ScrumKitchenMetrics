"""Utilities for aggregating advanced JIRA sprint metrics.

The service fetches sprint reports, enriches issues with changelog/worklog
information and derives statistics that can be presented through Metric
classes. Акценты: time-to-market, lead time (delivery/discovery), spillover,
plan/fact, velocity, разбивка по командам.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..api.jira_client import JiraClient
from ..config import get_settings

SECONDS_IN_DAY = 86400.0


@dataclass
class SprintSummary:
    board_id: int
    board_name: Optional[str]
    sprint_id: int
    sprint_name: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    state: str
    summary: Dict[str, Any]


class JiraSprintMetricsService:
    """Coordinator that fetches sprint reports and derives KPI scaffolding."""

    def __init__(self, client_factory=JiraClient):
        self._settings = get_settings().jira
        self._client_factory = client_factory
        self._cache: Optional[List[SprintSummary]] = None
        self._issue_cache: Dict[str, Dict[str, Any]] = {}
        self._worklog_cache: Dict[str, Dict[str, Any]] = {}

    # ---------------------- helpers ----------------------
    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:  # noqa: D401
        if not value:
            return None
        try:
            value = value.replace('Z', '+00:00')
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _to_iso(value: Optional[datetime]) -> Optional[str]:  # noqa: D401
        return value.isoformat() if value else None

    @staticmethod
    def _extract_story_points_from_stub(issue_stub: Dict[str, Any]) -> Optional[float]:
        stat = issue_stub.get('estimateStatistic', {}).get('statFieldValue', {})
        raw = stat.get('value')
        if raw is None:
            return None
        try:
            return float(raw)
        except Exception:  # noqa: BLE001
            return None

    def _settings_set(self, values: Iterable[str]) -> set[str]:
        return {v.strip() for v in values if isinstance(v, str) and v.strip()}

    def _get_issue_details(self, client: JiraClient, issue_key: str) -> Dict[str, Any]:
        if issue_key in self._issue_cache:
            return self._issue_cache[issue_key]
        fields = [
            'created',
            'resolutiondate',
            'status',
            'issuetype',
            'summary',
            'assignee',
            'labels',
        ]
        story_field = getattr(self._settings, 'story_points_field', None)
        if story_field:
            fields.append(story_field)
        team_field = getattr(self._settings, 'team_custom_field', None)
        if team_field:
            fields.append(team_field)
        field_param = ','.join(dict.fromkeys(fields))
        issue = client.get_issue(issue_key, fields=field_param, expand='changelog')
        self._issue_cache[issue_key] = issue
        return issue

    def _get_issue_worklog(self, client: JiraClient, issue_key: str) -> Dict[str, Any]:
        if issue_key in self._worklog_cache:
            return self._worklog_cache[issue_key]
        data = client.get_issue_worklog(issue_key)
        self._worklog_cache[issue_key] = data
        return data

    def _aggregate_issue_worklog(self, data: Dict[str, Any]) -> Dict[str, Any]:
        per_user: Dict[str, float] = defaultdict(float)
        total = 0.0
        for entry in data.get('worklogs', []) or []:
            seconds = entry.get('timeSpentSeconds') or 0
            hours = seconds / 3600.0
            if hours <= 0:
                continue
            author = entry.get('author', {}) or {}
            name = author.get('displayName') or author.get('name') or 'Unknown'
            per_user[name] += hours
            total += hours
        return {
            'per_user': {k: round(v, 2) for k, v in per_user.items()},
            'total_hours': round(total, 2),
        }

    def _build_status_timeline(self, issue: Dict[str, Any], created_at: Optional[datetime]) -> List[Tuple[datetime, Optional[str]]]:
        timeline: List[Tuple[datetime, Optional[str]]] = []
        histories = issue.get('changelog', {}).get('histories', []) or []
        transitions: List[Tuple[datetime, Optional[str]]] = []
        initial_status: Optional[str] = None
        for history in histories:
            ts = self._parse_dt(history.get('created'))
            if not ts:
                continue
            for item in history.get('items', []) or []:
                if item.get('field') != 'status':
                    continue
                if initial_status is None:
                    initial_status = item.get('fromString') or item.get('from')
                transitions.append((ts, item.get('toString') or item.get('to')))
        if initial_status is None:
            fields = issue.get('fields', {}) or {}
            status_field = fields.get('status')
            if isinstance(status_field, dict):
                initial_status = status_field.get('name')
            elif status_field is not None:
                initial_status = str(status_field)
        if created_at:
            timeline.append((created_at, initial_status))
        transitions.sort(key=lambda x: x[0])
        timeline.extend(transitions)
        return timeline

    @staticmethod
    def _first_time_in_status(timeline: List[Tuple[datetime, Optional[str]]], targets: set[str]) -> Optional[datetime]:
        if not targets:
            return None
        for ts, status in timeline:
            if status and status in targets:
                return ts
        return None

    def _extract_team(self, fields: Dict[str, Any]) -> Optional[str]:
        team_field = getattr(self._settings, 'team_custom_field', None)
        if not team_field:
            return None
        value = fields.get(team_field)
        if isinstance(value, dict):
            return value.get('displayName') or value.get('value') or value.get('name')
        if isinstance(value, list) and value:
            item = value[0]
            if isinstance(item, dict):
                return item.get('displayName') or item.get('value') or item.get('name')
            return str(item)
        if value is None:
            return None
        return str(value)

    def _compute_issue_metrics(
        self,
        issue: Dict[str, Any],
        sprint_start: Optional[datetime],
        sprint_end: Optional[datetime],
    ) -> Dict[str, Any]:
        fields = issue.get('fields', {}) or {}
        created_at = self._parse_dt(fields.get('created'))
        resolution_at = self._parse_dt(fields.get('resolutiondate')) or sprint_end
        story_points = None
        story_field = getattr(self._settings, 'story_points_field', None)
        if story_field:
            story_points = fields.get(story_field)
            if isinstance(story_points, dict):
                story_points = story_points.get('value')
            try:
                story_points = float(story_points) if story_points is not None else None
            except Exception:  # noqa: BLE001
                story_points = None
        timeline = self._build_status_timeline(issue, created_at)
        discovery_set = self._settings_set(self._settings.discovery_statuses)
        delivery_start_set = self._settings_set(self._settings.delivery_start_statuses)
        delivery_end_set = self._settings_set(self._settings.delivery_end_statuses)
        discovery_start_at = self._first_time_in_status(timeline, discovery_set)
        delivery_start_at = self._first_time_in_status(timeline, delivery_start_set)
        delivery_end_at = self._first_time_in_status(timeline, delivery_end_set) or resolution_at
        time_to_market = None
        lead_delivery = None
        lead_discovery = None
        if created_at and delivery_end_at and delivery_end_at >= created_at:
            time_to_market = round((delivery_end_at - created_at).total_seconds() / SECONDS_IN_DAY, 2)
        if delivery_start_at and delivery_end_at and delivery_end_at >= delivery_start_at:
            lead_delivery = round((delivery_end_at - delivery_start_at).total_seconds() / SECONDS_IN_DAY, 2)
        if discovery_start_at and delivery_start_at and delivery_start_at >= discovery_start_at:
            lead_discovery = round((delivery_start_at - discovery_start_at).total_seconds() / SECONDS_IN_DAY, 2)
        team = self._extract_team(fields)
        return {
            'created_at': created_at,
            'resolution_at': resolution_at,
            'discovery_start_at': discovery_start_at,
            'delivery_start_at': delivery_start_at,
            'delivery_end_at': delivery_end_at,
            'time_to_market_days': time_to_market,
            'lead_time_delivery_days': lead_delivery,
            'lead_time_discovery_days': lead_discovery,
            'story_points': story_points,
            'team': team,
        }

    @staticmethod
    def _extract_assignee(fields: Dict[str, Any]) -> Optional[str]:
        data = fields.get('assignee')
        if isinstance(data, dict):
            return data.get('displayName') or data.get('name')
        if data is None:
            return None
        return str(data)

    def _enrich_issue(
        self,
        issue_stub: Dict[str, Any],
        client: JiraClient,
        sprint_start: Optional[datetime],
        sprint_end: Optional[datetime],
    ) -> Dict[str, Any]:
        key = issue_stub.get('key') or issue_stub.get('issueKey')
        if not key:
            return {'key': None, 'story_points': 0, 'metrics': {}, 'worklog': {'per_user': {}, 'total_hours': 0.0}}
        issue = self._get_issue_details(client, key)
        metrics = self._compute_issue_metrics(issue, sprint_start, sprint_end)
        story_points = metrics.get('story_points')
        if story_points is None:
            story_points = self._extract_story_points_from_stub(issue_stub) or 0.0
        worklog_data = self._get_issue_worklog(client, key)
        worklog_summary = self._aggregate_issue_worklog(worklog_data)
        fields = issue.get('fields', {}) or {}
        issuetype = fields.get('issuetype') or {}
        status_field = fields.get('status') or {}
        return {
            'key': key,
            'summary': fields.get('summary'),
            'issuetype': issuetype.get('name') if isinstance(issuetype, dict) else issuetype,
            'assignee': self._extract_assignee(fields),
            'team': metrics.get('team') or 'Unassigned',
            'status': status_field.get('name') if isinstance(status_field, dict) else status_field,
            'story_points': float(story_points or 0.0),
            'metrics': {
                'created_at': self._to_iso(metrics.get('created_at')),
                'resolution_at': self._to_iso(metrics.get('resolution_at')),
                'discovery_start_at': self._to_iso(metrics.get('discovery_start_at')),
                'delivery_start_at': self._to_iso(metrics.get('delivery_start_at')),
                'delivery_end_at': self._to_iso(metrics.get('delivery_end_at')),
                'time_to_market_days': metrics.get('time_to_market_days'),
                'lead_time_delivery_days': metrics.get('lead_time_delivery_days'),
                'lead_time_discovery_days': metrics.get('lead_time_discovery_days'),
            },
            'worklog': worklog_summary,
        }

    def _aggregate_worklog(self, details: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        totals: Dict[str, float] = defaultdict(float)
        total_hours = 0.0
        for issues in details.values():
            for item in issues:
                worklog = item.get('worklog') or {}
                total_hours += worklog.get('total_hours', 0.0)
                for user, hours in (worklog.get('per_user') or {}).items():
                    totals[user] += hours
        return {
            'total_hours': round(total_hours, 2),
            'per_user': {k: round(v, 2) for k, v in totals.items()},
        }

    def _aggregate_team_summary(self, details: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        team_data: Dict[str, Dict[str, Any]] = {}
        for bucket_name, issues in details.items():
            for item in issues:
                team = item.get('team') or 'Unassigned'
                entry = team_data.setdefault(team, {
                    'team': team,
                    'issues': {
                        'planned': 0,
                        'completed': 0,
                        'not_completed': 0,
                        'added': 0,
                        'removed': 0,
                    },
                    'story_points': {
                        'planned': 0.0,
                        'completed': 0.0,
                        'not_completed': 0.0,
                        'added': 0.0,
                        'removed': 0.0,
                    },
                    'worklog_hours': 0.0,
                })
                sp = float(item.get('story_points') or 0.0)
                if bucket_name in {'completed', 'not_completed'}:
                    entry['issues']['planned'] += 1
                    entry['story_points']['planned'] += sp
                entry['issues'][bucket_name] += 1
                entry['story_points'][bucket_name] += sp
                entry['worklog_hours'] += item.get('worklog', {}).get('total_hours', 0.0)
        for entry in team_data.values():
            entry['worklog_hours'] = round(entry['worklog_hours'], 2)
            entry['story_points'] = {k: round(v, 2) for k, v in entry['story_points'].items()}
        return sorted(team_data.values(), key=lambda x: x['team'])

    def _build_summary(
        self,
        report: Dict[str, Any],
        client: JiraClient,
        sprint_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        contents = report.get('contents', {}) or {}
        buckets_raw = {
            'completed': contents.get('completedIssues', []) or [],
            'not_completed': contents.get('issuesNotCompletedInCurrentSprint', []) or [],
            'added': contents.get('issuesAddedDuringSprint', []) or [],
            'removed': contents.get('puntedIssues', []) or [],
        }
        sprint_start = self._parse_dt(sprint_meta.get('startDate'))
        sprint_end = self._parse_dt(sprint_meta.get('completeDate') or sprint_meta.get('endDate'))
        details: Dict[str, List[Dict[str, Any]]] = {
            bucket: [self._enrich_issue(issue, client, sprint_start, sprint_end) for issue in issues]
            for bucket, issues in buckets_raw.items()
        }
        summary: Dict[str, Any] = {
            'issues': {
                'planned': len(details['completed']) + len(details['not_completed']),
                'completed': len(details['completed']),
                'not_completed': len(details['not_completed']),
                'added': len(details['added']),
                'removed': len(details['removed']),
            },
            'story_points': {},
            'details': details,
        }
        completed_sp = sum(item.get('story_points', 0.0) for item in details['completed'])
        not_completed_sp = sum(item.get('story_points', 0.0) for item in details['not_completed'])
        added_sp = sum(item.get('story_points', 0.0) for item in details['added'])
        removed_sp = sum(item.get('story_points', 0.0) for item in details['removed'])
        summary['story_points'] = {
            'planned': round(completed_sp + not_completed_sp, 2),
            'completed': round(completed_sp, 2),
            'not_completed': round(not_completed_sp, 2),
            'added': round(added_sp, 2),
            'removed': round(removed_sp, 2),
        }
        summary['worklog'] = self._aggregate_worklog(details)
        summary['teams'] = self._aggregate_team_summary(details)
        return summary

    # ---------------------- fetch ----------------------
    def _fetch_reports(self) -> List[SprintSummary]:
        if self._cache is not None:
            return self._cache
        settings = self._settings
        if not settings.enabled or not settings.board_ids:
            self._cache = []
            return self._cache
        lookback = max(1, int(settings.sprint_lookback))
        snapshots: List[SprintSummary] = []
        with self._client_factory() as client:
            for board_id in settings.board_ids:
                sprints_payload = client.get_sprints(board_id, state="active,closed")
                sprints = sprints_payload.get('values', []) or []

                def _sort_key(item: Dict[str, Any]):
                    start = self._parse_dt(item.get('startDate')) or datetime.min
                    complete = self._parse_dt(item.get('completeDate') or item.get('endDate')) or datetime.min
                    return (start, complete)

                sprints_sorted = sorted(sprints, key=_sort_key)
                selected = sprints_sorted[-lookback:]
                for sprint in selected:
                    sprint_id = sprint.get('id')
                    if sprint_id is None:
                        continue
                    report = client.get_sprint_report(board_id, sprint_id)
                    sprint_meta = report.get('sprint', sprint)
                    summary = self._build_summary(report, client, sprint_meta)
                    snapshot = SprintSummary(
                        board_id=board_id,
                        board_name=str(sprint_meta.get('originBoardId') or board_id),
                        sprint_id=sprint_id,
                        sprint_name=sprint_meta.get('name', f'Sprint {sprint_id}'),
                        started_at=self._parse_dt(sprint_meta.get('startDate')),
                        completed_at=self._parse_dt(sprint_meta.get('completeDate') or sprint_meta.get('endDate')),
                        state=sprint_meta.get('state', sprint.get('state', 'unknown')),
                        summary=summary,
                    )
                    snapshots.append(snapshot)
        self._cache = snapshots
        return snapshots

    def fetch_recent_sprint_summaries(self) -> List[SprintSummary]:  # noqa: D401
        return self._fetch_reports()

    # ---------------------- aggregations ----------------------
    def _collect_issue_metric(self, metric_key: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for snap in self._fetch_reports():
            for item in snap.summary['details'].get('completed', []):
                metric_value = item['metrics'].get(metric_key)
                if metric_value is None:
                    continue
                rows.append({
                    'board_id': snap.board_id,
                    'sprint_id': snap.sprint_id,
                    'sprint': snap.sprint_name,
                    'issue': item['key'],
                    'team': item.get('team'),
                    metric_key: metric_value,
                })
        return rows

    def compute_time_to_market(self) -> Dict[str, Any]:  # noqa: D401
        rows = self._collect_issue_metric('time_to_market_days')
        avg = round(sum(r['time_to_market_days'] for r in rows) / len(rows), 2) if rows else None
        return {
            'value': avg,
            'unit': 'days',
            'details': rows,
            'note': 'T2M вычисляется как время от создания до статуса завершения (по changelog/worklog).',
        }

    def compute_lead_time_delivery(self) -> Dict[str, Any]:  # noqa: D401
        rows = self._collect_issue_metric('lead_time_delivery_days')
        avg = round(sum(r['lead_time_delivery_days'] for r in rows) / len(rows), 2) if rows else None
        return {
            'value': avg,
            'unit': 'days',
            'details': rows,
            'note': 'Lead Time (Delivery) — от первого статуса из delivery_start до статуса завершения.',
        }

    def compute_lead_time_discovery(self) -> Dict[str, Any]:  # noqa: D401
        rows = self._collect_issue_metric('lead_time_discovery_days')
        avg = round(sum(r['lead_time_discovery_days'] for r in rows) / len(rows), 2) if rows else None
        return {
            'value': avg,
            'unit': 'days',
            'details': rows,
            'note': 'Discovery lead time — от discovery статусов до начала delivery. Настройте списки статусов под свой процесс.',
        }

    def compute_spillover(self) -> Dict[str, Any]:  # noqa: D401
        values = []
        for snap in self._fetch_reports():
            summary = snap.summary
            planned = summary['issues']['planned']
            not_completed = summary['issues']['not_completed']
            planned_sp = summary['story_points']['planned']
            not_completed_sp = summary['story_points']['not_completed']
            rate = (not_completed / planned) if planned else 0.0 if planned == 0 and not_completed == 0 else None
            values.append({
                'board_id': snap.board_id,
                'sprint_id': snap.sprint_id,
                'sprint': snap.sprint_name,
                'rate': round(rate, 3) if rate is not None else None,
                'planned_issues': planned,
                'not_completed_issues': not_completed,
                'planned_story_points': planned_sp,
                'not_completed_story_points': not_completed_sp,
            })
        filtered = [v for v in values if v['rate'] is not None]
        avg = round(sum(v['rate'] for v in filtered) / len(filtered), 3) if filtered else None
        return {
            'value': avg,
            'unit': 'ratio',
            'details': values,
            'note': 'Spillover = незавершённые задачи / план. Учёт по историям и story points.',
        }

    def compute_plan_vs_fact(self) -> Dict[str, Any]:  # noqa: D401
        rows = []
        for snap in self._fetch_reports():
            summary = snap.summary
            rows.append({
                'board_id': snap.board_id,
                'sprint_id': snap.sprint_id,
                'sprint': snap.sprint_name,
                'issues_planned': summary['issues']['planned'],
                'issues_completed': summary['issues']['completed'],
                'issues_added': summary['issues']['added'],
                'issues_removed': summary['issues']['removed'],
                'story_points_planned': summary['story_points']['planned'],
                'story_points_completed': summary['story_points']['completed'],
                'story_points_added': summary['story_points']['added'],
                'story_points_removed': summary['story_points']['removed'],
                'worklog_hours': summary['worklog']['total_hours'],
                'team_summary': summary['teams'],
            })
        return {
            'value': rows[-1] if rows else None,
            'unit': 'table',
            'details': rows,
            'note': 'План/факт по спринтам с учётом story points и суммарных часов списаний.',
        }

    def compute_velocity_trend(self) -> Dict[str, Any]:  # noqa: D401
        points = []
        for snap in self._fetch_reports():
            points.append({
                'board_id': snap.board_id,
                'sprint_id': snap.sprint_id,
                'sprint': snap.sprint_name,
                'completed_story_points': snap.summary['story_points']['completed'],
            })
        trend = [p['completed_story_points'] for p in points]
        return {
            'value': trend[-1] if trend else None,
            'unit': 'story_points',
            'details': points,
            'note': 'Velocity по завершённым story points. Используйте details для построения графиков.',
        }

    def compute_sprint_overview(self) -> Dict[str, Any]:  # noqa: D401
        snapshots = self._fetch_reports()
        details = [
            {
                'board_id': snap.board_id,
                'sprint_id': snap.sprint_id,
                'sprint': snap.sprint_name,
                'issues': snap.summary['issues'],
                'story_points': snap.summary['story_points'],
                'worklog': snap.summary['worklog'],
                'teams': snap.summary['teams'],
            }
            for snap in snapshots
        ]
        return {
            'value': details[-1] if details else None,
            'unit': 'sprints',
            'details': details,
            'note': 'Обобщённые данные по последним спринтам (issues, story points, worklog, команды).',
        }

    def compute_team_breakdown(self) -> Dict[str, Any]:  # noqa: D401
        rows = []
        for snap in self._fetch_reports():
            rows.append({
                'board_id': snap.board_id,
                'sprint_id': snap.sprint_id,
                'sprint': snap.sprint_name,
                'teams': snap.summary['teams'],
            })
        return {
            'value': rows[-1]['teams'] if rows else [],
            'unit': 'teams',
            'details': rows,
            'note': 'Разбивка по командам: план/факт, story points, списанные часы.',
        }

__all__ = [
    'JiraSprintMetricsService',
    'SprintSummary',
]