from scrum_kitchen_metrics.config import get_settings, refresh_settings

def test_settings_load():
    # Rebuild settings to avoid cross-test env leakage
    settings = refresh_settings()
    assert settings.core.app_name
    # Ensure output directory exists (name may differ if env overrides present)
    assert settings.report.output_dir.exists()
