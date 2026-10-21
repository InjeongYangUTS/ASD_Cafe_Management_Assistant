FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py planner.py worker.py reviewer.py workflow.py ./

EXPOSE 5800

CMD ["python", "app.py"]