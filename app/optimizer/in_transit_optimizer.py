from itertools import permutations

import pulp

from app.database.db import get_connection
from app.services.routing import get_route_matrix


EPSILON = 0.000001
DROPOFF_SERVICE_MINUTES = 5


# =========================================================
# TIME HELPERS
# =========================================================

def _time_to_minutes(value):
    hour, minute = map(
        int,
        value.split(":"),
    )

    return (
        hour * 60
        +
        minute
    )


def _minutes_to_time(value):
    value = int(
        round(value)
    )

    hour = (
        value // 60
    ) % 24

    minute = (
        value % 60
    )

    return (
        f"{hour:02d}:"
        f"{minute:02d}"
    )


# =========================================================
# AVAILABLE COMPATIBLE PANTRIES
# =========================================================

def _get_candidate_pantries(
    food_type,
    excluded_pantry_ids=None,
):
    """
    Return pantries that:

    - accept this food type
    - are currently available
    - still have capacity
    - are not explicitly excluded

    Example exclusion:
        Southside just rejected/failed this delivery,
        so do not immediately send the food there again.
    """

    excluded_pantry_ids = set(
        excluded_pantry_ids
        or []
    )

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.latitude,
                p.longitude,
                p.available_capacity_lbs,
                pn.need_score

            FROM pantries p

            JOIN pantry_needs pn
                ON pn.pantry_id = p.id

            WHERE
                pn.food_type = ?
                AND
                p.status = 'available'
                AND
                p.available_capacity_lbs > 0

            ORDER BY
                pn.need_score DESC,
                p.id ASC
            """,
            (
                food_type,
            ),
        ).fetchall()

    finally:
        conn.close()

    return [
        dict(row)
        for row in rows
        if (
            row["id"]
            not in excluded_pantry_ids
        )
    ]


# =========================================================
# REMAINING FOOD ALLOCATION
# =========================================================

def _optimize_quantities(
    remaining_lbs,
    pantries,
    current_distance_miles,
):
    """
    Optimize ONLY the remaining food.

    Same priority as our main optimizer:

    1. Maximize rescued pounds
    2. Maximize pantry need
    3. Minimize food-distance from driver's current location
    """

    if not pantries:
        return []

    # =====================================================
    # STAGE 1 - MAXIMIZE RESCUED FOOD
    # =====================================================

    problem = pulp.LpProblem(
        "InTransitFoodAllocation",
        pulp.LpMaximize,
    )

    variables = {
        pantry["id"]:
            pulp.LpVariable(
                f"in_transit_pantry_{pantry['id']}",
                lowBound=0,
                upBound=pantry[
                    "available_capacity_lbs"
                ],
            )

        for pantry in pantries
    }

    total_rescue = pulp.lpSum(
        variables.values()
    )

    problem += (
        total_rescue
        <=
        remaining_lbs
    )

    problem += total_rescue

    problem.solve(
        pulp.PULP_CBC_CMD(
            msg=False
        )
    )

    if (
        pulp.LpStatus[
            problem.status
        ]
        !=
        "Optimal"
    ):
        return []

    best_rescue = (
        pulp.value(
            total_rescue
        )
        or 0.0
    )

    # =====================================================
    # STAGE 2 - MAXIMIZE NEED
    # =====================================================

    problem += (
        total_rescue
        >=
        best_rescue
        -
        EPSILON
    )

    need_objective = pulp.lpSum(
        variables[
            pantry["id"]
        ]
        *
        pantry[
            "need_score"
        ]

        for pantry in pantries
    )

    problem.sense = (
        pulp.LpMaximize
    )

    problem.setObjective(
        need_objective
    )

    problem.solve(
        pulp.PULP_CBC_CMD(
            msg=False
        )
    )

    best_need = (
        pulp.value(
            need_objective
        )
        or 0.0
    )

    # =====================================================
    # STAGE 3 - MINIMIZE FOOD-MILES
    # =====================================================

    problem += (
        need_objective
        >=
        best_need
        -
        EPSILON
    )

    distance_objective = (
        pulp.lpSum(
            variables[
                pantry["id"]
            ]
            *
            current_distance_miles[
                pantry["id"]
            ]

            for pantry in pantries
        )
    )

    problem.sense = (
        pulp.LpMinimize
    )

    problem.setObjective(
        distance_objective
    )

    problem.solve(
        pulp.PULP_CBC_CMD(
            msg=False
        )
    )

    if (
        pulp.LpStatus[
            problem.status
        ]
        !=
        "Optimal"
    ):
        return []

    assignments = []

    for pantry in pantries:

        quantity = (
            pulp.value(
                variables[
                    pantry["id"]
                ]
            )
            or 0.0
        )

        quantity = round(
            quantity,
            2,
        )

        if quantity >= 0.01:

            assignments.append(
                {
                    "pantry_id":
                        pantry["id"],

                    "pantry_name":
                        pantry["name"],

                    "quantity_lbs":
                        quantity,

                    "need_score":
                        pantry[
                            "need_score"
                        ],

                    "latitude":
                        pantry[
                            "latitude"
                        ],

                    "longitude":
                        pantry[
                            "longitude"
                        ],
                }
            )

    return assignments


# =========================================================
# FIND BEST ORDER FOR SAME DRIVER
# =========================================================

def _find_best_route(
    current_time,
    driver_available_until,
    assignments,
    route_matrix,
    pantry_matrix_indexes,
):
    """
    One driver is already carrying the food.

    Try all feasible stop orders and select the route
    finishing earliest.

    RescueMesh currently has only a small pantry network,
    so this is fine for the hackathon MVP.
    """

    if not assignments:
        return None

    start_minutes = (
        _time_to_minutes(
            current_time
        )
    )

    shift_end_minutes = (
        _time_to_minutes(
            driver_available_until
        )
    )

    if (
        start_minutes
        >
        shift_end_minutes
    ):
        return None

    best_route = None

    for ordering in permutations(
        assignments
    ):

        clock = float(
            start_minutes
        )

        current_index = 0

        total_distance = 0.0

        stops = []

        feasible = True

        for assignment in ordering:

            pantry_id = (
                assignment[
                    "pantry_id"
                ]
            )

            next_index = (
                pantry_matrix_indexes[
                    pantry_id
                ]
            )

            travel_minutes = (
                route_matrix[
                    "durations_minutes"
                ][
                    current_index
                ][
                    next_index
                ]
            )

            travel_distance = (
                route_matrix[
                    "distances_miles"
                ][
                    current_index
                ][
                    next_index
                ]
            )

            if (
                travel_minutes is None
                or
                travel_distance is None
            ):
                feasible = False
                break

            clock += (
                travel_minutes
            )

            arrival_time = (
                _minutes_to_time(
                    clock
                )
            )

            stops.append(
                {
                    "pantry_id":
                        pantry_id,

                    "pantry_name":
                        assignment[
                            "pantry_name"
                        ],

                    "quantity_lbs":
                        assignment[
                            "quantity_lbs"
                        ],

                    "arrival_time":
                        arrival_time,
                }
            )

            total_distance += (
                travel_distance
            )

            # Driver spends a few minutes unloading.
            clock += (
                DROPOFF_SERVICE_MINUTES
            )

            current_index = (
                next_index
            )

        if not feasible:
            continue

        # Entire remaining route must finish before shift end.
        if clock > shift_end_minutes:
            continue

        candidate = {
            "stops":
                stops,

            "route_complete":
                _minutes_to_time(
                    clock
                ),

            "remaining_distance_miles":
                round(
                    total_distance,
                    2,
                ),

            "duration_minutes":
                clock
                -
                start_minutes,
        }

        if (
            best_route is None
            or
            candidate[
                "duration_minutes"
            ]
            <
            best_route[
                "duration_minutes"
            ]
        ):
            best_route = (
                candidate
            )

    return best_route


# =========================================================
# PUBLIC IN-TRANSIT OPTIMIZER
# =========================================================

def optimize_in_transit_route(
    state,
):
    """
    Optimize food that is STILL physically with the driver.

    This does NOT touch completed deliveries.
    """

    remaining_lbs = float(
        state[
            "remaining_lbs"
        ]
    )

    if remaining_lbs <= 0:

        return {
            "status":
                "nothing_remaining",

            "remaining_lbs":
                0.0,
        }

    excluded = set(
        state.get(
            "excluded_pantry_ids",
            [],
        )
    )

    pantries = (
        _get_candidate_pantries(
            state[
                "food_type"
            ],
            excluded,
        )
    )

    if not pantries:

        return {
            "status":
                "no_feasible_pantry",

            "remaining_lbs":
                remaining_lbs,

            "rescued_lbs":
                0.0,

            "unrescued_lbs":
                remaining_lbs,
        }

    # =====================================================
    # BUILD ORS MATRIX
    #
    # Index 0:
    # driver's CURRENT known location
    #
    # Index 1+:
    # candidate pantries
    # =====================================================

    locations = [
        {
            "latitude":
                state[
                    "current_latitude"
                ],

            "longitude":
                state[
                    "current_longitude"
                ],
        }
    ]

    pantry_matrix_indexes = {}

    for pantry in pantries:

        pantry_matrix_indexes[
            pantry["id"]
        ] = len(
            locations
        )

        locations.append(
            {
                "latitude":
                    pantry[
                        "latitude"
                    ],

                "longitude":
                    pantry[
                        "longitude"
                    ],
            }
        )

    try:
        matrix = get_route_matrix(
            locations
        )

    except Exception as error:

        return {
            "status":
                "routing_error",

            "reason":
                str(error),
        }

    # =====================================================
    # REMOVE UNREACHABLE PANTRIES
    # =====================================================

    reachable_pantries = []

    current_distances = {}

    for pantry in pantries:

        matrix_index = (
            pantry_matrix_indexes[
                pantry["id"]
            ]
        )

        distance = (
            matrix[
                "distances_miles"
            ][0][matrix_index]
        )

        duration = (
            matrix[
                "durations_minutes"
            ][0][matrix_index]
        )

        if (
            distance is None
            or
            duration is None
        ):
            continue

        reachable_pantries.append(
            pantry
        )

        current_distances[
            pantry["id"]
        ] = distance

    if not reachable_pantries:

        return {
            "status":
                "route_infeasible",

            "remaining_lbs":
                remaining_lbs,

            "rescued_lbs":
                0.0,

            "unrescued_lbs":
                remaining_lbs,
        }

    # =====================================================
    # ALLOCATE REMAINING FOOD
    # =====================================================

    assignments = (
        _optimize_quantities(
            remaining_lbs,
            reachable_pantries,
            current_distances,
        )
    )

    rescued_lbs = round(
        sum(
            assignment[
                "quantity_lbs"
            ]

            for assignment
            in assignments
        ),
        2,
    )

    unrescued_lbs = round(
        remaining_lbs
        -
        rescued_lbs,
        2,
    )

        # =====================================================
    # BUILD A REAL FEASIBLE ROUTE FIRST
    #
    # Even if only part of the remaining food can be
    # rescued, we must verify that the proposed route is
    # actually feasible before showing it to a human.
    # =====================================================

    route = _find_best_route(
        state[
            "current_time"
        ],

        state[
            "driver_available_until"
        ],

        assignments,

        matrix,

        pantry_matrix_indexes,
    )

    if route is None:

        return {
            "status":
                "route_infeasible",

            "remaining_lbs":
                remaining_lbs,

            "rescued_lbs":
                rescued_lbs,

            "unrescued_lbs":
                unrescued_lbs,
        }

    # =====================================================
    # PARTIAL RESCUE
    #
    # We found a valid route, but it cannot rescue all
    # remaining food.
    #
    # Do NOT execute automatically.
    # This becomes a human-escalation decision.
    # =====================================================

    if (
        rescued_lbs
        <
        remaining_lbs
        -
        0.01
    ):

        return {
            "status":
                "partial_only",

            "operation_id":
                state[
                    "operation_id"
                ],

            "route_id":
                state[
                    "route_id"
                ],

            "driver_id":
                state[
                    "driver_id"
                ],

            "remaining_lbs":
                remaining_lbs,

            "rescued_lbs":
                rescued_lbs,

            "unrescued_lbs":
                unrescued_lbs,

            "assignments":
                assignments,

            "stops":
                route[
                    "stops"
                ],

            "route_complete":
                route[
                    "route_complete"
                ],

            "remaining_distance_miles":
                route[
                    "remaining_distance_miles"
                ],
        }

    # =====================================================
    # FULL SAFE RECOVERY
    #
    # Every remaining pound can be safely rerouted.
    # RescueMesh can execute this automatically.
    # =====================================================

    return {
        "status":
            "optimal",

        "operation_id":
            state[
                "operation_id"
            ],

        "route_id":
            state[
                "route_id"
            ],

        "driver_id":
            state[
                "driver_id"
            ],

        "remaining_lbs":
            remaining_lbs,

        "rescued_lbs":
            rescued_lbs,

        "unrescued_lbs":
            0.0,

        "assignments":
            assignments,

        "stops":
            route[
                "stops"
            ],

        "route_complete":
            route[
                "route_complete"
            ],

        "remaining_distance_miles":
            route[
                "remaining_distance_miles"
            ],
    }