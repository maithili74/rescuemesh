from app.database.db import get_connection


def _rows_to_dicts(rows):
    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# SYSTEM HEALTH
# =========================================================

def check_database():
    conn = get_connection()

    try:
        conn.execute(
            "SELECT 1"
        ).fetchone()

        return True

    except Exception:
        return False

    finally:
        conn.close()


# =========================================================
# DONORS
# =========================================================

def get_donors():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                name

            FROM donors

            ORDER BY name
            """
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()


def get_donor(
    donor_id,
):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *

            FROM donors

            WHERE id = ?
            """,
            (
                donor_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return dict(
            row
        )

    finally:
        conn.close()


# =========================================================
# DONATIONS
# =========================================================

def get_donor_donations(
    donor_id,
):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.food_type,
                d.quantity_lbs,
                d.available_at,
                d.pickup_deadline,
                d.status,

                o.id AS operation_id,
                o.status AS operation_status,
                o.rescued_lbs,
                o.unrescued_lbs

            FROM donations d

            LEFT JOIN operations o
                ON o.id = (
                    SELECT o2.id

                    FROM operations o2

                    WHERE
                        o2.donation_id = d.id

                    ORDER BY o2.id DESC

                    LIMIT 1
                )

            WHERE d.donor_id = ?

            ORDER BY d.id DESC
            """,
            (
                donor_id,
            ),
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()

def get_donor_metrics(
    donor_id,
):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT

                COUNT(*) AS donation_count,

                COALESCE(
                    SUM(quantity_lbs),
                    0
                ) AS total_donated_lbs,

                COALESCE(
                    SUM(
                        CASE
                            WHEN status IN (
                                'completed',
                                'completed_partial'
                            )
                            THEN quantity_lbs
                            ELSE 0
                        END
                    ),
                    0
                ) AS completed_donation_lbs

            FROM donations

            WHERE donor_id = ?
            """,
            (
                donor_id,
            ),
        ).fetchone()

        return dict(
            row
        )

    finally:
        conn.close()


# =========================================================
# OPERATIONS
# =========================================================

def get_operation_summary():
    conn = get_connection()

    try:
        active = conn.execute(
            """
            SELECT COUNT(*)

            FROM operations

            WHERE status IN (
                'planned',
                'active',
                'awaiting_human'
            )
            """
        ).fetchone()[0]

        in_transit = conn.execute(
            """
            SELECT COALESCE(
                SUM(r.assigned_lbs),
                0
            )

            FROM driver_routes r

            JOIN operations o
                ON o.id = r.operation_id

            WHERE
                o.status IN (
                    'active',
                    'awaiting_human'
                )
                AND
                r.status = 'picked_up'
            """
        ).fetchone()[0]

        escalations = conn.execute(
            """
            SELECT COUNT(*)

            FROM escalations

            WHERE status = 'pending'
            """
        ).fetchone()[0]

        totals = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(rescued_lbs),
                    0
                ),
                COALESCE(
                    SUM(
                        rescued_lbs
                        +
                        unrescued_lbs
                    ),
                    0
                )

            FROM operations

            WHERE status IN (
                'completed',
                'completed_partial'
            )
            """
        ).fetchone()

        rescued = float(
            totals[0]
            or 0
        )

        total = float(
            totals[1]
            or 0
        )

        rescue_rate = (
            rescued / total
            if total > 0
            else 0
        )

        return {
            "active_rescues":
                active,

            "food_in_transit_lbs":
                float(
                    in_transit
                    or 0
                ),

            "pending_escalations":
                escalations,

            "rescue_rate":
                rescue_rate,
        }

    finally:
        conn.close()
        
def get_supported_food_types():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT DISTINCT food_type

            FROM pantry_needs

            WHERE food_type IS NOT NULL

            ORDER BY food_type
            """
        ).fetchall()

        return [
            row["food_type"]
            for row in rows
        ]

    finally:
        conn.close()
        
# =========================================================
# DRIVERS
# =========================================================

def get_drivers():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                location,
                capacity_lbs,
                available_from,
                available_until,
                status

            FROM drivers

            ORDER BY name
            """
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()


def get_driver_assignments(
    driver_id,
):
    """
    Return current rescue assignments for one driver.

    Completed historical operations are intentionally
    excluded from the main Driver Portal.
    """

    conn = get_connection()

    try:
        routes = conn.execute(
            """
            SELECT
                r.id AS route_id,
                r.operation_id,
                r.driver_id,
                r.assigned_lbs,
                r.pickup_start,
                r.pickup_complete,
                r.route_complete,
                r.distance_miles,
                r.status AS route_status,

                o.status AS operation_status,
                o.donation_id,
                o.rescued_lbs,
                o.unrescued_lbs,

                d.food_type,
                d.quantity_lbs AS donation_quantity_lbs,
                d.available_at,
                d.pickup_deadline,

                donor.name AS donor_name,
                donor.location AS donor_location

            FROM driver_routes r

            JOIN operations o
                ON o.id = r.operation_id

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            WHERE
                r.driver_id = ?
                AND
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human'
                )

            ORDER BY r.id DESC
            """,
            (
                driver_id,
            ),
        ).fetchall()

        assignments = []

        for route in routes:

            route_dict = dict(
                route
            )

            stops = conn.execute(
                """
                SELECT
                    s.id AS stop_id,
                    s.stop_order,
                    s.quantity_lbs,
                    s.eta,
                    s.status,
                    s.pantry_id,
                    p.name AS pantry_name,
                    p.location AS pantry_location

                FROM delivery_stops s

                JOIN pantries p
                    ON p.id = s.pantry_id

                WHERE s.route_id = ?

                ORDER BY s.stop_order
                """,
                (
                    route[
                        "route_id"
                    ],
                ),
            ).fetchall()

            route_dict[
                "stops"
            ] = _rows_to_dicts(
                stops
            )

            assignments.append(
                route_dict
            )

        return assignments

    finally:
        conn.close()


def get_driver_metrics(
    driver_id,
):
    conn = get_connection()

    try:
        active_assignments = conn.execute(
            """
            SELECT COUNT(*)

            FROM driver_routes r

            JOIN operations o
                ON o.id = r.operation_id

            WHERE
                r.driver_id = ?
                AND
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human'
                )
            """,
            (
                driver_id,
            ),
        ).fetchone()[0]

        assigned_food = conn.execute(
            """
            SELECT COALESCE(
                SUM(r.assigned_lbs),
                0
            )

            FROM driver_routes r

            JOIN operations o
                ON o.id = r.operation_id

            WHERE
                r.driver_id = ?
                AND
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human'
                )
            """,
            (
                driver_id,
            ),
        ).fetchone()[0]

        remaining_stops = conn.execute(
            """
            SELECT COUNT(*)

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            WHERE
                r.driver_id = ?
                AND
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human'
                )
                AND
                s.status IN (
                    'pending',
                    'driver_delivered',
                    'failed'
                )
            """,
            (
                driver_id,
            ),
        ).fetchone()[0]

        return {
            "active_assignments":
                active_assignments,

            "assigned_food_lbs":
                float(
                    assigned_food
                    or 0
                ),

            "remaining_stops":
                remaining_stops,
        }

    finally:
        conn.close()
        
def get_all_driver_assignments():
    """
    Return all current RescueMesh driver assignments.

    Used by the fleet-style Driver Portal so judges can
    immediately see who RescueMesh assigned to each rescue.
    """

    conn = get_connection()

    try:
        routes = conn.execute(
            """
            SELECT
                r.id AS route_id,
                r.operation_id,
                r.driver_id,
                r.assigned_lbs,
                r.pickup_start,
                r.pickup_complete,
                r.route_complete,
                r.distance_miles,
                r.status AS route_status,

                o.status AS operation_status,
                o.donation_id,

                d.food_type,
                d.quantity_lbs AS donation_quantity_lbs,

                donor.name AS donor_name,
                donor.location AS donor_location,

                driver.name AS driver_name,
                driver.location AS driver_location,
                driver.capacity_lbs AS driver_capacity_lbs

            FROM driver_routes r

            JOIN operations o
                ON o.id = r.operation_id

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            JOIN drivers driver
                ON driver.id = r.driver_id

            WHERE
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human',
                    'completed',
                    'completed_partial'
                )

            ORDER BY
                r.pickup_start ASC,
                o.id ASC,
                r.id ASC
            """
        ).fetchall()

        assignments = []

        for route in routes:

            route_dict = dict(
                route
            )

            stops = conn.execute(
                """
                SELECT
                    s.id AS stop_id,
                    s.stop_order,
                    s.quantity_lbs,
                    s.eta,
                    s.status,
                    s.pantry_id,

                    p.name AS pantry_name,
                    p.location AS pantry_location

                FROM delivery_stops s

                JOIN pantries p
                    ON p.id = s.pantry_id

                WHERE s.route_id = ?

                ORDER BY s.stop_order
                """,
                (
                    route[
                        "route_id"
                    ],
                ),
            ).fetchall()

            route_dict[
                "stops"
            ] = _rows_to_dicts(
                stops
            )

            assignments.append(
                route_dict
            )

        return assignments

    finally:
        conn.close()
        
# =========================================================
# PANTRIES
# =========================================================

def get_pantries():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                name,
                location,
                max_capacity_lbs,
                available_capacity_lbs,
                status

            FROM pantries

            ORDER BY name
            """
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()


def get_pantry_incoming_deliveries(
    pantry_id,
):
    """
    Return current deliveries heading to this pantry.

    Includes:
    - planned/pending deliveries
    - deliveries marked delivered by the driver
      but not yet confirmed by the pantry
    """

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.stop_order,
                s.quantity_lbs,
                s.eta,
                s.status AS stop_status,

                r.id AS route_id,
                r.driver_id,
                r.status AS route_status,

                o.id AS operation_id,
                o.status AS operation_status,

                d.id AS donation_id,
                d.food_type,
                d.quantity_lbs AS donation_quantity_lbs,

                donor.name AS donor_name,
                donor.location AS donor_location,

                driver.name AS driver_name

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            JOIN drivers driver
                ON driver.id = r.driver_id

            WHERE
                s.pantry_id = ?
                AND
                o.status IN (
                    'planned',
                    'active',
                    'awaiting_human'
                )
                AND
                s.status IN (
                    'pending',
                    'driver_delivered'
                )

            ORDER BY
                s.eta ASC,
                o.id ASC
            """,
            (
                pantry_id,
            ),
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()


def get_pantry_completed_deliveries(
    pantry_id,
    limit=10,
):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.quantity_lbs,
                s.eta,

                o.id AS operation_id,

                d.food_type,

                donor.name AS donor_name,

                driver.name AS driver_name

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            JOIN drivers driver
                ON driver.id = r.driver_id

            WHERE
                s.pantry_id = ?
                AND
                s.status = 'completed'

            ORDER BY
                s.id DESC

            LIMIT ?
            """,
            (
                pantry_id,
                limit,
            ),
        ).fetchall()

        return _rows_to_dicts(
            rows
        )

    finally:
        conn.close()
        
import json


# =========================================================
# OPERATIONS CENTER
# =========================================================

def get_operations_dashboard(
    limit=20,
):
    """
    Return recent RescueMesh operations with
    drivers and delivery stops.

    Used by the Operations Center.
    """

    conn = get_connection()

    try:

        operation_rows = conn.execute(
            """
            SELECT
                o.id,
                o.donation_id,
                o.status,
                o.rescued_lbs,
                o.unrescued_lbs,
                o.rescue_rate,
                o.total_distance_miles,
                o.created_at,
                o.updated_at,

                d.food_type,
                d.quantity_lbs,
                d.available_at,
                d.pickup_deadline,

                donor.name AS donor_name,
                donor.location AS donor_location

            FROM operations o

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            ORDER BY o.id DESC

            LIMIT ?
            """,
            (
                limit,
            ),
        ).fetchall()

        operations = []

        for operation_row in operation_rows:

            operation = dict(
                operation_row
            )

            route_rows = conn.execute(
                """
                SELECT
                    r.id AS route_id,
                    r.driver_id,
                    r.assigned_lbs,
                    r.pickup_start,
                    r.pickup_complete,
                    r.route_complete,
                    r.distance_miles,
                    r.status AS route_status,

                    driver.name AS driver_name,
                    driver.location AS driver_location,
                    driver.capacity_lbs

                FROM driver_routes r

                JOIN drivers driver
                    ON driver.id = r.driver_id

                WHERE r.operation_id = ?

                ORDER BY r.id
                """,
                (
                    operation[
                        "id"
                    ],
                ),
            ).fetchall()

            routes = []

            for route_row in route_rows:

                route = dict(
                    route_row
                )

                stop_rows = conn.execute(
                    """
                    SELECT
                        s.id AS stop_id,
                        s.stop_order,
                        s.pantry_id,
                        s.quantity_lbs,
                        s.eta,
                        s.status AS stop_status,

                        p.name AS pantry_name,
                        p.location AS pantry_location

                    FROM delivery_stops s

                    JOIN pantries p
                        ON p.id = s.pantry_id

                    WHERE s.route_id = ?

                    ORDER BY s.stop_order
                    """,
                    (
                        route[
                            "route_id"
                        ],
                    ),
                ).fetchall()

                route[
                    "stops"
                ] = _rows_to_dicts(
                    stop_rows
                )

                routes.append(
                    route
                )

            operation[
                "routes"
            ] = routes

            operations.append(
                operation
            )

        return operations

    finally:
        conn.close()


def get_operation_timeline(
    operation_id,
    limit=20,
):
    """
    Return recent events for an operation.
    """

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                id,
                event_type,
                details,
                created_at

            FROM events

            WHERE operation_id = ?

            ORDER BY id DESC

            LIMIT ?
            """,
            (
                operation_id,
                limit,
            ),
        ).fetchall()

        events = []

        for row in rows:

            event = dict(
                row
            )

            details = event.get(
                "details"
            )

            if isinstance(
                details,
                str,
            ):
                try:
                    event[
                        "details"
                    ] = json.loads(
                        details
                    )
                except Exception:
                    pass

            events.append(
                event
            )

        return events

    finally:
        conn.close()