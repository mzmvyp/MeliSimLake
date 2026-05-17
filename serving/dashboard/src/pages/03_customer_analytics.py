"""Página 3 — Customer Analytics.

Fonte: `delta.gold.customer_rfm`, `delta.gold.dim_users`, `delta.gold.fact_orders`.
RFM segments calculados em runtime via NTILE.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.lib.trino_client import query_trino

st.set_page_config(page_title="Customer Analytics", page_icon="👥", layout="wide")
st.title("👥 Customer Analytics")
st.caption("RFM, distribuição de risco de churn (inatividade) e LTV — buyers reais do Melisim")


RFM_QUERY = """
WITH base AS (
    SELECT
        c.buyer_id,
        c.recency_days,
        c.frequency,
        c.monetary,
        u.name,
        u.email,
        u.user_type
    FROM delta.gold.customer_rfm c
    LEFT JOIN delta.gold.dim_users u ON u.user_id = c.buyer_id
),
scored AS (
    SELECT
        b.*,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency)         AS f_score,
        NTILE(5) OVER (ORDER BY monetary)          AS m_score
    FROM base b
)
SELECT
    buyer_id, name, email, user_type,
    recency_days, frequency, monetary,
    CASE
        WHEN r_score = 5 AND f_score >= 4 THEN 'Champions'
        WHEN r_score >= 4 AND f_score >= 3 THEN 'Loyal'
        WHEN r_score >= 3 AND m_score >= 4 THEN 'Big Spenders'
        WHEN r_score = 5 AND f_score <= 2 THEN 'New Customers'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
        ELSE 'Need Attention'
    END AS rfm_segment
FROM scored
"""


with st.spinner("Carregando dados de clientes..."):
    df_cust = query_trino(RFM_QUERY)

    df_users_total = query_trino(
        "SELECT COUNT(*) AS total FROM delta.gold.dim_users WHERE user_type = 'BUYER'"
    )

    df_inactive = query_trino(
        """
        SELECT
            CASE
                WHEN recency_days <= 7   THEN '0-7 dias'
                WHEN recency_days <= 30  THEN '8-30 dias'
                WHEN recency_days <= 90  THEN '31-90 dias'
                WHEN recency_days <= 180 THEN '91-180 dias'
                ELSE '>180 dias (churn risk)'
            END AS bucket,
            COUNT(*) AS buyers
        FROM delta.gold.customer_rfm
        WHERE recency_days IS NOT NULL
        GROUP BY 1
        ORDER BY MIN(recency_days)
        """
    )

# ── Top KPIs ────────────────────────────────────────────────────────────────
total_users = (
    int(df_users_total["total"].iloc[0]) if not df_users_total.empty else 0
)
total_buyers_with_orders = len(df_cust)

c1, c2, c3 = st.columns(3)
c1.metric("Buyers cadastrados (MySQL)", f"{total_users:,}")
c2.metric("Buyers que já compraram", f"{total_buyers_with_orders:,}")
c3.metric(
    "% ativos (já compraram)",
    f"{(total_buyers_with_orders / max(total_users, 1)) * 100:.1f}%",
)

st.divider()

# ── RFM segments ────────────────────────────────────────────────────────────
st.subheader("Segmentos RFM")
if df_cust.empty:
    st.info(
        "Sem dados em `delta.gold.customer_rfm`. "
        "É necessário haver pedidos confirmados para alimentar o RFM."
    )
else:
    seg_summary = (
        df_cust.groupby("rfm_segment")
        .agg(
            customer_count=("buyer_id", "count"),
            avg_monetary=("monetary", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_recency=("recency_days", "mean"),
        )
        .reset_index()
        .sort_values("customer_count", ascending=False)
    )

    col1, col2 = st.columns(2)
    with col1:
        fig_bar = px.bar(
            seg_summary,
            x="rfm_segment",
            y="customer_count",
            color="rfm_segment",
            labels={"rfm_segment": "Segmento", "customer_count": "Clientes"},
            title="Distribuição por segmento",
        )
        fig_bar.update_layout(showlegend=False, margin=dict(t=40))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        fig_ltv = px.bar(
            seg_summary,
            x="rfm_segment",
            y="avg_monetary",
            color="avg_monetary",
            color_continuous_scale="Greens",
            labels={"rfm_segment": "Segmento", "avg_monetary": "LTV médio (R$)"},
            title="LTV médio por segmento",
        )
        fig_ltv.update_layout(coloraxis_showscale=False, margin=dict(t=40))
        st.plotly_chart(fig_ltv, use_container_width=True)

    st.dataframe(
        seg_summary.style.format(
            {
                "avg_monetary": "R$ {:,.2f}",
                "avg_frequency": "{:.1f}",
                "avg_recency": "{:.1f} dias",
            }
        ),
        use_container_width=True,
    )

st.divider()

# ── Inactivity / churn risk buckets ────────────────────────────────────────
st.subheader("Risco de churn (por inatividade)")
if df_inactive.empty:
    st.info("Sem buyers em `customer_rfm`.")
else:
    fig_inact = px.funnel(
        df_inactive,
        x="buyers",
        y="bucket",
        color="bucket",
        labels={"bucket": "Inatividade", "buyers": "Buyers"},
    )
    fig_inact.update_layout(showlegend=False, margin=dict(t=10))
    st.plotly_chart(fig_inact, use_container_width=True)

st.divider()

# ── Buyer LTV table ─────────────────────────────────────────────────────────
st.subheader("Top buyers por LTV (monetary)")
if not df_cust.empty:
    top = df_cust.sort_values("monetary", ascending=False).head(20)
    st.dataframe(
        top[
            ["buyer_id", "name", "email", "rfm_segment", "frequency", "monetary", "recency_days"]
        ].style.format({"monetary": "R$ {:,.2f}", "recency_days": "{:.1f}"}),
        use_container_width=True,
    )
