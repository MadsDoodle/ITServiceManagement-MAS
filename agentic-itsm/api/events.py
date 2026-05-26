"""
SSE streaming endpoint — /events/stream

Forwards every event published to the in-process event_bus to any connected
HTTP client as a Server-Sent Events stream. Browser tabs and external tools
can connect to receive real-time lifecycle transitions.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.event_bus import event_stream

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
def stream_events():
    """
    SSE stream of all lifecycle events.
    Content-Type: text/event-stream

    Event types:
      - lifecycle_transition  {incident_id, from_stage, to_stage, agent, detail}
      - remediation_event     {incident_id, strategy, success, detail}
      - new_incident          {incident_id, severity, incident_type}
      - incident_resolved     {incident_id, stability_checks}
      - human_review_required {incident_id, reasons}
    """
    return StreamingResponse(
        event_stream(timeout=30.0),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
