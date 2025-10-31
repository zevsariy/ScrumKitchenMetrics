import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scrum_kitchen_metrics.config import refresh_settings  # noqa: E402
from scrum_kitchen_metrics.services.jira_changelog_metrics import (  # noqa: E402
    ChangelogMetricSpec,
    JiraChangelogMetricsService,
)


class FakeJiraClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def search_issues_all(self, jql, max_results=200):  # noqa: D401
        assert jql == 'project = DEMO'
        return [{'key': 'ISSUE-1'}, {'key': 'ISSUE-2'}, {'key': 'ISSUE-3'}]

    def get_issue(self, issue_key, fields=None, expand=None):  # noqa: D401
        assert expand == 'changelog'
        base = {
            'key': issue_key,
            'fields': {
                'summary': f'Summary {issue_key}',
                'created': '2024-01-01T09:00:00.000+0000',
                'assignee': {'displayName': 'Alice'},
                'issuetype': {'name': 'Story'},
            },
        }
        if issue_key == 'ISSUE-1':
            base['changelog'] = {
                'histories': [
                    {
                        'created': '2024-01-02T09:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'Backlog', 'toString': 'In Progress'}],
                    },
                    {
                        'created': '2024-01-04T09:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'In Progress', 'toString': 'Done'}],
                    },
                ]
            }
        elif issue_key == 'ISSUE-2':
            base['changelog'] = {
                'histories': [
                    {
                        'created': '2024-01-03T11:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'Backlog', 'toString': 'In Progress'}],
                    },
                    {
                        'created': '2024-01-08T15:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'In Progress', 'toString': 'Done'}],
                    },
                ]
            }
        else:  # ISSUE-3 без завершающего статуса
            base['changelog'] = {
                'histories': [
                    {
                        'created': '2024-01-05T10:00:00.000+0000',
                        'items': [{'field': 'status', 'fromString': 'Backlog', 'toString': 'In Progress'}],
                    }
                ]
            }
        return base


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    monkeypatch.setenv('JIRA_ENABLED', 'true')
    monkeypatch.setenv('JIRA_BASE_URL', 'https://example.atlassian.net')
    monkeypatch.setenv('JIRA_API_TOKEN', 'token')
    monkeypatch.setenv('JIRA_USER_EMAIL', 'user@example.com')
    refresh_settings()
    yield
    refresh_settings()


def test_changelog_service_average():
    spec = ChangelogMetricSpec(
        key='jira_custom_lead_time',
        label='Lead Time',
        jql='project = DEMO',
        from_statuses=('In Progress',),
        to_statuses=('Done',),
        aggregation='avg',
        unit='days',
        max_results=100,
    )
    service = JiraChangelogMetricsService(client_factory=lambda: FakeJiraClient())
    data = service.compute(spec)
    assert data['unit'] == 'days'
    assert data['stats']['count_total'] == 3
    assert data['stats']['count_with_duration'] == 2
    # Issue-1: 2 days, Issue-2: ~5.17 days; avg ≈ 3.58
    assert data['value'] == pytest.approx(3.58, rel=1e-2)
    durations = {d['issue']: d for d in data['details'] if d['duration_unit'] is not None}
    assert durations['ISSUE-1']['duration_unit'] == pytest.approx(2.0, rel=1e-3)
    assert durations['ISSUE-2']['duration_unit'] == pytest.approx(5.17, rel=1e-2)


def test_changelog_service_percentile():
    spec = ChangelogMetricSpec(
        key='jira_custom_p90',
        label='Lead Time p90',
        jql='project = DEMO',
        from_statuses=('In Progress',),
        to_statuses=('Done',),
        aggregation='p90',
        unit='hours',
        max_results=100,
    )
    service = JiraChangelogMetricsService(client_factory=lambda: FakeJiraClient())
    data = service.compute(spec)
    assert data['unit'] == 'hours'
    # durations: 48h и 124h -> p90 ~124h
    assert data['value'] == pytest.approx(124.0, rel=1e-2)