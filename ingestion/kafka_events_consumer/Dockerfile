FROM bitnami/spark:3.5.1

USER root
RUN pip install --no-cache-dir \
    loguru==0.7.2 \
    pydantic-settings==2.4.0 \
    python-dotenv==1.0.1

WORKDIR /app
COPY . /app/ingestion/kafka_events_consumer
ENV PYTHONPATH=/app

ENTRYPOINT ["spark-submit", \
  "--master", "spark://spark-master:7077", \
  "--packages", \
    "io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0", \
  "/app/ingestion/kafka_events_consumer/src/events_streaming_job.py"]
