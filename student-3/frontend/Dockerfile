FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5300

WORKDIR /app

COPY frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ ./frontend/
COPY assets/ ./assets/

WORKDIR /app/frontend

EXPOSE 5300

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5300/health', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5300", "--workers", "2", "--timeout", "120", "app:app"]
