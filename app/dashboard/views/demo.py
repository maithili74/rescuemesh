import streamlit as st

from app.dashboard.services.demo_reset import (
    reset_demo_environment,
)

from app.dashboard.services.actions import (
    accept_driver_assignment,
    confirm_driver_pickup,
    mark_driver_delivery,
)

from app.dashboard.services.data import (
    get_operations_dashboard,
)
from app.dashboard.views.disruptions import (
    render_disruption_controls,
)

def pretty_food_type(food_type):
    return (
        food_type
        .replace("_", " ")
        .title()
    )


def stop_status_label(status):
    labels = {
        "pending":
            "Upcoming",

        "driver_delivered":
            "🟠 Driver reported delivered",

        "completed":
            "✅ Pantry confirmed",

        "cancelled":
            "Replanned",

        "failed":
            "Delivery issue",

        "failed_released":
            "Replanned",
    }

    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


def render_demo_view():

    st.header(
        "🧪 Demo Event Simulator"
    )

    st.warning(
        "Hackathon demo tool — these controls simulate "
        "events that would normally come from a driver's "
        "phone, SMS link, or lightweight mobile interface."
    )

    st.caption(
        "Every button below uses the real RescueMesh "
        "backend event-processing logic. "
        "No UI-only state changes are being faked."
    )

    st.divider()
    
    # =====================================================
    # DEMO RESET
    # =====================================================

    with st.expander(
        "🔄 Reset Demo Environment",
        expanded=False,
    ):

        st.write(
            "Restore RescueMesh to the clean seeded "
            "starting state before a judge demo or "
            "video recording."
        )

        st.warning(
            "This deletes the current demo operations, "
            "routes, delivery stops, events and "
            "escalations from the local RescueMesh "
            "database."
        )

        confirm_reset = (
            st.checkbox(
                "I understand that current demo "
                "activity will be cleared.",
                key=
                    "confirm_demo_reset",
            )
        )

        if st.button(
            "Reset RescueMesh Demo",
            type="primary",
            use_container_width=True,
            disabled=
                not confirm_reset,
            key=
                "reset_rescuemesh_demo",
        ):

            try:

                with st.spinner(
                    "Restoring clean demo state..."
                ):

                    result = (
                        reset_demo_environment()
                    )

                # Clear any Streamlit cached database
                # results if caching is introduced.
                st.cache_data.clear()

                st.session_state[
                    "demo_reset_complete"
                ] = True

                st.session_state[
                    "demo_reset_counts"
                ] = result[
                    "counts"
                ]

                st.rerun()

            except Exception as error:

                st.error(
                    f"Demo reset failed: {error}"
                )

        if st.session_state.get(
            "demo_reset_complete"
        ):

            st.success(
                "✅ Clean demo environment ready."
            )

            counts = (
                st.session_state.get(
                    "demo_reset_counts",
                    {},
                )
            )

            if counts:

                c1, c2, c3 = (
                    st.columns(3)
                )

                with c1:

                    st.metric(
                        "Operations",
                        counts.get(
                            "operations",
                            0,
                        ),
                    )

                with c2:

                    st.metric(
                        "Routes",
                        counts.get(
                            "driver_routes",
                            0,
                        ),
                    )

                with c3:

                    st.metric(
                        "Events",
                        counts.get(
                            "events",
                            0,
                        ),
                    )


    # =====================================================
    # GOLDEN DEMO GUIDE
    # =====================================================

    with st.expander(
        "⭐ Golden Demo Flow",
        expanded=False,
    ):

        st.markdown(
            """
### 1. Create the rescue

Go to **Donor → Community Bakery** and create:

- **Food:** Prepared Food
- **Quantity:** 50 lbs
- **Available:** 11:00
- **Pickup deadline:** 14:00

Click **Create Donation & Start Rescue**.

RescueMesh will use the real Strands + Bedrock
coordination flow and deterministic logistics
optimizer to create the rescue plan.

### 2. Show the dispatch

Open **Driver Dispatch**.

Show the assigned driver, pickup time, pantry
destinations, quantities and ETAs.

### 3. Simulate the driver

Return to **Demo Simulator**.

Use the controls in order:

**Accept Assignment → Confirm Pickup → Deliver**

These buttons simulate events that would normally
arrive from the driver's phone or lightweight
mobile interface.

### 4. Confirm delivery at the pantry

Open **Pantry** and select the pantry that the
driver reported delivering to.

Click:

**Confirm Food Received**

This creates the real pantry-side confirmation.

### 5. Finish remaining stops

If the rescue has another pantry stop:

**Demo Simulator → Deliver next stop**

then:

**Pantry → Confirm Received**

### 6. Show the completed rescue

Open **Operations**.

The operation should now show:

**✅ Rescue Completed**

with all delivery stops confirmed.

Then open **Impact & Evaluation** to show the
measured RescueMesh results and benchmark coverage.
            """
        )

        st.info(
            "The optimizer may choose a different "
            "driver or pantry combination if network "
            "state changes. Always follow the actual "
            "plan RescueMesh generates."
        )

    st.divider()    
    
    

    operations = get_operations_dashboard(
        limit=20
    )

    # Only show operations that can still change.
    active_operations = [
        operation
        for operation in operations
        if operation["status"] in (
            "planned",
            "active",
            "awaiting_human",
        )
    ]

    if not active_operations:

        st.info(
            "There are no active rescues to simulate. "
            "Create a donation from the Donor Portal."
        )
        return

    # =====================================================
    # RESCUE SELECTOR
    # =====================================================

    operation_lookup = {}

    for operation in active_operations:

        label = (
            f"Rescue #{operation['id']} — "
            f"{operation['donor_name']} — "
            f"{pretty_food_type(operation['food_type'])} — "
            f"{float(operation['quantity_lbs']):.0f} lbs"
        )

        operation_lookup[
            label
        ] = operation

    selected_label = st.selectbox(
        "Rescue to simulate",
        options=list(
            operation_lookup.keys()
        ),
    )

    operation = operation_lookup[
        selected_label
    ]

    # =====================================================
    # RESCUE SUMMARY
    # =====================================================

    st.subheader(
        f"Rescue #{operation['id']}"
    )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:

        st.write(
            "**Donor**"
        )

        st.write(
            operation[
                "donor_name"
            ]
        )

    with col2:

        st.write(
            "**Food**"
        )

        st.write(
            pretty_food_type(
                operation[
                    "food_type"
                ]
            )
        )

    with col3:

        st.write(
            "**Quantity**"
        )

        st.write(
            f"{float(operation['quantity_lbs']):.0f} lbs"
        )

    st.caption(
        f"Current rescue status: "
        f"{operation['status'].replace('_', ' ').title()}"
    )

    st.divider()

    # =====================================================
    # HUMAN ESCALATION PAUSE
    # =====================================================

    if (
        operation["status"]
        ==
        "awaiting_human"
    ):

        st.warning(
            "This rescue is waiting for a human decision. "
            "Resolve the escalation from the Operations "
            "Center before simulating more driver activity."
        )

        return
    
    
    # =====================================================
    # DISRUPTION SIMULATOR
    # =====================================================

    render_disruption_controls(
        operation["id"]
    )

    # =====================================================
    # DRIVER EVENTS
    # =====================================================

    st.subheader(
        "Simulated Driver Events"
    )

    for route in operation[
        "routes"
    ]:

        with st.container(
            border=True
        ):

            driver_name = route[
                "driver_name"
            ]

            route_status = route[
                "route_status"
            ]

            st.markdown(
                f"### 🚗 {driver_name}"
            )

            st.caption(
                f"{float(route['assigned_lbs']):.0f} lbs assigned "
                f"• pickup {route['pickup_start']} "
                f"• route complete {route['route_complete']}"
            )

            # =================================================
            # STEP 1 — DRIVER ACCEPTS
            # =================================================

            if (
                operation["status"]
                ==
                "planned"
                and
                route_status
                in (
                    "assigned",
                    "planned",
                )
            ):

                st.info(
                    "📱 Simulating: driver receives "
                    "the rescue assignment."
                )

                if st.button(
                    f"Simulate {driver_name} Accepting Assignment",
                    type="primary",
                    use_container_width=True,
                    key=
                        f"demo_accept_{route['route_id']}",
                ):

                    try:

                        accept_driver_assignment(
                            operation_id=
                                operation["id"],

                            driver_id=
                                route["driver_id"],
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"Could not process driver acceptance: "
                            f"{error}"
                        )

            # =================================================
            # ACCEPTED, BUT OTHER DRIVERS MAY STILL NEED TO
            # =================================================

            elif (
                operation["status"]
                ==
                "planned"
            ):

                st.success(
                    f"✅ {driver_name} accepted the assignment."
                )

                st.caption(
                    "Waiting for the other assigned "
                    "driver(s) to accept."
                )

            # =================================================
            # STEP 2 — DRIVER PICKS UP FOOD
            # =================================================

            elif (
                operation["status"]
                ==
                "active"
                and
                route_status
                ==
                "active"
            ):

                st.info(
                    f"📱 Simulating: {driver_name} arrived "
                    "at the donor and loaded the food."
                )

                if st.button(
                    f"Simulate {driver_name} Confirming Pickup",
                    type="primary",
                    use_container_width=True,
                    key=
                        f"demo_pickup_{route['route_id']}",
                ):

                    try:

                        confirm_driver_pickup(
                            operation_id=
                                operation["id"],

                            driver_id=
                                route["driver_id"],
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"Could not process pickup: "
                            f"{error}"
                        )

            # =================================================
            # STEP 3 — DRIVER IS IN TRANSIT
            # =================================================

            elif (
                route_status
                ==
                "picked_up"
            ):

                st.success(
                    f"🚚 {driver_name} has the food "
                    "and is in transit."
                )

            elif (
                route_status
                ==
                "completed"
            ):

                st.success(
                    "✅ Driver route completed."
                )

            # =================================================
            # DELIVERY STOPS
            # =================================================

            st.markdown(
                "#### Delivery Stops"
            )

            pending_stops = 0
            waiting_pantries = 0

            for stop in route[
                "stops"
            ]:

                status = stop[
                    "stop_status"
                ]

                if status == "pending":
                    pending_stops += 1

                if status == "driver_delivered":
                    waiting_pantries += 1

                st.markdown(
                    f"**{stop['stop_order']}. "
                    f"{stop['pantry_name']}**"
                )

                st.write(
                    f"{float(stop['quantity_lbs']):.0f} lbs "
                    f"• ETA {stop['eta']}"
                )

                st.caption(
                    stop_status_label(
                        status
                    )
                )

                # =============================================
                # DRIVER REPORTS DELIVERY
                # =============================================

                if (
                    route_status
                    ==
                    "picked_up"
                    and
                    status
                    ==
                    "pending"
                ):

                    if st.button(
                        (
                            f"Simulate {driver_name} Delivering "
                            f"to {stop['pantry_name']}"
                        ),
                        use_container_width=True,
                        key=
                            f"demo_deliver_{stop['stop_id']}",
                    ):

                        try:

                            mark_driver_delivery(
                                operation_id=
                                    operation["id"],

                                stop_id=
                                    stop["stop_id"],
                            )

                            st.rerun()

                        except Exception as error:

                            st.error(
                                f"Could not process delivery: "
                                f"{error}"
                            )

                elif (
                    status
                    ==
                    "driver_delivered"
                ):

                    st.warning(
                        "Driver reported this delivery. "
                        "Now switch to the Pantry Portal "
                        "so the pantry can confirm receipt."
                    )

                elif (
                    status
                    ==
                    "completed"
                ):

                    st.success(
                        "Pantry confirmed the food was received."
                    )

                st.divider()

            # =================================================
            # ROUTE MESSAGE
            # =================================================

            if (
                pending_stops == 0
                and
                waiting_pantries > 0
            ):

                st.info(
                    "The driver has reported all drop-offs. "
                    "The rescue is now waiting for pantry "
                    "confirmation."
                )