from pathlib import Path
import sys

# Ensure src on path
SRC = Path(__file__).parent / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient  # type: ignore
from scrum_kitchen_metrics.api_server import app
from scrum_kitchen_metrics.config import get_settings

client = TestClient(app)

# Health
health = client.get('/health').json()
print('HEALTH:', health)

# Metrics
metrics = client.get('/metrics').json()
print('METRICS COUNT:', len(metrics))
print('METRICS SAMPLE:', metrics[:2])

# Report generation
report = client.post('/report').json()
print('REPORT FILES:', report)

# Confirm files exist
for f in report.get('files', []):
    p = Path(f)
    print('FILE EXISTS:', p, p.exists(), p.stat().st_size if p.exists() else None)
