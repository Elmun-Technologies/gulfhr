FROM python:3.11-slim

WORKDIR /app

COPY requirements-leadbot.txt .
RUN pip install --no-cache-dir -r requirements-leadbot.txt

COPY leadbot ./leadbot

CMD ["python", "-m", "leadbot.main"]
