from strands import tool

from app.events.processor import (
    process_event,
)


@tool
def process_rescue_event(
    operation_id: int,
    event_type: str,
    payload: dict | None = None,
) -> dict:
    """
    Process a real RescueMesh operational event.

    Use this tool for events such as driver acceptance,
    pickup completion, delivery completion, pantry receipt,
    driver cancellation, pantry closure, delivery failure,
    capacity change, and donation expiration.

    RescueMesh's deterministic execution layer decides
    whether the event can be handled normally, requires
    automatic replanning, or requires human escalation.

    Args:
        operation_id: RescueMesh operation ID.
        event_type: Supported RescueMesh event type.
        payload: Event-specific structured data.

    Returns:
        Event processing result.
    """

    try:
        return process_event(
            operation_id,
            event_type,
            payload or {},
        )

    except Exception as error:

        return {
            "status": "error",
            "operation_id": operation_id,
            "event_type": event_type,
            "error": str(error),
        }