from pathlib import Path

import pytest

import app.database.db as db
import app.optimizer.rescue_optimizer as optimizer

from app.operations.execution import (
    create_operation_from_plan,
    get_operation,
    start_operation,
    complete_delivery_stop,
    complete_operation,
    cancel_driver_and_replan,
)


# =========================================================
# TEST DATABASE SETUP
# =========================================================

@pytest.fixture
def test_db(
    tmp_path,
    monkeypatch,
):
    """
    Every test gets its own temporary SQLite database.

    This prevents tests from changing:
        data/rescuemesh.db
    """

    temporary_db = (
        tmp_path
        / "test_rescuemesh.db"
    )

    # db.get_connection() reads DB_PATH from the db module,
    # so changing it here redirects every execution-layer
    # database call to our temporary database.
    monkeypatch.setattr(
        db,
        "DB_PATH",
        temporary_db,
    )

    # Build all RescueMesh tables in the temporary DB.
    db.create_tables()

    seed_test_data()

    return temporary_db


# =========================================================
# TEST DATA
# =========================================================

def seed_test_data():
    """
    Create a small fake RescueMesh world.

    Drivers:
        James  -> 200 lbs
        Sarah  -> 150 lbs
        Daniel -> 100 lbs

    Pantries:
        Hope         -> 180 lbs free
        Neighborhood -> 40 lbs free
        Southside    -> 150 lbs free

    Donation:
        200 lbs produce
    """

    conn = db.get_connection()

    try:

        # =================================================
        # DONOR
        # =================================================

        conn.execute(
            """
            INSERT INTO donors (
                id,
                name,
                location,
                latitude,
                longitude
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                "Test GreenMart",
                "Test District",
                36.16,
                -86.78,
            ),
        )

        # =================================================
        # PANTRIES
        # =================================================

        conn.execute(
            """
            INSERT INTO pantries (
                id,
                name,
                location,
                latitude,
                longitude,
                max_capacity_lbs,
                available_capacity_lbs,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "Hope Community Pantry",
                "Central",
                36.15,
                -86.77,
                180,
                180,
                "available",
            ),
        )

        conn.execute(
            """
            INSERT INTO pantries (
                id,
                name,
                location,
                latitude,
                longitude,
                max_capacity_lbs,
                available_capacity_lbs,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "Neighborhood Relief Center",
                "South",
                36.12,
                -86.79,
                120,
                40,
                "available",
            ),
        )

        conn.execute(
            """
            INSERT INTO pantries (
                id,
                name,
                location,
                latitude,
                longitude,
                max_capacity_lbs,
                available_capacity_lbs,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                3,
                "Southside Outreach Center",
                "Southeast",
                36.11,
                -86.75,
                180,
                150,
                "available",
            ),
        )

        # =================================================
        # DRIVERS
        # =================================================

        conn.execute(
            """
            INSERT INTO drivers (
                id,
                name,
                location,
                latitude,
                longitude,
                capacity_lbs,
                available_from,
                available_until,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "James",
                "East",
                36.17,
                -86.74,
                200,
                "09:00",
                "13:00",
                "available",
            ),
        )

        conn.execute(
            """
            INSERT INTO drivers (
                id,
                name,
                location,
                latitude,
                longitude,
                capacity_lbs,
                available_from,
                available_until,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "Sarah",
                "Central",
                36.16,
                -86.78,
                150,
                "10:00",
                "14:00",
                "available",
            ),
        )

        conn.execute(
            """
            INSERT INTO drivers (
                id,
                name,
                location,
                latitude,
                longitude,
                capacity_lbs,
                available_from,
                available_until,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                3,
                "Daniel",
                "Central East",
                36.16,
                -86.77,
                100,
                "13:00",
                "18:00",
                "available",
            ),
        )

        # =================================================
        # DONATION
        # =================================================

        conn.execute(
            """
            INSERT INTO donations (
                id,
                donor_id,
                food_type,
                quantity_lbs,
                available_at,
                pickup_deadline,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "produce",
                200,
                "11:00",
                "14:00",
                "available",
            ),
        )

        # Optional pantry-needs records.
        #
        # The execution layer itself does not need these,
        # but they make the fake database realistic.

        for pantry_id, score in [
            (1, 0.95),
            (2, 0.99),
            (3, 0.97),
        ]:

            conn.execute(
                """
                INSERT INTO pantry_needs (
                    pantry_id,
                    food_type,
                    need_score
                )
                VALUES (?, ?, ?)
                """,
                (
                    pantry_id,
                    "produce",
                    score,
                ),
            )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# PLAN HELPERS
# =========================================================

def make_original_plan():
    """
    Original plan:

        James = 200 lbs

        Hope         = 10
        Neighborhood = 40
        Southside    = 150
    """

    return {
        "status": "optimal",

        "donation_id": 1,

        "rescued_lbs": 200.0,

        "unrescued_lbs": 0.0,

        "rescue_rate": 1.0,

        "drivers_used": 1,

        "total_distance_miles": 10.0,

        "driver_routes": [
            {
                "driver_id": 1,
                "driver_name": "James",

                "capacity_lbs": 200.0,

                "assigned_lbs": 200.0,

                "pickup_start": "11:00",
                "pickup_complete": "11:10",

                "route_complete": "11:45",

                "distance_miles": 10.0,

                "stops": [
                    {
                        "pantry_id": 1,
                        "pantry_name":
                            "Hope Community Pantry",

                        "quantity_lbs": 10.0,

                        "arrival_time": "11:15",
                    },
                    {
                        "pantry_id": 2,
                        "pantry_name":
                            "Neighborhood Relief Center",

                        "quantity_lbs": 40.0,

                        "arrival_time": "11:28",
                    },
                    {
                        "pantry_id": 3,
                        "pantry_name":
                            "Southside Outreach Center",

                        "quantity_lbs": 150.0,

                        "arrival_time": "11:40",
                    },
                ],
            }
        ],
    }


def make_replacement_plan():
    """
    Replacement after James cancels:

        Sarah  = 150
        Daniel = 50
    """

    return {
        "status": "optimal",

        "donation_id": 1,

        "rescued_lbs": 200.0,

        "unrescued_lbs": 0.0,

        "rescue_rate": 1.0,

        "drivers_used": 2,

        "total_distance_miles": 14.0,

        "driver_routes": [
            {
                "driver_id": 2,
                "driver_name": "Sarah",

                "capacity_lbs": 150.0,

                "assigned_lbs": 150.0,

                "pickup_start": "11:00",
                "pickup_complete": "11:10",

                "route_complete": "11:30",

                "distance_miles": 6.0,

                "stops": [
                    {
                        "pantry_id": 3,

                        "pantry_name":
                            "Southside Outreach Center",

                        "quantity_lbs":
                            150.0,

                        "arrival_time":
                            "11:25",
                    }
                ],
            },

            {
                "driver_id": 3,
                "driver_name": "Daniel",

                "capacity_lbs": 100.0,

                "assigned_lbs": 50.0,

                "pickup_start": "13:05",
                "pickup_complete": "13:15",

                "route_complete": "13:45",

                "distance_miles": 8.0,

                "stops": [
                    {
                        "pantry_id": 2,

                        "pantry_name":
                            "Neighborhood Relief Center",

                        "quantity_lbs":
                            40.0,

                        "arrival_time":
                            "13:30",
                    },
                    {
                        "pantry_id": 1,

                        "pantry_name":
                            "Hope Community Pantry",

                        "quantity_lbs":
                            10.0,

                        "arrival_time":
                            "13:40",
                    },
                ],
            },
        ],
    }


# =========================================================
# DATABASE QUERY HELPERS
# =========================================================

def get_driver_status(
    driver_id,
):
    conn = db.get_connection()

    try:

        row = conn.execute(
            """
            SELECT status
            FROM drivers
            WHERE id = ?
            """,
            (
                driver_id,
            ),
        ).fetchone()

        return row["status"]

    finally:

        conn.close()


def get_pantry_capacity(
    pantry_id,
):
    conn = db.get_connection()

    try:

        row = conn.execute(
            """
            SELECT available_capacity_lbs
            FROM pantries
            WHERE id = ?
            """,
            (
                pantry_id,
            ),
        ).fetchone()

        return row[
            "available_capacity_lbs"
        ]

    finally:

        conn.close()


def get_donation_status():
    conn = db.get_connection()

    try:

        row = conn.execute(
            """
            SELECT status
            FROM donations
            WHERE id = 1
            """
        ).fetchone()

        return row["status"]

    finally:

        conn.close()


# =========================================================
# TEST 1
# SAVING A PLAN DOES NOT RESERVE RESOURCES YET
# =========================================================

def test_create_operation_only_saves_plan(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "planned"
    )

    # Driver should still be available.
    assert (
        get_driver_status(1)
        ==
        "available"
    )

    # Pantry capacity should not change until operation
    # actually starts.
    assert get_pantry_capacity(1) == 180
    assert get_pantry_capacity(2) == 40
    assert get_pantry_capacity(3) == 150


# =========================================================
# TEST 2
# STARTING OPERATION RESERVES EVERYTHING
# =========================================================

def test_start_operation_reserves_resources(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "active"
    )

    # James is reserved.
    assert (
        get_driver_status(1)
        ==
        "busy"
    )

    # Pantry capacities are reserved.
    #
    # Hope:
    # 180 - 10 = 170
    assert get_pantry_capacity(1) == 170

    # Neighborhood:
    # 40 - 40 = 0
    assert get_pantry_capacity(2) == 0

    # Southside:
    # 150 - 150 = 0
    assert get_pantry_capacity(3) == 0

    assert (
        get_donation_status()
        ==
        "in_progress"
    )

    event_types = [
        event["event_type"]
        for event in operation["events"]
    ]

    assert (
        "RESOURCES_RESERVED"
        in event_types
    )

    assert (
        "OPERATION_STARTED"
        in event_types
    )


# =========================================================
# TEST 3
# OPERATION CANNOT START TWICE
# =========================================================

def test_start_operation_twice_does_not_double_reserve(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    with pytest.raises(
        ValueError
    ):
        start_operation(
            operation_id
        )

    # Capacity MUST NOT be deducted twice.
    assert get_pantry_capacity(1) == 170
    assert get_pantry_capacity(2) == 0
    assert get_pantry_capacity(3) == 0


# =========================================================
# TEST 4
# UNAVAILABLE DRIVER PREVENTS ACTIVATION
# =========================================================

def test_unavailable_driver_rolls_back_activation(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    conn = db.get_connection()

    try:

        conn.execute(
            """
            UPDATE drivers
            SET status = 'unavailable'
            WHERE id = 1
            """
        )

        conn.commit()

    finally:

        conn.close()

    with pytest.raises(
        ValueError
    ):
        start_operation(
            operation_id
        )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "planned"
    )

    assert (
        get_driver_status(1)
        ==
        "unavailable"
    )

    # Nothing was reserved.
    assert get_pantry_capacity(1) == 180
    assert get_pantry_capacity(2) == 40
    assert get_pantry_capacity(3) == 150


# =========================================================
# TEST 5
# INSUFFICIENT PANTRY CAPACITY ROLLS EVERYTHING BACK
# =========================================================

def test_insufficient_pantry_capacity_rolls_back(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    # Pretend Southside lost capacity after the plan
    # was created but before activation.

    conn = db.get_connection()

    try:

        conn.execute(
            """
            UPDATE pantries

            SET available_capacity_lbs = 100

            WHERE id = 3
            """
        )

        conn.commit()

    finally:

        conn.close()

    with pytest.raises(
        ValueError
    ):
        start_operation(
            operation_id
        )

    # James must NOT accidentally remain busy.
    assert (
        get_driver_status(1)
        ==
        "available"
    )

    # Other pantries must NOT have been partially reserved.
    assert get_pantry_capacity(1) == 180
    assert get_pantry_capacity(2) == 40

    # Only our simulated external change remains.
    assert get_pantry_capacity(3) == 100

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "planned"
    )


# =========================================================
# TEST 6
# CANNOT COMPLETE WHILE STOPS ARE PENDING
# =========================================================

def test_cannot_complete_operation_with_pending_stops(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    with pytest.raises(
        ValueError
    ):
        complete_operation(
            operation_id
        )

    assert (
        get_operation(
            operation_id
        )["status"]
        ==
        "active"
    )

    assert (
        get_driver_status(1)
        ==
        "busy"
    )


# =========================================================
# TEST 7
# COMPLETING ALL STOPS COMPLETES OPERATION
# =========================================================

def test_complete_operation_releases_driver_but_keeps_capacity_consumed(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    operation = get_operation(
        operation_id
    )

    # Complete every delivery.
    for route in operation[
        "driver_routes"
    ]:

        for stop in route[
            "stops"
        ]:

            complete_delivery_stop(
                stop["id"]
            )

    complete_operation(
        operation_id
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "completed"
    )

    # Driver becomes available again.
    assert (
        get_driver_status(1)
        ==
        "available"
    )

    # IMPORTANT:
    #
    # Pantry capacity remains consumed because food
    # was actually delivered.
    assert get_pantry_capacity(1) == 170
    assert get_pantry_capacity(2) == 0
    assert get_pantry_capacity(3) == 0

    assert (
        get_donation_status()
        ==
        "completed"
    )

    for route in operation[
        "driver_routes"
    ]:

        assert (
            route["status"]
            ==
            "completed"
        )

        for stop in route[
            "stops"
        ]:

            assert (
                stop["status"]
                ==
                "completed"
            )


# =========================================================
# TEST 8
# COMPLETED DELIVERY BLOCKS FULL REPLAN
# =========================================================

def test_completed_delivery_blocks_full_replan(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    operation = get_operation(
        operation_id
    )

    first_stop_id = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "id"
        ]
    )

    # One pantry already received food.
    complete_delivery_stop(
        first_stop_id
    )

    with pytest.raises(
        ValueError,
        match="Remaining-state replanning",
    ):
        cancel_driver_and_replan(
            operation_id,
            1,
        )

    # Operation remains active.
    assert (
        get_operation(
            operation_id
        )["status"]
        ==
        "active"
    )

    # James remains busy because we intentionally did
    # NOT release the operation.
    assert (
        get_driver_status(1)
        ==
        "busy"
    )


# =========================================================
# TEST 9
# DRIVER CANCELLATION AUTOMATICALLY REPLANS
# =========================================================

def test_driver_cancellation_replans_and_activates_replacement(
    test_db,
    monkeypatch,
):
    original_operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        original_operation_id
    )

    # Original reservations:
    assert get_driver_status(1) == "busy"
    assert get_pantry_capacity(1) == 170
    assert get_pantry_capacity(2) == 0
    assert get_pantry_capacity(3) == 0

    # =====================================================
    # FAKE RE-OPTIMIZATION
    # =====================================================

    def fake_optimizer(
        donation_id,
    ):
        """
        This function executes AFTER old resources have
        been released.

        That gives us a chance to verify that cancellation
        correctly restored the world BEFORE replanning.
        """

        assert donation_id == 1

        # James must already be unavailable.
        assert (
            get_driver_status(1)
            ==
            "unavailable"
        )

        # Pantry capacities must have been restored.
        assert get_pantry_capacity(1) == 180
        assert get_pantry_capacity(2) == 40
        assert get_pantry_capacity(3) == 150

        return make_replacement_plan()

    monkeypatch.setattr(
        optimizer,
        "optimize_rescue_plan",
        fake_optimizer,
    )

    result = (
        cancel_driver_and_replan(
            original_operation_id,
            1,
        )
    )

    assert (
        result["status"]
        ==
        "replanned"
    )

    new_operation_id = (
        result[
            "new_operation_id"
        ]
    )

    # =====================================================
    # OLD OPERATION
    # =====================================================

    old_operation = get_operation(
        original_operation_id
    )

    assert (
        old_operation["status"]
        ==
        "superseded"
    )

    assert (
        old_operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "cancelled"
    )

    for stop in (
        old_operation[
            "driver_routes"
        ][0][
            "stops"
        ]
    ):

        assert (
            stop["status"]
            ==
            "cancelled"
        )

    # James must remain unavailable so the optimizer
    # cannot immediately assign him again.
    assert (
        get_driver_status(1)
        ==
        "unavailable"
    )

    # =====================================================
    # NEW OPERATION
    # =====================================================

    new_operation = get_operation(
        new_operation_id
    )

    assert (
        new_operation["status"]
        ==
        "active"
    )

    # Replacement drivers are now busy.
    assert (
        get_driver_status(2)
        ==
        "busy"
    )

    assert (
        get_driver_status(3)
        ==
        "busy"
    )

    # The replacement operation reserved the pantry
    # capacity again.
    assert get_pantry_capacity(1) == 170
    assert get_pantry_capacity(2) == 0
    assert get_pantry_capacity(3) == 0

    # Full 200 lbs still rescued.
    assert (
        new_operation[
            "rescued_lbs"
        ]
        ==
        200
    )

    # =====================================================
    # EVENT HISTORY
    # =====================================================

    old_events = [
        event["event_type"]
        for event in old_operation[
            "events"
        ]
    ]

    assert (
        "DRIVER_CANCELLED"
        in old_events
    )

    assert (
        "RESOURCES_RELEASED"
        in old_events
    )

    assert (
        "REPLAN_CREATED"
        in old_events
    )

    new_events = [
        event["event_type"]
        for event in new_operation[
            "events"
        ]
    ]

    assert (
        "REPLAN_FROM_OPERATION"
        in new_events
    )


# =========================================================
# TEST 10
# WRONG DRIVER CANNOT CANCEL OPERATION
# =========================================================

def test_driver_not_assigned_to_operation_cannot_cancel(
    test_db,
):
    operation_id = (
        create_operation_from_plan(
            make_original_plan()
        )
    )

    start_operation(
        operation_id
    )

    # Sarah (driver 2) is not part of this operation.
    with pytest.raises(
        ValueError
    ):
        cancel_driver_and_replan(
            operation_id,
            2,
        )

    # Nothing should change.
    assert (
        get_operation(
            operation_id
        )["status"]
        ==
        "active"
    )

    assert (
        get_driver_status(1)
        ==
        "busy"
    )

    assert (
        get_driver_status(2)
        ==
        "available"
    )


# =========================================================
# TEST 11
# NON-OPTIMAL PLAN CANNOT BECOME OPERATION
# =========================================================

def test_non_optimal_plan_is_rejected(
    test_db,
):
    bad_plan = {
        "status":
            "no_feasible_plan"
    }

    with pytest.raises(
        ValueError
    ):
        create_operation_from_plan(
            bad_plan
        )