import json
import os

from app.database.db import get_connection


DISRUPTION_EVENTS = (
    "DRIVER_CANCELLED",
    "PANTRY_CAPACITY_CHANGED",
    "PANTRY_CLOSED",
    "DELIVERY_FAILED",
    "DONATION_EXPIRED",
)


def _safe_rate(
    numerator,
    denominator,
):
    if not denominator:
        return None

    return float(numerator) / float(denominator)


def get_evaluation_metrics():
    """
    Calculate RescueMesh performance metrics directly
    from the current SQLite database.

    No performance numbers are hard-coded.
    """

    conn = get_connection()

    try:

        # =================================================
        # OPERATIONS
        # =================================================

        operation_stats = conn.execute(
            """
            SELECT
                COUNT(*) AS total_operations,

                SUM(
                    CASE
                        WHEN status IN (
                            'completed',
                            'completed_partial'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS completed_operations,

                SUM(
                    CASE
                        WHEN status = 'completed'
                        THEN 1
                        ELSE 0
                    END
                ) AS fully_completed_operations,

                SUM(
                    CASE
                        WHEN status = 'completed_partial'
                        THEN 1
                        ELSE 0
                    END
                ) AS partially_completed_operations,

                SUM(
                    CASE
                        WHEN status IN (
                            'planned',
                            'active',
                            'awaiting_human'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS open_operations,

                COALESCE(
                    SUM(rescued_lbs),
                    0
                ) AS planned_rescued_lbs,

                COALESCE(
                    SUM(unrescued_lbs),
                    0
                ) AS unrescued_lbs,

                COALESCE(
                    AVG(
                        CASE
                            WHEN total_distance_miles > 0
                            THEN total_distance_miles
                        END
                    ),
                    0
                ) AS average_route_distance

            FROM operations

            WHERE status != 'superseded'
            """
        ).fetchone()

        total_operations = int(
            operation_stats[
                "total_operations"
            ]
            or 0
        )

        completed_operations = int(
            operation_stats[
                "completed_operations"
            ]
            or 0
        )

        fully_completed = int(
            operation_stats[
                "fully_completed_operations"
            ]
            or 0
        )

        partially_completed = int(
            operation_stats[
                "partially_completed_operations"
            ]
            or 0
        )

        open_operations = int(
            operation_stats[
                "open_operations"
            ]
            or 0
        )

        planned_rescued_lbs = float(
            operation_stats[
                "planned_rescued_lbs"
            ]
            or 0
        )

        unrescued_lbs = float(
            operation_stats[
                "unrescued_lbs"
            ]
            or 0
        )

        avg_route_distance = float(
            operation_stats[
                "average_route_distance"
            ]
            or 0
        )

        # =================================================
        # DONATED FOOD THAT ACTUALLY ENTERED RESCUEMESH
        # =================================================
        #
        # Seed donations that never became operations
        # are intentionally excluded.
        # =================================================

        donation_row = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(d.quantity_lbs),
                    0
                ) AS total_donation_lbs

            FROM donations d

            WHERE d.id IN (
                SELECT DISTINCT donation_id
                FROM operations
                WHERE status != 'superseded'
            )
            """
        ).fetchone()

        total_donation_lbs = float(
            donation_row[
                "total_donation_lbs"
            ]
            or 0
        )

        # =================================================
        # ACTUAL CONFIRMED FOOD
        # =================================================
        #
        # Important:
        # We only count food after PANTRY confirmation.
        #
        # driver_delivered does NOT count yet.
        # =================================================

        confirmed_row = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(s.quantity_lbs),
                    0
                ) AS confirmed_lbs

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN operations o
                ON o.id = r.operation_id

            WHERE
                s.status = 'completed'
                AND
                o.status != 'superseded'
            """
        ).fetchone()

        confirmed_lbs = float(
            confirmed_row[
                "confirmed_lbs"
            ]
            or 0
        )

        # =================================================
        # DRIVERS PER RESCUE
        # =================================================

        driver_row = conn.execute(
            """
            SELECT
                COALESCE(
                    AVG(driver_count),
                    0
                ) AS average_drivers

            FROM (
                SELECT
                    o.id,
                    COUNT(
                        DISTINCT r.driver_id
                    ) AS driver_count

                FROM operations o

                LEFT JOIN driver_routes r
                    ON r.operation_id = o.id

                WHERE
                    o.status != 'superseded'

                GROUP BY o.id
            )
            """
        ).fetchone()

        average_drivers = float(
            driver_row[
                "average_drivers"
            ]
            or 0
        )

        # =================================================
        # STOPS PER RESCUE
        # =================================================

        stop_row = conn.execute(
            """
            SELECT
                COALESCE(
                    AVG(stop_count),
                    0
                ) AS average_stops

            FROM (
                SELECT
                    o.id,
                    COUNT(
                        s.id
                    ) AS stop_count

                FROM operations o

                LEFT JOIN driver_routes r
                    ON r.operation_id = o.id

                LEFT JOIN delivery_stops s
                    ON s.route_id = r.id

                WHERE
                    o.status != 'superseded'

                GROUP BY o.id
            )
            """
        ).fetchone()

        average_stops = float(
            stop_row[
                "average_stops"
            ]
            or 0
        )

        # =================================================
        # ESCALATIONS
        # =================================================

        escalation_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_escalations,
                COUNT(
                    DISTINCT operation_id
                ) AS escalated_operations

            FROM escalations
            """
        ).fetchone()

        total_escalations = int(
            escalation_row[
                "total_escalations"
            ]
            or 0
        )

        # =================================================
        # DISRUPTION OPERATIONS
        # =================================================

        placeholders = ",".join(
            "?"
            for _ in DISRUPTION_EVENTS
        )

        disruption_rows = conn.execute(
            f"""
            SELECT DISTINCT
                operation_id

            FROM events

            WHERE
                operation_id IS NOT NULL
                AND event_type IN (
                    {placeholders}
                )
            """,
            DISRUPTION_EVENTS,
        ).fetchall()

        disrupted_operation_ids = {
            row["operation_id"]
            for row in disruption_rows
        }

        escalated_rows = conn.execute(
            """
            SELECT DISTINCT
                operation_id

            FROM escalations

            WHERE operation_id IS NOT NULL
            """
        ).fetchall()

        escalated_operation_ids = {
            row["operation_id"]
            for row in escalated_rows
        }

        # =================================================
        # COMPLETED DISRUPTION OPERATIONS
        # =================================================

        completed_rows = conn.execute(
            """
            SELECT id

            FROM operations

            WHERE status IN (
                'completed',
                'completed_partial'
            )
            """
        ).fetchall()

        completed_operation_ids = {
            row["id"]
            for row in completed_rows
        }

        completed_disrupted_ids = (
            disrupted_operation_ids
            &
            completed_operation_ids
        )

        autonomously_completed_ids = (
            completed_disrupted_ids
            -
            escalated_operation_ids
        )

        # Autonomous recovery here means:
        #
        # disruption happened
        # operation ultimately completed
        # no human escalation was created

        autonomous_recovery_rate = (
            _safe_rate(
                len(
                    autonomously_completed_ids
                ),
                len(
                    completed_disrupted_ids
                ),
            )
        )

        escalated_disruptions = (
            disrupted_operation_ids
            &
            escalated_operation_ids
        )

        human_escalation_rate = (
            _safe_rate(
                len(
                    escalated_disruptions
                ),
                len(
                    disrupted_operation_ids
                ),
            )
        )

        # =================================================
        # FINAL METRICS
        # =================================================

        return {
            "total_operations":
                total_operations,

            "completed_operations":
                completed_operations,

            "fully_completed_operations":
                fully_completed,

            "partially_completed_operations":
                partially_completed,

            "open_operations":
                open_operations,

            "total_donation_lbs":
                round(
                    total_donation_lbs,
                    2,
                ),

            "planned_rescued_lbs":
                round(
                    planned_rescued_lbs,
                    2,
                ),

            "confirmed_lbs":
                round(
                    confirmed_lbs,
                    2,
                ),

            "unrescued_lbs":
                round(
                    unrescued_lbs,
                    2,
                ),

            "confirmed_rescue_rate":
                _safe_rate(
                    confirmed_lbs,
                    total_donation_lbs,
                ),

            "completion_rate":
                _safe_rate(
                    completed_operations,
                    total_operations,
                ),

            "average_drivers_per_rescue":
                round(
                    average_drivers,
                    2,
                ),

            "average_stops_per_rescue":
                round(
                    average_stops,
                    2,
                ),

            "average_route_distance_miles":
                round(
                    avg_route_distance,
                    2,
                ),

            "total_escalations":
                total_escalations,

            "disrupted_operations":
                len(
                    disrupted_operation_ids
                ),

            "completed_disrupted_operations":
                len(
                    completed_disrupted_ids
                ),

            "autonomously_completed_disruptions":
                len(
                    autonomously_completed_ids
                ),

            "autonomous_recovery_rate":
                autonomous_recovery_rate,

            "human_escalation_rate":
                human_escalation_rate,
        }

    finally:
        conn.close()


# =========================================================
# RESCUE-BY-RESCUE RESULTS
# =========================================================

def get_rescue_evaluation_rows():
    """
    Detailed results for each rescue operation.
    """

    conn = get_connection()

    try:

        rows = conn.execute(
            """
            SELECT
                o.id AS rescue_id,

                donor.name AS donor,

                d.food_type,

                d.quantity_lbs
                    AS donated_lbs,

                o.rescued_lbs
                    AS planned_rescued_lbs,

                o.unrescued_lbs,

                o.status,

                o.total_distance_miles,

                COUNT(
                    DISTINCT r.driver_id
                ) AS drivers_used,

                COALESCE(
                    SUM(
                        CASE
                            WHEN s.status = 'completed'
                            THEN s.quantity_lbs
                            ELSE 0
                        END
                    ),
                    0
                ) AS confirmed_lbs

            FROM operations o

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            LEFT JOIN driver_routes r
                ON r.operation_id = o.id

            LEFT JOIN delivery_stops s
                ON s.route_id = r.id

            WHERE
                o.status != 'superseded'

            GROUP BY
                o.id,
                donor.name,
                d.food_type,
                d.quantity_lbs,
                o.rescued_lbs,
                o.unrescued_lbs,
                o.status,
                o.total_distance_miles

            ORDER BY
                o.id DESC
            """
        ).fetchall()

        results = []

        for row in rows:

            donated = float(
                row["donated_lbs"]
                or 0
            )

            confirmed = float(
                row["confirmed_lbs"]
                or 0
            )

            confirmed_percentage = (
                confirmed / donated * 100
                if donated
                else None
            )

            result = {
                "Rescue":
                    f"#{row['rescue_id']}",

                "Donor":
                    row["donor"],

                "Food":
                    row["food_type"]
                    .replace("_", " ")
                    .title(),

                "Donated":
                    f"{donated:.0f} lbs",

                "Confirmed":
                    f"{confirmed:.0f} lbs",

                "Confirmed %":
                    (
                        f"{confirmed_percentage:.0f}%"
                        if confirmed_percentage is not None
                        else "—"
                    ),

                "Drivers":
                    int(
                        row["drivers_used"]
                        or 0
                    ),

                "Distance":
                    (
                        f"{float(row['total_distance_miles']):.1f} mi"
                        if row["total_distance_miles"] is not None
                        else "—"
                    ),

                "Status":
                    row["status"]
                    .replace("_", " ")
                    .title(),
            }

            results.append(
                result
            )

        return results

    finally:
        conn.close()


# =========================================================
# AUTOMATED TEST RESULTS
# =========================================================

def get_latest_test_results():
    """
    Load results generated by:
        python scripts/run_evaluation.py
    """

    path = os.path.join(
        "evaluation",
        "results.json",
    )

    if not os.path.exists(
        path
    ):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception:
        return None

def get_scenario_benchmark_results():
    """
    Load scenario benchmark results generated by:

        python scripts/run_scenario_benchmark.py
    """

    path = os.path.join(
        "evaluation",
        "scenario_results.json",
    )

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except Exception:
        return None