"""
Workflow graph visualisation — renders the full 11-node LangGraph pipeline.
"""
from __future__ import annotations

import streamlit as st

_STEPS = [
    ("monitor",           "🔭 Monitor"),
    ("classify",          "🏷️ Classify"),
    ("rca",               "🔍 RCA"),
    ("score_risk",        "📊 Risk"),
    ("escalate",          "⚠️ Escalate"),
    ("github_ops",        "🐙 GitHub"),
    ("human_review",      "👤 Review"),
    ("remediate",         "🔧 Remediate"),
    ("recovery_validate", "📡 Validate"),
    ("resolve",           "🏁 Resolve"),
    ("complete",          "✅ Done"),
]


def render_workflow_diagram(active_step: str = ""):
    parts = []
    for key, label in _STEPS:
        if key == active_step:
            parts.append(
                f'<span style="background:#d73a4a;color:white;padding:3px 8px;'
                f'border-radius:4px;font-weight:bold;">{label}</span>'
            )
        else:
            parts.append(
                f'<span style="padding:3px 8px;border:1px solid #444;'
                f'border-radius:4px;color:#aaa;">{label}</span>'
            )
    arrow = ' <span style="color:#555;">→</span> '
    html  = (
        '<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">'
        + arrow.join(parts)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
