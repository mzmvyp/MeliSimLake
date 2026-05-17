"""Web Scraper — coleta preços de books.toscrape.com com Playwright."""

from __future__ import annotations

import asyncio
import datetime
import io
import json
from typing import Any, Final

import boto3
import pandas as pd
from loguru import logger
from playwright.async_api import Page, async_playwright
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

TARGET_URL: Final[str] = "https://books.toscrape.com"
BRONZE_BUCKET: Final[str] = "bronze"
MAX_PAGES: Final[int] = 5


class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MELISIMLAKE_")

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"


settings = ScraperSettings()


class BookRecord(BaseModel):
    title: str
    price_gbp: float
    rating: str
    availability: str
    url: str
    scraped_at: str


def _s3_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )


def _persist_books(books: list[BookRecord], date: str) -> None:
    """Persiste lista de livros como Parquet no Bronze.

    Args:
        books: Lista de registros scrapeados.
        date: Data de partição YYYY-MM-DD.
    """
    rows = [b.model_dump() for b in books]
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    key = f"scraper/books/event_date={date}/books_{date}.parquet"
    _s3_client().put_object(Bucket=BRONZE_BUCKET, Key=key, Body=buffer.getvalue())
    logger.info("Parquet scraper salvo", extra={"key": key, "records": len(books)})


async def _scrape_page(page: Page, url: str) -> list[BookRecord]:
    """Extrai livros de uma página do catálogo.

    Args:
        page: Página Playwright.
        url: URL da página.

    Returns:
        Lista de BookRecord.
    """
    await page.goto(url)
    await page.wait_for_selector("article.product_pod")

    books: list[BookRecord] = []
    articles = await page.query_selector_all("article.product_pod")
    for article in articles:
        title_el = await article.query_selector("h3 > a")
        price_el = await article.query_selector(".price_color")
        rating_el = await article.query_selector(".star-rating")
        avail_el = await article.query_selector(".availability")

        if not (title_el and price_el):
            continue

        title = await title_el.get_attribute("title") or ""
        price_str = await price_el.inner_text()
        price = float(price_str.replace("£", "").replace(",", "").strip())
        rating_classes = await rating_el.get_attribute("class") if rating_el else ""
        rating = (rating_classes or "").replace("star-rating ", "").strip()
        availability = (await avail_el.inner_text()).strip() if avail_el else ""

        books.append(
            BookRecord(
                title=title,
                price_gbp=price,
                rating=rating,
                availability=availability,
                url=url,
                scraped_at=datetime.datetime.now().isoformat(),
            )
        )
    return books


async def scrape(max_pages: int = MAX_PAGES) -> list[BookRecord]:
    """Scrapa N páginas do catálogo books.toscrape.com.

    Args:
        max_pages: Número máximo de páginas a raspar.

    Returns:
        Lista consolidada de BookRecord.
    """
    all_books: list[BookRecord] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                url = TARGET_URL
            else:
                url = f"{TARGET_URL}/catalogue/page-{page_num}.html"

            logger.info("Scraping página", extra={"page": page_num, "url": url})
            try:
                books = await _scrape_page(page, url)
                all_books.extend(books)
                logger.info("Livros coletados", extra={"page": page_num, "count": len(books)})
            except Exception as exc:
                logger.error("Erro ao scrapar página", extra={"page": page_num, "error": str(exc)})

        await browser.close()
    return all_books


def run() -> None:
    """Entry point do web scraper."""
    date = datetime.date.today().isoformat()
    logger.info("Web scraper iniciado", extra={"date": date, "target": TARGET_URL})
    books = asyncio.run(scrape())
    if books:
        _persist_books(books, date)
    logger.info("Web scraper concluído", extra={"total": len(books)})


if __name__ == "__main__":
    run()
