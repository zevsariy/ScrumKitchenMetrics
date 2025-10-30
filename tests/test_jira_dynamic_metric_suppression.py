import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scrum_kitchen_metrics.metrics.registry import get_metric_classes  # noqa: E402
from scrum_kitchen_metrics.config import get_settings  # noqa: E402
from scrum_kitchen_metrics.api_server import _collect  # noqa: E402
from scrum_kitchen_metrics.ui.router import reload_dynamic_metrics  # noqa: E402


def test_dynamic_jira_metric_suppressed(monkeypatch, tmp_path):
    # Prepare custom metric spec referencing jira_issues
    specs_path = Path('custom_metrics.json')
    specs_path.write_text('[{"key": "jira_issue_count_dyn", "label": "Issue Count Dyn", "expression": "len(jira_issues)", "description": "Count via jira_issues"}]', encoding='utf-8')
    # Disable JIRA
    monkeypatch.setenv('JIRA_ENABLED', 'false')
    monkeypatch.setenv('GITLAB_ENABLED', 'false')
    # Clear settings cache so disabled flag applies
    from scrum_kitchen_metrics import config as cfg
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]
    # Reload dynamic metrics after writing spec
    reload_dynamic_metrics()
    # Collect metrics
    results = _collect()
    # Assert dynamic metric is not present (should be tagged jira and filtered)
    keys = {r.key for r in results}
    assert 'jira_issue_count_dyn' not in keys

    # Enable JIRA and clear cache; metric should now appear
    monkeypatch.setenv('JIRA_ENABLED', 'true')
    cfg.get_settings.cache_clear()  # type: ignore[attr-defined]
    reload_dynamic_metrics()
    results_enabled = _collect()
    keys_enabled = {r.key for r in results_enabled}
    assert 'jira_issue_count_dyn' in keys_enabled
