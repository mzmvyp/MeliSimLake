FROM bitnamilegacy/spark:3.5.1

USER root
RUN pip install --no-cache-dir loguru==0.7.2

WORKDIR /app
COPY transformation/__init__.py /app/transformation/__init__.py
COPY transformation/spark_jobs /app/transformation/spark_jobs

ENV PYTHONPATH=/app

# Roda o pipeline batch em loop a cada BATCH_INTERVAL_SECONDS (default 60s).
# Cada execucao reescreve as tabelas Delta gold.
ENV BATCH_INTERVAL_SECONDS=60

ENTRYPOINT ["/bin/sh", "-c", "while true; do echo \"[batch-runner] $(date -u +%FT%TZ) submitting bronze->gold\"; spark-submit --master spark://spark-master:7077 --packages io.delta:delta-spark_2.12:3.2.0,org.apache.hadoop:hadoop-aws:3.3.4 /app/transformation/spark_jobs/src/jobs/bronze_to_gold_unified.py || echo '[batch-runner] job falhou'; echo \"[batch-runner] sleep ${BATCH_INTERVAL_SECONDS}s\"; sleep ${BATCH_INTERVAL_SECONDS}; done"]
