# AI-SOC FastAPI image. Do not copy .venv, .env, or secrets.
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    API_HOST=0.0.0.0 \
    API_PORT=8000

WORKDIR /app
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin aisoc \
    && mkdir -p /app \
    && chown aisoc:aisoc /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=aisoc:aisoc alembic.ini ./
COPY --chown=aisoc:aisoc migrations ./migrations
COPY --chown=aisoc:aisoc app ./app

USER aisoc
EXPOSE 8000

# Uvicorn handles SIGTERM. Keep-alive > typical SSE investigation duration.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--timeout-keep-alive", "75"]
