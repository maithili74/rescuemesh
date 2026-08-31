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
    close_pantry_and_replan,
    complete_operation,
    complete_pickup,
    confirm_pantry_received,
    expire_donation,
    fail_delivery,
    get_operation,
    mark_delivery_by_driver,
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

    return mark_delivery_by_driver(
        operation_id,
        stop_id,
    )
    
    
# =========================================================
# PANTRY RECEIVED
# =========================================================

def _handle_pantry_received(
    operation_id,
    payload,
):
    stop_id = _require_field(
        payload,
        "stop_id",
    )

    return confirm_pantry_received(
        operation_id,
        stop_id,
    )


# =========================================================
# PANTRY CLOSED
# =========================================================

def _handle_pantry_closed(
    operation_id,
    payload,
):
    pantry_id = _require_field(
        payload,
        "pantry_id",
    )

    return close_pantry_and_replan(
        operation_id,
        pantry_id,
    )


# =========================================================
# DELIVERY FAILED
# =========================================================

def _handle_delivery_failed(
    operation_id,
    payload,
):
    stop_id = _require_field(
        payload,
        "stop_id",
    )

    reason = payload.get(
        "reason"
    )

    return fail_delivery(
        operation_id,
        stop_id,
        reason,
    )


# =========================================================
# DONATION EXPIRED
# =========================================================

def _handle_donation_expired(
    operation_id,
    payload,
):
    donation_id = _require_field(
        payload,
        "donation_id",
    )

    return expire_donation(
        donation_id,
        operation_id,
    )    

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

    EventType.DELIVERY_COMPLETED.value:
        _handle_delivery_completed,

    EventType.PANTRY_RECEIVED.value:
        _handle_pantry_received,

    EventType.DRIVER_CANCELLED.value:
        _handle_driver_cancelled,

    EventType.PANTRY_CAPACITY_CHANGED.value:
        _handle_pantry_capacity_changed,

    EventType.PANTRY_CLOSED.value:
        _handle_pantry_closed,

    EventType.DELIVERY_FAILED.value:
        _handle_delivery_failed,

    EventType.DONATION_EXPIRED.value:
        _handle_donation_expired,
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
        "donation_id",
        "stop_id",
        "operation_completed",
        "pantry_id",
        "replanned",
        "failed_quantity_lbs",
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