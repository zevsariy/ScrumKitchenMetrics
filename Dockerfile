FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY src /app/src

RUN pip install --upgrade pip && \
    pip install . && \
    pip cache purge || true

EXPOSE 8000

ENV API_ENABLED=true \
    API_HOST=0.0.0.0 \
    API_PORT=8000

CMD ["uvicorn", "scrum_kitchen_metrics.api_server:app", "--host", "0.0.0.0", "--port", "8000"]