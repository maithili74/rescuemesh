from datetime import time

from app.agent.rescue_coordinator import agent
from app.database.db import get_connection
from app.operations.execution import get_operation

from app.optimizer.rescue_optimizer import (
    optimize_rescue_plan,
)

from app.events.processor import (
    process_event,
)

from app.events.processor import (
    process_event,
)
import os

from app.agent.agentcore_client import (
    invoke_rescue_coordinator,
)

def _invoke_rescue_agent(
    prompt,
):
    """
    Use AgentCore in the deployed environment.

    Fall back to the local Strands agent during
    local development and tests.
    """

    runtime_arn = os.getenv(
        "AGENTCORE_RUNTIME_ARN",
        "",
    ).strip()

    if runtime_arn:
        return invoke_rescue_coordinator(
            prompt
        )

    return agent(
        prompt
    )

def _format_time(value):
    if isinstance(value, time):
        return value.strftime("%H:%M")

    return str(value)


def create_donation_and_coordinate(
    donor_id,
    food_type,
    quantity_lbs,
    available_at,
    pickup_deadline,
):
    """
    Create a real donation and ask the RescueMesh Strands
    coordinator to plan it.

    Important:
    - SQLite/backend state is the source of truth.
    - We do not parse the LLM response to determine success.
    """

    quantity_lbs = float(quantity_lbs)

    if quantity_lbs <= 0:
        raise ValueError(
            "Donation quantity must be greater than zero."
        )

    available_at = _format_time(
        available_at
    )

    pickup_deadline = _format_time(
        pickup_deadline
    )

    if pickup_deadline <= available_at:
        raise ValueError(
            "Pickup deadline must be later than "
            "the available time."
        )

    # =====================================================
    # VERIFY DONOR + CREATE DONATION
    # =====================================================

    conn = get_connection()

    donation_id = None

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        donor = conn.execute(
            """
            SELECT
                id,
                name

            FROM donors

            WHERE id = ?
            """,
            (
                donor_id,
            ),
        ).fetchone()

        if donor is None:
            raise ValueError(
                f"Donor {donor_id} does not exist."
            )

        cursor = conn.execute(
            """
            INSERT INTO donations (
                donor_id,
                food_type,
                quantity_lbs,
                available_at,
                pickup_deadline,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'available')
            """,
            (
                donor_id,
                food_type,
                quantity_lbs,
                available_at,
                pickup_deadline,
            ),
        )

        donation_id = cursor.lastrowid

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # =====================================================
    # STRANDS COORDINATION
    # =====================================================

    agent_error = None
    agent_response = None

    try:
        response = _invoke_rescue_agent(
            f"Coordinate a rescue for donation {donation_id}. "
            f"Inspect the donation and current network state first. "
            f"Then use RescueMesh's deterministic planning tool. "
            f"Do not calculate logistics yourself. "
            f"Do not invent drivers, quantities, pantry assignments, "
            f"routes, ETAs, or feasibility. "
            f"Do not claim pickup or delivery has happened. "
            f"Report only the plan returned by the backend."
        )

        agent_response = str(
            response
        )

    except Exception as error:
        agent_error = str(
            error
        )

    # =====================================================
    # READ ACTUAL BACKEND RESULT
    # =====================================================

    conn = get_connection()

    try:
        operation_row = conn.execute(
            """
            SELECT
                id,
                status

            FROM operations

            WHERE donation_id = ?

            ORDER BY id DESC

            LIMIT 1
            """,
            (
                donation_id,
            ),
        ).fetchone()

        donation_row = conn.execute(
            """
            SELECT
                id,
                status

            FROM donations

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    # =====================================================
    # SUCCESS
    # =====================================================

    if operation_row is not None:
        operation_id = operation_row[
            "id"
        ]

        return {
            "status":
                "planned",

            "donation_id":
                donation_id,

            "operation_id":
                operation_id,

            "donation_status":
                donation_row["status"],

            "operation":
                get_operation(
                    operation_id
                ),

            "agent_response":
                agent_response,
        }

    # =====================================================
    # AGENT / PLANNING DID NOT CREATE AN OPERATION
    # =====================================================

        # =====================================================
    # EXPLAIN WHY NO OPERATION WAS CREATED
    # =====================================================

    planning_reason = None
    planning_status = None
    planning_result = None

    try:
        planning_result = optimize_rescue_plan(
            donation_id
        )

        planning_status = planning_result.get(
            "status"
        )

        planning_reason = planning_result.get(
            "reason"
        )

    except Exception as error:
        planning_reason = (
            f"Planning diagnostic failed: {error}"
        )
    
    
        return {
        "status":
            "not_planned",

        "donation_id":
            donation_id,

        "donation_status":
            (
                donation_row["status"]
                if donation_row
                else "unknown"
            ),

        "planning_status":
            planning_status,

        "planning_reason":
            planning_reason,

        "planning_result":
            planning_result,

        "agent_error":
            agent_error,

        "agent_response":
            agent_response,
    }
        
# =========================================================
# DRIVER ACTIONS
# =========================================================

def accept_driver_assignment(
    operation_id,
    driver_id,
):
    return process_event(
        operation_id=
            operation_id,

        event_type=
            "DRIVER_ACCEPTED",

        payload={
            "driver_id":
                driver_id,
        },
    )


def confirm_driver_pickup(
    operation_id,
    driver_id,
):
    return process_event(
        operation_id=
            operation_id,

        event_type=
            "PICKUP_COMPLETED",

        payload={
            "driver_id":
                driver_id,
        },
    )


def mark_driver_delivery(
    operation_id,
    stop_id,
):
    return process_event(
        operation_id=
            operation_id,

        event_type=
            "DELIVERY_COMPLETED",

        payload={
            "stop_id":
                stop_id,
        },
    )
    
# =========================================================
# PANTRY ACTIONS
# =========================================================

def confirm_pantry_receipt(
    operation_id,
    stop_id,
):
    """
    Pantry confirms that a driver-delivered stop
    was actually received.
    """

    return process_event(
        operation_id=
            operation_id,

        event_type=
            "PANTRY_RECEIVED",

        payload={
            "stop_id":
                stop_id,
        },
    )


def update_pantry_capacity(
    operation_id,
    pantry_id,
    new_max_capacity_lbs,
):
    """
    Update the pantry's TOTAL capacity.

    RescueMesh decides whether the existing plan can
    remain or whether replanning is necessary.
    """

    return process_event(
        operation_id=
            operation_id,

        event_type=
            "PANTRY_CAPACITY_CHANGED",

        payload={
            "pantry_id":
                pantry_id,

            "new_max_capacity_lbs":
                float(
                    new_max_capacity_lbs
                ),
        },
    )


def close_pantry(
    operation_id,
    pantry_id,
):
    """
    Mark the pantry unavailable and allow RescueMesh
    to replan affected rescue operations.
    """

    return process_event(
        operation_id=
            operation_id,

        event_type=
            "PANTRY_CLOSED",

        payload={
            "pantry_id":
                pantry_id,
        },
    )
    
from app.tools.escalation_tools import (
    approve_human_escalation,
)


# =========================================================
# HUMAN ESCALATION ACTION
# =========================================================

def resolve_human_escalation(
    escalation_id,
    option_id,
):
    """
    A HUMAN explicitly selects one of RescueMesh's
    pre-defined escalation options.

    The autonomous agent does not make this decision.
    """

    return approve_human_escalation(
        escalation_id=
            escalation_id,

        option_id=
            option_id,

        notes=
            "Decision made from RescueMesh Operations Center.",
    )