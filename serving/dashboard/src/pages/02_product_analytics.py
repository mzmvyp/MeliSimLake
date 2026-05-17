"""Página 2 — Product Analytics.

Fonte: `delta.gold.product_metrics_daily`, `delta.gold.dim_products`,
`delta.gold.fact_orders`, `delta.gold.fact_stock_alerts`.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.lib.trino_client import query_trino

st.set_page_config(page_title="Product Analytics", page_icon="🛒", layout="wide")
st.title("🛒 Product Analytics")
st.caption(
    "Catálogo, vendas e estoque do Melisim (products-service + orders-service + stock-monitor) "
    "materializado no lakehouse."
)

with st.spinner("Carregando dados de produtos..."):
    df_cat = query_trino(
        """
        SELECT
            COALESCE(p.category, 'unknown') AS category,
            SUM(m.gmv)                       AS gmv,
            SUM(m.orders)                    AS orders,
            SUM(m.units_sold)                AS units_sold
        FROM delta.gold.product_metrics_daily m
        LEFT JOIN delta.gold.dim_products p ON m.product_id = p.product_id
        WHERE m.order_date IS NOT NULL
          AND m.order_date >= CURRENT_DATE - INTERVAL '30' DAY
        GROUP BY 1
        ORDER BY gmv DESC NULLS LAST
        """
    )

    df_top = query_trino(
        """
        SELECT
            p.product_id,
            COALESCE(p.title, CAST(p.product_id AS varchar)) AS product_name,
            COALESCE(p.category, 'unknown')                  AS category,
            p.price,
            p.stock,
            COALESCE(SUM(m.gmv), 0)         AS gmv,
            COALESCE(SUM(m.orders), 0)      AS orders,
            COALESCE(SUM(m.units_sold), 0)  AS units_sold
        FROM delta.gold.dim_products p
        LEFT JOIN delta.gold.product_metrics_daily m ON p.product_id = m.product_id
        GROUP BY p.product_id, p.title, p.category, p.price, p.stock
        ORDER BY gmv DESC NULLS LAST
        LIMIT 25
        """
    )

    df_stock = query_trino(
        """
        SELECT product_id, title, stock
        FROM delta.gold.dim_products
        ORDER BY stock ASC NULLS FIRST
        LIMIT 15
        """
    )

    df_alerts = query_trino(
        """
        SELECT
            event_date AS alert_date,
            COUNT(*)   AS alerts
        FROM delta.gold.fact_stock_alerts
        WHERE event_date >= CURRENT_DATE - INTERVAL '30' DAY
        GROUP BY 1
        ORDER BY 1
        """
    )

# ── Category mix ────────────────────────────────────────────────────────────
st.subheader("Vendas por categoria (últimos 30 dias)")
if df_cat.empty:
    st.info(
        "Sem vendas em `product_metrics_daily`. "
        "Faça o bot gerar pedidos (`docker logs melisim-traffic-bot`) e rode o batch-runner."
    )
else:
    col1, col2 = st.columns(2)
    with col1:
        fig_cat = px.bar(
            df_cat,
            x="gmv",
            y="category",
            orientation="h",
            labels={"gmv": "GMV (R$)", "category": "Categoria"},
            color="gmv",
            color_continuous_scale="Blues",
        )
        fig_cat.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(t=10))
        st.plotly_chart(fig_cat, use_container_width=True)

    with col2:
        fig_pie = px.pie(
            df_cat,
            values="gmv",
            names="category",
            hole=0.4,
            title="Share por categoria",
        )
        fig_pie.update_layout(margin=dict(t=40))
        st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# ── Top products ────────────────────────────────────────────────────────────
st.subheader("Top 25 produtos do catálogo")
if df_top.empty:
    st.info("Sem produtos em `delta.gold.dim_products`.")
else:
    sold_df = df_top[df_top["gmv"] > 0]
    if not sold_df.empty:
        fig_top = px.bar(
            sold_df,
            x="gmv",
            y="product_name",
            orientation="h",
            color="category",
            labels={"gmv": "GMV (R$)", "product_name": "Produto"},
        )
        fig_top.update_layout(height=480, margin=dict(t=10))
        st.plotly_chart(fig_top, use_container_width=True)

    st.dataframe(
        df_top.style.format({"price": "R$ {:,.2f}", "gmv": "R$ {:,.2f}"}),
        use_container_width=True,
    )

# ── Stock low ───────────────────────────────────────────────────────────────
st.divider()
st.subheader("Produtos com menor estoque")
if df_stock.empty:
    st.info("Sem dados em `dim_products`.")
else:
    fig_stock = px.bar(
        df_stock,
        x="stock",
        y="title",
        orientation="h",
        color="stock",
        color_continuous_scale="Reds_r",
        labels={"stock": "Estoque", "title": "Produto"},
    )
    fig_stock.update_layout(coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig_stock, use_container_width=True)

# ── Stock alerts evolution ──────────────────────────────────────────────────
st.divider()
st.subheader("Alertas de estoque baixo (stock-monitor) — 30 dias")
if df_alerts.empty:
    st.info(
        "Tabela `fact_stock_alerts` vazia. O `stock-monitor` publica em `stock-alert` "
        "a cada `CHECK_INTERVAL_SECONDS` (default 60s). Aguarde alguns ciclos."
    )
else:
    fig_alerts = px.area(
        df_alerts,
        x="alert_date",
        y="alerts",
        labels={"alert_date": "Data", "alerts": "Alertas"},
        color_discrete_sequence=["#ef4444"],
    )
    fig_alerts.update_layout(showlegend=False, margin=dict(t=10))
    st.plotly_chart(fig_alerts, use_container_width=True)
