FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY app /app/app
COPY docs /app/docs
COPY alembic.ini /app/
COPY migrations /app/migrations

RUN pip install --upgrade pip \
    && pip install .

EXPOSE 8000

CMD ["python", "-m", "app.main"]
