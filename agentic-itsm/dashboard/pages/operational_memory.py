"""
Operational Memory — shows what the system has learned from historical incidents.
Strategy success rates, unstable services, recurring patterns, instability scores.
"""
from __future__ import annotations

import streamlit as st

from services.memory_service import recurring_pattern_summary, strategy_success_rate, service_stability_score
from state.persistent_store import get_all_incidents
from utils.constants import (
    REMEDIATION_RESET_AUTH, REMEDIATION_CLEAR_LATENCY,
    REMEDIATION_RESTART_SERVICE, REMEDIATION_ROLLBACK_DEPLOY,
)

_SERVICES = [
    "auth-service", "api-gateway", "database",
    "notification-service", "metrics-collector",
]
_STRATEGIES = [
    REMEDIATION_RESET_AUTH, REMEDIATION_CLEAR_LATENCY,
    REMEDIATION_RESTART_SERVICE, REMEDIATION_ROLLBACK_DEPLOY,
]


def render():
    st.title("🧠 Operational Memory")
    st.caption(
        "Historical pattern analysis — what the system has learned from past incidents "
        "to inform risk scoring and RCA."
    )

    lookback = st.slider("Lookback window (days)", 1, 30, 14)

    summary = recurring_pattern_summary(lookback_days=lookback)

    # ── Summary strip ─────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    c1.metric("Incidents in Window", summary["total_incidents"])
    c2.metric("Lookback Days",       summary["lookback_days"])
    st.divider()

    # ── Recurring incident types ──────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("📊 Top Recurring Incident Types")
        types = summary.get("top_incident_types", [])
        if types:
            for item in types:
                bar = "█" * item["count"]
                st.markdown(f"`{item['type']:<28}` {bar} **{item['count']}**")
        else:
            st.info("Not enough history yet.")

    with col_r:
        st.subheader("🔥 Most Unstable Services")
        services = summary.get("top_unstable_services", [])
        if services:
            for item in services:
                bar = "█" * item["count"]
                st.markdown(f"`{item['service']:<22}` {bar} **{item['count']}**")
        else:
            st.info("No service anomaly history yet.")

    st.divider()

    # ── Strategy effectiveness ────────────────────────────────────────────────
    st.subheader("🔧 Remediation Strategy Effectiveness")
    st.caption("Success rate per strategy per service, based on historical outcomes.")

    rows = []
    for strategy in _STRATEGIES:
        for service in _SERVICES:
            rate = strategy_success_rate(strategy, service)
            if rate is not None:
                rows.append({
                    "Strategy": strategy,
                    "Service":  service,
                    "Success Rate": f"{rate:.0%}",
                    "Rate Raw": rate,
                })

    if rows:
        for row in sorted(rows, key=lambda r: r["Rate Raw"], reverse=True):
            colour  = "#2da44e" if row["Rate Raw"] >= 0.7 else (
                "#e4e669" if row["Rate Raw"] >= 0.4 else "#d73a4a"
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;'
                f'margin-bottom:4px;">'
                f'<code style="width:180px;">{row["Strategy"]}</code>'
                f'<code style="width:160px;">{row["Service"]}</code>'
                f'<span style="color:{colour};font-weight:bold;">'
                f'{row["Success Rate"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No remediation history yet — strategies will be scored once incidents are remediated.")

    st.divider()

    # ── Failed strategies ─────────────────────────────────────────────────────
    failed_strats = summary.get("most_failed_strategies", [])
    if failed_strats:
        st.subheader("⚠️ Most-Failed Strategies")
        for item in failed_strats:
            st.markdown(f"- `{item['strategy']}` — **{item['failures']}** failed attempt(s)")

    st.divider()

    # ── Per-service instability scores ────────────────────────────────────────
    st.subheader("📉 Service Instability Scores")
    st.caption(f"Based on incident frequency over the last {lookback} days. Used to boost risk scores.")
    score_cols = st.columns(len(_SERVICES))
    for col, service in zip(score_cols, _SERVICES):
        score = service_stability_score(service, lookback_days=lookback)
        colour = "#2da44e" if score < 0.2 else ("#e4e669" if score < 0.5 else "#d73a4a")
        col.markdown(
            f'<div style="text-align:center;padding:8px;background:#1a1a2e;border-radius:6px;'
            f'border-top:3px solid {colour};">'
            f'<b style="color:{colour};">{score:.2f}</b><br/>'
            f'<small>{service}</small>'
            f'</div>',
            unsafe_allow_html=True,
        )
