# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

FROM base AS runtime
RUN useradd --system --uid 10001 --create-home app && mkdir -p /srv/storage && chown app /srv/storage
COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --chown=app alembic.ini ./
COPY --chown=app alembic ./alembic
COPY --chown=app app ./app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
# Migrations are run explicitly (see docker-compose.yml and docs/07-deployment.md), not on every boot.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "2"]
