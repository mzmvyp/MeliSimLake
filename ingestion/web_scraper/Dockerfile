FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin

RUN pip install --no-cache-dir \
    playwright==1.47.0 \
    boto3==1.35.0 \
    pandas==2.2.0 \
    pyarrow==17.0.0 \
    loguru==0.7.2 \
    pydantic==2.8.0 \
    pydantic-settings==2.4.0 \
    python-dotenv==1.0.1

WORKDIR /app
COPY . /app/ingestion/web_scraper
ENV PYTHONPATH=/app

CMD ["python", "-m", "ingestion.web_scraper.src.scraper_main"]
