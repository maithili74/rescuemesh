from datetime import time

import streamlit as st

from app.dashboard.components.common import (
    status_badge,
)

from app.dashboard.services.actions import (
    create_donation_and_coordinate,
)

from app.dashboard.services.data import (
    get_donor,
    get_donor_donations,
    get_donor_metrics,
    get_donors,
    get_supported_food_types,
)


def _pretty_food_type(
    food_type,
):
    return (
        food_type
        .replace(
            "_",
            " ",
        )
        .title()
    )


def _render_latest_result():
    result = st.session_state.get(
        "latest_donor_result"
    )

    if not result:
        return

    if result[
        "status"
    ] == "planned":

        operation = result[
            "operation"
        ]

        st.success(
            f"Donation #{result['donation_id']} "
            f"was created and RescueMesh "
            f"generated Operation "
            f"#{result['operation_id']}."
        )

        if operation:
            col1, col2, col3 = (
                st.columns(
                    3
                )
            )

            with col1:
                st.metric(
                    "Planned Rescue",
                    (
                        f"{float(operation['rescued_lbs']):.0f} lbs"
                    ),
                )

            with col2:
                st.metric(
                    "Unrescued",
                    (
                        f"{float(operation['unrescued_lbs']):.0f} lbs"
                    ),
                )

            with col3:
                st.metric(
                    "Drivers Assigned",
                    len(
                        operation[
                            "driver_routes"
                        ]
                    ),
                )

            with st.expander(
                "View rescue assignment",
                expanded=True,
            ):
                for route in operation[
                    "driver_routes"
                ]:

                    st.markdown(
                        f"**{route['driver_name']}** "
                        f"— {float(route['assigned_lbs']):.0f} lbs"
                    )

                    for stop in route[
                        "stops"
                    ]:
                        st.write(
                            "→ "
                            f"{stop['pantry_name']} "
                            f"• {float(stop['quantity_lbs']):.0f} lbs "
                            f"• ETA {stop['eta']}"
                        )

        st.caption(
            "The operation is planned only. "
            "Drivers must accept their assignments "
            "before the rescue becomes active."
        )

    else:
        st.warning(
            f"Donation #{result['donation_id']} "
            "was created, but a rescue could not "
            "currently be planned."
        )

        planning_reason = result.get(
            "planning_reason"
        )

        if planning_reason:
            st.info(
                f"Reason: {planning_reason}"
            )

        if result.get(
            "agent_error"
        ):
            with st.expander(
                "Coordinator diagnostics"
            ):
                st.write(
                    result[
                        "agent_error"
                    ]
                )

        st.caption(
            "The donation remains available in "
            "RescueMesh and can be coordinated again "
            "when network conditions change."
        )    


def render_donor_view():
    st.header(
        "Donor Portal"
    )

    st.caption(
        "Create surplus-food donations "
        "and track their rescue progress."
    )

    donors = get_donors()

    if not donors:
        st.warning(
            "No donors are currently available."
        )
        return

    donor_lookup = {
        donor["name"]:
            donor["id"]

        for donor in donors
    }

    selected_name = st.selectbox(
        "Donor organization",
        options=list(
            donor_lookup.keys()
        ),
    )

    donor_id = donor_lookup[
        selected_name
    ]

    donor = get_donor(
        donor_id
    )

    metrics = get_donor_metrics(
        donor_id
    )

    # =====================================================
    # ORGANIZATION
    # =====================================================

    st.markdown(
        "### Organization"
    )

    col1, col2 = st.columns(
        [2, 3]
    )

    with col1:
        st.write(
            f"**{selected_name}**"
        )

        if (
            donor
            and
            donor.get(
                "location"
            )
        ):
            st.caption(
                donor[
                    "location"
                ]
            )

    with col2:
        st.caption(
            "Donations submitted here are "
            "coordinated by the real RescueMesh "
            "agent and optimization backend."
        )

    st.divider()

    # =====================================================
    # METRICS
    # =====================================================

    metric1, metric2, metric3 = (
        st.columns(
            3
        )
    )

    with metric1:
        st.metric(
            "Donations",
            int(
                metrics[
                    "donation_count"
                ]
            ),
        )

    with metric2:
        st.metric(
            "Food Donated",
            (
                f"{float(metrics['total_donated_lbs']):,.0f} lbs"
            ),
        )

    with metric3:
        st.metric(
            "Completed Rescue",
            (
                f"{float(metrics['completed_donation_lbs']):,.0f} lbs"
            ),
        )

    # =====================================================
    # LAST ACTION
    # =====================================================

    if st.session_state.get(
        "latest_donor_id"
    ) != donor_id:

        st.session_state.pop(
            "latest_donor_result",
            None,
        )

    st.session_state[
        "latest_donor_id"
    ] = donor_id

    _render_latest_result()

    st.divider()

    # =====================================================
    # CREATE DONATION
    # =====================================================

    st.subheader(
        "Create a Donation"
    )

    st.caption(
        "RescueMesh will inspect current "
        "drivers, pantry capacity and food needs "
        "before creating a rescue operation."
    )

    food_types = (
        get_supported_food_types()
    )

    if not food_types:
        st.error(
            "No supported food types were found "
            "in the pantry network."
        )
        return

    with st.form(
        "create_donation_form"
    ):

        form_left, form_right = (
            st.columns(
                2
            )
        )

        with form_left:

            food_type = st.selectbox(
                "Food type",
                options=food_types,
                format_func=
                    _pretty_food_type,
            )

            quantity_lbs = (
                st.number_input(
                    "Quantity (lbs)",
                    min_value=1.0,
                    max_value=5000.0,
                    value=100.0,
                    step=5.0,
                )
            )

        with form_right:

            available_at = (
                st.time_input(
                    "Available from",
                    value=time(
                        11,
                        0,
                    ),
                )
            )

            pickup_deadline = (
                st.time_input(
                    "Pickup deadline",
                    value=time(
                        14,
                        0,
                    ),
                )
            )

        submitted = st.form_submit_button(
            "Create Donation & Start Rescue",
            type="primary",
            use_container_width=True,
        )

    # =====================================================
    # SUBMIT
    # =====================================================

    if submitted:

        if (
            pickup_deadline
            <=
            available_at
        ):
            st.error(
                "Pickup deadline must be later "
                "than the available time."
            )

        else:

            try:
                with st.spinner(
                    "RescueMesh is inspecting the "
                    "network and coordinating a rescue..."
                ):

                    result = (
                        create_donation_and_coordinate(
                            donor_id=
                                donor_id,

                            food_type=
                                food_type,

                            quantity_lbs=
                                quantity_lbs,

                            available_at=
                                available_at,

                            pickup_deadline=
                                pickup_deadline,
                        )
                    )

                st.session_state[
                    "latest_donor_result"
                ] = result

                st.rerun()

            except Exception as error:
                st.error(
                    "Could not create donation: "
                    f"{error}"
                )

    # =====================================================
    # HISTORY
    # =====================================================

    st.divider()

    st.subheader(
        "Donation History"
    )

    donations = (
        get_donor_donations(
            donor_id
        )
    )

    if not donations:
        st.info(
            "This donor has no donations yet."
        )
        return

    for donation in donations:

        with st.container(
            border=True
        ):

            col_a, col_b, col_c = (
                st.columns(
                    [1, 2, 2]
                )
            )

            with col_a:
                st.write(
                    f"**#{donation['id']}**"
                )

            with col_b:

                st.write(
                    _pretty_food_type(
                        donation[
                            "food_type"
                        ]
                    )
                )

                st.caption(
                    f"{float(donation['quantity_lbs']):.0f} lbs"
                )

            with col_c:
                st.write(
                    status_badge(
                        donation[
                            "status"
                        ]
                    )
                )