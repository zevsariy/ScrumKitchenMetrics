from pathlib import Path
import sys

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # type: ignore
from scrum_kitchen_metrics.api_server import app
from scrum_kitchen_metrics.config import refresh_settings
from scrum_kitchen_metrics.metrics.registry import get_metric_classes


def test_dynamic_metric_jira_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path))
    monkeypatch.setenv('JIRA_ENABLED', 'false')
    monkeypatch.chdir(tmp_path)
    refresh_settings()
    client = TestClient(app)
    resp = client.post('/ui/metrics/add', data={'key': 'jira_disabled_metric', 'label': 'Jira Disabled', 'expression': 'len(jira_issues)', 'description': ''})
    assert resp.status_code in (200, 303)
    classes = get_metric_classes()
    dyn = [c for c in classes if getattr(c, 'key', None) == 'jira_disabled_metric']
    assert dyn
    value = dyn[0]().compute().value
    assert value == 0


def test_dynamic_metric_jira_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path))
    monkeypatch.setenv('JIRA_ENABLED', 'true')
    monkeypatch.setenv('JIRA_BASE_URL', 'https://example.atlassian.net')
    monkeypatch.setenv('JIRA_API_TOKEN', 'dummy')
    monkeypatch.setenv('JIRA_USER_EMAIL', 'user@example.com')
    monkeypatch.chdir(tmp_path)

    # Stub JiraClient.search_issues_all
    class FakeIssue:
        def __init__(self, sp):
            self.data = {'fields': {'customfield_story_points': sp}}
        def get(self, k, default=None):
            if k == 'fields':
                return self.data['fields']
            return default

    from scrum_kitchen_metrics.api.jira_client import JiraClient
    def fake_search(self, jql, max_results=200):  # noqa: D401
        return [
            {'fields': {'customfield_story_points': 5}},
            {'fields': {'customfield_story_points': 8}},
            {'fields': {'customfield_story_points': 13}},
        ]
    JiraClient.search_issues_all = fake_search  # type: ignore

    refresh_settings()
    client = TestClient(app)
    expr = "avg([i['fields'].get('customfield_story_points',0) for i in jira_issues])"
    resp = client.post('/ui/metrics/add', data={'key': 'jira_sp_avg', 'label': 'SP Avg', 'expression': expr, 'description': 'Average story points'})
    assert resp.status_code in (200, 303)
    classes = get_metric_classes()
    dyn = [c for c in classes if getattr(c, 'key', None) == 'jira_sp_avg']
    assert dyn
    result = dyn[0]().compute()
    assert not (result.description or '').startswith('Dynamic error'), result.description
    value = result.value
    assert round(value,2) == round((5+8+13)/3,2)
    # cleanup registry to avoid leaking into other tests
    from scrum_kitchen_metrics.metrics import registry as reg
    if 'jira_sp_avg' in getattr(reg, '_REGISTRY', {}):  # type: ignore[attr-defined]
        reg._REGISTRY.pop('jira_sp_avg', None)  # type: ignore[attr-defined]
