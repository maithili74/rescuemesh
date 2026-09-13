import os
import secrets
import sqlite3
from datetime import date, datetime, time
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
)

from app.database.db import (
    get_donation_by_id,
    get_network_state,
)

from app.operations.execution import (
    get_operation,
    get_operation_events,
    plan_new_donation,
)

from app.escalation.manager import (
    get_escalation,
    get_pending_escalations,
)


load_dotenv()


app = FastAPI(
    title="RescueMesh Backend API",
    description=(
        "Internal backend API used by the "
        "RescueMesh AgentCore coordinator."
    ),
    version="1.0.0",
)


# =========================================================
# AUTHENTICATION
# =========================================================


def verify_internal_key(
    x_rescuemesh_key: str | None = Header(
        default=None,
        alias="X-RescueMesh-Key",
    ),
):
    """
    Protect internal AgentCore endpoints.

    AgentCore will send the shared key in:

        X-RescueMesh-Key
    """

    expected_key = os.getenv(
        "RESCUEMESH_INTERNAL_API_KEY"
    )

    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "RESCUEMESH_INTERNAL_API_KEY "
                "is not configured."
            ),
        )

    if (
        x_rescuemesh_key is None
        or not secrets.compare_digest(
            x_rescuemesh_key,
            expected_key,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid RescueMesh API key.",
        )


# =========================================================
# JSON CONVERSION
# =========================================================


def make_json_safe(value):
    """
    Recursively convert RescueMesh database values
    into JSON-safe Python objects.
    """

    if isinstance(
        value,
        sqlite3.Row,
    ):
        return {
            key: make_json_safe(
                value[key]
            )
            for key in value.keys()
        }

    if isinstance(
        value,
        dict,
    ):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(
        value,
        (
            datetime,
            date,
            time,
        ),
    ):
        return value.isoformat()

    return value


# =========================================================
# HEALTH CHECK
# =========================================================


@app.get(
    "/health"
)
def health():
    """
    Public health endpoint.

    Does not expose RescueMesh operational data.
    """

    return {
        "status": "ok",
        "service": "rescuemesh-backend",
    }


# =========================================================
# DONATION STATE
# =========================================================


@app.get(
    "/agent/donations/{donation_id}"
)
def inspect_donation_api(
    donation_id: int,
    _: None = Depends(
    verify_internal_key 
    ),
):
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
        "donation": make_json_safe(
            donation
        ),
    }


# =========================================================
# NETWORK STATE
# =========================================================


@app.get(
    "/agent/network/{donation_id}"
)
def inspect_network_api(
    donation_id: int,
    _: None = Depends(
    verify_internal_key
    ),
):
    try:
        state = get_network_state(
            donation_id
        )

        return {
            "status": "ok",
            "donation_id": donation_id,
            "network": make_json_safe(
                state
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


# =========================================================
# PLAN RESCUE
# =========================================================


@app.post(
    "/agent/donations/{donation_id}/plan"
)
def plan_rescue_api(
    donation_id: int,
    _: None = Depends(
    verify_internal_key
    ),
):
    try:
        result = plan_new_donation(
            donation_id
        )

        return {
            "status": "ok",
            "result": make_json_safe(
                result
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "donation_id": donation_id,
            "error": str(error),
        }


# =========================================================
# OPERATION STATE
# =========================================================


@app.get(
    "/agent/operations/{operation_id}"
)
def inspect_operation_api(
    operation_id: int,
    _: None = Depends(
    verify_internal_key
    ),
):
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
        "operation": make_json_safe(
            operation
        ),
    }


# =========================================================
# OPERATION EVENTS
# =========================================================


@app.get(
    "/agent/operations/{operation_id}/events"
)
def inspect_operation_events_api(
    operation_id: int,
    _: None = Depends(
    verify_internal_key
    ),
):
    try:
        events = get_operation_events(
            operation_id
        )

        return {
            "status": "ok",
            "operation_id": operation_id,
            "events": make_json_safe(
                events
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "operation_id": operation_id,
            "error": str(error),
        }


# =========================================================
# PENDING ESCALATIONS
# =========================================================


@app.get(
    "/agent/escalations"
)
def inspect_pending_escalations_api(
    operation_id: int | None = Query(
        default=None
    ),
    _: None = Depends(
    verify_internal_key
    ),
):
    try:
        escalations = (
            get_pending_escalations(
                operation_id
            )
        )

        return {
            "status": "ok",
            "escalations": make_json_safe(
                escalations
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "escalations": [],
            "error": str(error),
        }


# =========================================================
# ONE ESCALATION
# =========================================================


@app.get(
    "/agent/escalations/{escalation_id}"
)
def inspect_escalation_api(
    escalation_id: int,
    _: None = Depends(
    verify_internal_key
    ),
):
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
        "escalation": make_json_safe(
            escalation
        ),
    }
