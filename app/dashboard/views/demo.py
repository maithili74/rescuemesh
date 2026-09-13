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


# =========================================================
# DISPLAY HELPERS
# =========================================================

def pretty_food_type(food_type):
    return (
        food_type
        .replace("_", " ")
        .title()
    )


def pretty_status(status):
    return (
        status
        .replace("_", " ")
        .title()
    )


def stop_status_label(status):
    labels = {
        "pending":
            "○ Upcoming",

        "driver_delivered":
            "🟠 Waiting for pantry confirmation",

        "completed":
            "✅ Pantry confirmed",

        "cancelled":
            "↪ Replanned",

        "failed":
            "⚠️ Delivery issue",

        "failed_released":
            "↪ Replanned",
    }

    return labels.get(
        status,
        pretty_status(status),
    )


# =========================================================
# CURRENT / RELEVANT DELIVERY STOPS
# =========================================================

def _demo_stops(operation):
    """
    Return delivery stops that still belong to the
    current rescue path.

    Cancelled or released historical stops remain
    visible in route details, but they should not
    block the judge-facing progress indicator.
    """

    stops = []

    for route in operation.get(
        "routes",
        [],
    ):
        for stop in route.get(
            "stops",
            [],
        ):
            if stop.get(
                "stop_status"
            ) not in (
                "cancelled",
                "failed_released",
            ):
                stops.append(
                    stop
                )

    return stops


# =========================================================
# RESCUE PROGRESS
# =========================================================

def _demo_progress(operation):
    routes = operation.get(
        "routes",
        [],
    )

    stops = _demo_stops(
        operation
    )

    # A rescue shown on this page already has a plan.
    plan_created = True

    driver_accepted = (
        bool(routes)
        and
        all(
            route.get(
                "route_status"
            )
            not in (
                "assigned",
                "planned",
            )
            for route in routes
        )
    )

    pickup_complete = (
        bool(routes)
        and
        all(
            route.get(
                "route_status"
            )
            in (
                "picked_up",
                "completed",
            )
            for route in routes
        )
    )

    driver_delivery_complete = (
        bool(stops)
        and
        all(
            stop.get(
                "stop_status"
            )
            in (
                "driver_delivered",
                "completed",
            )
            for stop in stops
        )
    )

    pantry_confirmation_complete = (
        bool(stops)
        and
        all(
            stop.get(
                "stop_status"
            )
            ==
            "completed"
            for stop in stops
        )
    )

    rescue_complete = (
        operation.get(
            "status"
        )
        in (
            "completed",
            "completed_partial",
        )
    )

    return [
        (
            "Plan",
            plan_created,
        ),
        (
            "Accepted",
            driver_accepted,
        ),
        (
            "Picked Up",
            pickup_complete,
        ),
        (
            "Delivered",
            driver_delivery_complete,
        ),
        (
            "Verified",
            pantry_confirmation_complete,
        ),
        (
            "Complete",
            rescue_complete,
        ),
    ]


def render_demo_progress(operation):
    progress = _demo_progress(
        operation
    )

    first_incomplete = None

    for index, (_, complete) in enumerate(progress):
        if not complete:
            first_incomplete = index
            break

    awaiting_human = (
        operation.get("status")
        == "awaiting_human"
    )

    pieces = []

    for index, (label, complete) in enumerate(progress):

        # ---------------------------------------------
        # CIRCLE STATE
        # ---------------------------------------------

        if complete:
            state = "done"
            symbol = "✓"

        elif index == first_incomplete:
            state = "current"

            if awaiting_human:
                symbol = "!"
            else:
                symbol = ""

        else:
            state = "future"
            symbol = ""

        pieces.append(
            f"""
            <div class="rm-step">
                <div class="rm-circle {state}">
                    {symbol}
                </div>
                <div class="rm-label {state}">
                    {label}
                </div>
            </div>
            """
        )

        # ---------------------------------------------
        # CONNECTING LINE
        # ---------------------------------------------

        if index < len(progress) - 1:

            next_complete = progress[index + 1][1]

            if complete and next_complete:
                line_state = "done"

            elif complete:
                line_state = "current"

            else:
                line_state = "future"

            pieces.append(
                f"""
                <div class="rm-line {line_state}">
                </div>
                """
            )

    steps_html = "".join(pieces)

    st.html(
        f"""
<style>
.rm-progress {{
    display: flex;
    align-items: flex-start;
    width: 100%;
    padding: 6px 2px 4px 2px;
}}

.rm-step {{
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    min-width: 58px;
}}

.rm-circle {{
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    font-size: 14px;
    font-weight: 700;
    flex-shrink: 0;
}}

.rm-circle.done {{
    background: #496b58;
    border: 2px solid #496b58;
    color: white;
}}

.rm-circle.current {{
    background: #f8f1e5;
    border: 3px solid #496b58;
    position: relative;
}}

.rm-circle.current::after {{
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #496b58;
}}

.rm-circle.future {{
    background: #f8f1e5;
    border: 2px solid #c8c1b5;
}}

.rm-line {{
    flex: 1;
    height: 3px;
    margin-top: 12px;
    min-width: 18px;
}}

.rm-line.done {{
    background: #496b58;
}}

.rm-line.current {{
    background:
        linear-gradient(
            to right,
            #496b58 50%,
            #d6d0c5 50%
        );
}}

.rm-line.future {{
    background: #d6d0c5;
}}

.rm-label {{
    margin-top: 7px;
    font-size: 12px;
    white-space: nowrap;
}}

.rm-label.done {{
    color: #496b58;
    font-weight: 600;
}}

.rm-label.current {{
    color: #2f493b;
    font-weight: 700;
}}

.rm-label.future {{
    color: #8a867e;
}}

@media (max-width: 700px) {{
    .rm-step {{
        min-width: 43px;
    }}

    .rm-circle {{
        width: 22px;
        height: 22px;
        font-size: 12px;
    }}

    .rm-line {{
        margin-top: 10px;
        min-width: 7px;
    }}

    .rm-label {{
        font-size: 9px;
    }}
}}
</style>

<div class="rm-progress">
    {steps_html}
</div>
"""
    )

# =========================================================
# NEXT ACTION
# =========================================================

def _find_next_action(operation):
    """
    Return the single clearest next action.

    This prevents the judge from having to figure out
    which button should be clicked next.
    """

    status = operation.get(
        "status"
    )

    routes = operation.get(
        "routes",
        [],
    )

    # -----------------------------------------------------
    # COMPLETED
    # -----------------------------------------------------

    if status in (
        "completed",
        "completed_partial",
    ):

        unrescued_lbs = float(
            operation.get(
                "unrescued_lbs",
                0,
            )
            or 0
        )

        if (
            status
            ==
            "completed_partial"
            and
            unrescued_lbs > 0
        ):
            return {
                "kind":
                    "completed",

                "title":
                    "🎉 Rescue workflow completed",

                "message":
                    (
                        "All planned deliveries were completed "
                        "and verified. This rescue finished with "
                        f"{unrescued_lbs:.0f} lbs requiring "
                        "manual handling after a safe partial "
                        "recovery."
                    ),
            }

        return {
            "kind":
                "completed",

            "title":
                "🎉 Rescue completed",

            "message":
                (
                    "All food was delivered and independently "
                    "confirmed by the receiving pantry."
                ),
        }

    # -----------------------------------------------------
    # HUMAN ESCALATION
    # -----------------------------------------------------

    if (
        status
        ==
        "awaiting_human"
    ):

        return {
            "kind":
                "human",

            "title":
                "⚠️ Human decision required",

            "message":
                (
                    "RescueMesh could not safely resolve this "
                    "situation automatically. Open "
                    "**Operations** to review the escalation "
                    "and choose from the verified options."
                ),
        }

    # -----------------------------------------------------
    # DRIVER ACCEPTANCE
    # -----------------------------------------------------

    if (
        status
        ==
        "planned"
    ):

        for route in routes:

            if route.get(
                "route_status"
            ) in (
                "assigned",
                "planned",
            ):

                return {
                    "kind":
                        "accept",

                    "title":
                        "➡️ Driver accepts the rescue",

                    "message":
                        (
                            f"**{route['driver_name']}** has "
                            "received the assignment. Accept it "
                            "to begin the rescue."
                        ),

                    "route":
                        route,
                }

        return {
            "kind":
                "waiting",

            "title":
                "⏳ Waiting for driver acceptance",

            "message":
                (
                    "Some drivers have accepted. RescueMesh is "
                    "waiting for the remaining assigned driver."
                ),
        }

    # -----------------------------------------------------
    # PICKUP
    # -----------------------------------------------------

    for route in routes:

        if (
            route.get(
                "route_status"
            )
            ==
            "active"
        ):

            return {
                "kind":
                    "pickup",

                "title":
                    "➡️ Confirm food pickup",

                "message":
                    (
                        f"**{route['driver_name']}** accepted "
                        "the rescue. The next event is pickup "
                        f"from **{operation['donor_name']}**."
                    ),

                "route":
                    route,
            }

    # -----------------------------------------------------
    # DRIVER DELIVERY
    # -----------------------------------------------------

    for route in routes:

        if (
            route.get(
                "route_status"
            )
            ==
            "picked_up"
        ):

            pending_stops = [
                stop
                for stop
                in route.get(
                    "stops",
                    [],
                )
                if stop.get(
                    "stop_status"
                )
                ==
                "pending"
            ]

            if pending_stops:

                stop = sorted(
                    pending_stops,
                    key=lambda item:
                        item.get(
                            "stop_order",
                            999,
                        ),
                )[0]

                return {
                    "kind":
                        "deliver",

                    "title":
                        "➡️ Report the next delivery",

                    "message":
                        (
                            f"**{route['driver_name']}** has the "
                            "food. The next stop is "
                            f"**{stop['pantry_name']}** for "
                            f"**{float(stop['quantity_lbs']):.0f} lbs**."
                        ),

                    "route":
                        route,

                    "stop":
                        stop,
                }

    # -----------------------------------------------------
    # PANTRY CONFIRMATION
    # -----------------------------------------------------

    for route in routes:

        for stop in route.get(
            "stops",
            [],
        ):

            if (
                stop.get(
                    "stop_status"
                )
                ==
                "driver_delivered"
            ):

                return {
                    "kind":
                        "pantry",

                    "title":
                        "➡️ Pantry verifies receipt",

                    "message":
                        (
                            f"The driver reported delivery to "
                            f"**{stop['pantry_name']}**. "
                            "For independent verification, open "
                            "**Pantry**, select that location, "
                            "and click **Confirm Food Received**."
                        ),

                    "route":
                        route,

                    "stop":
                        stop,
                }

    # -----------------------------------------------------
    # FALLBACK
    # -----------------------------------------------------

    return {
        "kind":
            "waiting",

        "title":
            "ℹ️ Rescue is processing",

        "message":
            (
                "RescueMesh is processing the current rescue "
                "state. See the route details below for more "
                "information."
            ),
    }


# =========================================================
# NEXT ACTION UI
# =========================================================

def render_next_action(operation):
    action = _find_next_action(
        operation
    )

    kind = action[
        "kind"
    ]

    st.markdown(
        f"### {action['title']}"
    )

    # -----------------------------------------------------
    # COMPLETED
    # -----------------------------------------------------

    if kind == "completed":

        st.success(
            action[
                "message"
            ]
        )

        st.caption(
            "Review the completed rescue in Operations "
            "or open Impact & Evaluation for results."
        )

        return

    # -----------------------------------------------------
    # HUMAN
    # -----------------------------------------------------

    if kind == "human":

        st.warning(
            action[
                "message"
            ]
        )

        return

    # -----------------------------------------------------
    # ACCEPT
    # -----------------------------------------------------

    if kind == "accept":

        route = action[
            "route"
        ]

        st.info(
            action[
                "message"
            ]
        )

        if st.button(
            (
                "Accept Assignment — "
                f"{route['driver_name']}"
            ),
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
                    "Could not process driver "
                    f"acceptance: {error}"
                )

        return

    # -----------------------------------------------------
    # PICKUP
    # -----------------------------------------------------

    if kind == "pickup":

        route = action[
            "route"
        ]

        st.info(
            action[
                "message"
            ]
        )

        if st.button(
            (
                "Confirm Pickup — "
                f"{route['driver_name']}"
            ),
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
                    f"Could not process pickup: {error}"
                )

        return

    # -----------------------------------------------------
    # DELIVERY
    # -----------------------------------------------------

    if kind == "deliver":

        stop = action[
            "stop"
        ]

        st.info(
            action[
                "message"
            ]
        )

        if st.button(
            (
                "Report Delivery to "
                f"{stop['pantry_name']}"
            ),
            type="primary",
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
                    f"Could not process delivery: {error}"
                )

        return

    # -----------------------------------------------------
    # PANTRY
    # -----------------------------------------------------

    if kind == "pantry":

        st.warning(
            action[
                "message"
            ]
        )

        st.caption(
            "A driver report alone does not complete "
            "a RescueMesh delivery."
        )

        return

    # -----------------------------------------------------
    # WAITING
    # -----------------------------------------------------

    st.info(
        action[
            "message"
        ]
    )


# =========================================================
# RESET CONTROL
# =========================================================

def render_reset_control():

    st.write(
        "Restore RescueMesh to the clean seeded "
        "starting state before a judge demo or "
        "video recording."
    )

    st.warning(
        "Current demo operations, routes, delivery "
        "stops, events and escalations will be cleared."
    )

    confirm_reset = st.checkbox(
        "I understand that current demo activity "
        "will be cleared.",
        key=
            "confirm_demo_reset",
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
            "Clean demo environment ready."
        )


# =========================================================
# QUICK GUIDE
# =========================================================

def render_quick_guide():

    st.markdown(
        """
**1. Create a rescue**

Go to **Donor** and create a surplus-food donation.

For the standard demo:

- Community Bakery
- Prepared Food
- 50 lbs
- Available 11:00
- Pickup deadline 14:00

**2. Review dispatch**

Open **Driver Dispatch** to see the automatically
generated assignment and route.

**3. Run the rescue**

Return here and follow the highlighted **Next Step**.

**4. Verify delivery**

When prompted, open **Pantry** and confirm receipt.

**5. Review results**

Open **Operations**, then **Impact & Evaluation**.
        """
    )

    st.caption(
        "Drivers and pantries may vary because RescueMesh "
        "uses the current network state."
    )


# =========================================================
# ROUTE DETAILS
# =========================================================

def render_route_details(operation):

    for route_index, route in enumerate(
        operation.get(
            "routes",
            [],
        )
    ):

        if route_index > 0:
            st.divider()

        driver_name = route.get(
            "driver_name",
            "Driver",
        )

        route_status = route.get(
            "route_status",
            "unknown",
        )

        st.markdown(
            f"**🚗 {driver_name}**"
        )

        st.caption(
            (
                f"{float(route.get('assigned_lbs', 0)):.0f} lbs "
                f"• pickup {route.get('pickup_start', '—')} "
                f"• route complete "
                f"{route.get('route_complete', '—')} "
                f"• {pretty_status(route_status)}"
            )
        )

        stops = route.get(
            "stops",
            [],
        )

        if not stops:

            st.caption(
                "No delivery stops."
            )

            continue

        for stop in stops:

            status = stop.get(
                "stop_status",
                "unknown",
            )

            st.markdown(
                (
                    f"**{stop.get('stop_order', '—')}. "
                    f"{stop.get('pantry_name', 'Pantry')}**"
                )
            )

            st.caption(
                (
                    f"{float(stop.get('quantity_lbs', 0)):.0f} lbs "
                    f"• ETA {stop.get('eta', '—')} "
                    f"• {stop_status_label(status)}"
                )
            )


# =========================================================
# MAIN VIEW
# =========================================================

def render_demo_view():

    st.header(
        "🚚 Live Rescue Demo"
    )

    st.caption(
        "Follow a rescue from assignment to verified "
        "delivery. Demo actions use the real RescueMesh "
        "backend."
    )

    # =====================================================
    # SMALL TOP CONTROLS
    # =====================================================

    reset_col, guide_col = st.columns(
        2
    )

    with reset_col:

        with st.expander(
            "↻ Reset Demo",
            expanded=False,
        ):

            render_reset_control()

    with guide_col:

        with st.expander(
            "⭐ Demo Guide",
            expanded=False,
        ):

            render_quick_guide()

    st.divider()

    # =====================================================
    # LOAD RESCUES
    # =====================================================

    operations = get_operations_dashboard(
        limit=20
    )

    demo_operations = [
        operation
        for operation in operations
        if operation.get(
            "status"
        ) in (
            "planned",
            "active",
            "awaiting_human",
            "completed",
            "completed_partial",
        )
    ]

    if not demo_operations:

        st.info(
            "There are no rescues to display yet. "
            "Start by creating a donation from the "
            "Donor page."
        )

        return

    # =====================================================
    # RESCUE SELECTOR
    # =====================================================

    operation_lookup = {}

    for operation in demo_operations:

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
        "Rescue",
        options=list(
            operation_lookup.keys()
        ),
        key=
            "live_demo_rescue_selector",
    )

    operation = operation_lookup[
        selected_label
    ]

    # =====================================================
    # COMPACT SUMMARY
    # =====================================================

    st.subheader(
        f"Rescue #{operation['id']}"
    )

    donor_col, food_col, quantity_col = (
        st.columns(3)
    )

    with donor_col:

        st.caption(
            "DONOR"
        )

        st.markdown(
            f"**{operation['donor_name']}**"
        )

    with food_col:

        st.caption(
            "FOOD"
        )

        st.markdown(
            (
                f"**{pretty_food_type(operation['food_type'])}**"
            )
        )

    with quantity_col:

        st.caption(
            "QUANTITY"
        )

        st.markdown(
            (
                f"**{float(operation['quantity_lbs']):.0f} lbs**"
            )
        )

    # =====================================================
    # PROGRESS
    # =====================================================

    st.markdown(
        "#### Rescue Progress"
    )

    render_demo_progress(
        operation
    )

    st.divider()

    # =====================================================
    # ONE OBVIOUS NEXT STEP
    # =====================================================

    render_next_action(
        operation
    )

    st.divider()

    # =====================================================
    # ROUTE DETAILS — HIDDEN BY DEFAULT
    # =====================================================

    with st.expander(
        "🗺️ View Route Details",
        expanded=False,
    ):

        render_route_details(
            operation
        )

    # =====================================================
    # ADVANCED DISRUPTION CONTROLS
    # =====================================================
    #
    # Do NOT show disruption controls after completion.
    # Also do not encourage another disruption while the
    # rescue is paused for a human decision.
    # =====================================================

    if operation.get(
        "status"
    ) in (
        "planned",
        "active",
    ):

        with st.expander(
            "⚙️ Advanced Demo Controls",
            expanded=False,
        ):

            st.caption(
                "Optional: simulate a real-world failure "
                "such as a driver cancellation, pantry "
                "closure, or capacity change and watch "
                "RescueMesh replan or escalate safely."
            )

            render_disruption_controls(
                operation["id"]
            )