from app.optimizer.rescue_optimizer import optimize_rescue_plan


for donation_id in range(1, 19):

    print("\n")
    print("=" * 70)
    print(f"DONATION #{donation_id}")
    print("=" * 70)

    try:
        result = optimize_rescue_plan(
            donation_id
        )

        print(
            "Status:",
            result.get("status")
        )

        if result.get("status") == "optimal":

            print(
                "Food:",
                result["food_type"]
            )

            print(
                "Quantity:",
                result[
                    "donation_quantity_lbs"
                ]
            )

            print(
                "Rescued:",
                result["rescued_lbs"]
            )

            print(
                "Unrescued:",
                result["unrescued_lbs"]
            )

            print(
                "Drivers:",
                result["drivers_used"]
            )

            print(
                "Distance:",
                result[
                    "total_distance_miles"
                ]
            )

            print("\nPantries:")

            for pantry in result[
                "pantry_assignments"
            ]:

                print(
                    " ",
                    pantry["pantry_name"],
                    "->",
                    pantry["assigned_lbs"],
                    "lbs"
                )

            print("\nRoutes:")

            for route in result[
                "driver_routes"
            ]:

                print(
                    f"\n  {route['driver_name']} "
                    f"({route['assigned_lbs']} / "
                    f"{route['capacity_lbs']} lbs)"
                )

                print(
                    "  Pickup:",
                    route["pickup_start"],
                    "-",
                    route["pickup_complete"],
                )

                for stop in route[
                    "stops"
                ]:

                    print(
                        "   ->",
                        stop["pantry_name"],
                        stop["quantity_lbs"],
                        "lbs | ETA",
                        stop["arrival_time"],
                    )

                print(
                    "  Complete:",
                    route[
                        "route_complete"
                    ]
                )

        else:

            print(
                "Reason:",
                result.get(
                    "reason",
                    result.get("message")
                )
            )

    except Exception as error:

        print(
            "ERROR:",
            error
        )