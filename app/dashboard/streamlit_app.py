import streamlit as st

from app.dashboard.components.common import (
    render_database_status,
)

from app.dashboard.services.data import (
    check_database,
)

from app.dashboard.views.donor import (
    render_donor_view,
)

from app.dashboard.views.driver import (
    render_driver_view,
)

from app.dashboard.views.pantry import (
    render_pantry_view,
)

from app.dashboard.views.operations import (
    render_operations_view,
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="RescueMesh",
    page_icon="🥕",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# UI
# =========================================================

st.markdown(
    """
    <style>

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 2rem;
            max-width: 1450px;
        }

        .rm-title {
            font-size: 2.25rem;
            font-weight: 750;
            margin: 0;
        }

        .rm-subtitle {
            opacity: 0.70;
            margin-top: 0.1rem;
        }

        div[data-testid="stMetric"] {
            border: 1px solid
                rgba(128, 128, 128, 0.20);

            border-radius: 12px;

            padding:
                0.8rem
                1rem;
        }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================

header_left, header_center, header_right = (
    st.columns(
        [5, 2, 2],
        vertical_alignment="center",
    )
)

with header_left:
    st.markdown(
        """
        <div class="rm-title">
            RescueMesh
        </div>

        <div class="rm-subtitle">
            Autonomous food-rescue coordination
        </div>
        """,
        unsafe_allow_html=True,
    )

with header_center:
    demo_mode = st.toggle(
        "Demo Mode",
        value=True,
        key="demo_mode",
    )

with header_right:
    account = st.selectbox(
        "Account",
        [
            "Demo User",
            "Operations Coordinator",
        ],
        label_visibility="collapsed",
    )


database_ok = (
    check_database()
)

render_database_status(
    database_ok
)

st.divider()


# =========================================================
# NAVIGATION
# =========================================================

role = st.radio(
    "Navigation",
    [
        "Donor",
        "Driver",
        "Pantry",
        "Operations",
    ],
    horizontal=True,
    label_visibility="collapsed",
    key="active_role",
)


if not database_ok:
    st.stop()


# =========================================================
# VIEWS
# =========================================================

if role == "Donor":
    render_donor_view()

elif role == "Driver":
    render_driver_view()

elif role == "Pantry":
    render_pantry_view()

elif role == "Operations":
    render_operations_view()


# =========================================================
# FOOTER
# =========================================================

st.divider()

mode = (
    "Demo Mode"
    if demo_mode
    else "Standard Mode"
)

st.caption(
    f"RescueMesh • {mode} • {account}"
)