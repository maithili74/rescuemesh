from app.database.db import get_connection

from app.dashboard.services.metrics import (
    get_evaluation_metrics,
    get_rescue_evaluation_rows,
)


def fail(message):
    print(f"❌ FAIL: {message}")
    raise SystemExit(1)


def passed(message):
    print(f"✅ {message}")


def main():

    print()
    print("=" * 70)
    print("RESCUEMESH GOLDEN-PATH METRIC VERIFICATION")
    print("=" * 70)
    print()

    conn = get_connection()

    try:

        # =====================================================
        # CHECK CURRENT OPERATIONS
        # =====================================================

        operations = conn.execute(
            """
            SELECT
                o.id,
                o.status,
                o.rescued_lbs,
                o.unrescued_lbs,

                d.quantity_lbs AS donated_lbs,
                d.food_type,

                donor.name AS donor_name

            FROM operations o

            JOIN donations d
                ON d.id = o.donation_id

            JOIN donors donor
                ON donor.id = d.donor_id

            WHERE
                o.status != 'superseded'

            ORDER BY o.id
            """
        ).fetchall()

        if not operations:

            fail(
                "No rescue operation exists. "
                "Run the golden demo first."
            )

        if len(operations) != 1:

            fail(
                "Expected exactly 1 rescue after a clean "
                f"Demo Reset, but found {len(operations)}."
            )

        operation = operations[0]

        operation_id = operation["id"]

        donated_lbs = float(
            operation["donated_lbs"]
        )

        rescued_lbs = float(
            operation["rescued_lbs"]
            or 0
        )

        unrescued_lbs = float(
            operation["unrescued_lbs"]
            or 0
        )

        print(
            f"Rescue #{operation_id}"
        )

        print(
            f"Donor: {operation['donor_name']}"
        )

        print(
            f"Food: {operation['food_type']}"
        )

        print(
            f"Donated: {donated_lbs:.0f} lbs"
        )

        print(
            f"Operation status: {operation['status']}"
        )

        print()

        # =====================================================
        # OPERATION MUST BE COMPLETE
        # =====================================================

        if (
            operation["status"]
            not in (
                "completed",
                "completed_partial",
            )
        ):

            fail(
                "Golden rescue is not complete yet. "
                f"Current status: {operation['status']}"
            )

        passed(
            "Rescue operation reached a completed state."
        )

        # =====================================================
        # CHECK DELIVERY STOPS
        # =====================================================

        stop_rows = conn.execute(
            """
            SELECT
                s.id,
                s.quantity_lbs,
                s.status,
                p.name AS pantry_name

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN pantries p
                ON p.id = s.pantry_id

            WHERE
                r.operation_id = ?

            ORDER BY s.stop_order
            """,
            (
                operation_id,
            ),
        ).fetchall()

        if not stop_rows:

            fail(
                "Operation has no delivery stops."
            )

        unresolved_stops = [
            row
            for row in stop_rows
            if row["status"] != "completed"
        ]

        if unresolved_stops:

            fail(
                "Some delivery stops have not been "
                "confirmed by their pantries."
            )

        passed(
            "Every delivery stop is pantry-confirmed."
        )

        confirmed_lbs = sum(
            float(
                row["quantity_lbs"]
            )
            for row in stop_rows
            if row["status"] == "completed"
        )

        print()
        print(
            f"Pantry-confirmed food: "
            f"{confirmed_lbs:.0f} lbs"
        )

        # =====================================================
        # CHECK ROUTES
        # =====================================================

        route_rows = conn.execute(
            """
            SELECT
                id,
                driver_id,
                assigned_lbs,
                status

            FROM driver_routes

            WHERE operation_id = ?
            """,
            (
                operation_id,
            ),
        ).fetchall()

        if not route_rows:

            fail(
                "Operation has no driver routes."
            )

        incomplete_routes = [
            row
            for row in route_rows
            if row["status"] != "completed"
        ]

        if incomplete_routes:

            fail(
                "One or more driver routes are not complete."
            )

        passed(
            "All driver routes are complete."
        )

    finally:
        conn.close()

    # =========================================================
    # CHECK EVALUATION METRICS
    # =========================================================

    metrics = get_evaluation_metrics()

    print()
    print("-" * 70)
    print("EVALUATION METRICS")
    print("-" * 70)

    print(
        f"Operations: "
        f"{metrics['total_operations']}"
    )

    print(
        f"Completed operations: "
        f"{metrics['completed_operations']}"
    )

    print(
        f"Confirmed food: "
        f"{metrics['confirmed_lbs']:.0f} lbs"
    )

    print(
        f"Food entering operations: "
        f"{metrics['total_donation_lbs']:.0f} lbs"
    )

    print(
        "Confirmed rescue rate: "
        + (
            f"{metrics['confirmed_rescue_rate'] * 100:.1f}%"
            if metrics[
                "confirmed_rescue_rate"
            ]
            is not None
            else "—"
        )
    )

    print(
        "Completion rate: "
        + (
            f"{metrics['completion_rate'] * 100:.1f}%"
            if metrics[
                "completion_rate"
            ]
            is not None
            else "—"
        )
    )

    print()

    # =========================================================
    # EXPECTED GOLDEN PATH VALUES
    # =========================================================

    if (
        metrics[
            "total_operations"
        ]
        !=
        1
    ):

        fail(
            "Evaluation dashboard should contain exactly "
            "1 operation after the clean golden-path run."
        )

    passed(
        "Evaluation recorded exactly one rescue operation."
    )

    if (
        metrics[
            "completed_operations"
        ]
        !=
        1
    ):

        fail(
            "Evaluation did not record the rescue "
            "as completed."
        )

    passed(
        "Evaluation recorded the rescue as completed."
    )

    if abs(
        metrics[
            "confirmed_lbs"
        ]
        -
        confirmed_lbs
    ) > 0.01:

        fail(
            "Confirmed food metric does not match "
            "pantry-confirmed delivery stops."
        )

    passed(
        "Confirmed Food Rescued matches pantry receipts."
    )

    if abs(
        metrics[
            "total_donation_lbs"
        ]
        -
        donated_lbs
    ) > 0.01:

        fail(
            "Food Entering Operations does not match "
            "the golden rescue donation."
        )

    passed(
        "Food Entering Operations matches the donation."
    )

    # =========================================================
    # FULL VS PARTIAL RESCUE
    # =========================================================

    if (
        operation[
            "status"
        ]
        ==
        "completed"
    ):

        if abs(
            confirmed_lbs
            -
            donated_lbs
        ) > 0.01:

            fail(
                "Operation is marked fully completed, "
                "but confirmed food does not equal "
                "donated food."
            )

        passed(
            "Full rescue confirmed: all donated food arrived."
        )

        if (
            metrics[
                "confirmed_rescue_rate"
            ]
            is None
            or
            abs(
                metrics[
                    "confirmed_rescue_rate"
                ]
                -
                1.0
            ) > 0.0001
        ):

            fail(
                "Expected a 100% Confirmed Rescue Rate "
                "for this full golden-path rescue."
            )

        passed(
            "Confirmed Rescue Rate correctly shows 100%."
        )

        if (
            metrics[
                "completion_rate"
            ]
            is None
            or
            abs(
                metrics[
                    "completion_rate"
                ]
                -
                1.0
            ) > 0.0001
        ):

            fail(
                "Expected a 100% Operation Completion Rate."
            )

        passed(
            "Operation Completion Rate correctly shows 100%."
        )

        if abs(
            unrescued_lbs
        ) > 0.01:

            fail(
                "Full rescue should have 0 lbs unrescued."
            )

        passed(
            "Unrescued Food correctly equals 0 lbs."
        )

    else:

        print(
            "ℹ️ Golden path ended as a partial completion."
        )

        print(
            f"   Rescued: {rescued_lbs:.0f} lbs"
        )

        print(
            f"   Unrescued: {unrescued_lbs:.0f} lbs"
        )

    # =========================================================
    # RESCUE-BY-RESCUE TABLE
    # =========================================================

    rows = get_rescue_evaluation_rows()

    if len(rows) != 1:

        fail(
            "Rescue-by-Rescue table should contain "
            "exactly one row."
        )

    passed(
        "Rescue-by-Rescue evaluation table updated."
    )

    # =========================================================
    # FINAL RESULT
    # =========================================================

    print()
    print("=" * 70)
    print("✅ GOLDEN-PATH METRICS VERIFIED")
    print("=" * 70)

    print()
    print(
        "The Impact & Evaluation dashboard is correctly "
        "reflecting the completed rescue."
    )
    print()


if __name__ == "__main__":
    main()