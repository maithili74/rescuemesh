import streamlit as st

from app.dashboard.services.actions import (
    confirm_pantry_receipt,
)

from app.dashboard.services.data import (
    get_pantries,
    get_pantry_completed_deliveries,
    get_pantry_incoming_deliveries,
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


def delivery_status_label(status):
    labels = {
        "pending":
            "🔵 Scheduled",

        "driver_delivered":
            "🟠 Driver Dropped Off",

        "completed":
            "✅ Received",
    }

    return labels.get(
        status,
        status.replace("_", " ").title(),
    )


# =========================================================
# PANTRY PAGE
# =========================================================

def render_pantry_view():

    st.header(
        "Pantry Portal"
    )

    st.caption(
        "See food coming to your pantry and "
        "confirm when it has been received."
    )

    pantries = get_pantries()

    if not pantries:

        st.warning(
            "No pantries were found."
        )
        return

    # =====================================================
    # SELECT PANTRY
    # =====================================================

    pantry_lookup = {
        pantry["name"]: pantry
        for pantry in pantries
    }

    selected_name = st.selectbox(
        "Receiving Pantry",
        options=list(
            pantry_lookup.keys()
        ),
    )

    pantry = pantry_lookup[
        selected_name
    ]

    pantry_id = pantry[
        "id"
    ]

    incoming = (
        get_pantry_incoming_deliveries(
            pantry_id
        )
    )

    completed = (
        get_pantry_completed_deliveries(
            pantry_id
        )
    )

    # =====================================================
    # PANTRY HEADER
    # =====================================================

    left, right = st.columns(
        [4, 2]
    )

    with left:

        st.subheader(
            pantry["name"]
        )

        st.caption(
            pantry["location"]
        )

    with right:

        if pantry["status"] == "available":

            st.success(
                "🟢 Open to Receive"
            )

        else:

            st.error(
                "🔴 Not Receiving"
            )

    st.divider()

    # =====================================================
    # SIMPLE SUMMARY
    # =====================================================

    incoming_lbs = sum(
        float(
            delivery["quantity_lbs"]
        )
        for delivery in incoming
    )

    waiting_confirmation = sum(
        1
        for delivery in incoming
        if (
            delivery["stop_status"]
            ==
            "driver_delivered"
        )
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    with col1:

        st.metric(
            "Incoming Deliveries",
            len(incoming),
        )

    with col2:

        st.metric(
            "Food Coming",
            f"{incoming_lbs:.0f} lbs",
        )

    with col3:

        st.metric(
            "Needs Confirmation",
            waiting_confirmation,
        )

    st.divider()

    # =====================================================
    # INCOMING FOOD
    # =====================================================

    st.subheader(
        "Incoming Food"
    )

    if not incoming:

        st.info(
            "No food is currently waiting "
            "to be received by this pantry."
        )

    else:

        for delivery in incoming:

            with st.container(
                border=True
            ):

                # -----------------------------------------
                # FOOD + QUANTITY
                # -----------------------------------------

                top_left, top_right = (
                    st.columns(
                        [4, 2]
                    )
                )

                with top_left:

                    st.markdown(
                        f"### "
                        f"{pretty_food_type(delivery['food_type'])}"
                    )

                with top_right:

                    st.markdown(
                        f"### "
                        f"{float(delivery['quantity_lbs']):.0f} lbs"
                    )

                # -----------------------------------------
                # WHO IS SENDING IT?
                # -----------------------------------------

                st.write(
                    "**Coming from**"
                )

                st.write(
                    f"🏪 {delivery['donor_name']}"
                )

                st.caption(
                    delivery[
                        "donor_location"
                    ]
                )

                # -----------------------------------------
                # DRIVER
                # -----------------------------------------

                info1, info2 = (
                    st.columns(2)
                )

                with info1:

                    st.write(
                        "**Driver**"
                    )

                    st.write(
                        f"🚗 {delivery['driver_name']}"
                    )

                with info2:

                    st.write(
                        "**Expected arrival**"
                    )

                    st.write(
                        delivery["eta"]
                    )

                st.write(
                    "**Delivery status**"
                )

                st.write(
                    delivery_status_label(
                        delivery[
                            "stop_status"
                        ]
                    )
                )

                # -----------------------------------------
                # IMPORTANT EXPLANATION
                # -----------------------------------------

                if (
                    delivery["stop_status"]
                    ==
                    "pending"
                ):

                    st.info(
                        f"{delivery['driver_name']} "
                        "has not reported this delivery yet."
                    )

                elif (
                    delivery["stop_status"]
                    ==
                    "driver_delivered"
                ):

                    st.warning(
                        f"{delivery['driver_name']} says "
                        f"{float(delivery['quantity_lbs']):.0f} lbs "
                        "was dropped off here."
                    )

                    st.write(
                        "If the food is physically here, "
                        "confirm that you received it."
                    )

                    if st.button(
                        (
                            f"Confirm "
                            f"{float(delivery['quantity_lbs']):.0f} lbs "
                            "Received"
                        ),
                        type="primary",
                        use_container_width=True,
                        key=(
                            f"receive_"
                            f"{delivery['stop_id']}"
                        ),
                    ):

                        try:

                            confirm_pantry_receipt(
                                operation_id=
                                    delivery[
                                        "operation_id"
                                    ],

                                stop_id=
                                    delivery[
                                        "stop_id"
                                    ],
                            )

                            st.rerun()

                        except Exception as error:

                            st.error(
                                "Could not confirm "
                                f"delivery: {error}"
                            )

    # =====================================================
    # RECEIVED HISTORY
    # =====================================================

    st.divider()

    st.subheader(
        "Received Food"
    )

    if not completed:

        st.caption(
            "No deliveries have been confirmed yet."
        )

    else:

        for delivery in completed:

            with st.container(
                border=True
            ):

                col1, col2, col3 = (
                    st.columns(
                        [3, 2, 2]
                    )
                )

                with col1:

                    st.write(
                        f"**{pretty_food_type(delivery['food_type'])}**"
                    )

                    st.caption(
                        f"From {delivery['donor_name']}"
                    )

                with col2:

                    st.write(
                        f"{float(delivery['quantity_lbs']):.0f} lbs"
                    )

                with col3:

                    st.write(
                        "✅ Received"
                    )