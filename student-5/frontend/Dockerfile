FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY index.html .

EXPOSE 5500

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5500', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "http.server", "5500", "--bind", "0.0.0.0"]