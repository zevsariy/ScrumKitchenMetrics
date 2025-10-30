from scrum_kitchen_metrics.metrics.registry import get_metric_classes

def test_registry_discovers_metrics():
    classes = get_metric_classes()
    # Базовые примеры из проекта должны быть найдены
    keys = {c.key for c in classes}
    assert 'jira_issue_count' in keys
    assert 'gitlab_projects_count' in keys