"""ML Monitoring & Live Inference - consome MLflow Registry e ml-api."""
from __future__ import annotations

import os
from datetime import datetime

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.lib.trino_client import query_trino

ML_API = os.getenv("ML_API_URL", "http://ml-api:8000")
MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")


def _select_key_metric(name: str, metrics: dict) -> str:
    if not metrics:
        return "—"
    if "test_roc_auc" in metrics:
        return f"AUC {metrics['test_roc_auc']:.3f}"
    if "test_accuracy" in metrics:
        return f"acc {metrics['test_accuracy']:.3f}"
    if "val_mae" in metrics:
        return f"MAE {metrics['val_mae']:.2f}"
    if "matrix_density" in metrics:
        return f"density {metrics['matrix_density']:.3f}"
    k, v = next(iter(metrics.items()))
    return f"{k} {v:.3f}" if isinstance(v, (int, float)) else f"{k}={v}"


st.set_page_config(page_title="ML Monitoring", page_icon="🤖", layout="wide")
st.title("🤖 Machine Learning Monitoring")
st.caption(
    "Modelos servidos pelo `ml-api`, treinados pelo `ml-trainer` e registrados no MLflow. "
    "Inference em tempo real consumindo features de `delta.gold_ml.*`."
)

# ============================================================================
# 1. Modelos registrados (MLflow Registry via ml-api)
# ============================================================================
st.subheader("1. Modelos no MLflow Registry")

try:
    r = httpx.get(f"{ML_API}/models", timeout=10.0)
    r.raise_for_status()
    models = r.json().get("models", [])
except Exception as exc:
    st.error(f"ml-api indisponível em {ML_API}: {exc}")
    models = []

if not models:
    st.info(
        "Nenhum modelo registrado ainda. Aguarde o `ml-trainer` rodar (loop a cada 5min) "
        "ou rode manualmente `docker exec melisimlake-ml-trainer python -m src.run_all`."
    )
else:
    rows = []
    for m in models:
        metrics = m.get("metrics", {})
        rows.append(
            {
                "Modelo": m["name"],
                "Versão": m["version"],
                "Stage": m["stage"],
                "Loaded": "✅" if m.get("loaded") else "—",
                "Métrica chave": _select_key_metric(m["name"], metrics),
                "Run ID": m.get("run_id", "")[:12] + "…",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    cols = st.columns(min(4, len(models)))
    for col, m in zip(cols, models):
        with col:
            st.markdown(f"**{m['name']}** `v{m['version']}` ({m['stage']})")
            for k, v in (m.get("metrics") or {}).items():
                if isinstance(v, (int, float)):
                    st.metric(k, f"{v:.4f}")

# ============================================================================
# 2. Stats datasets de treino (delta.gold_ml.*)
# ============================================================================
st.divider()
st.subheader("2. Datasets de treino (gold_ml)")

ds_stats = query_trino(
    """
    SELECT
        (SELECT COUNT(*) FROM delta.gold_ml.user_features)     AS users,
        (SELECT COUNT(*) FROM delta.gold_ml.product_features)  AS products,
        (SELECT COUNT(*) FROM delta.gold_ml.churn_dataset)     AS churn_rows,
        (SELECT SUM(churn_label) FROM delta.gold_ml.churn_dataset) AS churners,
        (SELECT COUNT(*) FROM delta.gold_ml.payment_dataset)   AS payment_rows,
        (SELECT SUM(failed_label) FROM delta.gold_ml.payment_dataset) AS failed_rows,
        (SELECT COUNT(*) FROM delta.gold_ml.daily_demand)      AS demand_days,
        (SELECT COUNT(*) FROM delta.gold_ml.user_item_matrix)  AS interactions
    """
)
if not ds_stats.empty:
    row = ds_stats.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Users com features", f"{int(row['users']):,}")
    c1.metric("Items com features", f"{int(row['products']):,}")
    c2.metric("Churn rows", f"{int(row['churn_rows']):,}")
    churners = int(row['churners'] or 0)
    c2.metric("Churners (label=1)", churners)
    c3.metric("Payment rows", f"{int(row['payment_rows']):,}")
    c3.metric("Failed payments", int(row['failed_rows'] or 0))
    c4.metric("Dias na série de demanda", int(row['demand_days']))
    c4.metric("User-item interactions", int(row['interactions']))
else:
    st.info("Tabelas gold_ml ainda não materializadas.")

# ============================================================================
# 3. Inferência live: Churn
# ============================================================================
st.divider()
st.subheader("3. Live demo - Churn prediction")

users_df = query_trino(
    "SELECT buyer_id, recency_days, frequency_per_week, monetary, churn_label "
    "FROM delta.gold_ml.churn_dataset ORDER BY recency_days DESC LIMIT 50"
)
if users_df.empty:
    st.info("Sem buyers em gold_ml.churn_dataset (aguarde batch-runner).")
else:
    options = users_df["buyer_id"].astype(str).tolist()
    selected = st.selectbox("Selecione um buyer:", options=options, key="churn_buyer")
    if selected:
        try:
            r = httpx.post(f"{ML_API}/predict/churn/{selected}", timeout=10.0)
            r.raise_for_status()
            res = r.json()
            band_color = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
            color = band_color.get(res.get("churn_risk", "low"), "#999")
            st.markdown(
                f"<div style='padding:1em;border-radius:8px;background:{color};color:white;'>"
                f"<b>Probabilidade de churn:</b> {res['churn_probability']:.2%} "
                f"&nbsp;|&nbsp; <b>Risco:</b> {res['churn_risk'].upper()} "
                f"&nbsp;|&nbsp; <b>Modelo:</b> {res.get('model', '?')} v{res.get('model_version', '?')} "
                f"&nbsp;|&nbsp; <b>Latência:</b> {res.get('inference_ms', 0):.1f}ms"
                f"{' (FALLBACK)' if res.get('fallback') else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Features usadas"):
                st.json(res.get("features_used", {}))
        except httpx.HTTPStatusError as exc:
            st.error(f"ml-api retornou {exc.response.status_code}: {exc.response.text[:200]}")
        except Exception as exc:
            st.error(f"falha ao chamar ml-api: {exc}")

# ============================================================================
# 4. Inferência live: Payment fraud / failure risk
# ============================================================================
st.divider()
st.subheader("4. Live demo - Payment failure risk")

with st.form("payment_form"):
    c1, c2, c3 = st.columns(3)
    amount = c1.number_input("Amount (R$)", value=350.0, min_value=0.01, step=10.0)
    method = c2.selectbox("Method", options=["credit_card", "pix", "boleto", "debit_card"])
    buyer_id = c3.text_input(
        "Buyer ID (opcional, p/ enriquecer)",
        value=options[0] if not users_df.empty else "",
    )
    c4, c5 = st.columns(2)
    hour = c4.slider("Hora do dia", 0, 23, 14)
    dow = c5.slider("Dia da semana (1=dom)", 1, 7, 3)
    submitted = st.form_submit_button("Predict failure risk")

if submitted:
    try:
        body = {"amount": amount, "method": method, "hour": hour, "dow": dow}
        if buyer_id:
            body["buyer_id"] = buyer_id
        r = httpx.post(f"{ML_API}/predict/payment_fraud", json=body, timeout=10.0)
        r.raise_for_status()
        res = r.json()
        prob = res["failure_probability"]
        c1, c2, c3 = st.columns(3)
        c1.metric("P(failed)", f"{prob:.2%}")
        c2.metric("Banda", res["risk_band"].upper())
        c3.metric("High risk?", "🔴 SIM" if res["is_high_risk"] else "🟢 NÃO")
        st.caption(
            f"Modelo: {res.get('model','?')} v{res.get('model_version','?')} "
            f"· latência {res.get('inference_ms',0):.1f}ms"
            f"{' · FALLBACK heurístico' if res.get('fallback') else ''}"
        )
        with st.expander("Features enviadas ao modelo"):
            st.json(res.get("features_used", {}))
    except Exception as exc:
        st.error(f"falha: {exc}")

# ============================================================================
# 5. Forecast de demanda (LSTM)
# ============================================================================
st.divider()
st.subheader("5. Forecast de demanda - LSTM")

horizon = st.slider("Horizonte (dias)", 1, 14, 7, key="forecast_h")
if st.button("Gerar previsão"):
    try:
        r = httpx.post(
            f"{ML_API}/forecast/demand", json={"horizon_days": horizon}, timeout=20.0
        )
        r.raise_for_status()
        res = r.json()
        history = pd.DataFrame(res["history_used"])
        forecast = pd.DataFrame(res["forecast"]).rename(columns={"date": "date"})

        history["kind"] = "histórico"
        forecast["kind"] = "previsto"
        history = history.rename(columns={"date": "date"})

        plot_df = pd.concat(
            [
                history[["date", "orders", "kind"]],
                forecast[["date", "orders", "kind"]],
            ],
            ignore_index=True,
        )
        fig = px.line(
            plot_df,
            x="date",
            y="orders",
            color="kind",
            markers=True,
            title=f"Forecast de pedidos diários ({horizon} dias)",
        )
        st.plotly_chart(fig, use_container_width=True)

        plot_gmv = pd.concat(
            [
                history[["date", "gmv", "kind"]] if "gmv" in history.columns else pd.DataFrame(),
                forecast[["date", "gmv", "kind"]],
            ],
            ignore_index=True,
        )
        if not plot_gmv.empty:
            fig2 = px.line(
                plot_gmv,
                x="date",
                y="gmv",
                color="kind",
                markers=True,
                title="Forecast de GMV diário",
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.caption(
            f"Modelo: {res.get('model','?')} v{res.get('model_version','?')} "
            f"· latência {res.get('inference_ms',0):.1f}ms"
        )
    except Exception as exc:
        st.error(f"falha forecast: {exc}")

# ============================================================================
# 6. Recomendação ALS
# ============================================================================
st.divider()
st.subheader("6. Recomendação ALS - Top-K por buyer")

users_for_rec = query_trino(
    "SELECT DISTINCT buyer_id FROM delta.gold_ml.user_item_matrix ORDER BY buyer_id LIMIT 30"
)
if users_for_rec.empty:
    st.info("Sem buyers com interações em user_item_matrix.")
else:
    opts = users_for_rec["buyer_id"].astype(str).tolist()
    user_pick = st.selectbox("Buyer ID:", options=opts, key="rec_buyer")
    k = st.slider("Top-K", 1, 10, 5, key="rec_k")
    if st.button("Recomendar"):
        try:
            r = httpx.post(
                f"{ML_API}/recommend/{user_pick}", params={"k": k}, timeout=10.0
            )
            r.raise_for_status()
            res = r.json()
            recs = pd.DataFrame(res["recommendations"])
            if not recs.empty:
                st.dataframe(recs, use_container_width=True, hide_index=True)
                if res.get("cold_start"):
                    st.info("Buyer não estava no treino — usando top-K populares (cold-start).")
            else:
                st.warning("Sem recomendações.")
            st.caption(
                f"Modelo: {res.get('model','?')} v{res.get('model_version','?')} "
                f"· latência {res.get('inference_ms',0):.1f}ms"
            )
        except Exception as exc:
            st.error(f"falha: {exc}")

st.divider()
st.caption(
    f"ml-api: `{ML_API}` · MLflow: `{MLFLOW_URL}` · "
    "Treinos rodam em loop pelo `melisimlake-ml-trainer`."
)
