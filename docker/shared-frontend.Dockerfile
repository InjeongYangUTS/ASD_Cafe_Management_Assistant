# =====================================================================
# Shared entry point container : index.html, authentication pages,
# customer/staff dashboards and the shared CSS theme.
#
# The source in ./shared is owned by the group and is NOT modified by
# this image - it is only copied in and served.
#
# Added by Student 4 (Stella Kwon) so `docker compose up` brings up the
# single shared entry point required by Release 0.
#
# Build context is the repository root:
#     docker compose build shared-frontend
# =====================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5100

WORKDIR /app

RUN pip install --no-cache-dir Flask==3.0.3 Werkzeug==3.0.3 gunicorn==22.0.0

COPY shared/ /app/shared/

WORKDIR /app/shared/frontend

# Seed the shared users.db on first boot if it is not in the image.
RUN if [ ! -f /app/shared/database/users.db ]; then \
        python /app/shared/database/seed.py; \
    fi

EXPOSE 5100

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:5100/', timeout=4).status == 200 else 1)"

CMD ["gunicorn", "--bind", "0.0.0.0:5100", "--workers", "2", "app:app"]
