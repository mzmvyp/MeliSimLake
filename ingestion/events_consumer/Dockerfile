FROM bitnamilegacy/spark:3.5.1

USER root
RUN pip install --no-cache-dir loguru==0.7.2

WORKDIR /app
COPY ingestion/__init__.py /app/ingestion/__init__.py
COPY ingestion/events_consumer /app/ingestion/events_consumer

ENV PYTHONPATH=/app

ENTRYPOINT ["spark-submit", \
  "--master", "spark://spark-master:7077", \
  "--packages", \
    "org.apache.hadoop:hadoop-aws:3.3.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0", \
  "/app/ingestion/events_consumer/src/events_streaming_job.py"]
