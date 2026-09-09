import streamlit as st

from app.dashboard.services.actions import (
    resolve_human_escalation,
)

from app.dashboard.services.data import (
    get_operation_summary,
    get_operations_dashboard,
    get_operation_timeline,
)

from app.tools.escalation_tools import (
    inspect_pending_escalations,
)


# =========================================================
# HELPERS
# =========================================================

def pretty_food_type(food_type):
    return (
        food_type
        .replace("_", " ")
        .title()
    )


def operation_status_label(status):
    labels = {
        "planned":
            "🔵 Rescue Scheduled",

        "active":
            "🚚 Rescue Active",

        "awaiting_human":
            "🟡 Human Decision Needed",

        "completed":
            "✅ Rescue Completed",

        "completed_partial":
            "🟠 Partially Completed",

        "manual_resolution":
            "🟡 Manual Coordination",
    }

    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


def route_status_label(status):
    labels = {
        "assigned":
            "🔵 Scheduled",

        "planned":
            "🔵 Scheduled",

        "accepted":
            "🟣 Accepted",

        "active":
            "🟣 Heading to Pickup",

        "picked_up":
            "🚚 In Transit",

        "completed":
            "✅ Route Complete",
    }

    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


def stop_status_label(status):
    labels = {
        "pending":
            "🔵 Upcoming",

        "driver_delivered":
            "🟠 Waiting for Pantry",

        "completed":
            "✅ Pantry Confirmed",

        "cancelled":
            "Replanned",

        "failed":
            "🔴 Delivery Problem",

        "failed_released":
            "Replanned",
    }

    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


# =========================================================
# HUMAN ESCALATION
# =========================================================

def render_human_escalation(
    operation_id,
):

    pending = inspect_pending_escalations(
        operation_id
    )

    escalations = pending.get(
        "escalations",
        [],
    )

    if not escalations:
        return

    st.warning(
        "RescueMesh could not safely resolve this "
        "situation automatically. A human decision "
        "is required."
    )

    for escalation in escalations:

        with st.container(
            border=True
        ):

            st.markdown(
                "### 🧑 Human Decision Required"
            )

            st.write(
                escalation[
                    "reason"
                ]
            )

            recommended = (
                escalation.get(
                    "recommended_action"
                )
            )

            if recommended:

                st.caption(
                    "RescueMesh recommendation: "
                    f"{recommended.replace('_', ' ').title()}"
                )

            for option in escalation.get(
                "options",
                [],
            ):

                st.write(
                    f"**{option['label']}**"
                )

                st.caption(
                    option[
                        "description"
                    ]
                )

                if st.button(
                    option[
                        "label"
                    ],
                    type=(
                        "primary"
                        if option["id"]
                        ==
                        recommended
                        else "secondary"
                    ),
                    use_container_width=True,
                    key=(
                        f"operation_escalation_"
                        f"{escalation['id']}_"
                        f"{option['id']}"
                    ),
                ):

                    try:

                        resolve_human_escalation(
                            escalation_id=
                                escalation["id"],

                            option_id=
                                option["id"],
                        )

                        st.rerun()

                    except Exception as error:

                        st.error(
                            f"Could not apply decision: "
                            f"{error}"
                        )


# =========================================================
# TIMELINE
# =========================================================

def render_timeline(
    operation_id,
):

    events = get_operation_timeline(
        operation_id,
        limit=20,
    )

    if not events:

        st.caption(
            "No activity recorded yet."
        )
        return

    for event in reversed(
        events
    ):

        event_name = (
            event["event_type"]
            .replace("_", " ")
            .title()
        )

        st.write(
            f"**{event_name}**"
        )

        st.caption(
            event[
                "created_at"
            ]
        )


# =========================================================
# MAIN VIEW
# =========================================================

def render_operations_view():

    st.header(
        "Operations Center"
    )

    st.caption(
        "Monitor active food rescues, delivery progress, "
        "automatic replanning and human escalations."
    )

    summary = (
        get_operation_summary()
    )

    # =====================================================
    # METRICS
    # =====================================================

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.metric(
            "Active Rescues",
            summary[
                "active_rescues"
            ],
        )

    with col2:

        st.metric(
            "Food In Transit",
            (
                f"{summary['food_in_transit_lbs']:.0f} lbs"
            ),
        )

    with col3:

        st.metric(
            "Human Decisions",
            summary[
                "pending_escalations"
            ],
        )

    with col4:

        st.metric(
            "Completed Rescue Rate",
            (
                f"{summary['rescue_rate'] * 100:.0f}%"
            ),
        )

    st.divider()

    operations = (
        get_operations_dashboard()
    )

    if not operations:

        st.info(
            "No rescue operations yet."
        )
        return

    st.subheader(
        "Rescue Operations"
    )

    # =====================================================
    # OPERATIONS
    # =====================================================

    for operation in operations:

        with st.container(
            border=True
        ):

            top1, top2, top3 = (
                st.columns(
                    [4, 2, 2]
                )
            )

            with top1:

                st.markdown(
                    f"### Rescue #{operation['id']}"
                )

                st.write(
                    f"**{operation['donor_name']}**"
                )

                st.caption(
                    f"{pretty_food_type(operation['food_type'])} "
                    f"• {float(operation['quantity_lbs']):.0f} lbs"
                )

            with top2:

                st.write(
                    operation_status_label(
                        operation[
                            "status"
                        ]
                    )
                )

            with top3:

                st.write(
                    f"**{float(operation['rescued_lbs']):.0f} lbs rescued**"
                )

                if (
                    float(
                        operation[
                            "unrescued_lbs"
                        ]
                    )
                    >
                    0
                ):

                    st.caption(
                        f"{float(operation['unrescued_lbs']):.0f} lbs unresolved"
                    )

            # =================================================
            # HUMAN ESCALATION
            # =================================================

            if (
                operation[
                    "status"
                ]
                ==
                "awaiting_human"
            ):

                render_human_escalation(
                    operation[
                        "id"
                    ]
                )

            st.markdown(
                "#### Driver Routes"
            )

            # =================================================
            # ROUTES
            # =================================================

            for route in operation[
                "routes"
            ]:

                with st.container(
                    border=True
                ):

                    driver1, driver2 = (
                        st.columns(
                            [4, 2]
                        )
                    )

                    with driver1:

                        st.write(
                            f"**🚗 {route['driver_name']}**"
                        )

                        st.caption(
                            f"{float(route['assigned_lbs']):.0f} lbs "
                            f"• pickup {route['pickup_start']} "
                            f"• expected finish {route['route_complete']}"
                        )

                    with driver2:

                        st.write(
                            route_status_label(
                                route[
                                    "route_status"
                                ]
                            )
                        )

                    st.markdown(
                        "##### Delivery Progress"
                    )

                    for stop in route[
                        "stops"
                    ]:

                        c1, c2, c3 = (
                            st.columns(
                                [4, 2, 2]
                            )
                        )

                        with c1:

                            st.write(
                                f"**{stop['stop_order']}. "
                                f"{stop['pantry_name']}**"
                            )

                            st.caption(
                                stop[
                                    "pantry_location"
                                ]
                            )

                        with c2:

                            st.write(
                                f"{float(stop['quantity_lbs']):.0f} lbs"
                            )

                            st.caption(
                                f"ETA {stop['eta']}"
                            )

                        with c3:

                            st.write(
                                stop_status_label(
                                    stop[
                                        "stop_status"
                                    ]
                                )
                            )

            with st.expander(
                "Activity Timeline"
            ):

                render_timeline(
                    operation[
                        "id"
                    ]
                )