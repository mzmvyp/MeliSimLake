"""Testes do web scraper."""

from __future__ import annotations

import pytest

from ingestion.web_scraper.src.scraper_main import BookRecord


def test_book_record_validates_price() -> None:
    book = BookRecord(
        title="Clean Code",
        price_gbp=29.99,
        rating="Five",
        availability="In stock",
        url="http://books.toscrape.com",
        scraped_at="2026-01-01T00:00:00",
    )
    assert book.price_gbp == 29.99
    assert book.rating == "Five"


def test_book_record_requires_title() -> None:
    with pytest.raises(Exception):
        BookRecord(
            title=None,  # type: ignore[arg-type]
            price_gbp=10.0,
            rating="One",
            availability="In stock",
            url="http://x.com",
            scraped_at="2026-01-01",
        )
