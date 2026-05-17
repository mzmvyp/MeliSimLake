FROM bitnamilegacy/spark:3.5.1

USER root
RUN pip install --no-cache-dir \
    loguru==0.7.2 \
    pydantic-settings==2.4.0 \
    python-dotenv==1.0.1

WORKDIR /app
# Build context = repo root (see docker-compose service `build.context`).
COPY ingestion/__init__.py /app/ingestion/__init__.py
COPY ingestion/cdc_consumer /app/ingestion/cdc_consumer

ENV PYTHONPATH=/app

ENTRYPOINT ["spark-submit", \
  "--master", "spark://spark-master:7077", \
  "--packages", \
    "io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0", \
  "/app/ingestion/cdc_consumer/src/cdc_streaming_job.py"]
