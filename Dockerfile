FROM python:3.13-slim@sha256:8296499feed1c18bd8064c279d45e2a1b4b6be586f8b9e16dcf2aaf843480d88

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.lock /app/
COPY app /app/app
COPY docs /app/docs
COPY alembic.ini /app/
COPY migrations /app/migrations
COPY scripts /app/scripts

RUN pip install --no-cache-dir -c requirements.lock hatchling \
    && pip install --no-cache-dir --no-build-isolation -c requirements.lock .

EXPOSE 8000

CMD ["python", "-m", "app.main"]
