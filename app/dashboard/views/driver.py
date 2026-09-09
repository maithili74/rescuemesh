import streamlit as st

from app.dashboard.services.data import (
    get_all_driver_assignments,
)


def pretty_food_type(food_type):
    return (
        food_type
        .replace("_", " ")
        .title()
    )


def get_driver_status(route):
    route_status = route["route_status"]
    operation_status = route["operation_status"]

    stops = route.get(
        "stops",
        [],
    )

    if operation_status == "awaiting_human":
        return "🟡 Needs Human"

    if route_status == "planned":
        return "🔵 Assigned"

    if route_status == "active":
        return "🚗 Heading to Pickup"

    if route_status == "picked_up":

        delivered_count = sum(
            1
            for stop in stops
            if stop["status"]
            in (
                "driver_delivered",
                "completed",
            )
        )

        completed_count = sum(
            1
            for stop in stops
            if stop["status"] == "completed"
        )

        active_stops = [
            stop
            for stop in stops
            if stop["status"] != "cancelled"
        ]

        if (
            active_stops
            and
            completed_count
            ==
            len(active_stops)
        ):
            return "✅ Delivered"

        if delivered_count > 0:
            return "🟠 Delivery In Progress"

        return "🚚 In Transit"

    if route_status == "completed":
        return "✅ Delivered"

    return (
        route_status
        .replace("_", " ")
        .title()
    )


def get_stop_status(stop):
    status = stop["status"]

    labels = {
        "pending":
            "Upcoming",

        "driver_delivered":
            "Delivered — awaiting pantry",

        "completed":
            "✅ Delivered",

        "cancelled":
            "Cancelled",

        "failed":
            "Delivery issue",

        "failed_released":
            "Replanned",
    }

    return labels.get(
        status,
        status.replace(
            "_",
            " ",
        ).title(),
    )


def render_driver_view():

    st.header(
        "Driver Dispatch"
    )

    st.caption(
        "Live pickup and delivery assignments "
        "coordinated by RescueMesh."
    )

    assignments = (
        get_all_driver_assignments()
    )

    if not assignments:
        st.info(
            "No rescue assignments have "
            "been scheduled yet."
        )
        return

    # =====================================================
    # SUMMARY
    # =====================================================

    driver_ids = {
        assignment["driver_id"]
        for assignment in assignments
        if assignment[
            "operation_status"
        ]
        not in (
            "completed",
            "completed_partial",
        )
    }

    active_food = sum(
        float(
            assignment[
                "assigned_lbs"
            ]
        )
        for assignment
        in assignments
        if assignment[
            "operation_status"
        ]
        not in (
            "completed",
            "completed_partial",
        )
    )

    remaining_stops = sum(
        1
        for assignment in assignments
        for stop in assignment["stops"]
        if stop["status"]
        in (
            "pending",
            "driver_delivered",
        )
    )

    metric1, metric2, metric3 = (
        st.columns(3)
    )

    with metric1:
        st.metric(
            "Drivers Scheduled",
            len(driver_ids),
        )

    with metric2:
        st.metric(
            "Food Scheduled",
            f"{active_food:.0f} lbs",
        )

    with metric3:
        st.metric(
            "Stops Remaining",
            remaining_stops,
        )

    st.divider()

    # =====================================================
    # GROUP ROUTES BY OPERATION
    # =====================================================

    operations = {}

    for assignment in assignments:

        operation_id = assignment[
            "operation_id"
        ]

        operations.setdefault(
            operation_id,
            [],
        ).append(
            assignment
        )

    # =====================================================
    # TIMELINE
    # =====================================================

    st.subheader(
        "Pickup & Delivery Schedule"
    )

    for operation_id, routes in operations.items():

        first = routes[0]

        pickup_time = min(
            route["pickup_start"]
            for route in routes
            if route["pickup_start"]
        )

        with st.container(
            border=True
        ):

            # =============================================
            # DONATION HEADER
            # =============================================

            col_time, col_info, col_qty = (
                st.columns(
                    [1, 4, 1]
                )
            )

            with col_time:
                st.markdown(
                    f"### {pickup_time}"
                )

                st.caption(
                    "Pickup"
                )

            with col_info:
                st.markdown(
                    f"### Rescue #{operation_id}"
                )

                st.write(
                    f"**{first['donor_name']}** "
                    f"→ "
                    f"{pretty_food_type(first['food_type'])}"
                )

                st.caption(
                    first[
                        "donor_location"
                    ]
                )

            with col_qty:
                st.markdown(
                    f"### "
                    f"{float(first['donation_quantity_lbs']):.0f} lbs"
                )

            st.divider()

            # =============================================
            # ASSIGNED DRIVERS
            # =============================================

            for route in routes:

                driver_status = (
                    get_driver_status(
                        route
                    )
                )

                driver_left, driver_right = (
                    st.columns(
                        [4, 2]
                    )
                )

                with driver_left:

                    st.markdown(
                        f"#### 🚗 "
                        f"{route['driver_name']}"
                    )

                    st.caption(
                        f"Picking up "
                        f"{float(route['assigned_lbs']):.0f} lbs "
                        f"from {route['donor_name']}"
                    )

                with driver_right:

                    st.markdown(
                        f"**{driver_status}**"
                    )

                # =========================================
                # ROUTE
                # =========================================

                for stop in route[
                    "stops"
                ]:

                    if (
                        stop["status"]
                        ==
                        "cancelled"
                    ):

                        st.caption(
                            f"↳ ~~{stop['pantry_name']}~~ "
                            f"— cancelled during replanning"
                        )

                        continue

                    stop_col1, stop_col2, stop_col3 = (
                        st.columns(
                            [4, 2, 2]
                        )
                    )

                    with stop_col1:

                        st.write(
                            f"↳ **{stop['pantry_name']}**"
                        )

                        st.caption(
                            stop[
                                "pantry_location"
                            ]
                        )

                    with stop_col2:

                        st.write(
                            f"{float(stop['quantity_lbs']):.0f} lbs"
                        )

                        st.caption(
                            f"ETA {stop['eta']}"
                        )

                    with stop_col3:

                        st.write(
                            get_stop_status(
                                stop
                            )
                        )

                st.caption(
                    f"Route: "
                    f"{float(route['distance_miles']):.1f} miles "
                    f"• expected complete "
                    f"{route['route_complete']}"
                )

                st.markdown("---")