from strands import tool

from app.operations.execution import (
    plan_new_donation,
)


@tool
def plan_rescue(
    donation_id: int,
) -> dict:
    """
    Create a deterministic rescue plan for an available
    donation.

    This tool delegates logistics decisions to RescueMesh's
    tested optimization system using pantry compatibility,
    capacity, driver availability, PuLP allocation,
    OR-Tools routing, and road routing.

    The agent must NOT calculate allocations or routes
    itself.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Planning result and created operation information.
    """

    try:
        result = plan_new_donation(
            donation_id
        )

        return {
            "status": "ok",
            "result": result,
        }

    except Exception as error:

        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }