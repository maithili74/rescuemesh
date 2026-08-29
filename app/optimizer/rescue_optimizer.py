import pulp

from ortools.constraint_solver import (
    pywrapcp,
    routing_enums_pb2,
)

from app.database.db import get_network_state
from app.services.routing import get_route_matrix


# =========================================================
# CONFIGURATION
# =========================================================

PICKUP_SERVICE_MINUTES = 10
DROPOFF_SERVICE_MINUTES = 5
DRIVER_ACTIVATION_PENALTY_MINUTES = 10

EPSILON = 0.000001
WEIGHT_SCALE = 100

# =========================================================
# TIME HELPERS
# =========================================================

def time_to_minutes(time_string):
    """
    Convert:
        "11:30"
    into:
        690
    """

    hours, minutes = map(
        int,
        time_string.split(":"),
    )

    return hours * 60 + minutes


def minutes_to_time(minutes):
    """
    Convert:
        690
    into:
        "11:30"
    """

    minutes = int(
        round(minutes)
    )

    hours = minutes // 60
    mins = minutes % 60

    return f"{hours:02d}:{mins:02d}"


# =========================================================
# BUILD ONE REAL ROAD MATRIX
# =========================================================

def build_network_matrix(
    donation,
    pantries,
    drivers,
):
    """
    Build ONE ORS Matrix request containing:

        donor
        pantries
        drivers

    Instead of repeatedly asking ORS for individual routes.

    Returns:
        matrix
        donor index
        pantry index mapping
        driver index mapping
    """

    locations = []

    # -----------------------------------------------------
    # Index 0 = donor
    # -----------------------------------------------------

    donor_index = 0

    locations.append(
        (
            donation["donor_latitude"],
            donation["donor_longitude"],
        )
    )

    # -----------------------------------------------------
    # Pantry indexes
    # -----------------------------------------------------

    pantry_matrix_index = {}

    for pantry in pantries:

        matrix_index = len(
            locations
        )

        pantry_matrix_index[
            pantry["id"]
        ] = matrix_index

        locations.append(
            (
                pantry["latitude"],
                pantry["longitude"],
            )
        )

    # -----------------------------------------------------
    # Driver indexes
    # -----------------------------------------------------

    driver_matrix_index = {}

    for driver in drivers:

        matrix_index = len(
            locations
        )

        driver_matrix_index[
            driver["id"]
        ] = matrix_index

        locations.append(
            (
                driver["latitude"],
                driver["longitude"],
            )
        )

    matrix = get_route_matrix(
        locations
    )

    return {
        "matrix": matrix,
        "donor_index": donor_index,
        "pantry_matrix_index":
            pantry_matrix_index,
        "driver_matrix_index":
            driver_matrix_index,
    }


# =========================================================
# FILTER DRIVERS USING REAL TRAVEL TIME
# =========================================================

def get_pickup_feasible_drivers(
    donation,
    drivers,
    network,
):
    """
    Check whether each driver can actually reach the donor
    and complete pickup before the donation deadline.

    db.py already checks basic availability overlap.

    This function adds REAL road travel time.
    """

    durations = network[
        "matrix"
    ]["durations_minutes"]

    distances = network[
        "matrix"
    ]["distances_miles"]

    donor_index = network[
        "donor_index"
    ]

    donation_available = time_to_minutes(
        donation["available_at"]
    )

    pickup_deadline = time_to_minutes(
        donation["pickup_deadline"]
    )

    feasible = []

    for driver in drivers:

        driver_index = network[
            "driver_matrix_index"
        ][driver["id"]]

        travel_minutes = durations[
            driver_index
        ][donor_index]

        distance_miles = distances[
            driver_index
        ][donor_index]

        # ORS could theoretically be unable to find
        # a route between two coordinates.
        if travel_minutes is None:
            continue

        driver_start = time_to_minutes(
            driver["available_from"]
        )

        driver_end = time_to_minutes(
            driver["available_until"]
        )

        # Earliest time driver could reach donor.
        earliest_arrival = (
            driver_start
            +
            travel_minutes
        )

        # Food cannot be picked up before it is available.
        pickup_start = max(
            earliest_arrival,
            donation_available,
        )

        pickup_complete = (
            pickup_start
            +
            PICKUP_SERVICE_MINUTES
        )

        # Must finish loading before pickup deadline.
        if pickup_complete > pickup_deadline:
            continue

        # Driver must still be working.
        if pickup_complete > driver_end:
            continue

        driver_copy = dict(
            driver
        )

        driver_copy[
            "driver_to_donor_minutes"
        ] = travel_minutes

        driver_copy[
            "driver_to_donor_miles"
        ] = distance_miles

        driver_copy[
            "earliest_pickup_complete"
        ] = pickup_complete

        feasible.append(
            driver_copy
        )

    return feasible


# =========================================================
# PULP — PANTRY ALLOCATION
# =========================================================

def optimize_pantry_quantities(
    donation,
    pantries,
    drivers,
    network,
):
    """
    Decide HOW MUCH food each pantry should receive.

    PuLP does NOT decide routes.

    It only decides quantities.

    Optimization is lexicographic:

    STEP 1:
        maximize total food rescued

    STEP 2:
        while keeping that maximum rescue,
        maximize community need

    STEP 3:
        while keeping maximum rescue AND need,
        prefer geographically closer pantries
    """

    donation_quantity = donation[
        "quantity_lbs"
    ]

    if not pantries:
        return None

    if not drivers:
        return None

    # -----------------------------------------------------
    # Total transportation capacity
    # -----------------------------------------------------

    total_driver_capacity = sum(
        driver["capacity_lbs"]
        for driver in drivers
    )

    # -----------------------------------------------------
    # Create model
    # -----------------------------------------------------

    problem = pulp.LpProblem(
        "RescueMesh_Pantry_Allocation",
        pulp.LpMaximize,
    )

    allocation = {}

    for pantry in pantries:

        allocation[
            pantry["id"]
        ] = pulp.LpVariable(
            (
                f"pantry_"
                f"{pantry['id']}"
            ),
            lowBound=0,
            upBound=pantry[
                "available_capacity_lbs"
            ],
            cat="Continuous",
        )

    # -----------------------------------------------------
    # Total rescued
    # -----------------------------------------------------

    total_rescued = pulp.lpSum(
        allocation.values()
    )

    # Cannot rescue more food than exists.
    problem += (
        total_rescued
        <= donation_quantity,
        "DonationQuantity",
    )

    # Cannot plan more food than all available
    # drivers together can transport.
    problem += (
        total_rescued
        <= total_driver_capacity,
        "TotalDriverCapacity",
    )

    solver = pulp.PULP_CBC_CMD(
        msg=False
    )

    # =====================================================
    # STAGE 1
    # MAXIMUM FOOD RESCUED
    # =====================================================

    problem.setObjective(
        total_rescued
    )

    problem.sense = (
        pulp.LpMaximize
    )

    problem.solve(
        solver
    )

    if (
        pulp.LpStatus[
            problem.status
        ]
        != "Optimal"
    ):

        return None

    maximum_rescue = pulp.value(
        total_rescued
    )

    # Lock maximum rescue.
    problem += (
        total_rescued
        >= maximum_rescue
        - EPSILON,
        "KeepMaximumRescue",
    )

    # =====================================================
    # STAGE 2
    # MAXIMUM COMMUNITY NEED
    # =====================================================

    need_value = pulp.lpSum(

        allocation[
            pantry["id"]
        ]
        *
        pantry["need_score"]

        for pantry in pantries
    )

    problem.setObjective(
        need_value
    )

    problem.sense = (
        pulp.LpMaximize
    )

    problem.solve(
        solver
    )

    maximum_need = pulp.value(
        need_value
    )

    # Lock need quality.
    problem += (
        need_value
        >= maximum_need
        - EPSILON,
        "KeepMaximumNeed",
    )

    # =====================================================
    # STAGE 3
    # MINIMIZE FOOD-MILES
    # =====================================================

    distances = network[
        "matrix"
    ]["distances_miles"]

    donor_index = network[
        "donor_index"
    ]

    pantry_matrix_index = network[
        "pantry_matrix_index"
    ]

    distance_value = pulp.lpSum(

        allocation[
            pantry["id"]
        ]
        *
        distances[
            donor_index
        ][
            pantry_matrix_index[
                pantry["id"]
            ]
        ]

        for pantry in pantries
    )

    problem.setObjective(
        distance_value
    )

    problem.sense = (
        pulp.LpMinimize
    )

    problem.solve(
        solver
    )

    # -----------------------------------------------------
    # Read final allocation
    # -----------------------------------------------------

    assignments = []

    for pantry in pantries:

        quantity = (
            allocation[
                pantry["id"]
            ].value()
            or 0
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

                    "latitude":
                        pantry["latitude"],

                    "longitude":
                        pantry["longitude"],

                    "need_score":
                        pantry["need_score"],

                    "assigned_lbs":
                        quantity,

                    "matrix_index":
                        pantry_matrix_index[
                            pantry["id"]
                        ],
                }
            )

    return assignments


# =========================================================
# CREATE DELIVERY JOBS FOR OR-TOOLS
# =========================================================

def create_delivery_jobs(
    pantry_assignments,
    drivers,
):
    """
    Convert pantry allocations into routing jobs.

    A pantry is kept as ONE delivery job whenever at least
    one available driver can carry that entire allocation.

    We split a pantry delivery only when the allocation is
    larger than the largest available vehicle.
    """

    if not drivers:
        return []

    largest_capacity = max(
        driver["capacity_lbs"]
        for driver in drivers
    )

    jobs = []

    job_id = 1

    for pantry in pantry_assignments:

        remaining = pantry[
            "assigned_lbs"
        ]

        while remaining > EPSILON:

            quantity = min(
                largest_capacity,
                remaining,
            )

            jobs.append(
                {
                    "job_id":
                        job_id,

                    "pantry_id":
                        pantry[
                            "pantry_id"
                        ],

                    "pantry_name":
                        pantry[
                            "pantry_name"
                        ],

                    "need_score":
                        pantry[
                            "need_score"
                        ],

                    "quantity_lbs":
                        round(
                            quantity,
                            2,
                        ),

                    "matrix_index":
                        pantry[
                            "matrix_index"
                        ],
                }
            )

            remaining -= quantity

            job_id += 1

    return jobs


# =========================================================
# OR-TOOLS — MULTI-STOP DRIVER ROUTING
# =========================================================

def optimize_driver_routes(
    donation,
    pantry_assignments,
    drivers,
    network,
):
    """
    Assign drivers and determine efficient multi-stop routes.

    A driver may visit any number of pantries as long as:

    - total assigned food <= vehicle capacity
    - pickup is completed before the donation deadline
    - the entire route finishes before the driver's shift ends

    OR-Tools decides:
        - which driver is used
        - which pantries that driver visits
        - the order of those pantry stops

    ORS provides:
        - real road travel times
        - real road distances

    ETAs are calculated manually from the ORS matrix after
    OR-Tools chooses the route order.
    """

    if not pantry_assignments:
        return None

    if not drivers:
        return None

    # =====================================================
    # BUILD DELIVERY JOBS
    # =====================================================
    #
    # IMPORTANT:
    #
    # Earlier, we split deliveries using the SMALLEST
    # driver's capacity. That caused things such as:
    #
    # Southside 150 lbs
    #     ↓
    # 60 + 60 + 30
    #
    # which made OR-Tools sometimes visit Southside twice.
    #
    # Instead, keep a pantry as ONE delivery whenever
    # possible.
    #
    # Only split when the pantry allocation is larger than
    # the largest available vehicle.
    # =====================================================

    largest_driver_capacity = max(
        driver["capacity_lbs"]
        for driver in drivers
    )

    jobs = []

    job_id = 1

    for pantry in pantry_assignments:

        remaining = pantry[
            "assigned_lbs"
        ]

        while remaining > EPSILON:

            quantity = min(
                remaining,
                largest_driver_capacity,
            )

            jobs.append(
                {
                    "job_id":
                        job_id,

                    "pantry_id":
                        pantry["pantry_id"],

                    "pantry_name":
                        pantry["pantry_name"],

                    "need_score":
                        pantry["need_score"],

                    "quantity_lbs":
                        round(
                            quantity,
                            2,
                        ),

                    "matrix_index":
                        pantry["matrix_index"],
                }
            )

            remaining -= quantity

            job_id += 1

    if not jobs:
        return None

    # =====================================================
    # CREATE OR-TOOLS ROUTING MODEL
    # =====================================================

    num_vehicles = len(
        drivers
    )

    # Node 0:
    # donor
    #
    # Node 1..N:
    # pantry delivery jobs
    #
    # Final node:
    # dummy end node
    #
    # The dummy end means drivers do NOT need to return
    # to the donor after their final delivery.

    DONOR_NODE = 0

    END_NODE = (
        len(jobs)
        + 1
    )

    number_of_nodes = (
        len(jobs)
        + 2
    )

    starts = [
        DONOR_NODE
        for _ in drivers
    ]

    ends = [
        END_NODE
        for _ in drivers
    ]

    manager = (
        pywrapcp.RoutingIndexManager(
            number_of_nodes,
            num_vehicles,
            starts,
            ends,
        )
    )

    routing = (
        pywrapcp.RoutingModel(
            manager
        )
    )

    # =====================================================
    # CONNECT ROUTING NODES TO ORS MATRIX LOCATIONS
    # =====================================================

    donor_matrix_index = network[
        "donor_index"
    ]

    node_matrix_index = {
        DONOR_NODE:
            donor_matrix_index
    }

    job_by_node = {}

    for node, job in enumerate(
        jobs,
        start=1,
    ):

        node_matrix_index[
            node
        ] = job[
            "matrix_index"
        ]

        job_by_node[
            node
        ] = job

    # Dummy end has no physical location.
    node_matrix_index[
        END_NODE
    ] = None

    durations = network[
        "matrix"
    ][
        "durations_minutes"
    ]

    distances = network[
        "matrix"
    ][
        "distances_miles"
    ]

    # =====================================================
    # TRAVEL-TIME CALLBACK
    # =====================================================
    #
    # OR-Tools uses this while searching for the best route.
    #
    # Route:
    #
    # donor
    #   ↓ drive
    # pantry A
    #   ↓ unload 5 min
    #   ↓ drive
    # pantry B
    #   ↓ unload 5 min
    # etc.
    #
    # Pickup service is NOT included here because the route
    # begins after the driver has already loaded the food.
    # =====================================================

    def time_callback(
        from_index,
        to_index,
    ):

        from_node = (
            manager.IndexToNode(
                from_index
            )
        )

        to_node = (
            manager.IndexToNode(
                to_index
            )
        )

        # ---------------------------------------------
        # Finished route
        # ---------------------------------------------

        if to_node == END_NODE:

            # Empty vehicle route:
            # donor -> end
            if from_node == DONOR_NODE:
                return 0

            # Final pantry still requires unloading.
            return int(
                DROPOFF_SERVICE_MINUTES
                * 60
            )

        from_matrix = (
            node_matrix_index[
                from_node
            ]
        )

        to_matrix = (
            node_matrix_index[
                to_node
            ]
        )

        duration = durations[
            from_matrix
        ][
            to_matrix
        ]

        if duration is None:

            # Very large value makes this road connection
            # effectively impossible.
            return 10_000_000

        travel_seconds = int(
            round(
                duration
                * 60
            )
        )

        service_seconds = 0

        # If leaving a pantry, account for unloading there.
        if from_node != DONOR_NODE:

            same_location = (
                from_matrix
                ==
                to_matrix
            )

            # If two split jobs happen to represent the same
            # pantry, do not charge unloading twice between
            # those internal jobs.
            if not same_location:

                service_seconds = int(
                    DROPOFF_SERVICE_MINUTES
                    * 60
                )

        return (
            travel_seconds
            +
            service_seconds
        )

    time_callback_index = (
        routing.RegisterTransitCallback(
            time_callback
        )
    )

    # Main routing cost:
    # minimize travel time.
    routing.SetArcCostEvaluatorOfAllVehicles(
        time_callback_index
    )

    # =====================================================
    # DRIVER ACTIVATION COST
    # =====================================================
    #
    # Without this, OR-Tools may happily use several drivers
    # when one multi-stop driver could do the same work.
    #
    # This encourages:
    #
    # James:
    # donor -> pantry A -> pantry B -> pantry C
    #
    # instead of:
    #
    # Sarah -> A
    # Lisa  -> B
    # Mike  -> C
    # =====================================================

    for vehicle_id, driver in enumerate(
        drivers
    ):

        driver_to_donor_seconds = int(
            round(
                driver[
                    "driver_to_donor_minutes"
                ]
                * 60
            )
        )

        activation_seconds = int(
            DRIVER_ACTIVATION_PENALTY_MINUTES
            * 60
        )

        routing.SetFixedCostOfVehicle(
            (
                driver_to_donor_seconds
                +
                activation_seconds
            ),
            vehicle_id,
        )

    # =====================================================
    # VEHICLE CAPACITY
    # =====================================================

    demands = [
        0
        for _ in range(
            number_of_nodes
        )
    ]

    for node, job in (
        job_by_node.items()
    ):

        demands[
            node
        ] = int(
            round(
                job[
                    "quantity_lbs"
                ]
                * WEIGHT_SCALE
            )
        )

    def demand_callback(
        from_index,
    ):

        node = (
            manager.IndexToNode(
                from_index
            )
        )

        return demands[
            node
        ]

    demand_callback_index = (
        routing.RegisterUnaryTransitCallback(
            demand_callback
        )
    )

    vehicle_capacities = [
        int(
            round(
                driver[
                    "capacity_lbs"
                ]
                * WEIGHT_SCALE
            )
        )

        for driver in drivers
    ]

    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        vehicle_capacities,
        True,
        "Capacity",
    )

    # =====================================================
    # ROUTE TIME CONSTRAINT
    # =====================================================

    routing.AddDimension(
        time_callback_index,

        # No waiting needed after leaving donor.
        0,

        # Maximum route time horizon.
        24 * 60 * 60,

        # Different drivers have different possible
        # starting times.
        False,

        "Time",
    )

    time_dimension = (
        routing.GetDimensionOrDie(
            "Time"
        )
    )

    pickup_deadline_seconds = int(
        time_to_minutes(
            donation[
                "pickup_deadline"
            ]
        )
        * 60
    )

    for vehicle_id, driver in enumerate(
        drivers
    ):

        start_index = (
            routing.Start(
                vehicle_id
            )
        )

        end_index = (
            routing.End(
                vehicle_id
            )
        )

        # earliest_pickup_complete was calculated earlier
        # using:
        #
        # driver availability
        # +
        # drive to donor
        # +
        # donation availability
        # +
        # 10-minute pickup/loading time

        earliest_route_start_seconds = int(
            round(
                driver[
                    "earliest_pickup_complete"
                ]
                * 60
            )
        )

        driver_end_seconds = int(
            time_to_minutes(
                driver[
                    "available_until"
                ]
            )
            * 60
        )

        # Route starts AFTER pickup is complete.
        #
        # The latest allowed route start is therefore the
        # donation's pickup deadline.

        time_dimension.CumulVar(
            start_index
        ).SetRange(
            earliest_route_start_seconds,
            pickup_deadline_seconds,
        )

        # Entire delivery route must finish before the
        # driver stops being available.

        time_dimension.CumulVar(
            end_index
        ).SetRange(
            0,
            driver_end_seconds,
        )

        # Prefer starting and finishing as early as possible.

        routing.AddVariableMinimizedByFinalizer(
            time_dimension.CumulVar(
                start_index
            )
        )

        routing.AddVariableMinimizedByFinalizer(
            time_dimension.CumulVar(
                end_index
            )
        )

    # =====================================================
    # SOLVE ROUTING PROBLEM
    # =====================================================

    search = (
        pywrapcp
        .DefaultRoutingSearchParameters()
    )

    search.first_solution_strategy = (
        routing_enums_pb2
        .FirstSolutionStrategy
        .PATH_CHEAPEST_ARC
    )

    search.local_search_metaheuristic = (
        routing_enums_pb2
        .LocalSearchMetaheuristic
        .GUIDED_LOCAL_SEARCH
    )

    search.time_limit.FromSeconds(
        5
    )

    solution = (
        routing.SolveWithParameters(
            search
        )
    )

    if not solution:
        return None

    # =====================================================
    # READ ROUTES
    # =====================================================
    #
    # IMPORTANT CHANGE:
    #
    # We do NOT use the OR-Tools CumulVar values to print
    # pantry ETAs.
    #
    # OR-Tools chooses the STOP ORDER.
    #
    # Then we walk through that order ourselves using the
    # real ORS travel-time matrix.
    #
    # That makes the output easy to understand and verify.
    # =====================================================

    routes = []

    total_distance = 0.0

    total_routed_food = 0.0

    for vehicle_id, driver in enumerate(
        drivers
    ):

        start_index = (
            routing.Start(
                vehicle_id
            )
        )

        first_index = (
            solution.Value(
                routing.NextVar(
                    start_index
                )
            )
        )

        # ---------------------------------------------
        # UNUSED DRIVER
        # ---------------------------------------------
        #
        # This is more reliable than relying on
        # routing.IsVehicleUsed().
        #
        # If start goes directly to end, this driver has
        # no deliveries.

        if routing.IsEnd(
            first_index
        ):
            continue

        # =================================================
        # PICKUP TIMING
        # =================================================

        # Use the earliest physically possible pickup.
        #
        # We already know this driver can reach the donor in
        # time because get_pickup_feasible_drivers() checked
        # that earlier.

        pickup_complete = (
            driver[
                "earliest_pickup_complete"
            ]
        )

        pickup_start = (
            pickup_complete
            -
            PICKUP_SERVICE_MINUTES
        )

        leave_for_donor = (
            pickup_start
            -
            driver[
                "driver_to_donor_minutes"
            ]
        )

        # =================================================
        # BEGIN DELIVERY ROUTE
        # =================================================

        current_time = (
            pickup_complete
        )

        previous_matrix = (
            donor_matrix_index
        )

        route_distance = (
            driver[
                "driver_to_donor_miles"
            ]
        )

        driver_load = 0.0

        stops = []

        index = first_index

        # =================================================
        # FOLLOW OR-TOOLS' CHOSEN STOP ORDER
        # =================================================

        while not routing.IsEnd(
            index
        ):

            node = (
                manager.IndexToNode(
                    index
                )
            )

            job = job_by_node[
                node
            ]

            current_matrix = (
                node_matrix_index[
                    node
                ]
            )

            # =============================================
            # REAL TRAVEL TIME FROM ORS
            # =============================================

            leg_duration = durations[
                previous_matrix
            ][
                current_matrix
            ]

            if leg_duration is None:

                raise RuntimeError(
                    "ORS could not calculate "
                    "travel time for a route leg."
                )

            current_time += (
                leg_duration
            )

            arrival_time = (
                current_time
            )

            # =============================================
            # REAL ROAD DISTANCE
            # =============================================

            leg_distance = distances[
                previous_matrix
            ][
                current_matrix
            ]

            if leg_distance is None:

                raise RuntimeError(
                    "ORS could not calculate "
                    "distance for a route leg."
                )

            route_distance += (
                leg_distance
            )

            # =============================================
            # DELIVERY QUANTITY
            # =============================================

            quantity = (
                job[
                    "quantity_lbs"
                ]
            )

            driver_load += (
                quantity
            )

            total_routed_food += (
                quantity
            )

            # =============================================
            # SAME-PANTRY SAFETY
            # =============================================
            #
            # Usually there will now be only ONE job per
            # pantry.
            #
            # But if a huge pantry allocation had to be
            # split and two chunks appear consecutively,
            # combine them into one visible stop.

            if (
                stops
                and
                stops[-1][
                    "pantry_id"
                ]
                ==
                job[
                    "pantry_id"
                ]
            ):

                stops[-1][
                    "quantity_lbs"
                ] = round(
                    stops[-1][
                        "quantity_lbs"
                    ]
                    +
                    quantity,
                    2,
                )

                # Same physical location.
                # Do NOT add another unload period.

            else:

                stops.append(
                    {
                        "pantry_id":
                            job[
                                "pantry_id"
                            ],

                        "pantry_name":
                            job[
                                "pantry_name"
                            ],

                        "quantity_lbs":
                            round(
                                quantity,
                                2,
                            ),

                        "arrival_time":
                            minutes_to_time(
                                arrival_time
                            ),
                    }
                )

                # Spend 5 minutes unloading at this pantry.

                current_time += (
                    DROPOFF_SERVICE_MINUTES
                )

            previous_matrix = (
                current_matrix
            )

            index = (
                solution.Value(
                    routing.NextVar(
                        index
                    )
                )
            )

        # =================================================
        # ROUTE FINISHED
        # =================================================

        route_complete = (
            current_time
        )

        # =================================================
        # VALIDATE DRIVER CAPACITY
        # =================================================

        if (
            driver_load
            >
            driver[
                "capacity_lbs"
            ]
            +
            0.01
        ):

            raise RuntimeError(
                f"Capacity validation failed for "
                f"{driver['name']}: "
                f"{driver_load} lbs assigned but "
                f"capacity is "
                f"{driver['capacity_lbs']} lbs."
            )

        # =================================================
        # VALIDATE PICKUP DEADLINE
        # =================================================

        pickup_deadline = (
            time_to_minutes(
                donation[
                    "pickup_deadline"
                ]
            )
        )

        if (
            pickup_complete
            >
            pickup_deadline
            +
            EPSILON
        ):

            raise RuntimeError(
                f"{driver['name']} cannot "
                f"complete pickup before the "
                f"donation deadline."
            )

        # =================================================
        # VALIDATE DRIVER SHIFT
        # =================================================

        driver_end = (
            time_to_minutes(
                driver[
                    "available_until"
                ]
            )
        )

        if (
            route_complete
            >
            driver_end
            +
            EPSILON
        ):

            raise RuntimeError(
                f"Route for {driver['name']} "
                f"finishes at "
                f"{minutes_to_time(route_complete)}, "
                f"but their shift ends at "
                f"{driver['available_until']}."
            )

        # =================================================
        # SAVE ROUTE
        # =================================================

        routes.append(
            {
                "driver_id":
                    driver["id"],

                "driver_name":
                    driver["name"],

                "capacity_lbs":
                    driver[
                        "capacity_lbs"
                    ],

                "assigned_lbs":
                    round(
                        driver_load,
                        2,
                    ),

                "leave_for_donor":
                    minutes_to_time(
                        leave_for_donor
                    ),

                "pickup_start":
                    minutes_to_time(
                        pickup_start
                    ),

                "pickup_complete":
                    minutes_to_time(
                        pickup_complete
                    ),

                "route_complete":
                    minutes_to_time(
                        route_complete
                    ),

                "distance_miles":
                    round(
                        route_distance,
                        2,
                    ),

                "stops":
                    stops,
            }
        )

        total_distance += (
            route_distance
        )

    # =====================================================
    # FINAL FOOD VALIDATION
    # =====================================================

    expected_food = sum(
        assignment[
            "assigned_lbs"
        ]
        for assignment
        in pantry_assignments
    )

    if abs(
        total_routed_food
        -
        expected_food
    ) > 0.1:

        raise RuntimeError(
            "Routing validation failed: "
            f"PuLP allocated "
            f"{expected_food} lbs, "
            f"but driver routes contain "
            f"{total_routed_food} lbs."
        )

    # =====================================================
    # FINAL PANTRY VALIDATION
    # =====================================================
    #
    # Make sure every pound sent to each pantry matches
    # what PuLP planned.

    expected_by_pantry = {}

    for assignment in (
        pantry_assignments
    ):

        expected_by_pantry[
            assignment[
                "pantry_id"
            ]
        ] = assignment[
            "assigned_lbs"
        ]

    routed_by_pantry = {}

    for route in routes:

        for stop in route[
            "stops"
        ]:

            pantry_id = stop[
                "pantry_id"
            ]

            routed_by_pantry[
                pantry_id
            ] = (
                routed_by_pantry.get(
                    pantry_id,
                    0.0,
                )
                +
                stop[
                    "quantity_lbs"
                ]
            )

    for (
        pantry_id,
        expected_quantity,
    ) in expected_by_pantry.items():

        routed_quantity = (
            routed_by_pantry.get(
                pantry_id,
                0.0,
            )
        )

        if abs(
            routed_quantity
            -
            expected_quantity
        ) > 0.1:

            raise RuntimeError(
                "Pantry routing validation failed: "
                f"pantry {pantry_id} was allocated "
                f"{expected_quantity} lbs but "
                f"received {routed_quantity} lbs "
                f"in the routes."
            )

    return {
        "routes":
            routes,

        "total_distance_miles":
            round(
                total_distance,
                2,
            ),
    }

# =========================================================
# COMPLETE RESCUEMESH OPTIMIZER
# =========================================================

def optimize_rescue_plan(
    donation_id,
):
    """
    Full RescueMesh optimization pipeline.

    1. Load current state.
    2. Get real road matrix.
    3. Remove drivers who cannot reach donor in time.
    4. PuLP selects pantry quantities.
    5. OR-Tools assigns drivers and multi-stop routes.
    """

    state = get_network_state(
        donation_id
    )

    if state is None:

        return {
            "status": "error",
            "message":
                f"Donation {donation_id} does not exist.",
        }

    donation = state[
        "donation"
    ]

    pantries = state[
        "compatible_pantries"
    ]

    drivers = state[
        "eligible_drivers"
    ]

    quantity = donation[
        "quantity_lbs"
    ]

    if not pantries:

        return {
            "status":
                "no_feasible_plan",

            "reason":
                "No compatible pantry is available.",

            "rescued_lbs": 0,

            "unrescued_lbs":
                quantity,
        }

    if not drivers:

        return {
            "status":
                "no_feasible_plan",

            "reason":
                "No driver overlaps the donation window.",

            "rescued_lbs": 0,

            "unrescued_lbs":
                quantity,
        }

    # -----------------------------------------------------
    # Real road data
    # -----------------------------------------------------

    try:

        network = build_network_matrix(
            donation,
            pantries,
            drivers,
        )

    except Exception as error:

        return {
            "status":
                "routing_error",

            "reason":
                str(error),
        }

    # -----------------------------------------------------
    # Real pickup feasibility
    # -----------------------------------------------------

    feasible_drivers = (
        get_pickup_feasible_drivers(
            donation,
            drivers,
            network,
        )
    )

    if not feasible_drivers:

        return {
            "status":
                "no_feasible_plan",

            "reason":
                "No driver can reach the donor before the pickup deadline.",

            "rescued_lbs": 0,

            "unrescued_lbs":
                quantity,
        }

    # -----------------------------------------------------
    # PuLP allocation
    # -----------------------------------------------------

    pantry_assignments = (
        optimize_pantry_quantities(
            donation,
            pantries,
            feasible_drivers,
            network,
        )
    )

    if not pantry_assignments:

        return {
            "status":
                "no_feasible_plan",

            "reason":
                "No pantry allocation could be created.",

            "rescued_lbs": 0,

            "unrescued_lbs":
                quantity,
        }

    planned_rescue = sum(
        assignment[
            "assigned_lbs"
        ]
        for assignment
        in pantry_assignments
    )

    # -----------------------------------------------------
    # OR-Tools routes
    # -----------------------------------------------------

    routing_result = (
        optimize_driver_routes(
            donation,
            pantry_assignments,
            feasible_drivers,
            network,
        )
    )

    if routing_result is None:

        return {
            "status":
                "routing_infeasible",

            "reason":
                (
                    "Pantry quantities were feasible, "
                    "but no driver routing plan could "
                    "satisfy all capacity/time constraints."
                ),

            "planned_rescue_lbs":
                planned_rescue,
        }

    rescued_lbs = sum(
        route[
            "assigned_lbs"
        ]

        for route in routing_result[
            "routes"
        ]
    )

    unrescued = max(
        0,
        quantity
        -
        rescued_lbs,
    )

    return {
        "status":
            "optimal",

        "donation_id":
            donation_id,

        "donor_name":
            donation[
                "donor_name"
            ],

        "food_type":
            donation[
                "food_type"
            ],

        "donation_quantity_lbs":
            quantity,

        "rescued_lbs":
            round(
                rescued_lbs,
                2,
            ),

        "unrescued_lbs":
            round(
                unrescued,
                2,
            ),

        "rescue_rate":
            round(
                rescued_lbs
                /
                quantity,
                4,
            ),

        "drivers_used":
            len(
                routing_result[
                    "routes"
                ]
            ),

        "total_distance_miles":
            routing_result[
                "total_distance_miles"
            ],

        "pantry_assignments":
            pantry_assignments,

        "driver_routes":
            routing_result[
                "routes"
            ],
    }


# =========================================================
# MANUAL TEST
# =========================================================

if __name__ == "__main__":

    result = optimize_rescue_plan(
        1
    )

    print(
        "\n"
        + "=" * 65
    )

    print(
        "RESCUEMESH - MULTI-STOP RESCUE OPTIMIZER"
    )

    print(
        "=" * 65
    )

    if result[
        "status"
    ] != "optimal":

        print(
            result
        )

    else:

        print(
            f"\nDonation: "
            f"{result['donation_quantity_lbs']} lbs "
            f"{result['food_type']}"
        )

        print(
            f"Donor: "
            f"{result['donor_name']}"
        )

        # =============================================
        # Pantry allocation
        # =============================================

        print(
            "\nPANTRY ALLOCATION"
        )

        for pantry in result[
            "pantry_assignments"
        ]:

            print(
                f"  {pantry['pantry_name']}"
                f" -> "
                f"{pantry['assigned_lbs']} lbs"
                f" | Need: "
                f"{pantry['need_score']}"
            )

        # =============================================
        # Driver routes
        # =============================================

        print(
            "\nDRIVER ROUTES"
        )

        for route in result[
            "driver_routes"
        ]:

            print(
                f"\n  🚚 {route['driver_name']}"
            )

            print(
                f"     Load: "
                f"{route['assigned_lbs']} / "
                f"{route['capacity_lbs']} lbs"
            )

            print(
                f"     Leave for donor: "
                f"{route['leave_for_donor']}"
            )

            print(
                f"     Pickup: "
                f"{route['pickup_start']}"
                f" - "
                f"{route['pickup_complete']}"
            )

            for number, stop in enumerate(
                route["stops"],
                start=1,
            ):

                print(
                    f"     Stop {number}: "
                    f"{stop['pantry_name']}"
                    f" -> "
                    f"{stop['quantity_lbs']} lbs"
                    f" | ETA "
                    f"{stop['arrival_time']}"
                )

            print(
                f"     Route complete: "
                f"{route['route_complete']}"
            )

            print(
                f"     Distance: "
                f"{route['distance_miles']} miles"
            )

        # =============================================
        # Summary
        # =============================================

        print(
            "\nSUMMARY"
        )

        print(
            f"  Rescued: "
            f"{result['rescued_lbs']} lbs"
        )

        print(
            f"  Unrescued: "
            f"{result['unrescued_lbs']} lbs"
        )

        print(
            f"  Rescue rate: "
            f"{result['rescue_rate'] * 100:.1f}%"
        )

        print(
            f"  Drivers used: "
            f"{result['drivers_used']}"
        )

        print(
            f"  Total distance: "
            f"{result['total_distance_miles']} miles"
        )