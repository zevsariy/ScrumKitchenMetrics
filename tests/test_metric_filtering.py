import os
from pathlib import Path
import sys

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scrum_kitchen_metrics.config import get_settings  # noqa: E402
from scrum_kitchen_metrics.metrics.registry import get_metric_classes  # noqa: E402
from scrum_kitchen_metrics.api_server import _collect  # noqa: E402


def test_gitlab_project_ids_csv_parsing(monkeypatch):
    monkeypatch.setenv('GITLAB_PROJECT_IDS', '101, 202,303')
    # Clear cache to reload env
    from scrum_kitchen_metrics.config import _build_settings as build
    settings = build()
    assert settings.gitlab.project_ids == [101, 202, 303]


def test_metric_filtering(monkeypatch):
    # Disable JIRA/GitLab and ensure no jira/gitlab metrics returned
    monkeypatch.setenv('JIRA_ENABLED', 'false')
    monkeypatch.setenv('GITLAB_ENABLED', 'false')
    # Clear settings cache
    from scrum_kitchen_metrics.config import get_settings as gs  # noqa: E402
    gs.cache_clear()  # type: ignore[attr-defined]
    collected = _collect()
    # Ensure collected results exclude jira/gitlab metrics when disabled (by source attribute)
    assert all(getattr(r, 'source', None) != 'jira' for r in collected)
    assert all(getattr(r, 'source', None) != 'gitlab' for r in collected)
