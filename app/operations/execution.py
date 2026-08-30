import json

from app.database.db import (
    get_connection,
)


# =========================================================
# EVENT LOGGING
# =========================================================

def record_event(
    operation_id,
    event_type,
    details=None,
    connection=None,
):
    """
    Record something that happened during a rescue operation.

    Examples:

        PLAN_CREATED
        OPERATION_STARTED
        DRIVER_CANCELLED
        ROUTE_REPLANNED
        DELIVERY_COMPLETED
        OPERATION_COMPLETED

    details is stored as JSON.
    """

    owns_connection = (
        connection is None
    )

    conn = (
        connection
        if connection is not None
        else get_connection()
    )

    try:

        details_json = None

        if details is not None:
            details_json = json.dumps(
                details
            )

        cursor = conn.execute(
            """
            INSERT INTO events (
                operation_id,
                event_type,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                operation_id,
                event_type,
                details_json,
            ),
        )

        if owns_connection:
            conn.commit()

        return cursor.lastrowid

    finally:

        if owns_connection:
            conn.close()


# =========================================================
# CREATE OPERATION FROM OPTIMIZER PLAN
# =========================================================

def create_operation_from_plan(
    plan,
):
    """
    Take the dictionary returned by optimize_rescue_plan()
    and save it as an executable rescue operation.

    Example:

        plan = optimize_rescue_plan(1)

        operation_id = create_operation_from_plan(
            plan
        )
    """

    if not plan:

        raise ValueError(
            "Plan cannot be empty."
        )

    if plan.get("status") != "optimal":

        raise ValueError(
            "Only an optimal rescue plan "
            "can be converted into an operation."
        )

    conn = get_connection()

    try:

        # =================================================
        # TRANSACTION
        # =================================================
        #
        # Either EVERYTHING is saved,
        # or NOTHING is saved.
        #
        # We don't want:
        #
        # operation saved
        # but routes missing
        #
        # or routes saved
        # but pantry stops missing.
        # =================================================

        conn.execute(
            "BEGIN"
        )

        # =================================================
        # SAVE OPERATION
        # =================================================

        cursor = conn.execute(
            """
            INSERT INTO operations (
                donation_id,
                status,
                rescued_lbs,
                unrescued_lbs,
                rescue_rate,
                total_distance_miles
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                plan[
                    "donation_id"
                ],

                "planned",

                plan[
                    "rescued_lbs"
                ],

                plan[
                    "unrescued_lbs"
                ],

                plan[
                    "rescue_rate"
                ],

                plan[
                    "total_distance_miles"
                ],
            ),
        )

        operation_id = (
            cursor.lastrowid
        )

        # =================================================
        # SAVE DRIVER ROUTES
        # =================================================

        for route in plan[
            "driver_routes"
        ]:

            route_cursor = conn.execute(
                """
                INSERT INTO driver_routes (
                    operation_id,
                    driver_id,
                    assigned_lbs,
                    pickup_start,
                    pickup_complete,
                    route_complete,
                    distance_miles,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,

                    route[
                        "driver_id"
                    ],

                    route[
                        "assigned_lbs"
                    ],

                    route[
                        "pickup_start"
                    ],

                    route[
                        "pickup_complete"
                    ],

                    route[
                        "route_complete"
                    ],

                    route[
                        "distance_miles"
                    ],

                    "assigned",
                ),
            )

            route_id = (
                route_cursor.lastrowid
            )

            # =============================================
            # SAVE PANTRY STOPS
            # =============================================

            for stop_order, stop in enumerate(
                route[
                    "stops"
                ],
                start=1,
            ):

                conn.execute(
                    """
                    INSERT INTO delivery_stops (
                        route_id,
                        pantry_id,
                        stop_order,
                        quantity_lbs,
                        eta,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        route_id,

                        stop[
                            "pantry_id"
                        ],

                        stop_order,

                        stop[
                            "quantity_lbs"
                        ],

                        stop[
                            "arrival_time"
                        ],

                        "pending",
                    ),
                )

        # =================================================
        # RECORD INITIAL EVENT
        # =================================================

        record_event(
            operation_id=operation_id,

            event_type="PLAN_CREATED",

            details={
                "donation_id":
                    plan[
                        "donation_id"
                    ],

                "rescued_lbs":
                    plan[
                        "rescued_lbs"
                    ],

                "drivers_used":
                    plan[
                        "drivers_used"
                    ],
            },

            connection=conn,
        )

        conn.commit()

        return operation_id

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# =========================================================
# GET COMPLETE OPERATION
# =========================================================

def get_operation(
    operation_id,
):
    """
    Load an operation including:

        operation
        driver routes
        pantry stops
        event history
    """

    conn = get_connection()

    try:

        operation_row = conn.execute(
            """
            SELECT
                o.*,
                d.food_type,
                d.quantity_lbs,
                dn.name AS donor_name

            FROM operations o

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors dn
                ON dn.id = d.donor_id

            WHERE o.id = ?
            """,
            (
                operation_id,
            ),
        ).fetchone()

        if operation_row is None:
            return None

        operation = dict(
            operation_row
        )

        # =================================================
        # ROUTES
        # =================================================

        route_rows = conn.execute(
            """
            SELECT
                r.*,
                dr.name AS driver_name,
                dr.capacity_lbs

            FROM driver_routes r

            JOIN drivers dr
                ON dr.id = r.driver_id

            WHERE r.operation_id = ?

            ORDER BY r.id
            """,
            (
                operation_id,
            ),
        ).fetchall()

        routes = []

        for route_row in route_rows:

            route = dict(
                route_row
            )

            # =============================================
            # STOPS
            # =============================================

            stop_rows = conn.execute(
                """
                SELECT
                    s.*,
                    p.name AS pantry_name

                FROM delivery_stops s

                JOIN pantries p
                    ON p.id = s.pantry_id

                WHERE s.route_id = ?

                ORDER BY s.stop_order
                """,
                (
                    route[
                        "id"
                    ],
                ),
            ).fetchall()

            route[
                "stops"
            ] = [
                dict(row)
                for row in stop_rows
            ]

            routes.append(
                route
            )

        # =================================================
        # EVENTS
        # =================================================

        event_rows = conn.execute(
            """
            SELECT *
            FROM events

            WHERE operation_id = ?

            ORDER BY id
            """,
            (
                operation_id,
            ),
        ).fetchall()

        events = []

        for row in event_rows:

            event = dict(
                row
            )

            if event[
                "details"
            ]:

                try:
                    event[
                        "details"
                    ] = json.loads(
                        event[
                            "details"
                        ]
                    )

                except json.JSONDecodeError:
                    pass

            events.append(
                event
            )

        operation[
            "driver_routes"
        ] = routes

        operation[
            "events"
        ] = events

        return operation

    finally:

        conn.close()


# =========================================================
# UPDATE OPERATION STATUS
# =========================================================

def update_operation_status(
    operation_id,
    new_status,
):
    """
    Change operation state.

    Example:

        planned
            ↓
        active
            ↓
        completed
    """

    allowed_statuses = {
        "planned",
        "active",
        "completed",
        "cancelled",
        "needs_replan",
        "superseded",
    }

    if new_status not in allowed_statuses:

        raise ValueError(
            f"Invalid operation status: "
            f"{new_status}"
        )

    conn = get_connection()

    try:

        cursor = conn.execute(
            """
            UPDATE operations

            SET
                status = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                new_status,
                operation_id,
            ),
        )

        if cursor.rowcount == 0:

            raise ValueError(
                f"Operation "
                f"{operation_id} "
                f"does not exist."
            )

        conn.commit()

    finally:

        conn.close()


def _get_operation_driver_ids(
    conn,
    operation_id,
):
    """
    Return all drivers assigned to an operation.
    """

    rows = conn.execute(
        """
        SELECT DISTINCT driver_id
        FROM driver_routes
        WHERE operation_id = ?
        """,
        (
            operation_id,
        ),
    ).fetchall()

    return [
        row["driver_id"]
        for row in rows
    ]


def _get_operation_pantry_reservations(
    conn,
    operation_id,
):
    """
    Return the total amount reserved at each pantry.

    Example:

        {
            1: 10,
            5: 40,
            8: 150
        }
    """

    rows = conn.execute(
        """
        SELECT
            s.pantry_id,
            SUM(s.quantity_lbs) AS reserved_lbs

        FROM delivery_stops s

        JOIN driver_routes r
            ON r.id = s.route_id

        WHERE r.operation_id = ?

        GROUP BY s.pantry_id
        """,
        (
            operation_id,
        ),
    ).fetchall()

    return {
        row["pantry_id"]:
            row["reserved_lbs"]

        for row in rows
    }

# =========================================================
# START OPERATION
# =========================================================

def start_operation(
    operation_id,
):
    """
    Activate an operation and reserve its resources.

    This does three important things:

    1. Mark assigned drivers as busy.
    2. Deduct reserved quantity from pantry capacity.
    3. Change operation status planned -> active.

    Everything happens in ONE transaction.

    If any resource is no longer available,
    nothing is changed.
    """

    conn = get_connection()

    try:

        # BEGIN IMMEDIATE prevents another writer from
        # changing capacities while we're reserving them.
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        # =================================================
        # LOAD OPERATION
        # =================================================

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
                f"Operation {operation_id} "
                f"does not exist."
            )

        if operation["status"] != "planned":

            raise ValueError(
                f"Operation {operation_id} "
                f"cannot be started because its "
                f"status is '{operation['status']}'."
            )

        # =================================================
        # GET REQUIRED DRIVERS
        # =================================================

        driver_ids = (
            _get_operation_driver_ids(
                conn,
                operation_id,
            )
        )

        if not driver_ids:

            raise ValueError(
                "Operation has no assigned drivers."
            )

        # =================================================
        # VERIFY DRIVERS ARE STILL AVAILABLE
        # =================================================

        for driver_id in driver_ids:

            driver = conn.execute(
                """
                SELECT id, name, status
                FROM drivers
                WHERE id = ?
                """,
                (
                    driver_id,
                ),
            ).fetchone()

            if driver is None:

                raise ValueError(
                    f"Driver {driver_id} "
                    f"does not exist."
                )

            if driver["status"] != "available":

                raise ValueError(
                    f"Driver {driver['name']} "
                    f"is no longer available."
                )

        # =================================================
        # GET PANTRY RESERVATIONS
        # =================================================

        pantry_reservations = (
            _get_operation_pantry_reservations(
                conn,
                operation_id,
            )
        )

        # =================================================
        # VERIFY PANTRY CAPACITY IS STILL AVAILABLE
        # =================================================

        for (
            pantry_id,
            reserved_lbs,
        ) in pantry_reservations.items():

            pantry = conn.execute(
                """
                SELECT
                    id,
                    name,
                    available_capacity_lbs

                FROM pantries

                WHERE id = ?
                """,
                (
                    pantry_id,
                ),
            ).fetchone()

            if pantry is None:

                raise ValueError(
                    f"Pantry {pantry_id} "
                    f"does not exist."
                )

            if (
                pantry[
                    "available_capacity_lbs"
                ]
                + 0.001
                <
                reserved_lbs
            ):

                raise ValueError(
                    f"{pantry['name']} no longer "
                    f"has enough capacity. "
                    f"Needs {reserved_lbs} lbs, "
                    f"but only "
                    f"{pantry['available_capacity_lbs']} "
                    f"lbs remain."
                )

        # =================================================
        # MARK DRIVERS BUSY
        # =================================================

        for driver_id in driver_ids:

            cursor = conn.execute(
                """
                UPDATE drivers

                SET status = 'busy'

                WHERE
                    id = ?
                    AND
                    status = 'available'
                """,
                (
                    driver_id,
                ),
            )

            if cursor.rowcount != 1:

                raise RuntimeError(
                    f"Could not reserve driver "
                    f"{driver_id}."
                )

        # =================================================
        # RESERVE PANTRY CAPACITY
        # =================================================

        for (
            pantry_id,
            reserved_lbs,
        ) in pantry_reservations.items():

            cursor = conn.execute(
                """
                UPDATE pantries

                SET available_capacity_lbs =
                    available_capacity_lbs - ?

                WHERE
                    id = ?
                    AND
                    available_capacity_lbs >= ?
                """,
                (
                    reserved_lbs,
                    pantry_id,
                    reserved_lbs,
                ),
            )

            if cursor.rowcount != 1:

                raise RuntimeError(
                    f"Could not reserve "
                    f"{reserved_lbs} lbs at "
                    f"pantry {pantry_id}."
                )

        # =================================================
        # ACTIVATE ROUTES
        # =================================================

        conn.execute(
            """
            UPDATE driver_routes

            SET status = 'active'

            WHERE operation_id = ?
            """,
            (
                operation_id,
            ),
        )

        # =================================================
        # ACTIVATE OPERATION
        # =================================================

        conn.execute(
            """
            UPDATE operations

            SET
                status = 'active',
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        )

        # Donation is now actively being handled.

        conn.execute(
            """
            UPDATE donations

            SET status = 'in_progress'

            WHERE id = ?
            """,
            (
                operation[
                    "donation_id"
                ],
            ),
        )

        # =================================================
        # EVENTS
        # =================================================

        record_event(
            operation_id,

            "RESOURCES_RESERVED",

            {
                "driver_ids":
                    driver_ids,

                "pantries":
                    pantry_reservations,
            },

            connection=conn,
        )

        record_event(
            operation_id,

            "OPERATION_STARTED",

            connection=conn,
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()

    return get_operation(
        operation_id
    )


def _release_resources_for_replan(
    conn,
    operation_id,
    cancelled_driver_id,
):
    """
    Release all resources reserved by an operation.

    Used when a driver cancellation forces the whole
    pre-delivery operation to be replanned.

    The cancelled driver stays unavailable.

    Other drivers become available again.

    Pantry capacity is restored.
    """

    # =====================================================
    # RESTORE PANTRY CAPACITY
    # =====================================================

    pantry_reservations = (
        _get_operation_pantry_reservations(
            conn,
            operation_id,
        )
    )

    for (
        pantry_id,
        reserved_lbs,
    ) in pantry_reservations.items():

        # MIN prevents accidental capacity from exceeding
        # the pantry's original maximum.

        conn.execute(
            """
            UPDATE pantries

            SET available_capacity_lbs =
                MIN(
                    max_capacity_lbs,
                    available_capacity_lbs + ?
                )

            WHERE id = ?
            """,
            (
                reserved_lbs,
                pantry_id,
            ),
        )

    # =====================================================
    # RELEASE DRIVERS
    # =====================================================

    driver_ids = (
        _get_operation_driver_ids(
            conn,
            operation_id,
        )
    )

    for driver_id in driver_ids:

        if (
            driver_id
            ==
            cancelled_driver_id
        ):

            # IMPORTANT:
            #
            # The cancelled driver must NOT become available,
            # otherwise the optimizer could immediately
            # assign them again.

            conn.execute(
                """
                UPDATE drivers
                SET status = 'unavailable'
                WHERE id = ?
                """,
                (
                    driver_id,
                ),
            )

        else:

            conn.execute(
                """
                UPDATE drivers
                SET status = 'available'
                WHERE id = ?
                """,
                (
                    driver_id,
                ),
            )

    # =====================================================
    # OLD ROUTES ARE NO LONGER VALID
    # =====================================================

    conn.execute(
        """
        UPDATE driver_routes

        SET status =
            CASE
                WHEN driver_id = ?
                    THEN 'cancelled'
                ELSE 'released'
            END

        WHERE operation_id = ?
        """,
        (
            cancelled_driver_id,
            operation_id,
        ),
    )

    # The stops belong to the abandoned plan.

    conn.execute(
        """
        UPDATE delivery_stops

        SET status = 'cancelled'

        WHERE route_id IN (
            SELECT id
            FROM driver_routes
            WHERE operation_id = ?
        )
        """,
        (
            operation_id,
        ),
    )

    # =====================================================
    # OLD OPERATION NEEDS A NEW PLAN
    # =====================================================

    conn.execute(
        """
        UPDATE operations

        SET
            status = 'needs_replan',
            updated_at = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            operation_id,
        ),
    )

    # The donation is available for planning again because
    # NO deliveries have happened yet.

    conn.execute(
        """
        UPDATE donations

        SET status = 'available'

        WHERE id = (
            SELECT donation_id
            FROM operations
            WHERE id = ?
        )
        """,
        (
            operation_id,
        ),
    )

    return {
        "driver_ids":
            driver_ids,

        "pantry_reservations":
            pantry_reservations,
    }



def cancel_driver_and_replan(
    operation_id,
    driver_id,
):
    """
    Handle a driver cancellation and automatically
    create a replacement rescue operation.

    CURRENT SAFETY RULE:

    Automatic replanning is only allowed BEFORE any
    delivery stop has been completed.

    Why?

    If some food has already been delivered, we cannot
    simply restore the entire donation and pantry capacity.
    We would need to calculate the REMAINING rescue state.

    That more advanced partial-progress replan comes later.
    """

    # =====================================================
    # PHASE 1
    # VALIDATE + RELEASE OLD PLAN
    # =====================================================

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
                f"Operation {operation_id} "
                f"does not exist."
            )

        if operation["status"] != "active":

            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        # =================================================
        # DRIVER MUST ACTUALLY BELONG TO THIS OPERATION
        # =================================================

        assigned_driver = conn.execute(
            """
            SELECT
                dr.id,
                dr.name

            FROM driver_routes r

            JOIN drivers dr
                ON dr.id = r.driver_id

            WHERE
                r.operation_id = ?
                AND
                r.driver_id = ?
            """,
            (
                operation_id,
                driver_id,
            ),
        ).fetchone()

        if assigned_driver is None:

            raise ValueError(
                f"Driver {driver_id} "
                f"is not assigned to "
                f"operation {operation_id}."
            )

        # =================================================
        # DO NOT FULLY REPLAN AFTER A DELIVERY OCCURRED
        # =================================================

        completed_count = conn.execute(
            """
            SELECT COUNT(*)

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            WHERE
                r.operation_id = ?
                AND
                s.status = 'completed'
            """,
            (
                operation_id,
            ),
        ).fetchone()[0]

        if completed_count > 0:

            raise ValueError(
                "Automatic full replanning is not allowed "
                "after a delivery has already been completed. "
                "Remaining-state replanning is required."
            )

        donation_id = (
            operation[
                "donation_id"
            ]
        )

        # =================================================
        # RECORD CANCELLATION
        # =================================================

        record_event(
            operation_id,

            "DRIVER_CANCELLED",

            {
                "driver_id":
                    driver_id,

                "driver_name":
                    assigned_driver[
                        "name"
                    ],
            },

            connection=conn,
        )

        # =================================================
        # RELEASE OLD RESERVATIONS
        # =================================================

        released = (
            _release_resources_for_replan(
                conn,
                operation_id,
                driver_id,
            )
        )

        record_event(
            operation_id,

            "RESOURCES_RELEASED",

            released,

            connection=conn,
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()

    # =====================================================
    # PHASE 2
    # RUN OPTIMIZER AGAIN
    # =====================================================
    #
    # At this point:
    #
    # cancelled driver = unavailable
    #
    # other drivers = available
    #
    # pantry capacity = restored
    #
    # So the optimizer sees the NEW reality.
    # =====================================================

    from app.optimizer.rescue_optimizer import (
        optimize_rescue_plan,
    )

    new_plan = (
        optimize_rescue_plan(
            donation_id
        )
    )

    # =====================================================
    # REPLAN FAILED
    # =====================================================

    if (
        new_plan.get(
            "status"
        )
        !=
        "optimal"
    ):

        record_event(
            operation_id,

            "REPLAN_FAILED",

            {
                "optimizer_status":
                    new_plan.get(
                        "status"
                    ),

                "reason":
                    new_plan.get(
                        "reason"
                    ),
            },
        )

        return {
            "status":
                "replan_failed",

            "old_operation_id":
                operation_id,

            "plan":
                new_plan,
        }

    # =====================================================
    # CREATE NEW OPERATION
    # =====================================================

    new_operation_id = (
        create_operation_from_plan(
            new_plan
        )
    )

    # =====================================================
    # RESERVE NEW PLAN
    # =====================================================

    try:

        start_operation(
            new_operation_id
        )

    except Exception as error:

        record_event(
            operation_id,

            "REPLAN_ACTIVATION_FAILED",

            {
                "new_operation_id":
                    new_operation_id,

                "error":
                    str(error),
            },
        )

        return {
            "status":
                "activation_failed",

            "old_operation_id":
                operation_id,

            "new_operation_id":
                new_operation_id,

            "error":
                str(error),
        }

    # =====================================================
    # OLD PLAN HAS NOW BEEN REPLACED
    # =====================================================

    update_operation_status(
        operation_id,
        "superseded",
    )

    record_event(
        operation_id,

        "REPLAN_CREATED",

        {
            "replacement_operation_id":
                new_operation_id,

            "cancelled_driver_id":
                driver_id,

            "new_drivers_used":
                new_plan[
                    "drivers_used"
                ],
        },
    )

    record_event(
        new_operation_id,

        "REPLAN_FROM_OPERATION",

        {
            "previous_operation_id":
                operation_id,

            "reason":
                "driver_cancelled",

            "cancelled_driver_id":
                driver_id,
        },
    )

    return {
        "status":
            "replanned",

        "old_operation_id":
            operation_id,

        "new_operation_id":
            new_operation_id,

        "new_plan":
            new_plan,

        "new_operation":
            get_operation(
                new_operation_id
            ),
    }


# =========================================================
# COMPLETE DELIVERY STOP
# =========================================================

def complete_delivery_stop(
    stop_id,
):
    """
    Mark one pantry delivery as completed.
    """

    conn = get_connection()

    try:

        row = conn.execute(
            """
            SELECT
                s.id,
                s.route_id,
                s.pantry_id,
                s.quantity_lbs,
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

        conn.execute(
            """
            UPDATE delivery_stops

            SET status = 'completed'

            WHERE id = ?
            """,
            (
                stop_id,
            ),
        )

        conn.commit()

        record_event(
            row[
                "operation_id"
            ],

            "DELIVERY_COMPLETED",

            {
                "stop_id":
                    row[
                        "id"
                    ],

                "pantry_id":
                    row[
                        "pantry_id"
                    ],

                "quantity_lbs":
                    row[
                        "quantity_lbs"
                    ],
            },
        )

    finally:

        conn.close()


# =========================================================
# COMPLETE OPERATION
# =========================================================

def complete_operation(
    operation_id,
):
    """
    Complete an active rescue operation.

    All pantry delivery stops must already be completed.

    Drivers are released back to available.

    Pantry capacity is NOT restored because the food
    was actually delivered.
    """

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
                f"Operation {operation_id} "
                f"does not exist."
            )

        if operation["status"] != "active":

            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        # =================================================
        # CHECK ALL DELIVERIES
        # =================================================

        pending_count = conn.execute(
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

        if pending_count > 0:

            raise ValueError(
                "Operation cannot be completed "
                "because delivery stops are "
                "still pending."
            )

        # =================================================
        # RELEASE DRIVERS
        # =================================================

        driver_ids = (
            _get_operation_driver_ids(
                conn,
                operation_id,
            )
        )

        for driver_id in driver_ids:

            conn.execute(
                """
                UPDATE drivers

                SET status = 'available'

                WHERE
                    id = ?
                    AND
                    status = 'busy'
                """,
                (
                    driver_id,
                ),
            )

        # =================================================
        # COMPLETE ROUTES
        # =================================================

        conn.execute(
            """
            UPDATE driver_routes

            SET status = 'completed'

            WHERE operation_id = ?
            """,
            (
                operation_id,
            ),
        )

        # =================================================
        # COMPLETE OPERATION
        # =================================================

        conn.execute(
            """
            UPDATE operations

            SET
                status = 'completed',
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        )

        # =================================================
        # COMPLETE DONATION
        # =================================================

        conn.execute(
            """
            UPDATE donations

            SET status = 'completed'

            WHERE id = ?
            """,
            (
                operation[
                    "donation_id"
                ],
            ),
        )

        record_event(
            operation_id,

            "OPERATION_COMPLETED",

            {
                "drivers_released":
                    driver_ids,
            },

            connection=conn,
        )

        conn.commit()

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# =========================================================
# EVENT HISTORY
# =========================================================

def get_operation_events(
    operation_id,
):
    """
    Return only the event history.
    """

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT *

            FROM events

            WHERE operation_id = ?

            ORDER BY id
            """,
            (
                operation_id,
            ),
        ).fetchall()

        events = []

        for row in rows:

            event = dict(
                row
            )

            if event[
                "details"
            ]:

                try:
                    event[
                        "details"
                    ] = json.loads(
                        event[
                            "details"
                        ]
                    )

                except json.JSONDecodeError:
                    pass

            events.append(
                event
            )

        return events

    finally:

        conn.close()