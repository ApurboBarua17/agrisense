FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download the model at build time so pod startup is fast (no cold start over network).
RUN python -c "from model import get_pipeline; get_pipeline()"

CMD ["python", "worker.py"]
