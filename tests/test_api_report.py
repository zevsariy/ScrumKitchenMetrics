from pathlib import Path
import sys

SRC = Path(__file__).parent.parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # type: ignore
from scrum_kitchen_metrics.api_server import app
from scrum_kitchen_metrics.config import refresh_settings


def test_report_endpoint_creates_files(tmp_path, monkeypatch):
    # Point reports dir to temp
    monkeypatch.setenv('REPORT_OUTPUT_DIR', str(tmp_path))
    refresh_settings()
    client = TestClient(app)
    resp = client.post('/report')
    assert resp.status_code == 200
    data = resp.json()
    files = data.get('files', [])
    assert files, 'No files returned by /report'
    for f in files:
        p = Path(f)
        assert p.exists(), f'Missing file {p}'
        assert p.stat().st_size > 0, f'Empty file {p}'
