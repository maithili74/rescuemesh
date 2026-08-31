from app.database.db import (
    get_connection,
)

from app.events.types import (
    EventType,
    SUPPORTED_EVENT_TYPES,
)

from app.operations.execution import (
    accept_driver_assignment,
    cancel_driver_and_replan,
    change_pantry_capacity_and_replan,
    complete_delivery_stop,
    complete_operation,
    complete_pickup,
    get_operation,
    plan_new_donation,
    record_event,
)

# =========================================================
# PAYLOAD HELPERS
# =========================================================

def _require_field(
    payload,
    field_name,
):
    """
    Get a required event field.

    Raises a clean ValueError if missing.
    """

    if field_name not in payload:

        raise ValueError(
            f"Event payload is missing "
            f"required field: "
            f"{field_name}"
        )

    return payload[
        field_name
    ]


# =========================================================
# DRIVER CANCELLED
# =========================================================

def _handle_driver_cancelled(
    operation_id,
    payload,
):
    driver_id = _require_field(
        payload,
        "driver_id",
    )

    return (
        cancel_driver_and_replan(
            operation_id,
            driver_id,
        )
    )


# =========================================================
# DELIVERY COMPLETED
# =========================================================

def _handle_delivery_completed(
    operation_id,
    payload,
):
    stop_id = _require_field(
        payload,
        "stop_id",
    )

    conn = get_connection()

    try:

        # Make sure this stop actually belongs to the
        # operation supplied in the event.

        row = conn.execute(
            """
            SELECT
                s.id,
                s.status,
                r.operation_id

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            WHERE s.id = ?
            """,
            (
                stop_id,
            ),
        ).fetchone()

        if row is None:

            raise ValueError(
                f"Delivery stop "
                f"{stop_id} "
                f"does not exist."
            )

        if (
            row[
                "operation_id"
            ]
            !=
            operation_id
        ):

            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not belong to "
                f"operation {operation_id}."
            )

        if (
            row[
                "status"
            ]
            ==
            "completed"
        ):

            raise ValueError(
                f"Delivery stop {stop_id} "
                f"is already completed."
            )

    finally:

        conn.close()

    # Actual state change stays in execution.py.

    complete_delivery_stop(
        stop_id
    )

    # =====================================================
    # CHECK IF THIS WAS THE LAST DELIVERY
    # =====================================================

    conn = get_connection()

    try:

        pending_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM delivery_stops s

                JOIN driver_routes r
                    ON r.id = s.route_id

                WHERE
                    r.operation_id = ?
                    AND
                    s.status != 'completed'
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

    finally:

        conn.close()

    operation_completed = False

    if pending_count == 0:

        complete_operation(
            operation_id
        )

        operation_completed = True

    return {
        "status":
            "delivery_completed",

        "stop_id":
            stop_id,

        "operation_completed":
            operation_completed,
    }


# =========================================================
# PANTRY CAPACITY CHANGED
# =========================================================

def _handle_pantry_capacity_changed(
    operation_id,
    payload,
):
    pantry_id = _require_field(
        payload,
        "pantry_id",
    )

    new_capacity = _require_field(
        payload,
        "new_max_capacity_lbs",
    )

    try:

        new_capacity = float(
            new_capacity
        )

    except (
        TypeError,
        ValueError,
    ):

        raise ValueError(
            "new_max_capacity_lbs "
            "must be numeric."
        )

    return (
        change_pantry_capacity_and_replan(
            operation_id,
            pantry_id,
            new_capacity,
        )
    )



# =========================================================
# DONATION CREATED
# =========================================================

def _handle_donation_created(
    operation_id,
    payload,
):
    """
    operation_id is None here because an operation
    does not exist yet.
    """

    donation_id = _require_field(
        payload,
        "donation_id",
    )

    return plan_new_donation(
        donation_id
    )


# =========================================================
# DRIVER ACCEPTED
# =========================================================

def _handle_driver_accepted(
    operation_id,
    payload,
):
    driver_id = _require_field(
        payload,
        "driver_id",
    )

    return accept_driver_assignment(
        operation_id,
        driver_id,
    )


# =========================================================
# PICKUP COMPLETED
# =========================================================

def _handle_pickup_completed(
    operation_id,
    payload,
):
    driver_id = _require_field(
        payload,
        "driver_id",
    )

    return complete_pickup(
        operation_id,
        driver_id,
    )


# =========================================================
# HANDLER MAP
# =========================================================

EVENT_HANDLERS = {

    EventType.DONATION_CREATED.value:
        _handle_donation_created,

    EventType.DRIVER_ACCEPTED.value:
        _handle_driver_accepted,

    EventType.PICKUP_COMPLETED.value:
        _handle_pickup_completed,

    EventType.DRIVER_CANCELLED.value:
        _handle_driver_cancelled,

    EventType.DELIVERY_COMPLETED.value:
        _handle_delivery_completed,

    EventType.PANTRY_CAPACITY_CHANGED.value:
        _handle_pantry_capacity_changed,
}

# =========================================================
# RESULT SUMMARY FOR EVENT LOG
# =========================================================

def _summarize_result(
    result,
):
    """
    Keep EVENT_PROCESSED logs small.

    We don't want to save the entire optimizer result
    inside every event row.
    """

    if not isinstance(
        result,
        dict,
    ):

        return {
            "result":
                str(result)
        }

    useful_fields = [
        "status",
        "old_operation_id",
        "new_operation_id",
        "operation_id",
        "stop_id",
        "operation_completed",
        "pantry_id",
        "replanned",
    ]

    return {
        field:
            result[field]

        for field in useful_fields

        if field in result
    }


# =========================================================
# CENTRAL EVENT PROCESSOR
# =========================================================

def process_event(
    operation_id,
    event_type,
    payload=None,
):
    """
    Central entry point for RescueMesh events.

    Example:

        process_event(
            operation_id=2,
            event_type="DRIVER_CANCELLED",
            payload={
                "driver_id": 4
            }
        )

    Flow:

        validate event
            ↓
        select handler
            ↓
        execution layer performs action
            ↓
        EVENT_PROCESSED

    If something crashes:

        EVENT_FAILED
    """

    if payload is None:
        payload = {}

    # Enum input is allowed too.

    if isinstance(
        event_type,
        EventType,
    ):
        event_type = (
            event_type.value
        )

    if (
        event_type
        not in
        SUPPORTED_EVENT_TYPES
    ):

        error = (
            f"Unsupported event type: "
            f"{event_type}"
        )

        # Try to record failure if the operation exists.
        try:

            record_event(
                operation_id,

                "EVENT_FAILED",

                {
                    "trigger_event":
                        event_type,

                    "payload":
                        payload,

                    "error":
                        error,
                },
            )

        except Exception:
            pass

        raise ValueError(
            error
        )

    handler = (
        EVENT_HANDLERS[
            event_type
        ]
    )

    try:

        result = handler(
            operation_id,
            payload,
        )

        # =================================================
        # EVENT SUCCESS
        # =================================================

                # =================================================
        # WHICH OPERATION SHOULD OWN THE AUDIT EVENT?
        # =================================================
        #
        # For normal events:
        #
        #     use supplied operation_id
        #
        # For DONATION_CREATED:
        #
        #     no operation existed before processing,
        #     so use the operation created by the handler.
        # =================================================

        log_operation_id = (
            operation_id
        )

        if (
            log_operation_id
            is None
            and
            isinstance(
                result,
                dict,
            )
        ):

            log_operation_id = (
                result.get(
                    "operation_id"
                )
                or
                result.get(
                    "new_operation_id"
                )
            )

        if (
            log_operation_id
            is not None
        ):

            record_event(
                log_operation_id,

                "EVENT_PROCESSED",

                {
                    "trigger_event":
                        event_type,

                    "payload":
                        payload,

                    "result":
                        _summarize_result(
                            result
                        ),
                },
            )

        return {
            "status":
                "processed",

            "event_type":
                event_type,

            "operation_id":
                log_operation_id,

            "result":
                result,
        }
    except Exception as error:

        # =================================================
        # EVENT FAILURE
        # =================================================

        try:

            record_event(
                operation_id,

                "EVENT_FAILED",

                {
                    "trigger_event":
                        event_type,

                    "payload":
                        payload,

                    "error":
                        str(error),
                },
            )

        except Exception:
            # Do not hide the original failure just because
            # event logging also failed.
            pass

        raise