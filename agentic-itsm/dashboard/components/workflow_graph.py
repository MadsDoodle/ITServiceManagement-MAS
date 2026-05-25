"""
Workflow graph visualisation — renders a simple ASCII/HTML pipeline diagram
showing the LangGraph workflow structure.
"""
from __future__ import annotations

import streamlit as st


def render_workflow_diagram(active_step: str = ""):
    """
    Render the workflow pipeline.
    active_step: name of the currently active node (highlights it).
    """
    steps = [
        ("monitor",    "🔭 Monitor"),
        ("classify",   "🏷️ Classify"),
        ("rca",        "🔍 RCA"),
        ("escalate",   "⚠️ Escalate"),
        ("github_ops", "🐙 GitHub"),
        ("notify",     "📧 Notify"),
        ("complete",   "✅ Done"),
    ]

    parts = []
    for key, label in steps:
        if key == active_step:
            parts.append(f'<span style="background:#d73a4a;color:white;padding:3px 8px;border-radius:4px;font-weight:bold;">{label}</span>')
        else:
            parts.append(f'<span style="padding:3px 8px;border:1px solid #444;border-radius:4px;color:#aaa;">{label}</span>')

    arrow = ' <span style="color:#555;"> → </span> '
    html  = f'<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">{arrow.join(parts)}</div>'
    st.markdown(html, unsafe_allow_html=True)
