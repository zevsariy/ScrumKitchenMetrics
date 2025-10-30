"""Convenience launcher for FastAPI app."""
from __future__ import annotations

import uvicorn

def main():  # noqa: D401
    uvicorn.run("scrum_kitchen_metrics.api_server:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":  # pragma: no cover
    main()