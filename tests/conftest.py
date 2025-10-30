import os
from pathlib import Path
import shutil
import pytest

# Базовый путь к тестовой копии файла кастомных метрик
@pytest.fixture(autouse=True)
def isolate_custom_metrics(tmp_path, monkeypatch):
    """Изолирует custom_metrics.json через переменную окружения CUSTOM_METRICS_FILE."""
    test_file = tmp_path / 'custom_metrics.json'
    monkeypatch.setenv('CUSTOM_METRICS_FILE', str(test_file))
    yield
    if test_file.exists():
        test_file.unlink()
