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