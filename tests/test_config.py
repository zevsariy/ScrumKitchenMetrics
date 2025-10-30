from scrum_kitchen_metrics.config import get_settings

def test_settings_load():
    settings = get_settings()
    assert settings.core.app_name
    assert settings.report.output_dir.name == 'reports'
