"""Página 1 — Executive KPIs (Melisim → Lake).

Fonte: `delta.gold.fact_orders`, `delta.gold.fact_payments`,
`delta.gold.dim_products`. Todos os dados sao gerados pelo trafego real
do Melisim (bot + outbox + Debezium + Spark Streaming).
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.lib.trino_client import query_trino

st.set_page_config(page_title="Executive KPIs", page_icon="📈", layout="wide")
st.title("📈 Executive KPIs")
st.caption(
    "GMV, pedidos, AOV e taxa de pagamento confirmado — "
    "fonte real: orders-service (MySQL CDC) + payments-service (Postgres CDC) → lakehouse"
)

LIVE_STATUSES = ("'CREATED'", "'PAID'", "'CONFIRMED'", "'SHIPPED'", "'DELIVERED'")
LIVE_FILTER = f"status IN ({', '.join(LIVE_STATUSES)})"

with st.spinner("Carregando dados..."):
    df_daily = query_trino(
        f"""
        SELECT
            CAST(created_at AS date) AS order_date,
            SUM(total_amount)        AS gmv,
            COUNT(*)                 AS orders,
            AVG(total_amount)        AS aov
        FROM delta.gold.fact_orders
        WHERE created_at IS NOT NULL
          AND CAST(created_at AS date) >= CURRENT_DATE - INTERVAL '30' DAY
          AND {LIVE_FILTER}
        GROUP BY 1
        ORDER BY 1
        """
    )

    df_pay = query_trino(
        """
        SELECT
            CAST(created_at AS date)             AS pay_date,
            COUNT(*)                              AS attempts,
            COUNT_IF(status = 'CONFIRMED')        AS confirmed,
            COUNT_IF(status = 'FAILED')           AS failed
        FROM delta.gold.fact_payments
        WHERE created_at IS NOT NULL
          AND CAST(created_at AS date) >= CURRENT_DATE - INTERVAL '30' DAY
        GROUP BY 1
        ORDER BY 1
        """
    )

    df_status = query_trino(
        """
        SELECT status, COUNT(*) AS orders
        FROM delta.gold.fact_orders
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )

# ── KPI cards ───────────────────────────────────────────────────────────────
if df_daily.empty:
    st.warning(
        "Sem pedidos nos últimos 30 dias em `delta.gold.fact_orders`. "
        "Verifique: bot do Melisim (`melisim-traffic-bot`), outbox publisher "
        "(`melisim-orders-service`), Debezium (`melisimlake-debezium`), "
        "Spark CDC (`melisimlake-cdc-consumer`) e batch (`melisimlake-batch-runner`)."
    )
else:
    gmv_total = float(df_daily["gmv"].sum())
    orders_total = int(df_daily["orders"].sum())
    aov_avg = float(df_daily["aov"].mean())

    half = max(len(df_daily) // 2, 1)
    prev_gmv = float(df_daily["gmv"].iloc[:half].sum())
    curr_gmv = float(df_daily["gmv"].iloc[half:].sum())
    delta_gmv = (curr_gmv - prev_gmv) / max(prev_gmv, 1) * 100

    pay_rate = 0.0
    if not df_pay.empty:
        attempts = int(df_pay["attempts"].sum())
        confirmed = int(df_pay["confirmed"].sum())
        pay_rate = confirmed / max(attempts, 1) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GMV (30d)", f"R$ {gmv_total:,.0f}", f"{delta_gmv:+.1f}% vs período anterior")
    c2.metric("Pedidos (30d)", f"{orders_total:,}")
    c3.metric("Ticket Médio (AOV)", f"R$ {aov_avg:,.2f}")
    c4.metric("Taxa de pagamento confirmado", f"{pay_rate:.1f}%")

    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Evolução do GMV — 30 dias")
        fig_gmv = px.area(
            df_daily,
            x="order_date",
            y="gmv",
            labels={"order_date": "Data", "gmv": "GMV (R$)"},
            color_discrete_sequence=["#2563eb"],
        )
        fig_gmv.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig_gmv, use_container_width=True)

    with col_right:
        st.subheader("Pedidos por Dia")
        fig_orders = px.bar(
            df_daily,
            x="order_date",
            y="orders",
            labels={"order_date": "Data", "orders": "Pedidos"},
            color_discrete_sequence=["#16a34a"],
        )
        fig_orders.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig_orders, use_container_width=True)

    col_aov, col_pay = st.columns(2)
    with col_aov:
        st.subheader("Ticket Médio (AOV)")
        fig_aov = px.line(
            df_daily,
            x="order_date",
            y="aov",
            labels={"order_date": "Data", "aov": "AOV (R$)"},
            color_discrete_sequence=["#9333ea"],
        )
        fig_aov.update_layout(showlegend=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig_aov, use_container_width=True)

    with col_pay:
        if not df_pay.empty:
            df_pay = df_pay.copy()
            df_pay["confirmed_pct"] = (
                df_pay["confirmed"] / df_pay["attempts"].replace(0, 1) * 100
            )
            st.subheader("Pagamento confirmado (%)")
            fig_pay = px.line(
                df_pay,
                x="pay_date",
                y="confirmed_pct",
                labels={"pay_date": "Data", "confirmed_pct": "% confirmado"},
                color_discrete_sequence=["#ea580c"],
            )
            fig_pay.update_layout(showlegend=False, margin=dict(t=10, b=10))
            st.plotly_chart(fig_pay, use_container_width=True)
        else:
            st.info("Sem pagamentos no período.")

# ── Order status mix ────────────────────────────────────────────────────────
st.divider()
st.subheader("Composição de status de pedidos (todo o histórico)")
if df_status.empty:
    st.info("Sem registros em `delta.gold.fact_orders`.")
else:
    fig_status = px.bar(
        df_status,
        x="status",
        y="orders",
        color="status",
        labels={"status": "Status", "orders": "Pedidos"},
    )
    fig_status.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_status, use_container_width=True)
