"""MeliSimLake Dashboard — ponto de entrada Streamlit."""

from __future__ import annotations

import os

import streamlit as st

from src.lib.trino_client import query_trino

st.set_page_config(
    page_title="MeliSimLake Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("MeliSimLake — Lakehouse Analítico")
st.markdown(
    """
    Plataforma de dados que consome o ecossistema **Melisim** (e-commerce simulado
    estilo Mercado Livre) em tempo real e materializa métricas analíticas no
    formato Delta Lake, expostas via Trino.

    **Pipeline**

    `Melisim (Postgres + MySQL + Kafka)` → Debezium / Spark Streaming →
    `Bronze (Parquet)` → Spark batch → `Gold (Delta)` → Trino → Streamlit.

    Use o menu lateral para navegar:

    | Página | Descrição | Tabelas Gold |
    |--------|-----------|--------------|
    | 📈 Executive KPIs | GMV, pedidos, AOV, taxa de pagamento | `fact_orders`, `fact_payments` |
    | 🛒 Product Analytics | Catálogo, vendas, estoque, alertas | `dim_products`, `product_metrics_daily`, `fact_stock_alerts` |
    | 👥 Customer Analytics | RFM, churn por inatividade, LTV | `dim_users`, `customer_rfm`, `fact_orders` |
    | 💳 Payments Health | Funil pedido → pagamento, notificações | `fact_payments`, `notifications_daily` |
    | 🤖 ML Monitoring | Modelos no MLflow + previsões live (churn, fraude, demanda, recomendação) | `gold_ml.*`, MLflow Registry, ml-api |
    """,
    unsafe_allow_html=False,
)

st.divider()
st.subheader("Saúde do pipeline (em tempo real)")

stats = query_trino(
    """
    SELECT
        (SELECT COUNT(*) FROM delta.gold.dim_users)              AS users,
        (SELECT COUNT(*) FROM delta.gold.dim_products)           AS products,
        (SELECT COUNT(*) FROM delta.gold.fact_orders)            AS orders,
        (SELECT COUNT(*) FROM delta.gold.fact_payments)          AS payments,
        (SELECT COUNT(*) FROM delta.gold.fact_payments WHERE status = 'CONFIRMED') AS paid,
        (SELECT COUNT(*) FROM delta.gold.customer_rfm)           AS active_buyers
    """
)

if stats.empty:
    st.error(
        "Trino indisponível ou tabelas Gold ainda não materializadas. "
        "Suba os serviços com `docker compose up -d` e aguarde o batch-runner."
    )
else:
    row = stats.iloc[0]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Users (CDC MySQL)", f"{int(row['users']):,}")
    c2.metric("Products (CDC PG)", f"{int(row['products']):,}")
    c3.metric("Orders", f"{int(row['orders']):,}")
    c4.metric("Payments", f"{int(row['payments']):,}")
    c5.metric("Pagos", f"{int(row['paid']):,}")
    c6.metric("Buyers ativos", f"{int(row['active_buyers']):,}")

st.divider()
st.caption(
    f"Trino: `{os.getenv('TRINO_HOST', 'trino')}:{os.getenv('TRINO_PORT', '8080')}` · "
    f"Catalog: `{os.getenv('TRINO_CATALOG', 'delta')}` · "
    f"Schema: `{os.getenv('TRINO_SCHEMA', 'gold')}`"
)
