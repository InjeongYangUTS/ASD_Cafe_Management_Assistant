# =====================================================================
# Student 1 (Hangyeol Yi) - Customer Feedback & Reviews
# BACKEND / API microservice : review logic + AI-Mode
#
# BUILD CONTEXT IS student-1/, NOT student-1/backend/.
# The prompt files live at student-1/prompts so that this service and the
# agentic loop share one copy of them, and a Dockerfile cannot COPY from
# outside its context. docker-compose.yml therefore uses:
#
#     build:
#       context: ./student-1
#       dockerfile: backend/Dockerfile
#
# Build:  docker compose build student-1-backend
# =====================================================================
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

# Probes the shallow /api/health, which checks only the feedback database.
# A deep probe of the optional services takes longer than this timeout.
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8100/api/health', timeout=4).status == 200 else 1)"

# 240s timeout: an AI-Mode request waits on a full Ollama generation, and a
# cold model load on a laptop can take minutes.
CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "240", "app:app"]
