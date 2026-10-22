FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api /app/apps/api
COPY .env.example /app/.env.example

WORKDIR /app/apps/api
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 8010

CMD ["uvicorn", "pulse.main:app", "--host", "0.0.0.0", "--port", "8010"]
