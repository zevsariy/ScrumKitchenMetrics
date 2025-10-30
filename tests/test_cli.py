import pytest
from typer.testing import CliRunner

from scrum_kitchen_metrics.cli import app

runner = CliRunner()

def test_cli_fetch_metrics(monkeypatch):
    # Avoid real API calls: monkeypatch metric classes to return constant values
    from scrum_kitchen_metrics import cli as cli_module

    class DummyMetric:
        def __init__(self):
            self.key = 'dummy'
            self.label = 'Dummy'
            self.description = None
        def compute(self):
            from scrum_kitchen_metrics.metrics.base import MetricResult
            return MetricResult('dummy', 'Dummy', 123)
    monkeypatch.setattr(cli_module, 'METRIC_CLASSES', [DummyMetric])
    result = runner.invoke(app, ["fetch-metrics", "--json-output"])
    assert result.exit_code == 0, result.output
    assert 'dummy' in result.output
