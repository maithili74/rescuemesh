import streamlit as st

from app.dashboard.services.data import (
    get_operation_summary,
)

def render_operations_view():
    st.header(
        "Operations Center"
    )

    st.caption(
        "Live network coordination, "
        "replanning and human escalation."
    )

    summary = (
        get_operation_summary()
    )

    col1, col2, col3, col4 = (
        st.columns(
            4
        )
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
            "Pending Escalations",
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

    st.subheader(
        "Live Rescue Operations"
    )

    st.info(
        "The next Operations step will show "
        "individual rescue cards, routes, "
        "agent actions and escalation controls."
    )