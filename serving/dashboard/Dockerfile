FROM python:3.11-slim

RUN pip install --no-cache-dir \
    streamlit==1.38.0 \
    pandas==2.2.2 \
    plotly==5.24.0 \
    sqlalchemy==2.0.35 \
    psycopg2-binary==2.9.9 \
    trino==0.329.0 \
    httpx==0.27.0 \
    pydantic-settings==2.4.0 \
    loguru==0.7.2 \
    python-dotenv==1.0.1 \
    pyarrow==17.0.0 \
    mlflow==2.16.0

WORKDIR /app
COPY . /app

ENV PYTHONPATH=/app

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
