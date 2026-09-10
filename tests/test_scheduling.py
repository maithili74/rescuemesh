from app.optimizer import rescue_optimizer


def test_existing_route_blocks_overlapping_pickup(
    monkeypatch,
):
    """
    A driver whose existing route ends at 11:45
    must not be considered free for an 11:30 pickup.

    The same driver should become available again
    for a pickup after the route has completed.
    """

    class FakeResult:

        def fetchall(self):
            return [
                {
                    "pickup_start": "11:00",
                    "route_complete": "11:45",
                    "route_status": "assigned",
                    "operation_status": "planned",
                }
            ]

    class FakeConnection:

        def execute(
            self,
            query,
            params,
        ):
            return FakeResult()

        def close(self):
            pass

    monkeypatch.setattr(
        "app.database.db.get_connection",
        lambda: FakeConnection(),
    )

    # -----------------------------------------------------
    # OVERLAPPING PICKUP
    # -----------------------------------------------------

    pickup_1130 = (
        rescue_optimizer.time_to_minutes(
            "11:30"
        )
    )

    conflict = (
        rescue_optimizer.driver_has_scheduling_conflict(
            driver_id=3,
            proposed_pickup_start=pickup_1130,
        )
    )

    assert conflict is True

    # -----------------------------------------------------
    # PICKUP AFTER EXISTING ROUTE
    # -----------------------------------------------------

    pickup_1200 = (
        rescue_optimizer.time_to_minutes(
            "12:00"
        )
    )

    conflict = (
        rescue_optimizer.driver_has_scheduling_conflict(
            driver_id=3,
            proposed_pickup_start=pickup_1200,
        )
    )

    assert conflict is False


def test_pickup_feasibility_excludes_double_booked_driver(
    monkeypatch,
):
    """
    Even when two drivers can physically reach the donor,
    a driver with an overlapping RescueMesh commitment
    must be excluded from the feasible driver pool.
    """

    donation = {
        "available_at":
            "11:00",

        "pickup_deadline":
            "14:00",
    }

    drivers = [
        {
            "id":
                1,

            "name":
                "Lisa",

            "available_from":
                "10:00",

            "available_until":
                "17:00",
        },
        {
            "id":
                2,

            "name":
                "Emily",

            "available_from":
                "10:00",

            "available_until":
                "17:00",
        },
    ]

    # Matrix layout:
    #
    # index 0 = Lisa
    # index 1 = Emily
    # index 2 = Donor
    #
    # Both drivers can reach the donor in time.
    network = {
        "matrix": {
            "durations_minutes": [
                [0, 5, 10],
                [5, 0, 12],
                [10, 12, 0],
            ],

            "distances_miles": [
                [0, 2, 4],
                [2, 0, 5],
                [4, 5, 0],
            ],
        },

        "donor_index":
            2,

        "driver_matrix_index": {
            1: 0,
            2: 1,
        },
    }

    # Lisa is already committed to another rescue.
    # Emily is free.
    monkeypatch.setattr(
        rescue_optimizer,
        "driver_has_scheduling_conflict",
        lambda driver_id, proposed_pickup_start:
            driver_id == 1,
    )

    feasible = (
        rescue_optimizer.get_pickup_feasible_drivers(
            donation,
            drivers,
            network,
        )
    )

    feasible_driver_ids = [
        driver["id"]
        for driver in feasible
    ]

    assert 1 not in feasible_driver_ids
    assert 2 in feasible_driver_ids

    assert feasible_driver_ids == [2]


def test_shift_violation_retries_with_alternate_driver(
    monkeypatch,
):
    import app.optimizer.rescue_optimizer as optimizer

    donation = {
        "id": 999,
        "quantity_lbs": 50.0,
        "donor_name": "Test Donor",
        "food_type": "prepared_food",
    }

    pantries = [
        {
            "id": 1,
            "name": "Test Pantry",
        }
    ]

    lisa = {
        "id": 3,
        "name": "Lisa",
    }

    emily = {
        "id": 4,
        "name": "Emily",
    }

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: {
            "donation": donation,
            "compatible_pantries": pantries,
            "eligible_drivers": [
                lisa,
                emily,
            ],
        },
    )

    monkeypatch.setattr(
        optimizer,
        "build_network_matrix",
        lambda donation, pantries, drivers: {
            "test": True
        },
    )

    monkeypatch.setattr(
        optimizer,
        "get_pickup_feasible_drivers",
        lambda donation, drivers, network:
            drivers,
    )

    monkeypatch.setattr(
        optimizer,
        "optimize_pantry_quantities",
        lambda donation, pantries, drivers, network: [
            {
                "pantry_id": 1,
                "assigned_lbs": 50.0,
            }
        ],
    )

    routing_attempts = []

    def fake_routes(
        donation,
        assignments,
        drivers,
        network,
    ):
        names = [
            driver["name"]
            for driver in drivers
        ]

        routing_attempts.append(
            names
        )

        if "Lisa" in names:

            raise ValueError(
                "Route for Lisa finishes at 17:06, "
                "but their shift ends at 17:00."
            )

        return {
            "routes": [
                {
                    "driver_id": 4,
                    "driver_name": "Emily",
                    "assigned_lbs": 50.0,
                }
            ],
            "total_distance_miles": 5.0,
        }

    monkeypatch.setattr(
        optimizer,
        "optimize_driver_routes",
        fake_routes,
    )

    result = (
        optimizer.optimize_rescue_plan(
            999
        )
    )

    assert (
        result["status"]
        ==
        "optimal"
    )

    assert (
        result["rescued_lbs"]
        ==
        50.0
    )

    assert (
        result[
            "human_attention_required"
        ]
        is False
    )

    assert routing_attempts == [
        [
            "Lisa",
            "Emily",
        ],
        [
            "Emily",
        ],
    ]

    assert (
        len(
            result[
                "driver_rejections"
            ]
        )
        ==
        1
    )

    assert (
        result[
            "driver_rejections"
        ][0][
            "driver_name"
        ]
        ==
        "Lisa"
    )

    assert (
        result[
            "driver_rejections"
        ][0][
            "constraint"
        ]
        ==
        "shift_end"
    )


def test_shift_violation_requires_human_when_no_driver_remains(
    monkeypatch,
):
    import app.optimizer.rescue_optimizer as optimizer

    donation = {
        "id": 999,
        "quantity_lbs": 50.0,
        "donor_name": "Test Donor",
        "food_type": "prepared_food",
    }

    lisa = {
        "id": 3,
        "name": "Lisa",
    }

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: {
            "donation": donation,
            "compatible_pantries": [
                {
                    "id": 1,
                    "name": "Test Pantry",
                }
            ],
            "eligible_drivers": [
                lisa
            ],
        },
    )

    monkeypatch.setattr(
        optimizer,
        "build_network_matrix",
        lambda donation, pantries, drivers: {
            "test": True
        },
    )

    monkeypatch.setattr(
        optimizer,
        "get_pickup_feasible_drivers",
        lambda donation, drivers, network:
            drivers,
    )

    monkeypatch.setattr(
        optimizer,
        "optimize_pantry_quantities",
        lambda donation, pantries, drivers, network: [
            {
                "pantry_id": 1,
                "assigned_lbs": 50.0,
            }
        ],
    )

    def fake_routes(
        donation,
        assignments,
        drivers,
        network,
    ):
        raise ValueError(
            "Route for Lisa finishes at 17:06, "
            "but their shift ends at 17:00."
        )

    monkeypatch.setattr(
        optimizer,
        "optimize_driver_routes",
        fake_routes,
    )

    result = (
        optimizer.optimize_rescue_plan(
            999
        )
    )

    assert (
        result["status"]
        ==
        "no_feasible_plan"
    )

    assert (
        result[
            "human_attention_required"
        ]
        is True
    )

    assert (
        result["unrescued_lbs"]
        ==
        50.0
    )

    assert (
        result[
            "driver_rejections"
        ][0][
            "driver_name"
        ]
        ==
        "Lisa"
    )