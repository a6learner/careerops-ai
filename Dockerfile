FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir -e ".[worker]"

EXPOSE 8000

CMD ["uvicorn", "careerops.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
