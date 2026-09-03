# =====================================================================
# Student 4 (Stella Kwon) - Order & Kitchen Management
# DATABASE microservice : owns orders.db and exposes it over /db/*
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7400 \
    ORDER_DB_PATH=/app/data/orders.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh \
    && mkdir -p /app/data

EXPOSE 7400

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:7400/db/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
