import os

import requests
from strands import tool


def _get_backend_config():
    """
    Read the RescueMesh backend connection settings.

    Local development:
        RESCUEMESH_BACKEND_URL=http://127.0.0.1:8000

    AgentCore:
        RESCUEMESH_BACKEND_URL=https://<public-backend>
    """

    base_url = os.getenv(
        "RESCUEMESH_BACKEND_URL"
    )

    api_key = os.getenv(
        "RESCUEMESH_INTERNAL_API_KEY"
    )

    if not base_url:
        raise RuntimeError(
            "RESCUEMESH_BACKEND_URL is not configured."
        )

    if not api_key:
        raise RuntimeError(
            "RESCUEMESH_INTERNAL_API_KEY is not configured."
        )

    return (
        base_url.rstrip("/"),
        api_key,
    )


def _request_backend(
    method,
    path,
    *,
    params=None,
    timeout=60,
):
    """
    Send an authenticated request to the RescueMesh backend.
    """

    base_url, api_key = (
        _get_backend_config()
    )

    response = requests.request(
        method=method,
        url=f"{base_url}{path}",
        headers={
            "X-RescueMesh-Key":
                api_key,
        },
        params=params,
        timeout=timeout,
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# DONATION
# =========================================================


@tool
def remote_inspect_donation(
    donation_id: int,
) -> dict:
    """
    Inspect a donation before taking any action.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Current donation information from the
        RescueMesh backend.
    """

    try:
        return _request_backend(
            "GET",
            f"/agent/donations/{donation_id}",
        )

    except Exception as error:
        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


# =========================================================
# NETWORK STATE
# =========================================================


@tool
def remote_inspect_network_state(
    donation_id: int,
) -> dict:
    """
    Inspect the current RescueMesh logistics network.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Current pantry, driver and donation state.
    """

    try:
        return _request_backend(
            "GET",
            f"/agent/network/{donation_id}",
        )

    except Exception as error:
        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


# =========================================================
# PLAN RESCUE
# =========================================================


@tool
def remote_plan_rescue(
    donation_id: int,
) -> dict:
    """
    Ask RescueMesh's deterministic backend to create
    a rescue plan.

    The agent must not calculate quantities, driver
    assignments or routes itself.

    Args:
        donation_id: RescueMesh donation ID.

    Returns:
        Deterministic planning result.
    """

    try:
        return _request_backend(
            "POST",
            f"/agent/donations/{donation_id}/plan",
            timeout=90,
        )

    except Exception as error:
        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


# =========================================================
# OPERATION
# =========================================================


@tool
def remote_inspect_operation(
    operation_id: int,
) -> dict:
    """
    Inspect a RescueMesh rescue operation.

    Args:
        operation_id: RescueMesh operation ID.

    Returns:
        Current operation, route and stop state.
    """

    try:
        return _request_backend(
            "GET",
            f"/agent/operations/{operation_id}",
        )

    except Exception as error:
        return {
            "status": "error",
            "operation_id": operation_id,
            "error": str(error),
        }


# =========================================================
# OPERATION EVENTS
# =========================================================


@tool
def remote_inspect_operation_events(
    operation_id: int,
) -> dict:
    """
    Inspect the event history for a rescue operation.

    Args:
        operation_id: RescueMesh operation ID.

    Returns:
        Ordered operation events.
    """

    try:
        return _request_backend(
            "GET",
            (
                f"/agent/operations/"
                f"{operation_id}/events"
            ),
        )

    except Exception as error:
        return {
            "status": "error",
            "operation_id": operation_id,
            "error": str(error),
        }


# =========================================================
# PENDING ESCALATIONS
# =========================================================


@tool
def remote_inspect_pending_escalations(
    operation_id: int | None = None,
) -> dict:
    """
    Inspect escalations waiting for human judgment.

    Args:
        operation_id: Optional RescueMesh operation ID.

    Returns:
        Pending human escalations.
    """

    try:

        params = None

        if operation_id is not None:
            params = {
                "operation_id":
                    operation_id,
            }

        return _request_backend(
            "GET",
            "/agent/escalations",
            params=params,
        )

    except Exception as error:
        return {
            "status": "error",
            "escalations": [],
            "error": str(error),
        }


# =========================================================
# ONE ESCALATION
# =========================================================


@tool
def remote_inspect_escalation(
    escalation_id: int,
) -> dict:
    """
    Inspect one human escalation.

    Args:
        escalation_id: RescueMesh escalation ID.

    Returns:
        Escalation state and allowed human options.
    """

    try:
        return _request_backend(
            "GET",
            f"/agent/escalations/{escalation_id}",
        )

    except Exception as error:
        return {
            "status": "error",
            "escalation_id": escalation_id,
            "error": str(error),
        }


# =========================================================
# AGENTCORE SAFE TOOL SET
# =========================================================


REMOTE_RESCUE_COORDINATOR_TOOLS = [
    remote_inspect_donation,
    remote_inspect_network_state,
    remote_inspect_operation,
    remote_inspect_operation_events,
    remote_plan_rescue,
    remote_inspect_pending_escalations,
    remote_inspect_escalation,
]