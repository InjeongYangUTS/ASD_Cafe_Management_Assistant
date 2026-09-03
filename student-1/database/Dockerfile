# =====================================================================
# Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
# DATABASE microservice : owns feedback.db and exposes it over /db/*
#
# Build:  docker compose build student-1-database
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7100 \
    FEEDBACK_DB_PATH=/app/data/feedback.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh && mkdir -p /app/data

EXPOSE 7100

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:7100/db/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./entrypoint.sh"]
