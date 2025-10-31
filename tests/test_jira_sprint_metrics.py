import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from scrum_kitchen_metrics.config import refresh_settings  # noqa: E402
from scrum_kitchen_metrics.metrics import jira_sprint_metrics as metrics_module  # noqa: E402
from scrum_kitchen_metrics.metrics.jira_sprint_metrics import (  # noqa: E402
    JiraSprintLeadTimeDeliveryMetric,
    JiraSprintLeadTimeDiscoveryMetric,
    JiraSprintOverviewMetric,
    JiraSprintPlanFactMetric,
    JiraSprintSpilloverMetric,
    JiraSprintTeamProgressMetric,
    JiraSprintTimeToMarketMetric,
    JiraSprintVelocityTrendMetric,
)
from scrum_kitchen_metrics.services.jira_sprint_metrics import JiraSprintMetricsService  # noqa: E402


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setenv('JIRA_ENABLED', 'false')
    monkeypatch.delenv('JIRA_BOARD_IDS', raising=False)
    refresh_settings()
    yield
    refresh_settings()


def _ensure_disabled(metric_cls):
    metric = metric_cls()
    res = metric.compute()
    assert res.value is None
    assert 'JIRA' in (res.description or '')


def test_metrics_return_disabled_when_jira_off():
    for cls in [
        JiraSprintTimeToMarketMetric,
        JiraSprintLeadTimeDeliveryMetric,
        JiraSprintLeadTimeDiscoveryMetric,
        JiraSprintSpilloverMetric,
        JiraSprintPlanFactMetric,
        JiraSprintVelocityTrendMetric,
        JiraSprintOverviewMetric,
        JiraSprintTeamProgressMetric,
    ]:
        _ensure_disabled(cls)


class FakeJiraClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # Agile endpoints
    def get_sprints(self, board_id, state="active,closed", max_results=50, start_at=0):  # noqa: D401
        return {
            'values': [
                {
                    'id': 101,
                    'name': 'Sprint 1',
                    'startDate': '2024-01-01T09:00:00.000+0000',
                    'completeDate': '2024-01-14T18:00:00.000+0000',
                    'state': 'closed',
                }
            ]
        }

    def get_sprint_report(self, board_id, sprint_id):  # noqa: D401
        return {
            'sprint': {
                'id': sprint_id,
                'name': 'Sprint 1',
                'originBoardId': board_id,
                'startDate': '2024-01-01T09:00:00.000+0000',
                'completeDate': '2024-01-14T18:00:00.000+0000',
                'state': 'closed',
            },
            'contents': {
                'completedIssues': [
                    {
                        'key': 'PROJ-1',
                        'estimateStatistic': {
                            'statFieldValue': {'value': 8}
                        },
                    }
                ],
                'issuesNotCompletedInCurrentSprint': [],
                'issuesAddedDuringSprint': [],
                'puntedIssues': [],
            },
        }

    def get_issue(self, issue_key, fields=None, expand=None, extra=None):  # noqa: D401
        assert issue_key == 'PROJ-1'
        return {
            'fields': {
                'created': '2024-01-02T10:00:00.000+0000',
                'resolutiondate': '2024-01-14T18:30:00.000+0000',
                'status': {'name': 'Done'},
                'issuetype': {'name': 'Story'},
                'summary': 'Implement feature',
                'assignee': {'displayName': 'Alice'},
                'customfield_story_points': 8,
                'customfield_team': {'value': 'Team Rocket'},
            },
            'changelog': {
                'histories': [
                    {
                        'created': '2024-01-03T09:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'Backlog', 'toString': 'Discovery'}],
                    },
                    {
                        'created': '2024-01-05T09:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'Discovery', 'toString': 'In Progress'}],
                    },
                    {
                        'created': '2024-01-12T17:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'In Progress', 'toString': 'In Review'}],
                    },
                    {
                        'created': '2024-01-14T18:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'In Review', 'toString': 'Done'}],
                    },
                ]
            },
        }

    def get_issue_worklog(self, issue_key):  # noqa: D401
        return {
            'worklogs': [
                {
                    'author': {'displayName': 'Alice'},
                    'timeSpentSeconds': 4 * 3600,
                },
                {
                    'author': {'displayName': 'Bob'},
                    'timeSpentSeconds': 2 * 3600,
                },
            ]
        }


def _configure_env(monkeypatch):
    monkeypatch.setenv('JIRA_ENABLED', 'true')
    monkeypatch.setenv('JIRA_BOARD_IDS', '[1]')
    monkeypatch.setenv('JIRA_SPRINT_LOOKBACK', '1')
    monkeypatch.setenv('JIRA_STORY_POINTS_FIELD', 'customfield_story_points')
    monkeypatch.setenv('JIRA_DISCOVERY_STATUSES', 'Discovery')
    monkeypatch.setenv('JIRA_DELIVERY_START_STATUSES', 'In Progress,In Review')
    monkeypatch.setenv('JIRA_DELIVERY_END_STATUSES', 'Done')
    monkeypatch.setenv('JIRA_TEAM_CUSTOM_FIELD', 'customfield_team')
    refresh_settings()


def test_service_computations(monkeypatch):
    _configure_env(monkeypatch)
    service = JiraSprintMetricsService(client_factory=lambda: FakeJiraClient())

    t2m = service.compute_time_to_market()
    assert t2m['value'] == pytest.approx(12.33, rel=1e-2)

    lead_delivery = service.compute_lead_time_delivery()
    assert lead_delivery['value'] == pytest.approx(9.38, rel=1e-2)

    lead_discovery = service.compute_lead_time_discovery()
    assert lead_discovery['value'] == pytest.approx(2.0, rel=1e-3)

    spillover = service.compute_spillover()
    assert spillover['value'] == 0.0

    plan_fact = service.compute_plan_vs_fact()
    assert plan_fact['value']['worklog_hours'] == pytest.approx(6.0, rel=1e-3)
    assert plan_fact['value']['story_points_completed'] == pytest.approx(8.0, rel=1e-3)

    velocity = service.compute_velocity_trend()
    assert velocity['value'] == pytest.approx(8.0, rel=1e-3)

    overview = service.compute_sprint_overview()
    assert overview['value']['worklog']['total_hours'] == pytest.approx(6.0, rel=1e-3)

    team = service.compute_team_breakdown()
    assert team['value'][0]['team'] == 'Team Rocket'
    assert team['value'][0]['issues']['completed'] == 1
    assert team['value'][0]['worklog_hours'] == pytest.approx(6.0, rel=1e-3)


def test_metrics_with_stubbed_service(monkeypatch):
    _configure_env(monkeypatch)
    service = JiraSprintMetricsService(client_factory=lambda: FakeJiraClient())
    monkeypatch.setattr(metrics_module._BaseJiraSprintMetric, '_service', lambda self: service)

    assert JiraSprintTimeToMarketMetric().compute().value == pytest.approx(12.33, rel=1e-2)
    assert JiraSprintLeadTimeDeliveryMetric().compute().value == pytest.approx(9.38, rel=1e-2)
    assert JiraSprintLeadTimeDiscoveryMetric().compute().value == pytest.approx(2.0, rel=1e-3)
    assert JiraSprintSpilloverMetric().compute().value == 0.0
    assert JiraSprintPlanFactMetric().compute().value['worklog_hours'] == pytest.approx(6.0, rel=1e-3)
    assert JiraSprintVelocityTrendMetric().compute().value == pytest.approx(8.0, rel=1e-3)
    assert JiraSprintOverviewMetric().compute().value['worklog']['total_hours'] == pytest.approx(6.0, rel=1e-3)
    assert JiraSprintTeamProgressMetric().compute().value[0]['team'] == 'Team Rocket'
