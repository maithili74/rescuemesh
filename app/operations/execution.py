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
    unavailable_driver_id=None,
):
    """
    Release resources belonging to an abandoned operation.

    Pantry reservations are restored.

    Normally all drivers become available again.

    If unavailable_driver_id is provided, that driver
    remains unavailable.

    Examples:

    Driver cancellation:
        James -> unavailable
        everyone else -> available

    Pantry capacity change:
        all drivers -> available
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
            unavailable_driver_id
            is not None
            and
            driver_id
            ==
            unavailable_driver_id
        ):

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
    # INVALIDATE OLD ROUTES
    # =====================================================

    if unavailable_driver_id is None:

        # No particular driver failed.
        #
        # Example:
        # pantry capacity changed.
        conn.execute(
            """
            UPDATE driver_routes

            SET status = 'released'

            WHERE operation_id = ?
            """,
            (
                operation_id,
            ),
        )

    else:

        # Driver cancellation.
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
                unavailable_driver_id,
                operation_id,
            ),
        )

    # =====================================================
    # CANCEL OLD STOPS
    # =====================================================

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
    # MARK OPERATION FOR REPLAN
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

    # =====================================================
    # MAKE DONATION PLANNABLE AGAIN
    # =====================================================

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


def change_pantry_capacity_and_replan(
    operation_id,
    pantry_id,
    new_max_capacity_lbs,
):
    """
    Change a pantry's TOTAL capacity.

    If the currently active rescue plan still fits,
    keep the operation active.

    If the reservation no longer fits:

        release old operation resources
        apply new pantry capacity
        re-run optimizer
        create replacement operation
        activate replacement operation

    Current safety rule:

    We only automatically replan if NO delivery has
    been completed yet.
    """

    if new_max_capacity_lbs < 0:

        raise ValueError(
            "Pantry capacity cannot be negative."
        )

    conn = get_connection()

    needs_replan = False
    donation_id = None
    old_max_capacity = None
    old_available_capacity = None
    reserved_lbs = 0

    try:

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

        if operation["status"] != "active":

            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        donation_id = (
            operation[
                "donation_id"
            ]
        )

        # =================================================
        # SAFETY:
        # NO FULL REPLAN AFTER A DELIVERY OCCURRED
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
                "Automatic full replanning is not "
                "allowed after a delivery has already "
                "been completed. Remaining-state "
                "replanning is required."
            )
            
            
        picked_up_count = conn.execute(
            """
            SELECT COUNT(*)

            FROM driver_routes

            WHERE
                operation_id = ?
                AND
                status = 'picked_up'
            """,
            (
                operation_id,
            ),
        ).fetchone()[0]

        if picked_up_count > 0:

            raise ValueError(
                "Automatic full replanning is not "
                "allowed after food has already been "
                "picked up. In-transit replanning is "
                "required."
            )            

        # =================================================
        # LOAD PANTRY
        # =================================================

        pantry = conn.execute(
            """
            SELECT
                id,
                name,
                max_capacity_lbs,
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

        old_max_capacity = (
            pantry[
                "max_capacity_lbs"
            ]
        )

        old_available_capacity = (
            pantry[
                "available_capacity_lbs"
            ]
        )

        # =================================================
        # FIND HOW MUCH THIS OPERATION RESERVED HERE
        # =================================================

        pantry_reservations = (
            _get_operation_pantry_reservations(
                conn,
                operation_id,
            )
        )

        reserved_lbs = (
            pantry_reservations.get(
                pantry_id,
                0.0,
            )
        )

        # =================================================
        # HOW MUCH CAPACITY WAS ALREADY OCCUPIED BEFORE
        # THIS OPERATION RESERVED SPACE?
        # =================================================
        #
        # Example:
        #
        # max capacity = 180
        #
        # before rescue:
        # available = 150
        #
        # therefore existing food = 30
        #
        # operation reserves 150
        #
        # current available = 0
        #
        # occupied_before_reservation:
        #
        # 180 - 0 - 150 = 30
        # =================================================

        occupied_before_reservation = max(
            0.0,
            old_max_capacity
            -
            old_available_capacity
            -
            reserved_lbs,
        )

        capacity_available_for_operation = max(
            0.0,
            new_max_capacity_lbs
            -
            occupied_before_reservation,
        )

        # =================================================
        # CURRENT PLAN STILL FITS
        # =================================================

        if (
            reserved_lbs
            <=
            capacity_available_for_operation
            + 0.001
        ):

            new_available = max(
                0.0,

                new_max_capacity_lbs
                -
                occupied_before_reservation
                -
                reserved_lbs,
            )

            conn.execute(
                """
                UPDATE pantries

                SET
                    max_capacity_lbs = ?,
                    available_capacity_lbs = ?

                WHERE id = ?
                """,
                (
                    new_max_capacity_lbs,
                    new_available,
                    pantry_id,
                ),
            )

            record_event(
                operation_id,

                "PANTRY_CAPACITY_CHANGED",

                {
                    "pantry_id":
                        pantry_id,

                    "old_max_capacity_lbs":
                        old_max_capacity,

                    "new_max_capacity_lbs":
                        new_max_capacity_lbs,

                    "reserved_lbs":
                        reserved_lbs,

                    "triggered_replan":
                        False,
                },

                connection=conn,
            )

            conn.commit()

            return {
                "status":
                    "capacity_updated",

                "operation_id":
                    operation_id,

                "pantry_id":
                    pantry_id,

                "replanned":
                    False,
            }

        # =================================================
        # CURRENT PLAN NO LONGER FITS
        # =================================================

        needs_replan = True

        # First release the WHOLE old plan using the old
        # capacity values.
        _release_resources_for_replan(
            conn,
            operation_id,
        )

        # After releasing this operation, determine how much
        # REAL pre-existing capacity is occupied.

        pantry_after_release = conn.execute(
            """
            SELECT
                max_capacity_lbs,
                available_capacity_lbs

            FROM pantries

            WHERE id = ?
            """,
            (
                pantry_id,
            ),
        ).fetchone()

        occupied_without_operation = max(
            0.0,

            pantry_after_release[
                "max_capacity_lbs"
            ]
            -
            pantry_after_release[
                "available_capacity_lbs"
            ],
        )

        new_available = max(
            0.0,

            new_max_capacity_lbs
            -
            occupied_without_operation,
        )

        # NOW apply the new capacity.

        conn.execute(
            """
            UPDATE pantries

            SET
                max_capacity_lbs = ?,
                available_capacity_lbs = ?

            WHERE id = ?
            """,
            (
                new_max_capacity_lbs,
                new_available,
                pantry_id,
            ),
        )

        record_event(
            operation_id,

            "PANTRY_CAPACITY_CHANGED",

            {
                "pantry_id":
                    pantry_id,

                "old_max_capacity_lbs":
                    old_max_capacity,

                "new_max_capacity_lbs":
                    new_max_capacity_lbs,

                "reserved_lbs":
                    reserved_lbs,

                "triggered_replan":
                    True,
            },

            connection=conn,
        )

        record_event(
            operation_id,

            "RESOURCES_RELEASED",

            {
                "reason":
                    "pantry_capacity_changed"
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
    # NO REPLAN NEEDED
    # =====================================================

    if not needs_replan:

        return {
            "status":
                "capacity_updated",

            "operation_id":
                operation_id,

            "replanned":
                False,
        }

    # =====================================================
    # RUN OPTIMIZER AGAIN
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
    # NO REPLACEMENT PLAN
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
                "reason":
                    "pantry_capacity_changed",

                "optimizer_status":
                    new_plan.get(
                        "status"
                    ),

                "optimizer_reason":
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
    # CREATE REPLACEMENT
    # =====================================================

    new_operation_id = (
        create_operation_from_plan(
            new_plan
        )
    )

    try:

        start_operation(
            new_operation_id
        )

    except Exception as error:

        record_event(
            operation_id,

            "REPLAN_ACTIVATION_FAILED",

            {
                "reason":
                    "pantry_capacity_changed",

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
    # OLD OPERATION REPLACED
    # =====================================================

    update_operation_status(
        operation_id,
        "superseded",
    )

    record_event(
        operation_id,

        "REPLAN_CREATED",

        {
            "reason":
                "pantry_capacity_changed",

            "pantry_id":
                pantry_id,

            "replacement_operation_id":
                new_operation_id,

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
                "pantry_capacity_changed",

            "pantry_id":
                pantry_id,
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


def plan_new_donation(
    donation_id,
):
    """
    React to a newly-created donation.

    Flow:

        donation exists
            ↓
        optimize
            ↓
        save planned operation
            ↓
        drivers receive assignments

    IMPORTANT:
    This does NOT start the operation.

    Drivers must accept their assignments first.
    """

    conn = get_connection()

    try:

        donation = conn.execute(
            """
            SELECT *

            FROM donations

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        ).fetchone()

        if donation is None:

            raise ValueError(
                f"Donation {donation_id} "
                f"does not exist."
            )

        if (
            donation["status"]
            !=
            "available"
        ):

            raise ValueError(
                f"Donation {donation_id} "
                f"is not available for planning. "
                f"Current status: "
                f"{donation['status']}"
            )

        # Prevent duplicate operations for the same
        # donation.

        existing_operation = (
            conn.execute(
                """
                SELECT id, status

                FROM operations

                WHERE
                    donation_id = ?
                    AND
                    status IN (
                        'planned',
                        'active',
                        'needs_replan'
                    )

                LIMIT 1
                """,
                (
                    donation_id,
                ),
            ).fetchone()
        )

        if existing_operation:

            raise ValueError(
                f"Donation {donation_id} "
                f"already has operation "
                f"{existing_operation['id']} "
                f"with status "
                f"{existing_operation['status']}."
            )

    finally:

        conn.close()

    # =====================================================
    # OPTIMIZE
    # =====================================================

    from app.optimizer.rescue_optimizer import (
        optimize_rescue_plan,
    )

    plan = optimize_rescue_plan(
        donation_id
    )

    if (
        plan.get("status")
        !=
        "optimal"
    ):

        return {
            "status":
                "planning_failed",

            "donation_id":
                donation_id,

            "plan":
                plan,
        }

    # =====================================================
    # SAVE PLANNED OPERATION
    # =====================================================

    operation_id = (
        create_operation_from_plan(
            plan
        )
    )

    conn = get_connection()

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        conn.execute(
            """
            UPDATE donations

            SET status = 'planned'

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        )

        record_event(
            operation_id,

            "DONATION_CREATED",

            {
                "donation_id":
                    donation_id,

                "drivers_assigned":
                    plan["drivers_used"],

                "rescued_lbs":
                    plan["rescued_lbs"],
            },

            connection=conn,
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

    return {
        "status":
            "planned",

        "donation_id":
            donation_id,

        "operation_id":
            operation_id,

        "plan":
            plan,

        "operation":
            get_operation(
                operation_id
            ),
    }
    
    
def accept_driver_assignment(
    operation_id,
    driver_id,
):
    """
    Accept one driver's assignment.

    If every driver assigned to the operation has accepted,
    automatically activate the operation and reserve
    resources.
    """

    conn = get_connection()

    all_accepted = False
    remaining_drivers = 0

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        # =================================================
        # CHECK OPERATION
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

        if (
            operation["status"]
            !=
            "planned"
        ):

            raise ValueError(
                f"Operation {operation_id} "
                f"is not waiting for driver acceptance. "
                f"Current status: "
                f"{operation['status']}."
            )

        # =================================================
        # FIND DRIVER ROUTE
        # =================================================

        route = conn.execute(
            """
            SELECT *

            FROM driver_routes

            WHERE
                operation_id = ?
                AND
                driver_id = ?
            """,
            (
                operation_id,
                driver_id,
            ),
        ).fetchone()

        if route is None:

            raise ValueError(
                f"Driver {driver_id} "
                f"is not assigned to "
                f"operation {operation_id}."
            )

        if (
            route["status"]
            ==
            "accepted"
        ):

            raise ValueError(
                f"Driver {driver_id} "
                f"already accepted this assignment."
            )

        if (
            route["status"]
            !=
            "assigned"
        ):

            raise ValueError(
                f"Driver {driver_id} "
                f"cannot accept a route with "
                f"status {route['status']}."
            )

        # =================================================
        # ACCEPT ROUTE
        # =================================================

        conn.execute(
            """
            UPDATE driver_routes

            SET status = 'accepted'

            WHERE id = ?
            """,
            (
                route["id"],
            ),
        )

        record_event(
            operation_id,

            "DRIVER_ACCEPTED",

            {
                "driver_id":
                    driver_id,

                "route_id":
                    route["id"],
            },

            connection=conn,
        )

        # =================================================
        # CHECK IF EVERY DRIVER ACCEPTED
        # =================================================

        remaining_drivers = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM driver_routes

                WHERE
                    operation_id = ?
                    AND
                    status != 'accepted'
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

        all_accepted = (
            remaining_drivers
            ==
            0
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

    # =====================================================
    # START ONLY AFTER EVERY DRIVER ACCEPTS
    # =====================================================

    if all_accepted:

        operation = start_operation(
            operation_id
        )

        return {
            "status":
                "operation_started",

            "operation_id":
                operation_id,

            "driver_id":
                driver_id,

            "all_drivers_accepted":
                True,

            "remaining_drivers":
                0,

            "operation":
                operation,
        }

    return {
        "status":
            "accepted_waiting",

        "operation_id":
            operation_id,

        "driver_id":
            driver_id,

        "all_drivers_accepted":
            False,

        "remaining_drivers":
            remaining_drivers,
    }
    

def complete_pickup(
    operation_id,
    driver_id,
):
    """
    Mark a driver's pickup as completed.

    The food is now physically with this driver.
    """

    conn = get_connection()

    try:

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        # =================================================
        # CHECK OPERATION
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

        if (
            operation["status"]
            !=
            "active"
        ):

            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        # =================================================
        # FIND DRIVER ROUTE
        # =================================================

        route = conn.execute(
            """
            SELECT *

            FROM driver_routes

            WHERE
                operation_id = ?
                AND
                driver_id = ?
            """,
            (
                operation_id,
                driver_id,
            ),
        ).fetchone()

        if route is None:

            raise ValueError(
                f"Driver {driver_id} "
                f"is not assigned to "
                f"operation {operation_id}."
            )

        if (
            route["status"]
            ==
            "picked_up"
        ):

            raise ValueError(
                f"Driver {driver_id} "
                f"already completed pickup."
            )

        if (
            route["status"]
            !=
            "active"
        ):

            raise ValueError(
                f"Driver {driver_id} "
                f"cannot complete pickup "
                f"while route status is "
                f"{route['status']}."
            )

        # =================================================
        # PICKUP COMPLETED
        # =================================================

        conn.execute(
            """
            UPDATE driver_routes

            SET status = 'picked_up'

            WHERE id = ?
            """,
            (
                route["id"],
            ),
        )

        record_event(
            operation_id,

            "PICKUP_COMPLETED",

            {
                "driver_id":
                    driver_id,

                "route_id":
                    route["id"],

                "assigned_lbs":
                    route[
                        "assigned_lbs"
                    ],
            },

            connection=conn,
        )

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

    return {
        "status":
            "pickup_completed",

        "operation_id":
            operation_id,

        "driver_id":
            driver_id,

        "route_id":
            route["id"],

        "assigned_lbs":
            route[
                "assigned_lbs"
            ],
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

        picked_up_count = conn.execute(
            """
            SELECT COUNT(*)

            FROM driver_routes

            WHERE
                operation_id = ?
                AND
                status = 'picked_up'
            """,
            (
                operation_id,
            ),
        ).fetchone()[0]

        if picked_up_count > 0:

            raise ValueError(
                "Automatic full replanning is not "
                "allowed after food has already been "
                "picked up. In-transit replanning is "
                "required."
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


def mark_delivery_by_driver(
    operation_id,
    stop_id,
):
    """
    Driver reports that food was delivered.

    This does NOT yet complete the stop.

    The pantry must confirm receipt through
    PANTRY_RECEIVED.
    """

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        row = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.status AS stop_status,
                s.quantity_lbs,
                s.pantry_id,
                r.id AS route_id,
                r.driver_id,
                r.status AS route_status,
                r.operation_id,
                o.status AS operation_status

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            WHERE s.id = ?
            """,
            (
                stop_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not exist."
            )

        if (
            row["operation_id"]
            !=
            operation_id
        ):
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not belong to "
                f"operation {operation_id}."
            )

        if (
            row["operation_status"]
            !=
            "active"
        ):
            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        # Driver should physically have the food first.
        if (
            row["route_status"]
            !=
            "picked_up"
        ):
            raise ValueError(
                "Delivery cannot be completed "
                "before pickup."
            )

        if (
            row["stop_status"]
            ==
            "driver_delivered"
        ):
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"was already marked delivered "
                f"by the driver."
            )

        if (
            row["stop_status"]
            !=
            "pending"
        ):
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"cannot be delivered while "
                f"status is "
                f"{row['stop_status']}."
            )

        conn.execute(
            """
            UPDATE delivery_stops

            SET status = 'driver_delivered'

            WHERE id = ?
            """,
            (
                stop_id,
            ),
        )

        record_event(
            operation_id,

            "DELIVERY_COMPLETED",

            {
                "stop_id":
                    stop_id,

                "driver_id":
                    row["driver_id"],

                "pantry_id":
                    row["pantry_id"],

                "quantity_lbs":
                    row["quantity_lbs"],
            },

            connection=conn,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "status":
            "driver_delivered",

        "operation_id":
            operation_id,

        "stop_id":
            stop_id,

        "pantry_id":
            row["pantry_id"],

        "quantity_lbs":
            row["quantity_lbs"],
    }
    
    
    
# pantry confirms receipt 

def confirm_pantry_received(
    operation_id,
    stop_id,
):
    """
    Pantry confirms that food was actually received.

    driver_delivered
            ↓
        completed

    If this was the final stop, complete the entire
    operation.
    """

    conn = get_connection()

    all_completed = False

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        row = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.status AS stop_status,
                s.quantity_lbs,
                s.pantry_id,
                r.driver_id,
                r.operation_id,
                o.status AS operation_status

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            WHERE s.id = ?
            """,
            (
                stop_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not exist."
            )

        if (
            row["operation_id"]
            !=
            operation_id
        ):
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not belong to "
                f"operation {operation_id}."
            )

        if (
            row["operation_status"]
            !=
            "active"
        ):
            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        if (
            row["stop_status"]
            ==
            "completed"
        ):
            raise ValueError(
                f"Pantry already confirmed "
                f"delivery stop {stop_id}."
            )

        if (
            row["stop_status"]
            !=
            "driver_delivered"
        ):
            raise ValueError(
                "Pantry cannot confirm receipt "
                "until the driver marks the "
                "delivery as delivered."
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

        record_event(
            operation_id,

            "PANTRY_RECEIVED",

            {
                "stop_id":
                    stop_id,

                "pantry_id":
                    row["pantry_id"],

                "driver_id":
                    row["driver_id"],

                "quantity_lbs":
                    row["quantity_lbs"],
            },

            connection=conn,
        )

        remaining = conn.execute(
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

        all_completed = (
            remaining == 0
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # complete_operation() has its own transaction.
    if all_completed:
        complete_operation(
            operation_id
        )

    return {
        "status":
            "pantry_received",

        "operation_id":
            operation_id,

        "stop_id":
            stop_id,

        "operation_completed":
            all_completed,
    }
    

#delivery failed

def fail_delivery(
    operation_id,
    stop_id,
    reason=None,
):
    """
    Mark a delivery attempt as failed.

    Because the food may already be physically in transit,
    we do NOT restore pantry capacity, release the driver,
    or pretend the food returned to the donor.

    Instead we mark the operation as needing replanning.

    A future in-transit replan will decide where the
    undelivered food should go.
    """

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        row = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.status AS stop_status,
                s.quantity_lbs,
                s.pantry_id,
                r.driver_id,
                r.status AS route_status,
                r.operation_id,
                o.status AS operation_status

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            WHERE s.id = ?
            """,
            (
                stop_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not exist."
            )

        if (
            row["operation_id"]
            !=
            operation_id
        ):
            raise ValueError(
                f"Delivery stop {stop_id} "
                f"does not belong to "
                f"operation {operation_id}."
            )

        if (
            row["operation_status"]
            !=
            "active"
        ):
            raise ValueError(
                f"Operation {operation_id} "
                f"is not active."
            )

        if (
            row["route_status"]
            !=
            "picked_up"
        ):
            raise ValueError(
                "DELIVERY_FAILED requires the "
                "food to have been picked up."
            )

        if (
            row["stop_status"]
            ==
            "completed"
        ):
            raise ValueError(
                "A completed delivery cannot "
                "be marked failed."
            )

        conn.execute(
            """
            UPDATE delivery_stops

            SET status = 'failed'

            WHERE id = ?
            """,
            (
                stop_id,
            ),
        )

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

        record_event(
            operation_id,

            "DELIVERY_FAILED",

            {
                "stop_id":
                    stop_id,

                "driver_id":
                    row["driver_id"],

                "pantry_id":
                    row["pantry_id"],

                "quantity_lbs":
                    row["quantity_lbs"],

                "reason":
                    reason,
            },

            connection=conn,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "status":
            "requires_in_transit_replan",

        "operation_id":
            operation_id,

        "stop_id":
            stop_id,

        "driver_id":
            row[
                "driver_id"
            ],

        "pantry_id":
            row[
                "pantry_id"
            ],

        "failed_quantity_lbs":
            row[
                "quantity_lbs"
            ],

        "reason":
            reason,
    }
    
    
#pantry closed

def close_pantry_and_replan(
    operation_id,
    pantry_id,
):
    """
    Mark a pantry unavailable.

    If the current operation does not use the pantry:
        simply close it.

    If the operation does use it:
        before pickup -> safe full replan
        after pickup  -> require in-transit replan
    """

    conn = get_connection()

    donation_id = None
    operation_was_active = False

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

        if (
            operation["status"]
            not in (
                "planned",
                "active",
            )
        ):
            raise ValueError(
                f"Operation {operation_id} "
                f"cannot react to pantry closure "
                f"while status is "
                f"{operation['status']}."
            )

        donation_id = (
            operation["donation_id"]
        )

        operation_was_active = (
            operation["status"]
            ==
            "active"
        )

        pantry = conn.execute(
            """
            SELECT *

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

        # Is this pantry actually part of this rescue?

        affected_stop_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM delivery_stops s

                JOIN driver_routes r
                    ON r.id = s.route_id

                WHERE
                    r.operation_id = ?
                    AND
                    s.pantry_id = ?
                    AND
                    s.status NOT IN (
                        'completed',
                        'cancelled'
                    )
                """,
                (
                    operation_id,
                    pantry_id,
                ),
            ).fetchone()[0]
        )

        # Close the pantry regardless.
        conn.execute(
            """
            UPDATE pantries

            SET status = 'unavailable'

            WHERE id = ?
            """,
            (
                pantry_id,
            ),
        )

        record_event(
            operation_id,

            "PANTRY_CLOSED",

            {
                "pantry_id":
                    pantry_id,

                "affected_operation":
                    affected_stop_count > 0,
            },

            connection=conn,
        )

        # =================================================
        # OPERATION DOESN'T USE THIS PANTRY
        # =================================================

        if affected_stop_count == 0:

            conn.commit()

            return {
                "status":
                    "pantry_closed",

                "operation_id":
                    operation_id,

                "pantry_id":
                    pantry_id,

                "replanned":
                    False,
            }

        # =================================================
        # SAFETY CHECK AFTER PICKUP
        # =================================================

        picked_up_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM driver_routes

                WHERE
                    operation_id = ?
                    AND
                    status = 'picked_up'
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

        driver_delivered_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM delivery_stops s

                JOIN driver_routes r
                    ON r.id = s.route_id

                WHERE
                    r.operation_id = ?
                    AND
                    s.status IN (
                        'driver_delivered',
                        'completed'
                    )
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

        if (
            picked_up_count > 0
            or
            driver_delivered_count > 0
        ):

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

            record_event(
                operation_id,

                "IN_TRANSIT_REPLAN_REQUIRED",

                {
                    "reason":
                        "pantry_closed",

                    "pantry_id":
                        pantry_id,
                },

                connection=conn,
            )

            conn.commit()

            return {
                "status":
                    "requires_in_transit_replan",

                "operation_id":
                    operation_id,

                "pantry_id":
                    pantry_id,
            }

        # =================================================
        # SAFE TO INVALIDATE OLD PLAN
        # =================================================

        if operation_was_active:

            released = (
                _release_resources_for_replan(
                    conn,
                    operation_id,
                )
            )

            record_event(
                operation_id,

                "RESOURCES_RELEASED",

                {
                    "reason":
                        "pantry_closed",

                    "driver_ids":
                        released[
                            "driver_ids"
                        ],

                    "pantry_reservations":
                        released[
                            "pantry_reservations"
                        ],
                },

                connection=conn,
            )

        else:
            # PLANNED operation:
            #
            # Resources were never reserved, so DO NOT
            # "restore" pantry capacity.

            conn.execute(
                """
                UPDATE driver_routes

                SET status = 'released'

                WHERE operation_id = ?
                """,
                (
                    operation_id,
                ),
            )

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

            conn.execute(
                """
                UPDATE donations

                SET status = 'available'

                WHERE id = ?
                """,
                (
                    donation_id,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # =====================================================
    # REOPTIMIZE WITHOUT CLOSED PANTRY
    # =====================================================

    from app.optimizer.rescue_optimizer import (
        optimize_rescue_plan,
    )

    new_plan = optimize_rescue_plan(
        donation_id
    )

    if (
        new_plan.get("status")
        !=
        "optimal"
    ):

        record_event(
            operation_id,

            "REPLAN_FAILED",

            {
                "reason":
                    "pantry_closed",

                "pantry_id":
                    pantry_id,

                "optimizer_status":
                    new_plan.get(
                        "status"
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

    new_operation_id = (
        create_operation_from_plan(
            new_plan
        )
    )

    # Match the state of the operation being replaced.
    #
    # If drivers had already accepted and operation was
    # active, activate the replacement like our existing
    # replan behavior.
    #
    # If it was still planned, replacement stays planned.

    if operation_was_active:
        start_operation(
            new_operation_id
        )

    update_operation_status(
        operation_id,
        "superseded",
    )

    record_event(
        operation_id,

        "REPLAN_CREATED",

        {
            "reason":
                "pantry_closed",

            "pantry_id":
                pantry_id,

            "replacement_operation_id":
                new_operation_id,
        },
    )

    record_event(
        new_operation_id,

        "REPLAN_FROM_OPERATION",

        {
            "previous_operation_id":
                operation_id,

            "reason":
                "pantry_closed",

            "pantry_id":
                pantry_id,
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
    

#donation expired

def expire_donation(
    donation_id,
    operation_id=None,
):
    """
    Expire a donation that can no longer be picked up.

    Safe cases:

        available donation
        planned operation
        active operation before pickup

    Unsafe:

        food already picked up
    """

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        donation = conn.execute(
            """
            SELECT *

            FROM donations

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        ).fetchone()

        if donation is None:
            raise ValueError(
                f"Donation {donation_id} "
                f"does not exist."
            )

        if (
            donation["status"]
            ==
            "completed"
        ):
            raise ValueError(
                "Completed donation cannot expire."
            )

        # If operation wasn't provided, find current one.

        if operation_id is None:

            row = conn.execute(
                """
                SELECT id

                FROM operations

                WHERE
                    donation_id = ?
                    AND
                    status IN (
                        'planned',
                        'active'
                    )

                ORDER BY id DESC

                LIMIT 1
                """,
                (
                    donation_id,
                ),
            ).fetchone()

            if row is not None:
                operation_id = (
                    row["id"]
                )

        # =================================================
        # NO OPERATION EXISTS
        # =================================================

        if operation_id is None:

            conn.execute(
                """
                UPDATE donations

                SET status = 'expired'

                WHERE id = ?
                """,
                (
                    donation_id,
                ),
            )

            conn.commit()

            return {
                "status":
                    "expired",

                "donation_id":
                    donation_id,

                "operation_id":
                    None,
            }

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

        if (
            operation["donation_id"]
            !=
            donation_id
        ):
            raise ValueError(
                f"Operation {operation_id} "
                f"does not belong to "
                f"donation {donation_id}."
            )

        # =================================================
        # FOOD ALREADY PICKED UP?
        # =================================================

        picked_up_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM driver_routes

                WHERE
                    operation_id = ?
                    AND
                    status = 'picked_up'
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

        delivered_count = (
            conn.execute(
                """
                SELECT COUNT(*)

                FROM delivery_stops s

                JOIN driver_routes r
                    ON r.id = s.route_id

                WHERE
                    r.operation_id = ?
                    AND
                    s.status IN (
                        'driver_delivered',
                        'completed'
                    )
                """,
                (
                    operation_id,
                ),
            ).fetchone()[0]
        )

        if (
            picked_up_count > 0
            or
            delivered_count > 0
        ):

            raise ValueError(
                "Donation cannot expire after food "
                "has already been picked up."
            )

        # =================================================
        # ACTIVE → RELEASE RESOURCES
        # =================================================

        if (
            operation["status"]
            ==
            "active"
        ):

            released = (
                _release_resources_for_replan(
                    conn,
                    operation_id,
                )
            )

            record_event(
                operation_id,

                "RESOURCES_RELEASED",

                {
                    "reason":
                        "donation_expired",

                    "driver_ids":
                        released[
                            "driver_ids"
                        ],

                    "pantry_reservations":
                        released[
                            "pantry_reservations"
                        ],
                },

                connection=conn,
            )

        # =================================================
        # PLANNED → NOTHING WAS RESERVED
        # =================================================

        elif (
            operation["status"]
            ==
            "planned"
        ):

            conn.execute(
                """
                UPDATE driver_routes

                SET status = 'cancelled'

                WHERE operation_id = ?
                """,
                (
                    operation_id,
                ),
            )

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

        else:
            raise ValueError(
                f"Donation cannot expire while "
                f"operation status is "
                f"{operation['status']}."
            )

        # =================================================
        # FINAL EXPIRED STATE
        # =================================================

        conn.execute(
            """
            UPDATE operations

            SET
                status = 'cancelled',
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                operation_id,
            ),
        )

        conn.execute(
            """
            UPDATE donations

            SET status = 'expired'

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        )

        record_event(
            operation_id,

            "DONATION_EXPIRED",

            {
                "donation_id":
                    donation_id,
            },

            connection=conn,
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "status":
            "expired",

        "donation_id":
            donation_id,

        "operation_id":
            operation_id,
    }        
    
    
def _add_minutes_to_time(
    time_value,
    minutes,
):
    hour, minute = map(
        int,
        time_value.split(":"),
    )

    total = (
        hour * 60
        +
        minute
        +
        minutes
    )

    return (
        f"{(total // 60) % 24:02d}:"
        f"{total % 60:02d}"
    )


# =========================================================
# PREPARE REMAINING PHYSICAL STATE
# =========================================================

def _prepare_in_transit_replan(
    operation_id,
    driver_id,
    reason,
    excluded_pantry_ids=None,
):
    """
    Build the TRUE remaining state after food has already
    been picked up.

    Rules:

    COMPLETED
        Food already received.
        Keep it permanently.

    DRIVER_DELIVERED
        Food physically left the driver's vehicle and is
        waiting for pantry confirmation.
        Keep its reservation.

    PENDING
        Food still in vehicle.
        Release old reservation and replan it.

    FAILED
        Delivery failed.
        Food is still in vehicle.
        Release old reservation and replan it.
    """

    excluded_pantry_ids = set(
        excluded_pantry_ids
        or []
    )

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        # =================================================
        # OPERATION + DONATION
        # =================================================

        operation = conn.execute(
            """
            SELECT
                o.*,
                d.food_type,
                dn.latitude AS donor_latitude,
                dn.longitude AS donor_longitude

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

        if operation is None:

            raise ValueError(
                f"Operation {operation_id} "
                f"does not exist."
            )

        if (
            operation["status"]
            not in (
                "active",
                "needs_replan",
            )
        ):

            raise ValueError(
                "In-transit replanning requires "
                "an active or disrupted operation."
            )

        # =================================================
        # DRIVER ROUTE
        # =================================================

        route = conn.execute(
            """
            SELECT
                r.*,
                d.name AS driver_name,
                d.available_until

            FROM driver_routes r

            JOIN drivers d
                ON d.id = r.driver_id

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

        if route is None:

            raise ValueError(
                f"Driver {driver_id} "
                f"is not assigned to "
                f"operation {operation_id}."
            )

        if (
            route["status"]
            !=
            "picked_up"
        ):

            raise ValueError(
                "In-transit replanning requires "
                "the driver to already have the food."
            )

        # =================================================
        # ROUTE STOPS
        # =================================================

        stops = conn.execute(
            """
            SELECT
                s.*,
                p.name AS pantry_name,
                p.latitude,
                p.longitude

            FROM delivery_stops s

            JOIN pantries p
                ON p.id = s.pantry_id

            WHERE s.route_id = ?

            ORDER BY s.stop_order ASC
            """,
            (
                route["id"],
            ),
        ).fetchall()

        # =================================================
        # ESTIMATE CURRENT DRIVER LOCATION
        # =================================================
        #
        # Until we have GPS:
        #
        # no stop reached:
        #     donor location
        #
        # stop reached:
        #     latest reached pantry
        # =================================================

        current_latitude = (
            operation[
                "donor_latitude"
            ]
        )

        current_longitude = (
            operation[
                "donor_longitude"
            ]
        )

        current_time = (
            route[
                "pickup_complete"
            ]
        )

        progressed_stops = [
            stop
            for stop in stops
            if stop["status"] in (
                "completed",
                "driver_delivered",
                "failed",
            )
        ]

        if progressed_stops:

            latest_stop = max(
                progressed_stops,
                key=lambda stop:
                    stop[
                        "stop_order"
                    ],
            )

            current_latitude = (
                latest_stop[
                    "latitude"
                ]
            )

            current_longitude = (
                latest_stop[
                    "longitude"
                ]
            )

            current_time = (
                _add_minutes_to_time(
                    latest_stop[
                        "eta"
                    ],
                    5,
                )
            )

        # =================================================
        # FOOD STILL IN VEHICLE
        # =================================================

        remaining_stops = [
            stop
            for stop in stops
            if stop["status"] in (
                "pending",
                "failed",
            )
        ]

        remaining_lbs = round(
            sum(
                stop[
                    "quantity_lbs"
                ]

                for stop
                in remaining_stops
            ),
            2,
        )

        if remaining_lbs <= 0:

            raise ValueError(
                "No undelivered food remains "
                "with this driver."
            )

        # A failed pantry should not immediately be selected
        # again for that same failed delivery.

        for stop in remaining_stops:

            if (
                stop["status"]
                ==
                "failed"
            ):

                excluded_pantry_ids.add(
                    stop[
                        "pantry_id"
                    ]
                )

        # =================================================
        # RELEASE ONLY UNUSED RESERVATIONS
        # =================================================

        released_reservations = {}

        for stop in remaining_stops:

            pantry_id = (
                stop[
                    "pantry_id"
                ]
            )

            released_reservations[
                pantry_id
            ] = (
                released_reservations.get(
                    pantry_id,
                    0.0,
                )
                +
                stop[
                    "quantity_lbs"
                ]
            )

        for (
            pantry_id,
            quantity,
        ) in (
            released_reservations.items()
        ):

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
                    quantity,
                    pantry_id,
                ),
            )

        # =================================================
        # PRESERVE OLD HISTORY
        # =================================================

        # Old pending destinations are no longer valid.

        conn.execute(
            """
            UPDATE delivery_stops

            SET status = 'cancelled'

            WHERE
                route_id = ?
                AND
                status = 'pending'
            """,
            (
                route["id"],
            ),
        )

        # Failed food was released for replanning.
        #
        # Use a distinct state so another retry cannot
        # restore its pantry capacity twice.

        conn.execute(
            """
            UPDATE delivery_stops

            SET status = 'failed_released'

            WHERE
                route_id = ?
                AND
                status = 'failed'
            """,
            (
                route["id"],
            ),
        )

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

        record_event(
            operation_id,

            "IN_TRANSIT_REPLAN_STARTED",

            {
                "reason":
                    reason,

                "driver_id":
                    driver_id,

                "route_id":
                    route["id"],

                "remaining_lbs":
                    remaining_lbs,

                "released_reservations":
                    released_reservations,

                "excluded_pantry_ids":
                    sorted(
                        excluded_pantry_ids
                    ),
            },

            connection=conn,
        )

        conn.commit()

        return {
            "operation_id":
                operation_id,

            "donation_id":
                operation[
                    "donation_id"
                ],

            "route_id":
                route[
                    "id"
                ],

            "driver_id":
                driver_id,

            "driver_name":
                route[
                    "driver_name"
                ],

            "driver_available_until":
                route[
                    "available_until"
                ],

            "food_type":
                operation[
                    "food_type"
                ],

            "remaining_lbs":
                remaining_lbs,

            "current_latitude":
                current_latitude,

            "current_longitude":
                current_longitude,

            "current_time":
                current_time,

            "excluded_pantry_ids":
                sorted(
                    excluded_pantry_ids
                ),
        }

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =========================================================
# APPLY REPLACEMENT ROUTE
# =========================================================

def _apply_in_transit_plan(
    state,
    plan,
):
    """
    Apply the replacement destinations to the SAME route.

    The driver already has the food, so we do not:

    - create another pickup
    - release the driver
    - create another donor pickup
    - create an entirely fake fresh operation
    """

    operation_id = (
        state[
            "operation_id"
        ]
    )

    route_id = (
        state[
            "route_id"
        ]
    )

    conn = get_connection()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        route = conn.execute(
            """
            SELECT *

            FROM driver_routes

            WHERE id = ?
            """,
            (
                route_id,
            ),
        ).fetchone()

        if route is None:

            raise ValueError(
                f"Route {route_id} "
                f"does not exist."
            )

        if (
            route["status"]
            !=
            "picked_up"
        ):

            raise ValueError(
                "Driver route is no longer "
                "eligible for in-transit replanning."
            )

        # =================================================
        # RESERVE NEW PANTRY CAPACITY
        # =================================================

        for assignment in (
            plan[
                "assignments"
            ]
        ):

            pantry_id = (
                assignment[
                    "pantry_id"
                ]
            )

            quantity = float(
                assignment[
                    "quantity_lbs"
                ]
            )

            cursor = conn.execute(
                """
                UPDATE pantries

                SET available_capacity_lbs =
                    available_capacity_lbs - ?

                WHERE
                    id = ?
                    AND
                    status = 'available'
                    AND
                    available_capacity_lbs >= ?
                """,
                (
                    quantity,
                    pantry_id,
                    quantity,
                ),
            )

            if cursor.rowcount != 1:

                raise ValueError(
                    f"Pantry {pantry_id} "
                    f"no longer has enough "
                    f"available capacity."
                )

        # =================================================
        # APPEND REPLACEMENT STOPS
        # =================================================

        current_max_order = (
            conn.execute(
                """
                SELECT COALESCE(
                    MAX(stop_order),
                    0
                )

                FROM delivery_stops

                WHERE route_id = ?
                """,
                (
                    route_id,
                ),
            ).fetchone()[0]
        )

        for (
            offset,
            stop,
        ) in enumerate(
            plan[
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

                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'pending'
                )
                """,
                (
                    route_id,

                    stop[
                        "pantry_id"
                    ],

                    current_max_order
                    +
                    offset,

                    stop[
                        "quantity_lbs"
                    ],

                    stop[
                        "arrival_time"
                    ],
                ),
            )

        # =================================================
        # UPDATE CURRENT ROUTE
        # =================================================

        conn.execute(
            """
            UPDATE driver_routes

            SET route_complete = ?

            WHERE id = ?
            """,
            (
                plan[
                    "route_complete"
                ],
                route_id,
            ),
        )

        # Same operation becomes active again.

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

        record_event(
            operation_id,

            "IN_TRANSIT_REPLAN_APPLIED",

            {
                "driver_id":
                    state[
                        "driver_id"
                    ],

                "route_id":
                    route_id,

                "remaining_lbs":
                    state[
                        "remaining_lbs"
                    ],

                "replacement_stops":
                    plan[
                        "stops"
                    ],

                "remaining_distance_miles":
                    plan[
                        "remaining_distance_miles"
                    ],
            },

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


# =========================================================
# PUBLIC IN-TRANSIT REPLAN
# =========================================================

def replan_in_transit(
    operation_id,
    driver_id,
    reason,
    excluded_pantry_ids=None,
):
    """
    Replan ONLY the food still carried by this driver.

    If every remaining pound can be safely rerouted:
        apply automatically.

    Otherwise:
        do not silently accept a partial solution.
        hand the problem to human escalation.
    """

    state = (
        _prepare_in_transit_replan(
            operation_id,
            driver_id,
            reason,
            excluded_pantry_ids,
        )
    )

    from app.optimizer.in_transit_optimizer import (
        optimize_in_transit_route,
    )

    plan = (
        optimize_in_transit_route(
            state
        )
    )

    # =====================================================
    # FULL AUTONOMOUS RECOVERY
    # =====================================================

    if (
        plan.get(
            "status"
        )
        ==
        "optimal"
    ):

        try:
            operation = (
                _apply_in_transit_plan(
                    state,
                    plan,
                )
            )

        except Exception as error:

            record_event(
                operation_id,

                "IN_TRANSIT_REPLAN_ACTIVATION_FAILED",

                {
                    "reason":
                        reason,

                    "driver_id":
                        driver_id,

                    "error":
                        str(error),
                },
            )

            return {
                "status":
                    "requires_human_escalation",

                "operation_id":
                    operation_id,

                "driver_id":
                    driver_id,

                "remaining_lbs":
                    state[
                        "remaining_lbs"
                    ],

                "reason":
                    "replacement_plan_could_not_be_applied",

                "error":
                    str(error),

                "plan":
                    plan,
            }

        return {
            "status":
                "in_transit_replanned",

            "operation_id":
                operation_id,

            "driver_id":
                driver_id,

            "remaining_lbs":
                state[
                    "remaining_lbs"
                ],

            "plan":
                plan,

            "operation":
                operation,
        }

    # =====================================================
    # AUTONOMOUS RECOVERY NOT GOOD ENOUGH
    # =====================================================

    record_event(
        operation_id,

        "IN_TRANSIT_REPLAN_FAILED",

        {
            "reason":
                reason,

            "driver_id":
                driver_id,

            "remaining_lbs":
                state[
                    "remaining_lbs"
                ],

            "optimizer_status":
                plan.get(
                    "status"
                ),

            "rescued_lbs":
                plan.get(
                    "rescued_lbs"
                ),

            "unrescued_lbs":
                plan.get(
                    "unrescued_lbs"
                ),
        },
    )

    return {
        "status":
            "requires_human_escalation",

        "operation_id":
            operation_id,

        "driver_id":
            driver_id,

        "remaining_lbs":
            state[
                "remaining_lbs"
            ],

        "reason":
            "no_safe_full_remaining_plan",

        "plan":
            plan,
    }


# =========================================================
# PANTRY-CLOSURE HELPER
# =========================================================

def replan_closed_pantry_in_transit(
    operation_id,
    pantry_id,
):
    """
    Find picked-up drivers whose undelivered route still
    depended on the closed pantry and replan those routes.
    """

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT DISTINCT
                r.driver_id

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            WHERE
                r.operation_id = ?
                AND
                s.pantry_id = ?
                AND
                r.status = 'picked_up'
                AND
                s.status IN (
                    'pending',
                    'failed'
                )
            """,
            (
                operation_id,
                pantry_id,
            ),
        ).fetchall()

    finally:

        conn.close()

    affected_driver_ids = [
        row[
            "driver_id"
        ]
        for row in rows
    ]

    # Example:
    #
    # driver already delivered food to the pantry and it
    # closes while waiting for confirmation.
    #
    # That is not a routing problem anymore.
    # Human judgment is appropriate.

    if not affected_driver_ids:

        record_event(
            operation_id,

            "IN_TRANSIT_REPLAN_FAILED",

            {
                "reason":
                    "pantry_closed",

                "pantry_id":
                    pantry_id,

                "detail":
                    "No reroutable in-vehicle stop "
                    "was found.",
            },
        )

        return {
            "status":
                "requires_human_escalation",

            "operation_id":
                operation_id,

            "pantry_id":
                pantry_id,

            "reason":
                "food_not_safely_reroutable",
        }

    results = []

    for driver_id in (
        affected_driver_ids
    ):

        result = replan_in_transit(
            operation_id=
                operation_id,

            driver_id=
                driver_id,

            reason=
                "pantry_closed",

            excluded_pantry_ids=[
                pantry_id
            ],
        )

        results.append(
            result
        )

    if all(
        result[
            "status"
        ]
        ==
        "in_transit_replanned"

        for result in results
    ):

        return {
            "status":
                "in_transit_replanned",

            "operation_id":
                operation_id,

            "pantry_id":
                pantry_id,

            "replans":
                results,
        }

    return {
        "status":
            "requires_human_escalation",

        "operation_id":
            operation_id,

        "pantry_id":
            pantry_id,

        "replans":
            results,
    }

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