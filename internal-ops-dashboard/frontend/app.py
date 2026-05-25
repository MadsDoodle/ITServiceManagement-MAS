import streamlit as st

st.set_page_config(
    page_title="Internal Ops Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import after page config
from components.navbar import render_navbar  # noqa: E402
from pages import dashboard, deployments, incidents, logs, metrics  # noqa: E402

render_navbar()

page = st.sidebar.radio(
    "Go to",
    ["Dashboard", "Incidents", "Deployments", "Metrics", "Logs"],
)

PAGES = {
    "Dashboard": dashboard.render,
    "Incidents": incidents.render,
    "Deployments": deployments.render,
    "Metrics": metrics.render,
    "Logs": logs.render,
}

PAGES[page]()