from pathlib import Path
import sys

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # type: ignore
from scrum_kitchen_metrics.api_server import app
from scrum_kitchen_metrics.config import refresh_settings
from scrum_kitchen_metrics.metrics.registry import get_metric_classes


def test_add_custom_metric(tmp_path, monkeypatch):
    # Redirect report output dir to tmp to avoid pollution
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path))
    # Ensure custom metrics file is in temp dir by changing CWD
    monkeypatch.chdir(tmp_path)
    refresh_settings()
    client = TestClient(app)

    # Add custom metric via UI form
    resp = client.post('/ui/metrics/add', data={
        'key': 'custom_test_metric',
        'label': 'Custom Test Metric',
        'expression': '42',
        'description': 'Answer to everything'
    })
    assert resp.status_code in (200, 303)

    # Fetch metrics list page to ensure it appears (optional)
    page = client.get('/ui/metrics')
    assert page.status_code == 200
    assert 'custom_test_metric' in page.text

    # Verify dynamic registry includes the metric and compute works
    classes = get_metric_classes()
    dyn_cls = [c for c in classes if getattr(c, 'key', None) == 'custom_test_metric']
    assert dyn_cls, 'Dynamic custom metric class not registered'
    inst = dyn_cls[0]()
    res = inst.compute()
    assert res.value == 42
    assert res.key == 'custom_test_metric'
