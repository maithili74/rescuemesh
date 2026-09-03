import json

from app.database.db import get_connection


# =========================================================
# HELPERS
# =========================================================

TERMINAL_OPERATION_STATUSES = {
    "completed",
    "completed_partial",
    "cancelled",
    "superseded",
}


def _json_load(value, default):
    if value is None:
        return default

    return json.loads(value)


def _row_to_escalation(row):
    if row is None:
        return None

    result = dict(row)

    result["options"] = _json_load(
        result.pop("options_json"),
        [],
    )

    result["context"] = _json_load(
        result.pop("context_json"),
        {},
    )

    return result


# =========================================================
# READ ONE ESCALATION
# =========================================================

def get_escalation(
    escalation_id,
):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *

            FROM escalations

            WHERE id = ?
            """,
            (
                escalation_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    return _row_to_escalation(
        row
    )


# =========================================================
# READ PENDING ESCALATIONS
# =========================================================

def get_pending_escalations(
    operation_id=None,
):
    conn = get_connection()

    try:

        if operation_id is None:

            rows = conn.execute(
                """
                SELECT *

                FROM escalations

                WHERE status = 'pending'

                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()

        else:

            rows = conn.execute(
                """
                SELECT *

                FROM escalations

                WHERE
                    operation_id = ?
                    AND status = 'pending'

                ORDER BY created_at ASC, id ASC
                """,
                (
                    operation_id,
                ),
            ).fetchall()

    finally:
        conn.close()

    return [
        _row_to_escalation(row)
        for row in rows
    ]


# =========================================================
# CREATE ESCALATION
# =========================================================

def create_escalation(
    operation_id,
    escalation_type,
    reason,
    context,
    options,
    recommended_action=None,
):
    """
    Pause an operation only when autonomous recovery
    is no longer safe.

    Duplicate pending escalations of the same type for the
    same operation are prevented.
    """

    if not escalation_type:
        raise ValueError(
            "escalation_type is required."
        )

    if not reason:
        raise ValueError(
            "Escalation reason is required."
        )

    if not options:
        raise ValueError(
            "At least one human decision option is required."
        )

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        operation = conn.execute(
            """
            SELECT *

            FROM operations

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        ).fetchone()

        if operation is None:
            raise ValueError(
                f"Operation {operation_id} does not exist."
            )

        if (
            operation["status"]
            in TERMINAL_OPERATION_STATUSES
        ):
            raise ValueError(
                "A terminal operation cannot create "
                "a human escalation."
            )

        # -------------------------------------------------
        # PREVENT DUPLICATE PENDING ESCALATIONS
        # -------------------------------------------------

        existing = conn.execute(
            """
            SELECT *

            FROM escalations

            WHERE
                operation_id = ?
                AND escalation_type = ?
                AND status = 'pending'

            ORDER BY id DESC

            LIMIT 1
            """,
            (
                operation_id,
                escalation_type,
            ),
        ).fetchone()

        if existing is not None:
            conn.rollback()

            return _row_to_escalation(
                existing
            )

        # -------------------------------------------------
        # CREATE ESCALATION
        # -------------------------------------------------

        cursor = conn.execute(
            """
            INSERT INTO escalations (
                operation_id,
                escalation_type,
                reason,
                status,
                recommended_action,
                options_json,
                context_json
            )

            VALUES (?, ?, ?, 'pending', ?, ?, ?)
            """,
            (
                operation_id,

                escalation_type,

                reason,

                recommended_action,

                json.dumps(
                    options
                ),

                json.dumps(
                    context
                ),
            ),
        )

        escalation_id = (
            cursor.lastrowid
        )

        # Operation is deliberately paused.
        conn.execute(
            """
            UPDATE operations

            SET
                status = 'awaiting_human',
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        )

        # Import locally to avoid circular imports.
        from app.operations.execution import (
            record_event,
        )

        record_event(
            operation_id,

            "ESCALATION_CREATED",

            {
                "escalation_id":
                    escalation_id,

                "escalation_type":
                    escalation_type,

                "reason":
                    reason,

                "recommended_action":
                    recommended_action,
            },

            connection=conn,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_escalation(
        escalation_id
    )


# =========================================================
# APPROVE HUMAN DECISION
# =========================================================

def approve_escalation(
    escalation_id,
    option_id,
    notes=None,
):
    """
    Execute one of the explicit, pre-defined actions.

    The human NEVER supplies arbitrary executable code
    or arbitrary logistics instructions.
    """

    escalation = get_escalation(
        escalation_id
    )

    if escalation is None:
        raise ValueError(
            f"Escalation {escalation_id} does not exist."
        )

    if (
        escalation["status"]
        !=
        "pending"
    ):
        raise ValueError(
            "Only a pending escalation can be approved."
        )

    selected_option = next(
        (
            option
            for option
            in escalation["options"]
            if option.get("id")
            ==
            option_id
        ),
        None,
    )

    if selected_option is None:
        raise ValueError(
            f"Option '{option_id}' is not valid "
            f"for escalation {escalation_id}."
        )

    action = selected_option.get(
        "action"
    )

    operation_id = (
        escalation[
            "operation_id"
        ]
    )

    # =====================================================
    # ACTION 1:
    # EXECUTE FEASIBLE PARTIAL RESCUE
    #
    # Human explicitly accepts responsibility for the
    # unresolved remainder.
    # =====================================================

    if (
        action
        ==
        "approve_partial_replan"
    ):

        context = escalation[
            "context"
        ]

        state = context.get(
            "state"
        )

        plan = context.get(
            "plan"
        )

        if state is None or plan is None:
            raise ValueError(
                "Escalation does not contain "
                "a stored partial rescue plan."
            )

        if (
            plan.get("status")
            !=
            "partial_only"
        ):
            raise ValueError(
                "Stored plan is not a partial rescue plan."
            )

        if not plan.get("stops"):
            raise ValueError(
                "Partial rescue plan has no feasible route."
            )

        # Import locally to avoid circular imports.
        from app.operations.execution import (
            _apply_in_transit_plan,
        )

        # This performs all normal capacity checks again.
        #
        # If the world changed after the escalation was
        # created, this can fail rather than executing an
        # stale unsafe plan.

        _apply_in_transit_plan(
            state,
            plan,
        )

        newly_unrescued_lbs = float(
            plan.get(
                "unrescued_lbs",
                0.0,
            )
        )

        conn = get_connection()

        try:
            conn.execute(
                "BEGIN IMMEDIATE"
            )

            # Original operation metrics represented the
            # previously expected rescued quantity.
            #
            # The human has now accepted that some of that
            # food will require manual handling.

            conn.execute(
                """
                UPDATE operations

                SET
                    rescued_lbs =
                        MAX(
                            0,
                            rescued_lbs - ?
                        ),

                    unrescued_lbs =
                        unrescued_lbs + ?,

                    status = 'active',

                    updated_at =
                        CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    newly_unrescued_lbs,
                    newly_unrescued_lbs,
                    operation_id,
                ),
            )

            conn.execute(
                """
                UPDATE escalations

                SET
                    status = 'approved',
                    decision = ?,
                    decision_notes = ?,
                    resolved_at = CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    option_id,
                    notes,
                    escalation_id,
                ),
            )

            from app.operations.execution import (
                record_event,
            )

            record_event(
                operation_id,

                "HUMAN_APPROVED",

                {
                    "escalation_id":
                        escalation_id,

                    "decision":
                        option_id,

                    "action":
                        action,

                    "rescued_lbs":
                        plan.get(
                            "rescued_lbs"
                        ),

                    "manual_remainder_lbs":
                        newly_unrescued_lbs,
                },

                connection=conn,
            )

            record_event(
                operation_id,

                "ESCALATION_RESOLVED",

                {
                    "escalation_id":
                        escalation_id,

                    "resolution":
                        "approved_partial_replan",
                },

                connection=conn,
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    # =====================================================
    # ACTION 2:
    # HUMAN TAKES OVER REMAINING PHYSICAL COORDINATION
    # =====================================================

    elif (
        action
        ==
        "manual_takeover"
    ):

        conn = get_connection()

        try:
            conn.execute(
                "BEGIN IMMEDIATE"
            )

            conn.execute(
                """
                UPDATE operations

                SET
                    status = 'manual_resolution',
                    updated_at = CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    operation_id,
                ),
            )

            conn.execute(
                """
                UPDATE escalations

                SET
                    status = 'approved',
                    decision = ?,
                    decision_notes = ?,
                    resolved_at = CURRENT_TIMESTAMP

                WHERE id = ?
                """,
                (
                    option_id,
                    notes,
                    escalation_id,
                ),
            )

            from app.operations.execution import (
                record_event,
            )

            record_event(
                operation_id,

                "HUMAN_APPROVED",

                {
                    "escalation_id":
                        escalation_id,

                    "decision":
                        option_id,

                    "action":
                        "manual_takeover",
                },

                connection=conn,
            )

            record_event(
                operation_id,

                "ESCALATION_RESOLVED",

                {
                    "escalation_id":
                        escalation_id,

                    "resolution":
                        "manual_takeover",
                },

                connection=conn,
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            conn.close()

    else:

        raise ValueError(
            f"Unsupported escalation action: {action}"
        )

    return get_escalation(
        escalation_id
    )


# =========================================================
# REJECT RECOMMENDATION
# =========================================================

def reject_escalation(
    escalation_id,
    notes=None,
):
    """
    Rejecting RescueMesh's recommendation does NOT cause
    another automatic action.

    Control moves to manual resolution.
    """

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        escalation = conn.execute(
            """
            SELECT *

            FROM escalations

            WHERE id = ?
            """,
            (
                escalation_id,
            ),
        ).fetchone()

        if escalation is None:
            raise ValueError(
                f"Escalation {escalation_id} "
                f"does not exist."
            )

        if (
            escalation["status"]
            !=
            "pending"
        ):
            raise ValueError(
                "Only a pending escalation can be rejected."
            )

        operation_id = (
            escalation[
                "operation_id"
            ]
        )

        conn.execute(
            """
            UPDATE escalations

            SET
                status = 'rejected',
                decision = 'rejected',
                decision_notes = ?,
                resolved_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                notes,
                escalation_id,
            ),
        )

        # Don't try the exact same automatic logic again.
        #
        # Human has explicitly rejected the recommendation.

        conn.execute(
            """
            UPDATE operations

            SET
                status = 'manual_resolution',
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        )

        from app.operations.execution import (
            record_event,
        )

        record_event(
            operation_id,

            "HUMAN_REJECTED",

            {
                "escalation_id":
                    escalation_id,

                "notes":
                    notes,
            },

            connection=conn,
        )

        record_event(
            operation_id,

            "ESCALATION_RESOLVED",

            {
                "escalation_id":
                    escalation_id,

                "resolution":
                    "rejected",
            },

            connection=conn,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_escalation(
        escalation_id
    )