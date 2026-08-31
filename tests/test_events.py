import pytest

import app.database.db as db
import app.optimizer.rescue_optimizer as optimizer
import app.events.processor as processor

from app.operations.execution import (
    create_operation_from_plan,
    get_operation,
    start_operation,
)


# =========================================================
# TEMP DATABASE
# =========================================================

@pytest.fixture
def event_db(
    tmp_path,
    monkeypatch,
):
    temporary_db = (
        tmp_path
        / "events_test.db"
    )

    monkeypatch.setattr(
        db,
        "DB_PATH",
        temporary_db,
    )

    db.create_tables()

    seed_event_world()

    return temporary_db


# =========================================================
# SEED SMALL WORLD
# =========================================================

def seed_event_world():

    conn = db.get_connection()

    try:

        # Donor

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
                "Test Donor",
                "Central",
                36.16,
                -86.78,
            ),
        )

        # Pantry

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
                "Test Pantry",
                "Central",
                36.15,
                -86.77,
                180,
                180,
                "available",
            ),
        )

        # Original driver

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
                100,
                "09:00",
                "15:00",
                "available",
            ),
        )

        # Replacement driver

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
                100,
                "09:00",
                "15:00",
                "available",
            ),
        )

        # Donation

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
                50,
                "10:00",
                "12:00",
                "available",
            ),
        )

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
                1,
                "produce",
                0.95,
            ),
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# PLAN HELPERS
# =========================================================

def original_plan():

    return {
        "status":
            "optimal",

        "donation_id":
            1,

        "rescued_lbs":
            50.0,

        "unrescued_lbs":
            0.0,

        "rescue_rate":
            1.0,

        "drivers_used":
            1,

        "total_distance_miles":
            5.0,

        "driver_routes": [
            {
                "driver_id":
                    1,

                "driver_name":
                    "James",

                "capacity_lbs":
                    100.0,

                "assigned_lbs":
                    50.0,

                "pickup_start":
                    "10:00",

                "pickup_complete":
                    "10:10",

                "route_complete":
                    "10:25",

                "distance_miles":
                    5.0,

                "stops": [
                    {
                        "pantry_id":
                            1,

                        "pantry_name":
                            "Test Pantry",

                        "quantity_lbs":
                            50.0,

                        "arrival_time":
                            "10:20",
                    }
                ],
            }
        ],
    }


def replacement_plan(
    quantity=50.0,
):

    unrescued = (
        50.0
        -
        quantity
    )

    return {
        "status":
            "optimal",

        "donation_id":
            1,

        "rescued_lbs":
            quantity,

        "unrescued_lbs":
            unrescued,

        "rescue_rate":
            quantity
            / 50.0,

        "drivers_used":
            1,

        "total_distance_miles":
            6.0,

        "driver_routes": [
            {
                "driver_id":
                    2,

                "driver_name":
                    "Sarah",

                "capacity_lbs":
                    100.0,

                "assigned_lbs":
                    quantity,

                "pickup_start":
                    "10:00",

                "pickup_complete":
                    "10:10",

                "route_complete":
                    "10:30",

                "distance_miles":
                    6.0,

                "stops": [
                    {
                        "pantry_id":
                            1,

                        "pantry_name":
                            "Test Pantry",

                        "quantity_lbs":
                            quantity,

                        "arrival_time":
                            "10:25",
                    }
                ],
            }
        ],
    }


def create_active_operation():

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    start_operation(
        operation_id
    )

    return operation_id


# =========================================================
# QUERY HELPERS
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

        return row[
            "status"
        ]

    finally:

        conn.close()


def get_pantry():

    conn = db.get_connection()

    try:

        return dict(
            conn.execute(
                """
                SELECT *

                FROM pantries

                WHERE id = 1
                """
            ).fetchone()
        )

    finally:

        conn.close()


# =========================================================
# TEST 1
# EVENT TYPES EXIST
# =========================================================

def test_supported_event_types():

    assert (
        "DRIVER_CANCELLED"
        in
        processor.SUPPORTED_EVENT_TYPES
    )

    assert (
        "DELIVERY_COMPLETED"
        in
        processor.SUPPORTED_EVENT_TYPES
    )

    assert (
        "PANTRY_CAPACITY_CHANGED"
        in
        processor.SUPPORTED_EVENT_TYPES
    )


# =========================================================
# TEST 2
# UNSUPPORTED EVENT FAILS
# =========================================================

def test_unsupported_event_records_failure(
    event_db,
):

    operation_id = (
        create_active_operation()
    )

    with pytest.raises(
        ValueError
    ):

        processor.process_event(
            operation_id,
            "ALIEN_INVASION",
            {},
        )

    operation = get_operation(
        operation_id
    )

    event_types = [
        event[
            "event_type"
        ]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "EVENT_FAILED"
        in event_types
    )


# =========================================================
# TEST 3
# BAD PAYLOAD RECORDS EVENT_FAILED
# =========================================================

def test_missing_driver_id_records_failure(
    event_db,
):

    operation_id = (
        create_active_operation()
    )

    with pytest.raises(
        ValueError
    ):

        processor.process_event(
            operation_id,
            "DRIVER_CANCELLED",
            {},
        )

    operation = get_operation(
        operation_id
    )

    event_types = [
        event[
            "event_type"
        ]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "EVENT_FAILED"
        in event_types
    )


# =========================================================
# TEST 4
# DELIVERY EVENT COMPLETES LAST STOP + OPERATION
# =========================================================

def test_driver_delivery_waits_for_pantry_confirmation(
    event_db,
):
    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    processor.process_event(
        operation_id,
        "DRIVER_ACCEPTED",
        {
            "driver_id": 1
        },
    )

    processor.process_event(
        operation_id,
        "PICKUP_COMPLETED",
        {
            "driver_id": 1
        },
    )

    operation = get_operation(
        operation_id
    )

    stop_id = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "id"
        ]
    )

    result = (
        processor.process_event(
            operation_id,
            "DELIVERY_COMPLETED",
            {
                "stop_id": stop_id
            },
        )
    )

    assert (
        result["status"]
        ==
        "processed"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "active"
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "status"
        ]
        ==
        "driver_delivered"
    )

    # Driver remains busy until pantry confirms.
    assert (
        get_driver_status(1)
        ==
        "busy"
    )
    
    
#pantry received test

def test_pantry_received_completes_final_delivery(
    event_db,
):
    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    processor.process_event(
        operation_id,
        "DRIVER_ACCEPTED",
        {
            "driver_id": 1
        },
    )

    processor.process_event(
        operation_id,
        "PICKUP_COMPLETED",
        {
            "driver_id": 1
        },
    )

    operation = get_operation(
        operation_id
    )

    stop_id = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "id"
        ]
    )

    processor.process_event(
        operation_id,
        "DELIVERY_COMPLETED",
        {
            "stop_id": stop_id
        },
    )

    result = (
        processor.process_event(
            operation_id,
            "PANTRY_RECEIVED",
            {
                "stop_id": stop_id
            },
        )
    )

    assert (
        result["result"][
            "operation_completed"
        ]
        is True
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "completed"
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "status"
        ]
        ==
        "completed"
    )

    assert (
        get_driver_status(1)
        ==
        "available"
    )

    event_types = [
        event["event_type"]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "PANTRY_RECEIVED"
        in event_types
    )

    assert (
        "OPERATION_COMPLETED"
        in event_types
    )
    
# DELIVERY_FAILED test


def test_delivery_failed_requires_in_transit_replan(
    event_db,
):
    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    processor.process_event(
        operation_id,
        "DRIVER_ACCEPTED",
        {
            "driver_id": 1
        },
    )

    processor.process_event(
        operation_id,
        "PICKUP_COMPLETED",
        {
            "driver_id": 1
        },
    )

    operation = get_operation(
        operation_id
    )

    stop_id = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "id"
        ]
    )

    result = (
        processor.process_event(
            operation_id,
            "DELIVERY_FAILED",
            {
                "stop_id":
                    stop_id,

                "reason":
                    "pantry unable to receive food",
            },
        )
    )

    assert (
        result["result"][
            "status"
        ]
        ==
        "requires_in_transit_replan"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "needs_replan"
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ][0][
            "status"
        ]
        ==
        "failed"
    )

    # Food is still physically with James.
    assert (
        get_driver_status(1)
        ==
        "busy"
    )
    
# donation expired test 


def test_planned_donation_can_expire(
    event_db,
):
    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    result = (
        processor.process_event(
            operation_id,
            "DONATION_EXPIRED",
            {
                "donation_id": 1
            },
        )
    )

    assert (
        result["result"][
            "status"
        ]
        ==
        "expired"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "cancelled"
    )

    conn = db.get_connection()

    try:
        donation = conn.execute(
            """
            SELECT status

            FROM donations

            WHERE id = 1
            """
        ).fetchone()

    finally:
        conn.close()

    assert (
        donation["status"]
        ==
        "expired"
    )

    # Driver never became busy.
    assert (
        get_driver_status(1)
        ==
        "available"
    )
    
# pantry closed test 

def test_pantry_closed_marks_pantry_unavailable(
    event_db,
    monkeypatch,
):
    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    processor.process_event(
        operation_id,
        "DRIVER_ACCEPTED",
        {
            "driver_id": 1
        },
    )

    monkeypatch.setattr(
        optimizer,
        "optimize_rescue_plan",
        lambda donation_id: {
            "status":
                "no_compatible_pantry",

            "donation_id":
                donation_id,
        },
    )

    result = (
        processor.process_event(
            operation_id,
            "PANTRY_CLOSED",
            {
                "pantry_id": 1
            },
        )
    )

    assert (
        result["result"][
            "status"
        ]
        ==
        "replan_failed"
    )

    conn = db.get_connection()

    try:
        pantry = conn.execute(
            """
            SELECT status

            FROM pantries

            WHERE id = 1
            """
        ).fetchone()

    finally:
        conn.close()

    assert (
        pantry["status"]
        ==
        "unavailable"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "needs_replan"
    )

    # James was released because pickup had not occurred.
    assert (
        get_driver_status(1)
        ==
        "available"
    )

# =========================================================
# TEST 5
# CAPACITY CHANGE THAT STILL FITS
# =========================================================

def test_pantry_capacity_change_without_replan(
    event_db,
):

    operation_id = (
        create_active_operation()
    )

    # Original:
    #
    # max = 180
    # reserved = 50
    # available after reservation = 130
    #
    # New max = 160
    #
    # reservation still fits.

    result = (
        processor.process_event(
            operation_id,

            "PANTRY_CAPACITY_CHANGED",

            {
                "pantry_id":
                    1,

                "new_max_capacity_lbs":
                    160,
            },
        )
    )

    assert (
        result[
            "status"
        ]
        ==
        "processed"
    )

    handler_result = (
        result[
            "result"
        ]
    )

    assert (
        handler_result[
            "replanned"
        ]
        is False
    )

    pantry = (
        get_pantry()
    )

    assert (
        pantry[
            "max_capacity_lbs"
        ]
        ==
        160
    )

    # No pre-existing occupancy:
    #
    # 160 - 50 reserved = 110 free.

    assert (
        pantry[
            "available_capacity_lbs"
        ]
        ==
        110
    )

    assert (
        get_operation(
            operation_id
        )[
            "status"
        ]
        ==
        "active"
    )


# =========================================================
# TEST 6
# DRIVER CANCELLED EVENT REPLANS
# =========================================================

def test_driver_cancelled_event_replans(
    event_db,
    monkeypatch,
):

    operation_id = (
        create_active_operation()
    )

    # We know execution layer itself has already been
    # thoroughly tested.
    #
    # Here the important part is proving the EVENT reaches
    # the cancellation/replan behavior.

    monkeypatch.setattr(
        optimizer,

        "optimize_rescue_plan",

        lambda donation_id:
            replacement_plan(
                50
            ),
    )

    result = (
        processor.process_event(
            operation_id,

            "DRIVER_CANCELLED",

            {
                "driver_id":
                    1
            },
        )
    )

    assert (
        result[
            "status"
        ]
        ==
        "processed"
    )

    handler_result = (
        result[
            "result"
        ]
    )

    assert (
        handler_result[
            "status"
        ]
        ==
        "replanned"
    )

    old_operation = (
        get_operation(
            operation_id
        )
    )

    assert (
        old_operation[
            "status"
        ]
        ==
        "superseded"
    )

    assert (
        get_driver_status(1)
        ==
        "unavailable"
    )

    new_operation = (
        get_operation(
            handler_result[
                "new_operation_id"
            ]
        )
    )

    assert (
        new_operation[
            "status"
        ]
        ==
        "active"
    )

    assert (
        get_driver_status(2)
        ==
        "busy"
    )

    old_event_types = [
        event[
            "event_type"
        ]

        for event in old_operation[
            "events"
        ]
    ]

    assert (
        "EVENT_PROCESSED"
        in old_event_types
    )


# =========================================================
# TEST 7
# PANTRY CAPACITY DROP TRIGGERS REPLAN
# =========================================================

def test_pantry_capacity_drop_triggers_replan(
    event_db,
    monkeypatch,
):

    operation_id = (
        create_active_operation()
    )

    # Original reservation:
    # 50 lbs
    #
    # New TOTAL pantry capacity:
    # 30 lbs
    #
    # Old operation can no longer fit.

    monkeypatch.setattr(
        optimizer,

        "optimize_rescue_plan",

        lambda donation_id:
            replacement_plan(
                30
            ),
    )

    result = (
        processor.process_event(
            operation_id,

            "PANTRY_CAPACITY_CHANGED",

            {
                "pantry_id":
                    1,

                "new_max_capacity_lbs":
                    30,
            },
        )
    )

    assert (
        result[
            "status"
        ]
        ==
        "processed"
    )

    handler_result = (
        result[
            "result"
        ]
    )

    assert (
        handler_result[
            "status"
        ]
        ==
        "replanned"
    )

    old_operation = (
        get_operation(
            operation_id
        )
    )

    assert (
        old_operation[
            "status"
        ]
        ==
        "superseded"
    )

    new_operation = (
        get_operation(
            handler_result[
                "new_operation_id"
            ]
        )
    )

    assert (
        new_operation[
            "status"
        ]
        ==
        "active"
    )

    assert (
        new_operation[
            "rescued_lbs"
        ]
        ==
        30
    )

    pantry = (
        get_pantry()
    )

    assert (
        pantry[
            "max_capacity_lbs"
        ]
        ==
        30
    )

    # Replacement plan reserved all 30 lbs.

    assert (
        pantry[
            "available_capacity_lbs"
        ]
        ==
        0
    )
    
# donation created
    
def test_donation_created_builds_planned_operation(
    event_db,
    monkeypatch,
):

    monkeypatch.setattr(
        optimizer,
        "optimize_rescue_plan",
        lambda donation_id:
            original_plan(),
    )

    result = (
        processor.process_event(
            None,

            "DONATION_CREATED",

            {
                "donation_id":
                    1
            },
        )
    )

    assert (
        result["status"]
        ==
        "processed"
    )

    operation_id = (
        result[
            "result"
        ][
            "operation_id"
        ]
    )

    operation = get_operation(
        operation_id
    )

    # Operation exists, but is not active yet.
    assert (
        operation["status"]
        ==
        "planned"
    )

    # Driver hasn't accepted yet.
    assert (
        operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "assigned"
    )

    # Driver should NOT be busy yet.
    assert (
        get_driver_status(1)
        ==
        "available"
    )

    event_types = [
        event["event_type"]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "DONATION_CREATED"
        in event_types
    )

    assert (
        "EVENT_PROCESSED"
        in event_types
    ) 
    
# driver accepted

def test_driver_acceptance_starts_single_driver_operation(
    event_db,
):

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    result = (
        processor.process_event(
            operation_id,

            "DRIVER_ACCEPTED",

            {
                "driver_id":
                    1
            },
        )
    )

    assert (
        result["status"]
        ==
        "processed"
    )

    assert (
        result[
            "result"
        ][
            "status"
        ]
        ==
        "operation_started"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "active"
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "active"
    )

    assert (
        get_driver_status(1)
        ==
        "busy"
    )

    event_types = [
        event["event_type"]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "DRIVER_ACCEPTED"
        in event_types
    )

    assert (
        "OPERATION_STARTED"
        in event_types
    )
    
# pickup completed

def test_pickup_completed_marks_route_picked_up(
    event_db,
):

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    # Driver accepts, which starts the one-driver operation.

    processor.process_event(
        operation_id,

        "DRIVER_ACCEPTED",

        {
            "driver_id":
                1
        },
    )

    result = (
        processor.process_event(
            operation_id,

            "PICKUP_COMPLETED",

            {
                "driver_id":
                    1
            },
        )
    )

    assert (
        result["status"]
        ==
        "processed"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "picked_up"
    )

    assert (
        get_driver_status(1)
        ==
        "busy"
    )

    event_types = [
        event["event_type"]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "PICKUP_COMPLETED"
        in event_types
    )
    
# cannot pick up before operation starts

def test_pickup_before_driver_acceptance_fails(
    event_db,
):

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    with pytest.raises(
        ValueError
    ):

        processor.process_event(
            operation_id,

            "PICKUP_COMPLETED",

            {
                "driver_id":
                    1
            },
        )

    operation = get_operation(
        operation_id
    )

    assert (
        operation["status"]
        ==
        "planned"
    )

    event_types = [
        event["event_type"]

        for event in operation[
            "events"
        ]
    ]

    assert (
        "EVENT_FAILED"
        in event_types
    )
    
# cancellation after pickup blocked

def test_full_driver_replan_blocked_after_pickup(
    event_db,
):

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    processor.process_event(
        operation_id,

        "DRIVER_ACCEPTED",

        {
            "driver_id":
                1
        },
    )

    processor.process_event(
        operation_id,

        "PICKUP_COMPLETED",

        {
            "driver_id":
                1
        },
    )

    with pytest.raises(
        ValueError,
        match="In-transit replanning",
    ):

        processor.process_event(
            operation_id,

            "DRIVER_CANCELLED",

            {
                "driver_id":
                    1
            },
        )

    operation = get_operation(
        operation_id
    )

    # Nothing should have been reset.
    assert (
        operation["status"]
        ==
        "active"
    )

    assert (
        operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "picked_up"
    )

    assert (
        get_driver_status(1)
        ==
        "busy"
    )
    
