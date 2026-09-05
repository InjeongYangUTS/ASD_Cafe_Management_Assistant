FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8100 \
    PROMPT_DIR=/app/prompts

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY prompts/ /app/prompts/

EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8100/api/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "240", "app:app"]
