# ingestion/kafka_events_consumer

Spark Structured Streaming que consome tópicos de eventos comportamentais do Melisim.

## Tópicos

| Tópico             | Evento         | Schema              |
|--------------------|----------------|---------------------|
| `events.clicks`    | Clique         | CLICK_SCHEMA        |
| `events.cart`      | Carrinho       | CART_SCHEMA         |
| `events.search`    | Busca          | SEARCH_SCHEMA       |
| `events.purchase`  | Compra         | PURCHASE_SCHEMA     |

## Saída Bronze

```
s3a://bronze/events/clicks/event_date=YYYY-MM-DD/
s3a://bronze/events/cart/event_date=YYYY-MM-DD/
s3a://bronze/events/search/event_date=YYYY-MM-DD/
s3a://bronze/events/purchase/event_date=YYYY-MM-DD/
```
