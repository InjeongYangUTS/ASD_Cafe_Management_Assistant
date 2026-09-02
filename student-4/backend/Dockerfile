# =====================================================================
# Student 4 (Stella Kwon) - Order & Kitchen Management
# BACKEND / API microservice : ordering logic + AI-Mode
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8400

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8400

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8400/api/health', timeout=4).status == 200 else 1)"

# 60s timeout: an Ollama generation can legitimately take that long.
CMD ["gunicorn", "--bind", "0.0.0.0:8400", "--workers", "2", "--timeout", "90", "app:app"]
