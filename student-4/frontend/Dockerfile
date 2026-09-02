# =====================================================================
# Student 4 (Stella Kwon) - Order & Kitchen Management
# FRONTEND microservice : POS, Kitchen Display, Order Status (HTMX)
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5400 \
    SHARED_DIR=/app/shared

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5400

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:5400/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5400", "--workers", "2", "--timeout", "90", "app:app"]
