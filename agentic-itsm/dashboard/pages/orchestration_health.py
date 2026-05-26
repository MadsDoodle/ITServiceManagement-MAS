"""
Orchestration Health — monitors the ITSM platform itself.
Shows monitoring loop liveness, stuck incidents, and heartbeat age.
"""
from __future__ import annotations

import streamlit as st

from services.watchdog_service import get_orchestration_health
from state.persistent_store import get_open_incidents, get_all_incidents


def render():
    st.title("🔭 Orchestration Health")
    st.caption("Self-monitoring view — tracks the health of the Agentic ITSM platform itself.")

    auto_refresh = st.checkbox("Auto-refresh every 15s", value=False)
    if auto_refresh:
        import time; time.sleep(15); st.rerun()

    if st.button("🔄 Refresh"):
        st.rerun()

    health = get_orchestration_health()

    # ── Loop status banner ────────────────────────────────────────────────────
    loop_status = health.get("loop_status", "unknown")
    hb_age      = health.get("heartbeat_age_s")
    last_checked = (health.get("last_checked") or "")[:19].replace("T", " ")

    status_map = {
        "running":     ("🟢", "success", "Monitoring loop is running"),
        "stalled":     ("🔴", "error",   "Monitoring loop appears STALLED"),
        "not_started": ("🟡", "warning", "Monitoring loop has not started yet"),
        "unknown":     ("⚪", "info",    "Loop status unknown — watchdog may not be running"),
    }
    icon, fn_name, msg = status_map.get(loop_status, ("⚪", "info", loop_status))
    getattr(st, fn_name)(f"{icon} **{msg}**")

    # ── Metrics strip ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Loop Status",    loop_status.replace("_", " ").title())
    c2.metric("Heartbeat Age",  f"{hb_age:.0f}s" if hb_age is not None else "N/A")
    c3.metric("Stuck Incidents", len(health.get("stuck_incidents", [])))
    c4.metric("Last Watchdog Check", last_checked or "Never")

    st.divider()

    # ── Stuck incidents ───────────────────────────────────────────────────────
    stuck = health.get("stuck_incidents", [])
    if stuck:
        st.subheader("⚠️ Stuck Incidents")
        st.caption("These incidents have been in the same lifecycle stage longer than expected.")
        for s in stuck:
            mins = int(s.get("time_in_stage_s", 0) / 60)
            thresh_mins = int(s.get("threshold_s", 0) / 60)
            st.error(
                f"`{s.get('incident_id')}` — stage `{s.get('stage')}` · "
                f"**{mins} minutes** (threshold: {thresh_mins} min)"
            )

        st.divider()
    else:
        st.success("✅ No stuck incidents detected.")

    # ── Open incident stage overview ──────────────────────────────────────────
    st.subheader("Open Incidents by Stage")
    open_incs = get_open_incidents()
    if not open_incs:
        st.info("No open incidents.")
    else:
        stage_counts: dict[str, int] = {}
        for inc in open_incs:
            s = inc.get("lifecycle_stage") or "unknown"
            stage_counts[s] = stage_counts.get(s, 0) + 1
        for stage, count in sorted(stage_counts.items()):
            bar = "█" * count
            st.markdown(f"`{stage:<22}` {bar} **{count}**")

    # ── Heartbeat history ─────────────────────────────────────────────────────
    st.divider()
    with st.expander("ℹ️ About Self-Monitoring"):
        st.markdown("""
**How this works:**

- The monitoring loop writes a heartbeat timestamp to the database on every tick
- The watchdog thread (runs every 60s) reads the heartbeat and compares it to `WATCHDOG_STALE_SECONDS`
- If the heartbeat is stale, the loop is flagged as **stalled**
- Incidents are flagged as **stuck** if they remain in the same lifecycle stage beyond the per-stage timeout:
  - `new` / `triage`: 5–10 min
  - `investigating` / `fix_in_progress`: 30 min
  - `monitoring`: 2 hours
  - `awaiting_review`: 24 hours (human review can take time)
        """)
