FROM python:3.12-slim

WORKDIR /app

COPY student-3/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY student-3 /app/student-3

WORKDIR /app/student-3/backend

EXPOSE 5003

CMD ["python", "app.py"]