"""DAG: ingestion_scraping_daily — scraping de preços públicos."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task

from orchestration.dags.lib.callbacks import slack_failure_callback

DEFAULT_ARGS = {
    "owner": "melisimlake",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=1),
    "on_failure_callback": slack_failure_callback,
}


@dag(
    dag_id="ingestion_scraping_daily",
    default_args=DEFAULT_ARGS,
    schedule="0 3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bronze", "ingestion", "scraping"],
)
def ingestion_scraping_daily() -> None:

    @task
    def scrape_books() -> None:
        """Executa scraper de livros (books.toscrape.com)."""
        from ingestion.web_scraper.src.scraper_main import run
        run()

    scrape_books()


ingestion_scraping_daily()
