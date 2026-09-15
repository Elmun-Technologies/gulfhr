FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY leadbot ./leadbot

RUN mkdir -p /app/data

# Fly'da ishga tushiriladigan bot: Gulf HR — nomzodlarni vakansiya talablari
# bo'yicha saralash + (sozlangan bo'lsa) amoCRM jarayon nazorati
CMD ["python", "-m", "app.main"]
