FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy Italian model
RUN python -m spacy download it_core_news_sm

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs data

# Single worker + single pipeline slot = at most one query running at a time.
# WORKERS and MAX_CONCURRENT_PIPELINES can be overridden at runtime via env vars
# if more throughput is needed, but the defaults enforce strict serialisation.
ENV WORKERS=1
ENV MAX_CONCURRENT_PIPELINES=1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS}
