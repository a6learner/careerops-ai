FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY constraints/deployment-py311-linux.txt ./constraints/deployment-py311-linux.txt
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir \
        --constraint constraints/deployment-py311-linux.txt ".[worker]" \
    && addgroup --system careerops \
    && adduser --system --ingroup careerops careerops

FROM base AS worker

RUN apt-get update \
    && apt-get install --no-install-recommends --yes libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

USER careerops

CMD ["dramatiq", "careerops.workers.tasks", "--processes", "1", "--threads", "4"]

FROM base AS api

USER careerops

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["uvicorn", "careerops.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
