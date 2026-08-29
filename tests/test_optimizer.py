import pytest

import app.optimizer.rescue_optimizer as optimizer


# =========================================================
# TEST DATA HELPERS
# =========================================================

def make_donation(
    quantity=100.0,
    food_type="produce",
    available_at="10:00",
    pickup_deadline="12:00",
):
    return {
        "id": 1,
        "donor_name": "Test Donor",
        "donor_location": "Test Area",
        "donor_latitude": 36.10,
        "donor_longitude": -86.70,
        "food_type": food_type,
        "quantity_lbs": quantity,
        "available_at": available_at,
        "pickup_deadline": pickup_deadline,
        "status": "available",
    }


def make_pantry(
    pantry_id=1,
    name="Test Pantry",
    capacity=500.0,
    need_score=0.90,
    latitude=36.11,
    longitude=-86.71,
):
    return {
        "id": pantry_id,
        "name": name,
        "location": "Test Area",
        "latitude": latitude,
        "longitude": longitude,
        "available_capacity_lbs": capacity,
        "need_score": need_score,
        "food_type": "produce",
    }


def make_driver(
    driver_id=1,
    name="Test Driver",
    capacity=100.0,
    available_from="09:00",
    available_until="15:00",
    latitude=36.09,
    longitude=-86.69,
):
    return {
        "id": driver_id,
        "name": name,
        "location": "Test Area",
        "latitude": latitude,
        "longitude": longitude,
        "capacity_lbs": capacity,
        "available_from": available_from,
        "available_until": available_until,
        "status": "available",
    }


def make_state(
    donation,
    pantries,
    drivers,
):
    return {
        "donation": donation,
        "compatible_pantries": pantries,
        "eligible_drivers": drivers,
    }


def make_network(
    pantries,
    drivers,
    donor_to_pantry_minutes=10,
    driver_to_donor_minutes=5,
    pantry_to_pantry_minutes=5,
):
    """
    Create a fake routing matrix.

    Layout:

        index 0 = donor
        next indexes = pantries
        final indexes = drivers

    No real ORS request is made.
    """

    donor_index = 0

    pantry_matrix_index = {}
    driver_matrix_index = {}

    next_index = 1

    for pantry in pantries:
        pantry_matrix_index[
            pantry["id"]
        ] = next_index

        next_index += 1

    for driver in drivers:
        driver_matrix_index[
            driver["id"]
        ] = next_index

        next_index += 1

    size = next_index

    # Default road travel:
    # 5 minutes and 2 miles between locations.
    durations = [
        [
            0 if i == j else pantry_to_pantry_minutes
            for j in range(size)
        ]
        for i in range(size)
    ]

    distances = [
        [
            0 if i == j else 2.0
            for j in range(size)
        ]
        for i in range(size)
    ]

    # Donor -> pantry
    for pantry in pantries:

        pantry_index = pantry_matrix_index[
            pantry["id"]
        ]

        durations[
            donor_index
        ][
            pantry_index
        ] = donor_to_pantry_minutes

        durations[
            pantry_index
        ][
            donor_index
        ] = donor_to_pantry_minutes

        distances[
            donor_index
        ][
            pantry_index
        ] = 4.0

        distances[
            pantry_index
        ][
            donor_index
        ] = 4.0

    # Driver -> donor
    for driver in drivers:

        driver_index = driver_matrix_index[
            driver["id"]
        ]

        durations[
            driver_index
        ][
            donor_index
        ] = driver_to_donor_minutes

        durations[
            donor_index
        ][
            driver_index
        ] = driver_to_donor_minutes

        distances[
            driver_index
        ][
            donor_index
        ] = 2.0

        distances[
            donor_index
        ][
            driver_index
        ] = 2.0

    return {
        "donor_index": donor_index,

        "pantry_matrix_index":
            pantry_matrix_index,

        "driver_matrix_index":
            driver_matrix_index,

        "matrix": {
            "durations_minutes":
                durations,

            "distances_miles":
                distances,
        },
    }


def install_fake_world(
    monkeypatch,
    state,
    network,
):
    """
    Replace DB + ORS calls with deterministic test data.
    """

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: state,
    )

    monkeypatch.setattr(
        optimizer,
        "build_network_matrix",
        lambda donation, pantries, drivers: network,
    )


# =========================================================
# TEST 1
# UNKNOWN DONATION
# =========================================================

def test_unknown_donation_returns_error(
    monkeypatch,
):
    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: None,
    )

    result = (
        optimizer.optimize_rescue_plan(
            9999
        )
    )

    assert result["status"] == "error"


# =========================================================
# TEST 2
# NO COMPATIBLE PANTRY
# =========================================================

def test_no_compatible_pantry(
    monkeypatch,
):
    donation = make_donation(
        quantity=100
    )

    driver = make_driver(
        capacity=100
    )

    state = make_state(
        donation,
        [],
        [driver],
    )

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: state,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert (
        result["status"]
        ==
        "no_feasible_plan"
    )

    assert result["rescued_lbs"] == 0

    assert (
        result["unrescued_lbs"]
        ==
        100
    )


# =========================================================
# TEST 3
# NO AVAILABLE DRIVER
# =========================================================

def test_no_available_driver(
    monkeypatch,
):
    donation = make_donation(
        quantity=100
    )

    pantry = make_pantry(
        capacity=200
    )

    state = make_state(
        donation,
        [pantry],
        [],
    )

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: state,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert (
        result["status"]
        ==
        "no_feasible_plan"
    )

    assert result["rescued_lbs"] == 0

    assert (
        result["unrescued_lbs"]
        ==
        100
    )


# =========================================================
# TEST 4
# PARTIAL RESCUE DUE TO DRIVER CAPACITY
# =========================================================

def test_partial_rescue_when_transport_capacity_is_insufficient(
    monkeypatch,
):
    donation = make_donation(
        quantity=250
    )

    pantry = make_pantry(
        capacity=500
    )

    # Only 120 lbs of transportation exists.
    driver = make_driver(
        capacity=120
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    network = make_network(
        [pantry],
        [driver],
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert result["status"] == "optimal"

    assert (
        result["rescued_lbs"]
        ==
        pytest.approx(
            120.0,
            abs=0.1,
        )
    )

    assert (
        result["unrescued_lbs"]
        ==
        pytest.approx(
            130.0,
            abs=0.1,
        )
    )

    assert (
        result["rescue_rate"]
        ==
        pytest.approx(
            0.48,
            abs=0.01,
        )
    )

    assert result["drivers_used"] == 1


# =========================================================
# TEST 5
# PANTRY CAPACITY LIMIT
# =========================================================

def test_partial_rescue_when_pantry_capacity_is_insufficient(
    monkeypatch,
):
    donation = make_donation(
        quantity=200
    )

    # Pantry can accept only 75 lbs.
    pantry = make_pantry(
        capacity=75
    )

    driver = make_driver(
        capacity=200
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    network = make_network(
        [pantry],
        [driver],
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert result["status"] == "optimal"

    assert (
        result["rescued_lbs"]
        ==
        pytest.approx(
            75.0,
            abs=0.1,
        )
    )

    assert (
        result["unrescued_lbs"]
        ==
        pytest.approx(
            125.0,
            abs=0.1,
        )
    )


# =========================================================
# TEST 6
# EXACT VEHICLE CAPACITY
# =========================================================

def test_driver_can_carry_exact_capacity(
    monkeypatch,
):
    donation = make_donation(
        quantity=100
    )

    pantry = make_pantry(
        capacity=100
    )

    driver = make_driver(
        capacity=100
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    network = make_network(
        [pantry],
        [driver],
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert result["status"] == "optimal"

    assert result["rescued_lbs"] == 100

    route = result[
        "driver_routes"
    ][0]

    assert route["assigned_lbs"] == 100
    assert route["capacity_lbs"] == 100


# =========================================================
# TEST 7
# EXACT PICKUP DEADLINE
# =========================================================

def test_pickup_completed_exactly_at_deadline_is_allowed(
    monkeypatch,
):
    # Driver:
    #
    # starts = 10:00
    # drive = 5 min
    # pickup service = 10 min
    #
    # pickup complete = 10:15
    #
    # deadline = 10:15
    #
    # Should be allowed.

    donation = make_donation(
        quantity=50,
        available_at="10:00",
        pickup_deadline="10:15",
    )

    pantry = make_pantry(
        capacity=100
    )

    driver = make_driver(
        capacity=50,
        available_from="10:00",
        available_until="12:00",
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    network = make_network(
        [pantry],
        [driver],
        driver_to_donor_minutes=5,
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert result["status"] == "optimal"

    route = result[
        "driver_routes"
    ][0]

    assert (
        route["pickup_complete"]
        ==
        "10:15"
    )


# =========================================================
# TEST 8
# ONE MINUTE AFTER DEADLINE
# =========================================================

def test_pickup_after_deadline_is_rejected(
    monkeypatch,
):
    # Same driver:
    #
    # pickup complete = 10:15
    #
    # but deadline = 10:14.

    donation = make_donation(
        quantity=50,
        available_at="10:00",
        pickup_deadline="10:14",
    )

    pantry = make_pantry(
        capacity=100
    )

    driver = make_driver(
        capacity=50,
        available_from="10:00",
        available_until="12:00",
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    network = make_network(
        [pantry],
        [driver],
        driver_to_donor_minutes=5,
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert (
        result["status"]
        ==
        "no_feasible_plan"
    )


# =========================================================
# TEST 9
# MULTI-STOP ONE DRIVER
# =========================================================

def test_one_driver_can_make_multiple_nearby_drops(
    monkeypatch,
):
    donation = make_donation(
        quantity=100
    )

    pantry_a = make_pantry(
        pantry_id=1,
        name="Pantry A",
        capacity=40,
        need_score=0.99,
        latitude=36.11,
        longitude=-86.71,
    )

    pantry_b = make_pantry(
        pantry_id=2,
        name="Pantry B",
        capacity=60,
        need_score=0.98,
        latitude=36.12,
        longitude=-86.72,
    )

    driver = make_driver(
        capacity=100
    )

    pantries = [
        pantry_a,
        pantry_b,
    ]

    drivers = [
        driver,
    ]

    state = make_state(
        donation,
        pantries,
        drivers,
    )

    network = make_network(
        pantries,
        drivers,
        donor_to_pantry_minutes=5,
        pantry_to_pantry_minutes=3,
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert result["status"] == "optimal"

    assert result["rescued_lbs"] == 100

    assert result["drivers_used"] == 1

    route = result[
        "driver_routes"
    ][0]

    assert len(route["stops"]) == 2

    assert route["assigned_lbs"] == 100

    delivered = sum(
        stop["quantity_lbs"]
        for stop in route["stops"]
    )

    assert delivered == 100


# =========================================================
# TEST 10
# ROUTE EXCEEDS DRIVER SHIFT
# =========================================================

def test_route_finishing_after_driver_shift_is_rejected(
    monkeypatch,
):
    donation = make_donation(
        quantity=50,
        available_at="10:00",
        pickup_deadline="10:20",
    )

    pantry = make_pantry(
        capacity=100
    )

    driver = make_driver(
        capacity=50,
        available_from="10:00",
        available_until="10:30",
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    # Driver reaches donor quickly,
    # but donor -> pantry takes 40 minutes.
    #
    # Pickup complete around 10:12.
    #
    # Delivery cannot finish before 10:30.
    network = make_network(
        [pantry],
        [driver],
        donor_to_pantry_minutes=40,
        driver_to_donor_minutes=2,
    )

    install_fake_world(
        monkeypatch,
        state,
        network,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert (
        result["status"]
        ==
        "routing_infeasible"
    )


# =========================================================
# TEST 11
# ROUTING API FAILURE
# =========================================================

def test_routing_api_failure_returns_clean_error(
    monkeypatch,
):
    donation = make_donation(
        quantity=100
    )

    pantry = make_pantry(
        capacity=100
    )

    driver = make_driver(
        capacity=100
    )

    state = make_state(
        donation,
        [pantry],
        [driver],
    )

    monkeypatch.setattr(
        optimizer,
        "get_network_state",
        lambda donation_id: state,
    )

    def fake_routing_failure(
        donation,
        pantries,
        drivers,
    ):
        raise RuntimeError(
            "ORS service unavailable"
        )

    monkeypatch.setattr(
        optimizer,
        "build_network_matrix",
        fake_routing_failure,
    )

    result = (
        optimizer.optimize_rescue_plan(
            1
        )
    )

    assert (
        result["status"]
        ==
        "routing_error"
    )

    assert (
        "ORS service unavailable"
        in result["reason"]
    )