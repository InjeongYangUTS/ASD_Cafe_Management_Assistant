FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7300
ENV INVENTORY_DB_PATH=/app/data/inventory.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py init_db.py ./
RUN mkdir -p /app/data

EXPOSE 7300

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:7300/db/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:7300", "--workers", "1", "--timeout", "90", "app:app"]
