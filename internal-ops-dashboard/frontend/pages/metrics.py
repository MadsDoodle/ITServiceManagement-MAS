import pandas as pd
import streamlit as st

from services.api_client import get_metric_history, get_metrics


def render():
    st.title("📊 Operational Metrics")

    metrics = get_metrics()
    if "error" in metrics:
        st.error(f"Failed to load metrics: {metrics['error']}")
        return

    st.subheader("Current Snapshot")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latency (ms)",      metrics.get("request_latency_ms", "?"))
    c2.metric("Error Rate (%)",    metrics.get("error_rate_pct", "?"))
    c3.metric("Req / min",         metrics.get("requests_per_min", "?"))
    c4.metric("Active Incidents",  metrics.get("active_incidents", "?"))

    c5, c6 = st.columns(2)
    c5.metric("Service Uptime",    f"{metrics.get('service_uptime_pct', '?')}%")
    c6.metric("Deploys / week",    metrics.get("deployment_frequency_per_week", "?"))

    st.markdown("---")
    st.subheader("Historical Metrics")
    hours = st.slider("Hours to display", 1, 24, 24)

    history_data = get_metric_history(hours=hours)
    history = history_data.get("history", [])

    if not history:
        st.info("No historical data available yet — metrics accumulate over time.")
        return

    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")

    st.markdown("**Request Latency (ms)**")
    st.line_chart(df[["request_latency_ms"]])

    st.markdown("**Error Rate (%)**")
    st.line_chart(df[["error_rate_pct"]])

    st.markdown("**Requests per Minute**")
    st.line_chart(df[["requests_per_min"]])