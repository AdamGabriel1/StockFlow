# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) deps (layer cache: só reinstala se requirements.txt mudar)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2) código (muda com frequência → layer separada, rebuild rápido)
COPY stockflow/ ./stockflow/
COPY run_api.py .

# 3) usuário não-root + diretório do banco
RUN useradd --create-home --uid 1000 app \
 && mkdir -p /data \
 && chown -R app:app /app /data
USER app

ENV STOCKFLOW_DB=/data/stockflow.db \
    STOCKFLOW_HOST=0.0.0.0 \
    STOCKFLOW_PORT=8000 \
    STOCKFLOW_RELOAD=0

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)" || exit 1

CMD ["uvicorn", "stockflow.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
