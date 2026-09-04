from strands import tool

from app.escalation.manager import (
    approve_escalation,
    get_escalation,
    get_pending_escalations,
    reject_escalation,
)


@tool
def inspect_pending_escalations(
    operation_id: int | None = None,
) -> dict:
    """
    Inspect human escalations that are currently waiting for
    a decision.

    Only use this when RescueMesh reports that an operation
    is awaiting human judgment.

    Args:
        operation_id: Optional operation ID. If omitted,
            return all pending escalations.

    Returns:
        Pending escalation records.
    """

    try:
        escalations = (
            get_pending_escalations(
                operation_id
            )
        )

        return {
            "status": "ok",
            "escalations": escalations,
        }

    except Exception as error:

        return {
            "status": "error",
            "escalations": [],
            "error": str(error),
        }


@tool
def inspect_escalation(
    escalation_id: int,
) -> dict:
    """
    Inspect one human escalation and its allowed options.

    Args:
        escalation_id: RescueMesh escalation ID.

    Returns:
        Escalation details.
    """

    escalation = get_escalation(
        escalation_id
    )

    if escalation is None:
        return {
            "status": "not_found",
            "escalation_id": escalation_id,
        }

    return {
        "status": "found",
        "escalation": escalation,
    }


@tool
def approve_human_escalation(
    escalation_id: int,
    option_id: str,
    notes: str | None = None,
) -> dict:
    """
    Execute a human-approved escalation option.

    This tool should only be used AFTER a real human has
    explicitly chosen an available escalation option.

    The agent must never approve an escalation on behalf
    of the human.

    Args:
        escalation_id: RescueMesh escalation ID.
        option_id: Explicit option selected by the human.
        notes: Optional human notes.

    Returns:
        Updated escalation record.
    """

    try:
        result = approve_escalation(
            escalation_id,
            option_id,
            notes,
        )

        return {
            "status": "ok",
            "escalation": result,
        }

    except Exception as error:

        return {
            "status": "error",
            "error": str(error),
        }


@tool
def reject_human_escalation(
    escalation_id: int,
    notes: str | None = None,
) -> dict:
    """
    Record a human rejection of RescueMesh's recommendation.

    This tool should only be used after a real human has
    explicitly rejected the recommendation.

    Args:
        escalation_id: RescueMesh escalation ID.
        notes: Optional human notes.

    Returns:
        Updated escalation record.
    """

    try:
        result = reject_escalation(
            escalation_id,
            notes,
        )

        return {
            "status": "ok",
            "escalation": result,
        }

    except Exception as error:

        return {
            "status": "error",
            "error": str(error),
        }