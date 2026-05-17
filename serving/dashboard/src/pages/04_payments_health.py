"""Página 4 — Payments & Notifications Health.

Fonte: `delta.gold.fact_payments`, `delta.gold.notifications_daily`,
`delta.gold.fact_orders`. Mostra a saude do funil pedido -> pagamento
e o volume de notificacoes geradas pelos eventos do Melisim.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.lib.trino_client import query_trino

st.set_page_config(page_title="Payments Health", page_icon="💳", layout="wide")
st.title("💳 Payments & Notifications Health")
st.caption(
    "Funil pedido → pagamento confirmado e fluxo de notificações "
    "(payments-service + notifications-service)."
)

with st.spinner("Carregando dados de pagamentos..."):
    df_pay_status = query_trino(
        """
        SELECT status, COUNT(*) AS payments, SUM(amount) AS total_amount
        FROM delta.gold.fact_payments
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )

    df_method = query_trino(
        """
        SELECT method, COUNT(*) AS payments, SUM(amount) AS total_amount
        FROM delta.gold.fact_payments
        WHERE status = 'CONFIRMED'
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )

    df_funnel = query_trino(
        """
        SELECT
            (SELECT COUNT(*) FROM delta.gold.fact_orders)                                 AS orders,
            (SELECT COUNT(*) FROM delta.gold.fact_payments)                                AS payments,
            (SELECT COUNT(*) FROM delta.gold.fact_payments WHERE status = 'CONFIRMED')     AS paid,
            (SELECT COUNT(*) FROM delta.gold.fact_payments WHERE status = 'FAILED')        AS failed
        """
    )

    df_notif = query_trino(
        """
        SELECT
            notif_date,
            event_type,
            SUM(notifications) AS notifications
        FROM delta.gold.notifications_daily
        WHERE notif_date >= CURRENT_DATE - INTERVAL '30' DAY
        GROUP BY 1, 2
        ORDER BY 1
        """
    )

# ── KPI cards ───────────────────────────────────────────────────────────────
if df_funnel.empty:
    st.warning("Sem dados em `fact_orders`/`fact_payments`.")
else:
    row = df_funnel.iloc[0]
    orders = int(row["orders"]) if row["orders"] is not None else 0
    payments = int(row["payments"]) if row["payments"] is not None else 0
    paid = int(row["paid"]) if row["paid"] is not None else 0
    failed = int(row["failed"]) if row["failed"] is not None else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos totais", f"{orders:,}")
    c2.metric("Tentativas de pagamento", f"{payments:,}")
    c3.metric("Confirmados", f"{paid:,}", f"{(paid / max(payments,1)) * 100:.1f}% sucesso")
    c4.metric("Falhados", f"{failed:,}")

st.divider()

# ── Status mix + funnel ─────────────────────────────────────────────────────
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Mix de status de pagamentos")
    if df_pay_status.empty:
        st.info("Sem pagamentos no Lake.")
    else:
        fig = px.pie(
            df_pay_status,
            values="payments",
            names="status",
            hole=0.4,
        )
        fig.update_layout(margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("GMV pago por método")
    if df_method.empty:
        st.info("Sem pagamentos confirmados.")
    else:
        fig = px.bar(
            df_method,
            x="method",
            y="total_amount",
            color="method",
            labels={"method": "Método", "total_amount": "Valor confirmado (R$)"},
        )
        fig.update_layout(showlegend=False, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Notifications ───────────────────────────────────────────────────────────
st.subheader("Notificações geradas (últimos 30 dias)")
if df_notif.empty:
    st.info(
        "Tabela `notifications_daily` vazia. "
        "Lembre que `notifications-service` consome `order-created`/`payment-*`/`stock-alert`."
    )
else:
    fig_n = px.bar(
        df_notif,
        x="notif_date",
        y="notifications",
        color="event_type",
        labels={"notif_date": "Data", "notifications": "Notificações", "event_type": "Tipo"},
    )
    fig_n.update_layout(margin=dict(t=10))
    st.plotly_chart(fig_n, use_container_width=True)

    st.dataframe(
        df_notif.pivot_table(
            index="notif_date", columns="event_type", values="notifications", fill_value=0
        ),
        use_container_width=True,
    )
