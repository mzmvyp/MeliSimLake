# ingestion/web_scraper

Scraper Playwright que coleta preços e dados de livros de `books.toscrape.com` (site de demonstração — não scraping de sites reais).

## Saída Bronze

```
s3a://bronze/scraper/books/event_date=YYYY-MM-DD/books_YYYY-MM-DD.parquet
```

## Como rodar

```bash
python -m ingestion.web_scraper.src.scraper_main
# ou via Docker:
docker run --rm melisimlake-scraper
```
