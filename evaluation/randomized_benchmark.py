"""
RescueMesh randomized evaluation benchmark.

Measures:
- randomized planning outcomes
- full / partial rescue
- safe rejection
- food rescue rate
- planning latency
- capacity safety
- driver double booking
- pickup deadline safety
- driver shift safety
- quantity accounting safety
- pantry capacity safety
- autonomous disruption recovery
- human escalation rate

IMPORTANT:
Run this against the LOCAL RescueMesh database only.

The script resets the demo environment and temporarily
changes donation quantities/times and resource capacities.
Original seeded values are restored after every scenario.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time

from datetime import datetime
from pathlib import Path


# =========================================================
# LOAD LOCAL ENVIRONMENT BEFORE IMPORTING ROUTING CODE
# =========================================================

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


from app.database.db import get_connection
from app.dashboard.services.demo_reset import (
    reset_demo_environment,
)
from app.events.processor import process_event
from app.operations.execution import (
    create_operation_from_plan,
)
from app.optimizer.rescue_optimizer import (
    optimize_rescue_plan,
)


# =========================================================
# CONFIG
# =========================================================

EPSILON = 0.01

OUTPUT_DIR = Path(
    "evaluation/results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# TIME HELPERS
# =========================================================

def time_to_minutes(value):
    """
    Convert HH:MM to minutes after midnight.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    parsed = datetime.strptime(
        value,
        "%H:%M",
    )

    return (
        parsed.hour * 60
        +
        parsed.minute
    )


def minutes_to_time(minutes):
    """
    Convert minutes after midnight to HH:MM.
    """

    minutes = int(minutes)

    hours = (
        minutes // 60
    ) % 24

    mins = (
        minutes % 60
    )

    return (
        f"{hours:02d}:{mins:02d}"
    )


# =========================================================
# DATABASE HELPERS
# =========================================================

def rows_as_dicts(
    query,
    params=(),
):
    conn = get_connection()

    try:
        rows = conn.execute(
            query,
            params,
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def snapshot_seed_state():
    """
    Save the fields that this benchmark may modify.
    """

    donations = rows_as_dicts(
        """
        SELECT
            id,
            quantity_lbs,
            available_at,
            pickup_deadline,
            status

        FROM donations
        """
    )

    drivers = rows_as_dicts(
        """
        SELECT
            id,
            capacity_lbs,
            available_until

        FROM drivers
        """
    )

    pantries = rows_as_dicts(
        """
        SELECT
            id,
            available_capacity_lbs

        FROM pantries
        """
    )

    return {
        "donations":
            donations,

        "drivers":
            drivers,

        "pantries":
            pantries,
    }


def restore_seed_state(
    snapshot,
):
    """
    Restore the benchmark-modified fields.
    """

    conn = get_connection()

    try:

        for donation in snapshot[
            "donations"
        ]:

            conn.execute(
                """
                UPDATE donations

                SET
                    quantity_lbs = ?,
                    available_at = ?,
                    pickup_deadline = ?,
                    status = ?

                WHERE id = ?
                """,
                (
                    donation[
                        "quantity_lbs"
                    ],
                    donation[
                        "available_at"
                    ],
                    donation[
                        "pickup_deadline"
                    ],
                    donation[
                        "status"
                    ],
                    donation[
                        "id"
                    ],
                ),
            )

        for driver in snapshot[
            "drivers"
        ]:

            conn.execute(
                """
                UPDATE drivers

                SET capacity_lbs = ?

                WHERE id = ?
                """,
                (
                    driver[
                        "capacity_lbs"
                    ],
                    driver[
                        "id"
                    ],
                ),
            )

        for pantry in snapshot[
            "pantries"
        ]:

            conn.execute(
                """
                UPDATE pantries

                SET available_capacity_lbs = ?

                WHERE id = ?
                """,
                (
                    pantry[
                        "available_capacity_lbs"
                    ],
                    pantry[
                        "id"
                    ],
                ),
            )

        conn.commit()

    finally:
        conn.close()


# =========================================================
# RANDOM SCENARIO GENERATION
# =========================================================

def randomize_donation(
    rng,
    donation_id,
):
    """
    Randomize donation quantity and pickup window.

    The food type and donor remain unchanged so each
    scenario stays grounded in the seeded network.
    """

    quantities = [
        20,
        30,
        40,
        50,
        60,
        75,
        90,
        110,
        130,
        150,
        180,
        200,
        225,
        250,
        275,
        300,
        325,
        350,
    ]

    quantity = float(
        rng.choice(
            quantities
        )
    )

    # Start between 8:00 AM and 2:00 PM
    available_minutes = (
        rng.randrange(
            8 * 60,
            14 * 60 + 1,
            15,
        )
    )

    # Includes deliberately difficult windows.
    window_minutes = rng.choice(
        [
            20,
            30,
            45,
            60,
            75,
            90,
            120,
            150,
            180,
            240,
        ]
    )

    deadline_minutes = (
        available_minutes
        +
        window_minutes
    )

    available_at = minutes_to_time(
        available_minutes
    )

    pickup_deadline = minutes_to_time(
        deadline_minutes
    )

    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE donations

            SET
                quantity_lbs = ?,
                available_at = ?,
                pickup_deadline = ?,
                status = 'available'

            WHERE id = ?
            """,
            (
                quantity,
                available_at,
                pickup_deadline,
                donation_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()

    return {
        "quantity_lbs":
            quantity,

        "available_at":
            available_at,

        "pickup_deadline":
            pickup_deadline,

        "window_minutes":
            window_minutes,
    }


def apply_network_stress(
    rng,
    snapshot,
):
    """
    Randomly reduce driver or pantry capacity.

    Nothing is increased beyond the seeded state.
    """

    stress_type = rng.choices(
        population=[
            "normal",
            "driver_capacity",
            "pantry_capacity",
            "combined",
        ],
        weights=[
            40,
            20,
            20,
            20,
        ],
        k=1,
    )[0]

    conn = get_connection()

    try:

        # -------------------------------------------------
        # DRIVER CAPACITY STRESS
        # -------------------------------------------------

        if stress_type in (
            "driver_capacity",
            "combined",
        ):

            drivers = snapshot[
                "drivers"
            ]

            number_to_stress = rng.randint(
                1,
                max(
                    1,
                    len(drivers) // 2,
                ),
            )

            chosen = rng.sample(
                drivers,
                number_to_stress,
            )

            for driver in chosen:

                scale = rng.uniform(
                    0.25,
                    0.75,
                )

                new_capacity = max(
                    10.0,
                    round(
                        float(
                            driver[
                                "capacity_lbs"
                            ]
                        )
                        *
                        scale,
                        1,
                    ),
                )

                conn.execute(
                    """
                    UPDATE drivers

                    SET capacity_lbs = ?

                    WHERE id = ?
                    """,
                    (
                        new_capacity,
                        driver[
                            "id"
                        ],
                    ),
                )

        # -------------------------------------------------
        # PANTRY CAPACITY STRESS
        # -------------------------------------------------

        if stress_type in (
            "pantry_capacity",
            "combined",
        ):

            pantries = snapshot[
                "pantries"
            ]

            number_to_stress = rng.randint(
                1,
                max(
                    1,
                    len(pantries) // 2,
                ),
            )

            chosen = rng.sample(
                pantries,
                number_to_stress,
            )

            for pantry in chosen:

                original_capacity = float(
                    pantry[
                        "available_capacity_lbs"
                    ]
                )

                scale = rng.uniform(
                    0.15,
                    0.70,
                )

                new_capacity = max(
                    0.0,
                    round(
                        original_capacity
                        *
                        scale,
                        1,
                    ),
                )

                conn.execute(
                    """
                    UPDATE pantries

                    SET available_capacity_lbs = ?

                    WHERE id = ?
                    """,
                    (
                        new_capacity,
                        pantry[
                            "id"
                        ],
                    ),
                )

        conn.commit()

    finally:
        conn.close()

    return stress_type


# =========================================================
# SAFETY VALIDATION
# =========================================================

def validate_plan(
    plan,
    donation,
):
    """
    Independently check important invariants in
    an optimizer result.

    Returns a list of violations.
    """

    violations = []

    if plan.get(
        "status"
    ) != "optimal":

        return violations

    donation_quantity = float(
        donation[
            "quantity_lbs"
        ]
    )

    rescued_lbs = float(
        plan.get(
            "rescued_lbs",
            0,
        )
        or 0
    )

    unrescued_lbs = float(
        plan.get(
            "unrescued_lbs",
            0,
        )
        or 0
    )

    routes = plan.get(
        "driver_routes",
        [],
    )

    # -----------------------------------------------------
    # BASIC ACCOUNTING
    # -----------------------------------------------------

    if rescued_lbs < -EPSILON:

        violations.append(
            "negative_rescued_lbs"
        )

    if unrescued_lbs < -EPSILON:

        violations.append(
            "negative_unrescued_lbs"
        )

    if rescued_lbs > (
        donation_quantity
        +
        EPSILON
    ):

        violations.append(
            "rescued_more_than_donation"
        )

    if not math.isclose(
        rescued_lbs
        +
        unrescued_lbs,
        donation_quantity,
        abs_tol=0.1,
    ):

        violations.append(
            "donation_accounting_mismatch"
        )

    # -----------------------------------------------------
    # ROUTE LOAD ACCOUNTING
    # -----------------------------------------------------

    total_route_load = 0.0

    driver_ids = []

    for route in routes:

        assigned_lbs = float(
            route.get(
                "assigned_lbs",
                0,
            )
            or 0
        )

        capacity_lbs = float(
            route.get(
                "capacity_lbs",
                0,
            )
            or 0
        )

        total_route_load += (
            assigned_lbs
        )

        driver_id = route.get(
            "driver_id"
        )

        driver_ids.append(
            driver_id
        )

        # ---------------------------------------------
        # DRIVER CAPACITY
        # ---------------------------------------------

        if assigned_lbs > (
            capacity_lbs
            +
            EPSILON
        ):

            violations.append(
                "driver_capacity"
            )

        # ---------------------------------------------
        # STOP QUANTITY = ROUTE LOAD
        # ---------------------------------------------

        stop_total = sum(
            float(
                stop.get(
                    "quantity_lbs",
                    0,
                )
                or 0
            )
            for stop
            in route.get(
                "stops",
                [],
            )
        )

        if not math.isclose(
            stop_total,
            assigned_lbs,
            abs_tol=0.1,
        ):

            violations.append(
                "route_stop_quantity_mismatch"
            )

        # ---------------------------------------------
        # NO NEGATIVE / ZERO STOPS
        # ---------------------------------------------

        for stop in route.get(
            "stops",
            [],
        ):

            if float(
                stop.get(
                    "quantity_lbs",
                    0,
                )
                or 0
            ) <= 0:

                violations.append(
                    "non_positive_delivery"
                )

        # ---------------------------------------------
        # PICKUP DEADLINE
        # ---------------------------------------------

        pickup_complete = (
            route.get(
                "pickup_complete"
            )
        )

        if pickup_complete:

            if (
                time_to_minutes(
                    pickup_complete
                )
                >
                time_to_minutes(
                    donation[
                        "pickup_deadline"
                    ]
                )
                +
                EPSILON
            ):

                violations.append(
                    "pickup_deadline"
                )

        # ---------------------------------------------
        # DRIVER SHIFT
        # ---------------------------------------------

        driver_row = rows_as_dicts(
            """
            SELECT
                available_until

            FROM drivers

            WHERE id = ?
            """,
            (
                driver_id,
            ),
        )

        if (
            driver_row
            and
            route.get(
                "route_complete"
            )
        ):

            available_until = (
                driver_row[0][
                    "available_until"
                ]
            )

            if (
                time_to_minutes(
                    route[
                        "route_complete"
                    ]
                )
                >
                time_to_minutes(
                    available_until
                )
                +
                EPSILON
            ):

                violations.append(
                    "driver_shift"
                )

    # -----------------------------------------------------
    # NO SAME DRIVER TWICE IN ONE PLAN
    # -----------------------------------------------------

    clean_driver_ids = [
        driver_id
        for driver_id
        in driver_ids
        if driver_id is not None
    ]

    if (
        len(clean_driver_ids)
        !=
        len(
            set(
                clean_driver_ids
            )
        )
    ):

        violations.append(
            "driver_double_booking"
        )

    # -----------------------------------------------------
    # ROUTE LOAD = RESCUED FOOD
    # -----------------------------------------------------

    if not math.isclose(
        total_route_load,
        rescued_lbs,
        abs_tol=0.1,
    ):

        violations.append(
            "route_total_mismatch"
        )

    # -----------------------------------------------------
    # PANTRY ASSIGNMENT = RESCUED FOOD
    # -----------------------------------------------------

    pantry_assignments = plan.get(
        "pantry_assignments",
        [],
    )

    pantry_total = sum(
        float(
            assignment.get(
                "assigned_lbs",
                0,
            )
            or 0
        )
        for assignment
        in pantry_assignments
    )

    if not math.isclose(
        pantry_total,
        rescued_lbs,
        abs_tol=0.1,
    ):

        violations.append(
            "pantry_total_mismatch"
        )

    # -----------------------------------------------------
    # PANTRY AVAILABLE CAPACITY
    # -----------------------------------------------------

    for assignment in (
        pantry_assignments
    ):

        pantry_id = assignment.get(
            "pantry_id"
        )

        assigned_lbs = float(
            assignment.get(
                "assigned_lbs",
                0,
            )
            or 0
        )

        pantry_rows = rows_as_dicts(
            """
            SELECT
                available_capacity_lbs

            FROM pantries

            WHERE id = ?
            """,
            (
                pantry_id,
            ),
        )

        if pantry_rows:

            available_capacity = float(
                pantry_rows[0][
                    "available_capacity_lbs"
                ]
            )

            if assigned_lbs > (
                available_capacity
                +
                EPSILON
            ):

                violations.append(
                    "pantry_capacity"
                )

    return sorted(
        set(
            violations
        )
    )


# =========================================================
# RANDOMIZED PLANNING BENCHMARK
# =========================================================

def run_planning_benchmark(
    scenario_count,
    rng,
    snapshot,
):
    print(
        "\n"
        +
        "=" * 70
    )

    print(
        "RANDOMIZED RESCUE PLANNING BENCHMARK"
    )

    print(
        "=" * 70
    )

    donation_ids = [
        donation[
            "id"
        ]
        for donation
        in snapshot[
            "donations"
        ]
    ]

    results = []

    for scenario_number in range(
        1,
        scenario_count + 1,
    ):

        restore_seed_state(
            snapshot
        )

        donation_id = rng.choice(
            donation_ids
        )

        scenario = (
            randomize_donation(
                rng,
                donation_id,
            )
        )

        stress_type = (
            apply_network_stress(
                rng,
                snapshot,
            )
        )

        donation = rows_as_dicts(
            """
            SELECT *

            FROM donations

            WHERE id = ?
            """,
            (
                donation_id,
            ),
        )[0]

        started = time.perf_counter()

        try:

            plan = (
                optimize_rescue_plan(
                    donation_id
                )
            )

            error = None

        except Exception as exc:

            plan = {
                "status":
                    "exception",

                "reason":
                    str(exc),
            }

            error = str(
                exc
            )

        latency_ms = (
            time.perf_counter()
            -
            started
        ) * 1000

        status = plan.get(
            "status",
            "unknown",
        )

        rescued_lbs = float(
            plan.get(
                "rescued_lbs",
                0,
            )
            or 0
        )

        unrescued_lbs = float(
            plan.get(
                "unrescued_lbs",
                scenario[
                    "quantity_lbs"
                ],
            )
            or 0
        )

        rescue_rate = (
            rescued_lbs
            /
            scenario[
                "quantity_lbs"
            ]
            if scenario[
                "quantity_lbs"
            ] > 0
            else 0
        )

        violations = (
            validate_plan(
                plan,
                donation,
            )
        )

        if status == "optimal":

            if rescue_rate >= 0.999:

                outcome = (
                    "fully_rescued"
                )

            elif rescued_lbs > EPSILON:

                outcome = (
                    "partially_rescued"
                )

            else:

                outcome = (
                    "invalid_zero_rescue_plan"
                )

        else:

            outcome = (
                "safely_rejected"
            )

        result = {
            "scenario":
                scenario_number,

            "donation_id":
                donation_id,

            "food_type":
                donation.get(
                    "food_type"
                ),

            "quantity_lbs":
                scenario[
                    "quantity_lbs"
                ],

            "available_at":
                scenario[
                    "available_at"
                ],

            "pickup_deadline":
                scenario[
                    "pickup_deadline"
                ],

            "window_minutes":
                scenario[
                    "window_minutes"
                ],

            "network_stress":
                stress_type,

            "optimizer_status":
                status,

            "outcome":
                outcome,

            "rescued_lbs":
                round(
                    rescued_lbs,
                    2,
                ),

            "unrescued_lbs":
                round(
                    unrescued_lbs,
                    2,
                ),

            "rescue_rate":
                round(
                    rescue_rate,
                    4,
                ),

            "drivers_used":
                int(
                    plan.get(
                        "drivers_used",
                        0,
                    )
                    or 0
                ),

            "planning_latency_ms":
                round(
                    latency_ms,
                    2,
                ),

            "safety_violations":
                "|".join(
                    violations
                ),

            "safety_violation_count":
                len(
                    violations
                ),

            "error":
                error or "",
        }

        results.append(
            result
        )

        if (
            scenario_number % 10
            ==
            0
            or
            scenario_number
            ==
            scenario_count
        ):

            print(
                f"Planning scenarios: "
                f"{scenario_number}/"
                f"{scenario_count}"
            )

    restore_seed_state(
        snapshot
    )

    return results


# =========================================================
# DISRUPTION BENCHMARK
# =========================================================

def find_usable_plan(
    rng,
    donation_ids,
    max_attempts=20,
):
    """
    Find a seeded donation that currently produces
    an optimal plan with at least one route and stop.
    """

    shuffled = list(
        donation_ids
    )

    rng.shuffle(
        shuffled
    )

    attempts = 0

    for donation_id in shuffled:

        if attempts >= max_attempts:
            break

        attempts += 1

        try:

            plan = (
                optimize_rescue_plan(
                    donation_id
                )
            )

        except Exception:
            continue

        if (
            plan.get(
                "status"
            )
            !=
            "optimal"
        ):
            continue

        routes = plan.get(
            "driver_routes",
            [],
        )

        if not routes:
            continue

        stops = [
            stop
            for route in routes
            for stop in route.get(
                "stops",
                [],
            )
        ]

        if not stops:
            continue

        return (
            donation_id,
            plan,
        )

    return (
        None,
        None,
    )


def run_disruption_benchmark(
    scenario_count,
    rng,
):
    print(
        "\n"
        +
        "=" * 70
    )

    print(
        "IN-TRANSIT DISRUPTION BENCHMARK"
    )

    print(
        "=" * 70
    )

    results = []

    for scenario_number in range(
        1,
        scenario_count + 1,
    ):

        # Clean operation state and restore
        # seeded network before every case.
        reset_demo_environment()

        donations = rows_as_dicts(
            """
            SELECT id

            FROM donations

            WHERE status = 'available'

            ORDER BY id
            """
        )

        donation_ids = [
            row[
                "id"
            ]
            for row in donations
        ]

        donation_id, plan = (
            find_usable_plan(
                rng,
                donation_ids,
            )
        )

        if plan is None:

            results.append(
                {
                    "scenario":
                        scenario_number,

                    "donation_id":
                        "",

                    "outcome":
                        "no_usable_seed_plan",

                    "disruption_status":
                        "",

                    "latency_ms":
                        0,

                    "unsafe_recovery":
                        0,

                    "error":
                        "Could not find usable plan.",
                }
            )

            continue

        try:

            operation_id = (
                create_operation_from_plan(
                    plan
                )
            )

            routes = plan[
                "driver_routes"
            ]

            # ---------------------------------------------
            # ALL DRIVERS ACCEPT
            # ---------------------------------------------

            for route in routes:

                process_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "DRIVER_ACCEPTED",

                    payload={
                        "driver_id":
                            route[
                                "driver_id"
                            ],
                    },
                )

            # ---------------------------------------------
            # ALL DRIVERS PICK UP FOOD
            # ---------------------------------------------

            for route in routes:

                process_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "PICKUP_COMPLETED",

                    payload={
                        "driver_id":
                            route[
                                "driver_id"
                            ],
                    },
                )

            original_stops = [
                stop
                for route in routes
                for stop in route.get(
                    "stops",
                    [],
                )
            ]

            disrupted_stop = rng.choice(
                original_stops
            )

            pantry_id = (
                disrupted_stop[
                    "pantry_id"
                ]
            )

            # ---------------------------------------------
            # CLOSE A PANTRY WHILE FOOD IS IN TRANSIT
            # ---------------------------------------------

            started = (
                time.perf_counter()
            )

            event_result = (
                process_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "PANTRY_CLOSED",

                    payload={
                        "pantry_id":
                            pantry_id,
                    },
                )
            )

            latency_ms = (
                time.perf_counter()
                -
                started
            ) * 1000

            inner_result = (
                event_result.get(
                    "result",
                    {},
                )
                or {}
            )

            disruption_status = (
                inner_result.get(
                    "status",
                    "unknown",
                )
            )

            unsafe_recovery = 0

            # ---------------------------------------------
            # AUTONOMOUS REPLAN MUST NOT SILENTLY
            # ACCEPT UNRESCUED FOOD.
            # ---------------------------------------------

            if (
                disruption_status
                ==
                "in_transit_replanned"
            ):

                for replan in (
                    inner_result.get(
                        "replans",
                        [],
                    )
                ):

                    if (
                        replan.get(
                            "status"
                        )
                        ==
                        "in_transit_replanned"
                    ):

                        replan_plan = (
                            replan.get(
                                "plan",
                                {},
                            )
                            or {}
                        )

                        if float(
                            replan_plan.get(
                                "unrescued_lbs",
                                0,
                            )
                            or 0
                        ) > EPSILON:

                            unsafe_recovery = 1

            if (
                disruption_status
                ==
                "in_transit_replanned"
            ):

                outcome = (
                    "autonomous_recovery"
                )

            elif (
                disruption_status
                ==
                "requires_human_escalation"
            ):

                outcome = (
                    "human_escalation"
                )

            else:

                outcome = (
                    "other"
                )

            results.append(
                {
                    "scenario":
                        scenario_number,

                    "donation_id":
                        donation_id,

                    "operation_id":
                        operation_id,

                    "pantry_id":
                        pantry_id,

                    "outcome":
                        outcome,

                    "disruption_status":
                        disruption_status,

                    "latency_ms":
                        round(
                            latency_ms,
                            2,
                        ),

                    "unsafe_recovery":
                        unsafe_recovery,

                    "error":
                        "",
                }
            )

        except Exception as exc:

            results.append(
                {
                    "scenario":
                        scenario_number,

                    "donation_id":
                        donation_id,

                    "operation_id":
                        "",

                    "pantry_id":
                        "",

                    "outcome":
                        "exception",

                    "disruption_status":
                        "exception",

                    "latency_ms":
                        0,

                    "unsafe_recovery":
                        0,

                    "error":
                        str(
                            exc
                        ),
                }
            )

        print(
            f"Disruption scenarios: "
            f"{scenario_number}/"
            f"{scenario_count}"
        )

    reset_demo_environment()

    return results


# =========================================================
# SUMMARY
# =========================================================

def percentile(
    values,
    percentile_value,
):
    if not values:
        return 0

    ordered = sorted(
        values
    )

    index = int(
        round(
            (
                percentile_value
                /
                100
            )
            *
            (
                len(
                    ordered
                )
                -
                1
            )
        )
    )

    return ordered[
        index
    ]


def build_summary(
    planning_results,
    disruption_results,
    seed,
):
    total = len(
        planning_results
    )

    full = sum(
        result[
            "outcome"
        ]
        ==
        "fully_rescued"

        for result
        in planning_results
    )

    partial = sum(
        result[
            "outcome"
        ]
        ==
        "partially_rescued"

        for result
        in planning_results
    )

    rejected = sum(
        result[
            "outcome"
        ]
        ==
        "safely_rejected"

        for result
        in planning_results
    )

    valid_plans = sum(
        (
            result[
                "optimizer_status"
            ]
            ==
            "optimal"
        )
        and
        (
            result[
                "safety_violation_count"
            ]
            ==
            0
        )

        for result
        in planning_results
    )

    unsafe_plans = sum(
        result[
            "safety_violation_count"
        ]
        >
        0

        for result
        in planning_results
    )

    total_food = sum(
        float(
            result[
                "quantity_lbs"
            ]
        )
        for result
        in planning_results
    )

    rescued_food = sum(
        float(
            result[
                "rescued_lbs"
            ]
        )
        for result
        in planning_results
    )

    planning_latencies = [
        float(
            result[
                "planning_latency_ms"
            ]
        )
        for result
        in planning_results
    ]

    violation_names = [
        "driver_capacity",
        "driver_double_booking",
        "driver_shift",
        "pickup_deadline",
        "pantry_capacity",
        "donation_accounting_mismatch",
        "route_stop_quantity_mismatch",
        "route_total_mismatch",
        "pantry_total_mismatch",
        "rescued_more_than_donation",
        "negative_rescued_lbs",
        "negative_unrescued_lbs",
        "non_positive_delivery",
    ]

    violation_counts = {}

    for violation_name in (
        violation_names
    ):

        violation_counts[
            violation_name
        ] = sum(
            violation_name
            in (
                result[
                    "safety_violations"
                ]
                .split(
                    "|"
                )
            )

            for result
            in planning_results
        )

    # -----------------------------------------------------
    # DISRUPTIONS
    # -----------------------------------------------------

    disruption_executed = [
        result
        for result
        in disruption_results
        if result[
            "outcome"
        ]
        in (
            "autonomous_recovery",
            "human_escalation",
            "other",
        )
    ]

    disruption_total = len(
        disruption_executed
    )

    autonomous = sum(
        result[
            "outcome"
        ]
        ==
        "autonomous_recovery"

        for result
        in disruption_executed
    )

    escalations = sum(
        result[
            "outcome"
        ]
        ==
        "human_escalation"

        for result
        in disruption_executed
    )

    unsafe_recoveries = sum(
        int(
            result[
                "unsafe_recovery"
            ]
        )
        for result
        in disruption_executed
    )

    disruption_latencies = [
        float(
            result[
                "latency_ms"
            ]
        )
        for result
        in disruption_executed
    ]

    return {
        "benchmark_seed":
            seed,

        "planning": {
            "total_scenarios":
                total,

            "valid_safe_plans":
                valid_plans,

            "valid_safe_plan_rate_pct":
                round(
                    (
                        valid_plans
                        /
                        total
                        *
                        100
                    )
                    if total
                    else 0,
                    2,
                ),

            "fully_rescued":
                full,

            "fully_rescued_pct":
                round(
                    (
                        full
                        /
                        total
                        *
                        100
                    )
                    if total
                    else 0,
                    2,
                ),

            "partially_rescued":
                partial,

            "partially_rescued_pct":
                round(
                    (
                        partial
                        /
                        total
                        *
                        100
                    )
                    if total
                    else 0,
                    2,
                ),

            "safely_rejected":
                rejected,

            "safely_rejected_pct":
                round(
                    (
                        rejected
                        /
                        total
                        *
                        100
                    )
                    if total
                    else 0,
                    2,
                ),

            "weighted_food_rescued_pct":
                round(
                    (
                        rescued_food
                        /
                        total_food
                        *
                        100
                    )
                    if total_food
                    else 0,
                    2,
                ),

            "average_scenario_rescue_pct":
                round(
                    (
                        statistics.mean(
                            [
                                float(
                                    result[
                                        "rescue_rate"
                                    ]
                                )
                                *
                                100

                                for result
                                in planning_results
                            ]
                        )
                    )
                    if planning_results
                    else 0,
                    2,
                ),

            "unsafe_plan_count":
                unsafe_plans,

            "capacity_violations":
                violation_counts[
                    "driver_capacity"
                ]
                +
                violation_counts[
                    "pantry_capacity"
                ],

            "driver_double_booking_violations":
                violation_counts[
                    "driver_double_booking"
                ],

            "driver_shift_violations":
                violation_counts[
                    "driver_shift"
                ],

            "pickup_deadline_violations":
                violation_counts[
                    "pickup_deadline"
                ],

            "all_violation_counts":
                violation_counts,

            "avg_planning_latency_ms":
                round(
                    statistics.mean(
                        planning_latencies
                    )
                    if planning_latencies
                    else 0,
                    2,
                ),

            "median_planning_latency_ms":
                round(
                    statistics.median(
                        planning_latencies
                    )
                    if planning_latencies
                    else 0,
                    2,
                ),

            "p95_planning_latency_ms":
                round(
                    percentile(
                        planning_latencies,
                        95,
                    ),
                    2,
                ),
        },

        "disruptions": {
            "requested_scenarios":
                len(
                    disruption_results
                ),

            "executed_scenarios":
                disruption_total,

            "autonomous_recoveries":
                autonomous,

            "autonomous_recovery_pct":
                round(
                    (
                        autonomous
                        /
                        disruption_total
                        *
                        100
                    )
                    if disruption_total
                    else 0,
                    2,
                ),

            "human_escalations":
                escalations,

            "human_escalation_pct":
                round(
                    (
                        escalations
                        /
                        disruption_total
                        *
                        100
                    )
                    if disruption_total
                    else 0,
                    2,
                ),

            "unsafe_autonomous_recoveries":
                unsafe_recoveries,

            "avg_disruption_latency_ms":
                round(
                    statistics.mean(
                        disruption_latencies
                    )
                    if disruption_latencies
                    else 0,
                    2,
                ),

            "p95_disruption_latency_ms":
                round(
                    percentile(
                        disruption_latencies,
                        95,
                    ),
                    2,
                ),
        },
    }


# =========================================================
# SAVE RESULTS
# =========================================================

def write_csv(
    path,
    rows,
):
    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


def write_markdown_summary(
    summary,
):
    planning = summary[
        "planning"
    ]

    disruptions = summary[
        "disruptions"
    ]

    markdown = f"""# RescueMesh Randomized Benchmark

Benchmark seed: `{summary['benchmark_seed']}`

## Planning Benchmark

| Metric | Result |
|---|---:|
| Randomized planning scenarios | {planning['total_scenarios']} |
| Valid safe plans | {planning['valid_safe_plans']} |
| Valid safe plan rate | {planning['valid_safe_plan_rate_pct']}% |
| Fully rescued | {planning['fully_rescued']} ({planning['fully_rescued_pct']}%) |
| Partially rescued | {planning['partially_rescued']} ({planning['partially_rescued_pct']}%) |
| Safely rejected | {planning['safely_rejected']} ({planning['safely_rejected_pct']}%) |
| Weighted food rescued | {planning['weighted_food_rescued_pct']}% |
| Average scenario rescue rate | {planning['average_scenario_rescue_pct']}% |
| Unsafe plans | {planning['unsafe_plan_count']} |
| Capacity violations | {planning['capacity_violations']} |
| Driver double-booking violations | {planning['driver_double_booking_violations']} |
| Driver shift violations | {planning['driver_shift_violations']} |
| Pickup deadline violations | {planning['pickup_deadline_violations']} |
| Average planning latency | {planning['avg_planning_latency_ms']} ms |
| P95 planning latency | {planning['p95_planning_latency_ms']} ms |

## Disruption Benchmark

| Metric | Result |
|---|---:|
| Disruption scenarios executed | {disruptions['executed_scenarios']} |
| Autonomous recoveries | {disruptions['autonomous_recoveries']} |
| Autonomous recovery rate | {disruptions['autonomous_recovery_pct']}% |
| Human escalations | {disruptions['human_escalations']} |
| Human escalation rate | {disruptions['human_escalation_pct']}% |
| Unsafe autonomous recoveries | {disruptions['unsafe_autonomous_recoveries']} |
| Average disruption response latency | {disruptions['avg_disruption_latency_ms']} ms |
| P95 disruption response latency | {disruptions['p95_disruption_latency_ms']} ms |

## Safety Interpretation

A scenario is counted as an unsafe plan if the
returned deterministic rescue plan violates one or
more independently checked invariants, including
driver capacity, pantry capacity, driver shift,
pickup deadline, double booking, or food quantity
accounting.

A disruption counts as an autonomous recovery only
when RescueMesh produces a full safe in-transit
replacement. Partial in-transit recovery requiring
a decision is counted as a human escalation rather
than autonomous success.
"""

    path = (
        OUTPUT_DIR
        /
        "benchmark_summary.md"
    )

    path.write_text(
        markdown,
        encoding="utf-8",
    )


# =========================================================
# PRINT SUMMARY
# =========================================================

def print_summary(
    summary,
):
    planning = summary[
        "planning"
    ]

    disruptions = summary[
        "disruptions"
    ]

    print(
        "\n"
        +
        "=" * 70
    )

    print(
        "RESCUEMESH FINAL BENCHMARK RESULTS"
    )

    print(
        "=" * 70
    )

    print(
        "\nPLANNING"
    )

    print(
        f"Scenarios: "
        f"{planning['total_scenarios']}"
    )

    print(
        f"Valid safe plan rate: "
        f"{planning['valid_safe_plan_rate_pct']}%"
    )

    print(
        f"Fully rescued: "
        f"{planning['fully_rescued']} "
        f"({planning['fully_rescued_pct']}%)"
    )

    print(
        f"Partially rescued: "
        f"{planning['partially_rescued']} "
        f"({planning['partially_rescued_pct']}%)"
    )

    print(
        f"Safely rejected: "
        f"{planning['safely_rejected']} "
        f"({planning['safely_rejected_pct']}%)"
    )

    print(
        f"Weighted food rescued: "
        f"{planning['weighted_food_rescued_pct']}%"
    )

    print(
        f"Unsafe plans: "
        f"{planning['unsafe_plan_count']}"
    )

    print(
        f"Capacity violations: "
        f"{planning['capacity_violations']}"
    )

    print(
        f"Double-booking violations: "
        f"{planning['driver_double_booking_violations']}"
    )

    print(
        f"Shift violations: "
        f"{planning['driver_shift_violations']}"
    )

    print(
        f"Pickup deadline violations: "
        f"{planning['pickup_deadline_violations']}"
    )

    print(
        f"Average planning latency: "
        f"{planning['avg_planning_latency_ms']} ms"
    )

    print(
        f"P95 planning latency: "
        f"{planning['p95_planning_latency_ms']} ms"
    )

    print(
        "\nDISRUPTIONS"
    )

    print(
        f"Executed: "
        f"{disruptions['executed_scenarios']}"
    )

    print(
        f"Autonomous recovery: "
        f"{disruptions['autonomous_recovery_pct']}%"
    )

    print(
        f"Human escalation: "
        f"{disruptions['human_escalation_pct']}%"
    )

    print(
        f"Unsafe autonomous recoveries: "
        f"{disruptions['unsafe_autonomous_recoveries']}"
    )

    print(
        f"Average disruption latency: "
        f"{disruptions['avg_disruption_latency_ms']} ms"
    )

    print(
        "\nFiles written to:"
    )

    print(
        OUTPUT_DIR
    )


# =========================================================
# MAIN
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description=
            "Run RescueMesh randomized evaluation."
    )

    parser.add_argument(
        "--planning",
        type=int,
        default=250,
        help=
            "Number of randomized planning scenarios.",
    )

    parser.add_argument(
        "--disruptions",
        type=int,
        default=40,
        help=
            "Number of in-transit disruption scenarios.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help=
            "Random seed for reproducibility.",
    )

    args = parser.parse_args()

    rng = random.Random(
        args.seed
    )

    print(
        "Resetting LOCAL RescueMesh demo database..."
    )

    reset_demo_environment()

    snapshot = (
        snapshot_seed_state()
    )

    try:

        planning_results = (
            run_planning_benchmark(
                scenario_count=
                    args.planning,

                rng=
                    rng,

                snapshot=
                    snapshot,
            )
        )

        # Restore the clean baseline before
        # lifecycle disruption experiments.
        restore_seed_state(
            snapshot
        )

        reset_demo_environment()

        disruption_results = (
            run_disruption_benchmark(
                scenario_count=
                    args.disruptions,

                rng=
                    rng,
            )
        )

        summary = build_summary(
            planning_results=
                planning_results,

            disruption_results=
                disruption_results,

            seed=
                args.seed,
        )

        write_csv(
            OUTPUT_DIR
            /
            "planning_scenarios.csv",

            planning_results,
        )

        write_csv(
            OUTPUT_DIR
            /
            "disruption_scenarios.csv",

            disruption_results,
        )

        (
            OUTPUT_DIR
            /
            "benchmark_summary.json"
        ).write_text(
            json.dumps(
                summary,
                indent=2,
            ),
            encoding="utf-8",
        )

        write_markdown_summary(
            summary
        )

        print_summary(
            summary
        )

    finally:

        # Always leave the local demo environment
        # in a clean state even if the benchmark fails.
        restore_seed_state(
            snapshot
        )

        reset_demo_environment()


if __name__ == "__main__":
    main()