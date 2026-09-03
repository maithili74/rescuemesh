import pytest

import app.database.db as db
import app.optimizer.in_transit_optimizer as in_transit_optimizer

from app.operations.execution import (
    complete_pickup,
    confirm_pantry_received,
    create_operation_from_plan,
    get_operation,
    mark_delivery_by_driver,
    replan_in_transit,
    start_operation,
)
from app.escalation.manager import (
    approve_escalation,
    create_escalation,
    get_escalation,
    get_pending_escalations,
    reject_escalation,
)
# =========================================================
# TEST DATABASE
# =========================================================

@pytest.fixture
def in_transit_db(
    tmp_path,
    monkeypatch,
):
    temporary_db = (
        tmp_path
        /
        "in_transit_test.db"
    )

    monkeypatch.setattr(
        db,
        "DB_PATH",
        temporary_db,
    )

    db.create_tables()

    seed_world()

    return temporary_db


# =========================================================
# TEST WORLD
# =========================================================

def seed_world():

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
                "GreenMart",
                "Central",
                36.16,
                -86.78,
            ),
        )

        # Hope

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
                "Hope",
                "North",
                36.15,
                -86.77,
                100,
                100,
                "available",
            ),
        )

        # Southside

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
                "Southside",
                "South",
                36.11,
                -86.75,
                150,
                150,
                "available",
            ),
        )

        # Backup pantry

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
                "Community Care",
                "East",
                36.14,
                -86.73,
                200,
                200,
                "available",
            ),
        )

        for pantry_id, need_score in [
            (1, 0.95),
            (2, 0.97),
            (3, 0.90),
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
                    need_score,
                ),
            )

        # Driver

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
                "Central",
                36.16,
                -86.78,
                200,
                "09:00",
                "17:00",
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
                200,
                "11:00",
                "14:00",
                "available",
            ),
        )

        conn.commit()

    finally:

        conn.close()


# =========================================================
# ORIGINAL PLAN
# =========================================================

def original_plan():

    return {
        "status":
            "optimal",

        "donation_id":
            1,

        "rescued_lbs":
            200.0,

        "unrescued_lbs":
            0.0,

        "rescue_rate":
            1.0,

        "drivers_used":
            1,

        "total_distance_miles":
            10.0,

        "driver_routes": [
            {
                "driver_id":
                    1,

                "driver_name":
                    "James",

                "capacity_lbs":
                    200.0,

                "assigned_lbs":
                    200.0,

                "pickup_start":
                    "11:00",

                "pickup_complete":
                    "11:10",

                "route_complete":
                    "12:00",

                "distance_miles":
                    10.0,

                "stops": [
                    {
                        "pantry_id":
                            1,

                        "pantry_name":
                            "Hope",

                        "quantity_lbs":
                            50.0,

                        "arrival_time":
                            "11:25",
                    },
                    {
                        "pantry_id":
                            2,

                        "pantry_name":
                            "Southside",

                        "quantity_lbs":
                            150.0,

                        "arrival_time":
                            "11:45",
                    },
                ],
            }
        ],
    }


def activate_and_pick_up():

    operation_id = (
        create_operation_from_plan(
            original_plan()
        )
    )

    start_operation(
        operation_id
    )

    complete_pickup(
        operation_id,
        1,
    )

    return operation_id


def complete_first_delivery(
    operation_id,
):

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

    mark_delivery_by_driver(
        operation_id,
        first_stop_id,
    )

    confirm_pantry_received(
        operation_id,
        first_stop_id,
    )


# =========================================================
# TEST 1
# COMPLETED WORK MUST SURVIVE REPLAN
# =========================================================

def test_in_transit_replan_preserves_completed_delivery(
    in_transit_db,
    monkeypatch,
):

    operation_id = (
        activate_and_pick_up()
    )

    complete_first_delivery(
        operation_id
    )

    def fake_optimizer(
        state,
    ):

        assert (
            state[
                "remaining_lbs"
            ]
            ==
            150
        )

        assert (
            2
            in
            state[
                "excluded_pantry_ids"
            ]
        )

        return {
            "status":
                "optimal",

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        150.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        150.0,

                    "arrival_time":
                        "12:05",
                }
            ],

            "route_complete":
                "12:10",

            "remaining_distance_miles":
                4.0,
        }

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",
        fake_optimizer,
    )

    result = replan_in_transit(
        operation_id=
            operation_id,

        driver_id=
            1,

        reason=
            "pantry_closed",

        excluded_pantry_ids=[
            2
        ],
    )

    assert (
        result[
            "status"
        ]
        ==
        "in_transit_replanned"
    )

    operation = get_operation(
        operation_id
    )

    stops = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ]
    )

    # Hope's completed 50 lb is historical truth.
    assert any(
        stop[
            "pantry_id"
        ]
        ==
        1
        and
        stop[
            "quantity_lbs"
        ]
        ==
        50
        and
        stop[
            "status"
        ]
        ==
        "completed"

        for stop in stops
    )

    # Old Southside plan must be cancelled.
    assert any(
        stop[
            "pantry_id"
        ]
        ==
        2
        and
        stop[
            "status"
        ]
        ==
        "cancelled"

        for stop in stops
    )

    # Replacement destination added.
    assert any(
        stop[
            "pantry_id"
        ]
        ==
        3
        and
        stop[
            "quantity_lbs"
        ]
        ==
        150
        and
        stop[
            "status"
        ]
        ==
        "pending"

        for stop in stops
    )

    # Same physical operation continues.
    assert (
        operation[
            "status"
        ]
        ==
        "active"
    )

    # Same driver still physically has the remaining food.
    assert (
        operation[
            "driver_routes"
        ][0][
            "status"
        ]
        ==
        "picked_up"
    )


# =========================================================
# TEST 2
# RELEASE ONLY UNDELIVERED CAPACITY
# =========================================================

def test_in_transit_replan_releases_only_unused_capacity(
    in_transit_db,
    monkeypatch,
):

    operation_id = (
        activate_and_pick_up()
    )

    complete_first_delivery(
        operation_id
    )

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",

        lambda state: {
            "status":
                "optimal",

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        150.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        150.0,

                    "arrival_time":
                        "12:05",
                }
            ],

            "route_complete":
                "12:10",

            "remaining_distance_miles":
                4.0,
        },
    )

    replan_in_transit(
        operation_id,
        1,
        "pantry_closed",
        [
            2
        ],
    )

    conn = db.get_connection()

    try:

        hope = conn.execute(
            """
            SELECT available_capacity_lbs

            FROM pantries

            WHERE id = 1
            """
        ).fetchone()

        southside = conn.execute(
            """
            SELECT available_capacity_lbs

            FROM pantries

            WHERE id = 2
            """
        ).fetchone()

        community = conn.execute(
            """
            SELECT available_capacity_lbs

            FROM pantries

            WHERE id = 3
            """
        ).fetchone()

    finally:

        conn.close()

    # Hope:
    # started 100
    # received 50
    # MUST stay consumed.

    assert (
        hope[
            "available_capacity_lbs"
        ]
        ==
        50
    )

    # Southside:
    # old unused 150 reservation released.

    assert (
        southside[
            "available_capacity_lbs"
        ]
        ==
        150
    )

    # Community Care:
    # 200 - new 150 reservation = 50.

    assert (
        community[
            "available_capacity_lbs"
        ]
        ==
        50
    )


# =========================================================
# TEST 3
# PARTIAL RECOVERY SHOULD NOT SILENTLY EXECUTE
# =========================================================

def test_partial_in_transit_plan_creates_human_escalation(
    in_transit_db,
    monkeypatch,
):
    operation_id = (
        activate_and_pick_up()
    )

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",

        lambda state: {
            "status":
                "partial_only",

            "operation_id":
                operation_id,

            "route_id":
                state[
                    "route_id"
                ],

            "driver_id":
                1,

            "remaining_lbs":
                state[
                    "remaining_lbs"
                ],

            "rescued_lbs":
                120.0,

            "unrescued_lbs":
                80.0,

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,

                    "arrival_time":
                        "12:00",
                }
            ],

            "route_complete":
                "12:05",

            "remaining_distance_miles":
                4.0,
        },
    )

    result = replan_in_transit(
        operation_id=
            operation_id,

        driver_id=
            1,

        reason=
            "delivery_failed",
    )

    # =====================================================
    # AUTO RECOVERY COULD NOT SAVE EVERYTHING
    # SO THE OPERATION SHOULD NOW WAIT FOR A HUMAN
    # =====================================================

    assert (
        result[
            "status"
        ]
        ==
        "awaiting_human"
    )

    # =====================================================
    # A REAL ESCALATION RECORD SHOULD EXIST
    # =====================================================

    escalation = (
        result[
            "escalation"
        ]
    )

    assert (
        escalation[
            "status"
        ]
        ==
        "pending"
    )

    assert (
        escalation[
            "escalation_type"
        ]
        ==
        "partial_in_transit_rescue"
    )

    assert (
        escalation[
            "recommended_action"
        ]
        ==
        "proceed_partial"
    )

    # =====================================================
    # THE PARTIAL PLAN SHOULD STILL BE PRESERVED
    # =====================================================

    assert (
        result[
            "plan"
        ][
            "rescued_lbs"
        ]
        ==
        120
    )

    assert (
        result[
            "plan"
        ][
            "unrescued_lbs"
        ]
        ==
        80
    )

    assert (
        len(
            result[
                "plan"
            ][
                "stops"
            ]
        )
        ==
        1
    )

    assert (
        result[
            "plan"
        ][
            "stops"
        ][0][
            "pantry_id"
        ]
        ==
        3
    )

    # =====================================================
    # OPERATION SHOULD BE PAUSED FOR HUMAN DECISION
    # =====================================================

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "awaiting_human"
    )
    
def test_full_safe_replan_does_not_create_human_escalation(
    in_transit_db,
    monkeypatch,
):
    operation_id = (
        activate_and_pick_up()
    )

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",

        lambda state: {
            "status":
                "optimal",

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        200.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        200.0,

                    "arrival_time":
                        "12:00",
                }
            ],

            "route_complete":
                "12:05",

            "remaining_distance_miles":
                4.0,
        },
    )

    result = replan_in_transit(
        operation_id=
            operation_id,

        driver_id=
            1,

        reason=
            "pantry_closed",
    )

    assert (
        result[
            "status"
        ]
        ==
        "in_transit_replanned"
    )

    conn = db.get_connection()

    try:
        count = conn.execute(
            """
            SELECT COUNT(*)

            FROM escalations

            WHERE operation_id = ?
            """,
            (
                operation_id,
            ),
        ).fetchone()[0]

    finally:
        conn.close()

    # THE MOST IMPORTANT HUMAN-ESCALATION RULE:
    #
    # If RescueMesh can safely fix the problem itself,
    # a human must never be bothered.

    assert count == 0
    
def test_partial_replan_creates_real_human_escalation(
    in_transit_db,
    monkeypatch,
):
    operation_id = (
        activate_and_pick_up()
    )

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",

        lambda state: {
            "status":
                "partial_only",

            "operation_id":
                operation_id,

            "route_id":
                state[
                    "route_id"
                ],

            "driver_id":
                1,

            "remaining_lbs":
                200.0,

            "rescued_lbs":
                120.0,

            "unrescued_lbs":
                80.0,

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,

                    "arrival_time":
                        "12:00",
                }
            ],

            "route_complete":
                "12:05",

            "remaining_distance_miles":
                4.0,
        },
    )

    result = replan_in_transit(
        operation_id=
            operation_id,

        driver_id=
            1,

        reason=
            "delivery_failed",
    )

    assert (
        result[
            "status"
        ]
        ==
        "awaiting_human"
    )

    escalation = (
        result[
            "escalation"
        ]
    )

    assert (
        escalation[
            "status"
        ]
        ==
        "pending"
    )

    assert (
        escalation[
            "escalation_type"
        ]
        ==
        "partial_in_transit_rescue"
    )

    assert (
        escalation[
            "recommended_action"
        ]
        ==
        "proceed_partial"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "awaiting_human"
    )
    
def test_human_can_approve_partial_rescue(
    in_transit_db,
    monkeypatch,
):
    operation_id = (
        activate_and_pick_up()
    )

    monkeypatch.setattr(
        in_transit_optimizer,
        "optimize_in_transit_route",

        lambda state: {
            "status":
                "partial_only",

            "operation_id":
                operation_id,

            "route_id":
                state[
                    "route_id"
                ],

            "driver_id":
                1,

            "remaining_lbs":
                200.0,

            "rescued_lbs":
                120.0,

            "unrescued_lbs":
                80.0,

            "assignments": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,
                }
            ],

            "stops": [
                {
                    "pantry_id":
                        3,

                    "pantry_name":
                        "Community Care",

                    "quantity_lbs":
                        120.0,

                    "arrival_time":
                        "12:00",
                }
            ],

            "route_complete":
                "12:05",

            "remaining_distance_miles":
                4.0,
        },
    )

    result = replan_in_transit(
        operation_id=
            operation_id,

        driver_id=
            1,

        reason=
            "delivery_failed",
    )

    escalation_id = (
        result[
            "escalation"
        ][
            "id"
        ]
    )

    resolved = approve_escalation(
        escalation_id=
            escalation_id,

        option_id=
            "proceed_partial",

        notes=
            "Proceed with the feasible rescue.",
    )

    assert (
        resolved[
            "status"
        ]
        ==
        "approved"
    )

    assert (
        resolved[
            "decision"
        ]
        ==
        "proceed_partial"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "active"
    )

    assert (
        operation[
            "unrescued_lbs"
        ]
        ==
        80
    )
    
# duplicate pending escalation is prevented
    
def test_duplicate_pending_escalation_is_prevented(
    in_transit_db,
):
    operation_id = (
        activate_and_pick_up()
    )

    first = create_escalation(
        operation_id=
            operation_id,

        escalation_type=
            "driver_failure_after_pickup",

        reason=
            "Driver cannot continue after pickup.",

        context={
            "driver_id":
                1,

            "remaining_lbs":
                200.0,
        },

        options=[
            {
                "id":
                    "manual_takeover",

                "action":
                    "manual_takeover",

                "label":
                    "Take over manually",
            }
        ],

        recommended_action=
            "manual_takeover",
    )

    second = create_escalation(
        operation_id=
            operation_id,

        escalation_type=
            "driver_failure_after_pickup",

        reason=
            "Driver cannot continue after pickup.",

        context={
            "driver_id":
                1,

            "remaining_lbs":
                200.0,
        },

        options=[
            {
                "id":
                    "manual_takeover",

                "action":
                    "manual_takeover",

                "label":
                    "Take over manually",
            }
        ],

        recommended_action=
            "manual_takeover",
    )

    # RescueMesh should return the already-existing
    # pending escalation instead of creating another one.

    assert (
        first[
            "id"
        ]
        ==
        second[
            "id"
        ]
    )

    pending = (
        get_pending_escalations(
            operation_id
        )
    )

    assert len(
        pending
    ) == 1

    assert (
        pending[0][
            "escalation_type"
        ]
        ==
        "driver_failure_after_pickup"
    )
    
# invalid human option is rejected

def test_invalid_human_option_is_rejected(
    in_transit_db,
):
    operation_id = (
        activate_and_pick_up()
    )

    escalation = create_escalation(
        operation_id=
            operation_id,

        escalation_type=
            "no_feasible_destination",

        reason=
            "No safe destination exists.",

        context={
            "driver_id":
                1,

            "remaining_lbs":
                200.0,
        },

        options=[
            {
                "id":
                    "manual_takeover",

                "action":
                    "manual_takeover",

                "label":
                    "Take over manually",
            }
        ],

        recommended_action=
            "manual_takeover",
    )

    with pytest.raises(
        ValueError,
        match="not valid",
    ):

        approve_escalation(
            escalation_id=
                escalation[
                    "id"
                ],

            option_id=
                "invent_a_new_route",
        )

    # Invalid decision must NOT change the escalation.

    stored = get_escalation(
        escalation[
            "id"
        ]
    )

    assert (
        stored[
            "status"
        ]
        ==
        "pending"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "awaiting_human"
    )
    
# same escalation cannot be approved twice 

def test_escalation_cannot_be_approved_twice(
    in_transit_db,
):
    operation_id = (
        activate_and_pick_up()
    )

    escalation = create_escalation(
        operation_id=
            operation_id,

        escalation_type=
            "driver_failure_after_pickup",

        reason=
            "Driver cannot continue safely.",

        context={
            "driver_id":
                1,

            "remaining_lbs":
                200.0,
        },

        options=[
            {
                "id":
                    "manual_takeover",

                "action":
                    "manual_takeover",

                "label":
                    "Take over manually",
            }
        ],

        recommended_action=
            "manual_takeover",
    )

    # First approval should work.

    first_result = (
        approve_escalation(
            escalation_id=
                escalation[
                    "id"
                ],

            option_id=
                "manual_takeover",

            notes=
                "Operations coordinator will handle it.",
        )
    )

    assert (
        first_result[
            "status"
        ]
        ==
        "approved"
    )

    # Second approval must be blocked.

    with pytest.raises(
        ValueError,
        match="Only a pending escalation can be approved",
    ):

        approve_escalation(
            escalation_id=
                escalation[
                    "id"
                ],

            option_id=
                "manual_takeover",
        )

    stored = get_escalation(
        escalation[
            "id"
        ]
    )

    assert (
        stored[
            "status"
        ]
        ==
        "approved"
    )
    
# rejection moves operation to manual resolution

def test_rejected_escalation_moves_operation_to_manual_resolution(
    in_transit_db,
):
    operation_id = (
        activate_and_pick_up()
    )

    escalation = create_escalation(
        operation_id=
            operation_id,

        escalation_type=
            "partial_in_transit_rescue",

        reason=
            "Only part of the remaining food "
            "can be safely rescued.",

        context={
            "driver_id":
                1,

            "remaining_lbs":
                200.0,
        },

        options=[
            {
                "id":
                    "manual_takeover",

                "action":
                    "manual_takeover",

                "label":
                    "Take over manually",
            }
        ],

        recommended_action=
            "manual_takeover",
    )

    result = reject_escalation(
        escalation_id=
            escalation[
                "id"
            ],

        notes=
            "Coordinator rejected the suggested action.",
    )

    assert (
        result[
            "status"
        ]
        ==
        "rejected"
    )

    assert (
        result[
            "decision"
        ]
        ==
        "rejected"
    )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "manual_resolution"
    )
    
# completed operation cannot create escalation

def test_completed_operation_cannot_create_escalation(
    in_transit_db,
):
    operation_id = (
        activate_and_pick_up()
    )

    operation = get_operation(
        operation_id
    )

    stops = (
        operation[
            "driver_routes"
        ][0][
            "stops"
        ]
    )

    # Complete every delivery normally.
    #
    # Driver confirms delivery first,
    # pantry then confirms receipt.

    for stop in stops:

        mark_delivery_by_driver(
            operation_id,
            stop[
                "id"
            ],
        )

        confirm_pantry_received(
            operation_id,
            stop[
                "id"
            ],
        )

    operation = get_operation(
        operation_id
    )

    assert (
        operation[
            "status"
        ]
        ==
        "completed"
    )

    # A completed rescue is terminal.
    # Creating an escalation must be forbidden.

    with pytest.raises(
        ValueError,
        match="terminal operation",
    ):

        create_escalation(
            operation_id=
                operation_id,

            escalation_type=
                "fake_late_problem",

            reason=
                "This should never be created.",

            context={},

            options=[
                {
                    "id":
                        "manual_takeover",

                    "action":
                        "manual_takeover",

                    "label":
                        "Take over manually",
                }
            ],

            recommended_action=
                "manual_takeover",
        )

    pending = (
        get_pending_escalations(
            operation_id
        )
    )

    assert (
        len(
            pending
        )
        ==
        0
    )