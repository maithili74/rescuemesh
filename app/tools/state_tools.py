from strands import tool

from app.database.db import (
    get_connection,
    get_donation_by_id,
    get_network_state,
)

from app.operations.execution import (
    get_operation,
    get_operation_events,
)


@tool
def inspect_donation(
    donation_id: int,
) -> dict:
    """
    Inspect a donation before taking any action.

    Use this tool to read the donation's current food type,
    quantity, pickup window, donor information, and status.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Current donation information.
    """

    donation = get_donation_by_id(
        donation_id
    )

    if donation is None:
        return {
            "status": "not_found",
            "donation_id": donation_id,
        }

    return {
        "status": "found",
        "donation": dict(donation),
    }


@tool
def inspect_network_state(
    donation_id: int,
) -> dict:
    """
    Inspect the current RescueMesh logistics network for
    a specific donation.

    Use this before planning or recovering a rescue when
    current pantry compatibility, pantry capacity, driver
    availability, and donation state are needed.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Current RescueMesh network state relevant to the
        specified donation.
    """

    try:
        state = get_network_state(
            donation_id
        )

        return {
            "status": "ok",
            "donation_id": donation_id,
            "network": state,
        }

    except Exception as error:

        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


@tool
def inspect_operation(
    operation_id: int,
) -> dict:
    """
    Inspect a rescue operation and its current execution
    state.

    Use this before making decisions about an existing
    rescue, especially after a disruption.

    Args:
        operation_id: RescueMesh operation ID.

    Returns:
        Operation, driver routes, stops, and statuses.
    """

    try:
        operation = get_operation(
            operation_id
        )

    except Exception as error:
        return {
            "status": "error",
            "operation_id": operation_id,
            "error": str(error),
        }

    if operation is None:
        return {
            "status": "not_found",
            "operation_id": operation_id,
        }

    return {
        "status": "found",
        "operation": operation,
    }


@tool
def inspect_operation_events(
    operation_id: int,
) -> dict:
    """
    Inspect the event history for a rescue operation.

    Use this to understand what has already happened before
    deciding what action should happen next.

    Args:
        operation_id: RescueMesh operation ID.

    Returns:
        Ordered event history for the operation.
    """

    try:
        events = get_operation_events(
            operation_id
        )

    except Exception as error:
        return {
            "status": "error",
            "operation_id": operation_id,
            "error": str(error),
        }

    return {
        "status": "ok",
        "operation_id": operation_id,
        "events": events,
    }