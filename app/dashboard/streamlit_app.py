import streamlit as st
from pathlib import Path
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

from app.dashboard.views.demo import (
    render_demo_view,
)
from app.dashboard.views.evaluation import (
    render_evaluation_view,
)
from app.dashboard.theme import (
    apply_rescuemesh_theme,
)

ASSETS_DIR = Path(__file__).parent / "assets"


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="RescueMesh",
    page_icon="🥕",
    layout="wide",
)

apply_rescuemesh_theme()


# =========================================================
# HERO HEADER
# =========================================================

hero_left, hero_right = st.columns(
    [3.2, 1.2],
    vertical_alignment="center",
)

with hero_left:

    st.title(
        "RescueMesh"
    )

    st.markdown(
        "### Turning surplus food into coordinated rescues."
    )

    st.markdown(
        """
        RescueMesh connects food donors, volunteer drivers,
        and community pantries to move surplus food where
        it is needed most. It creates feasible rescue plans,
        coordinates deliveries, adapts when conditions change,
        and involves people when human judgment is needed.
        """
    )


with hero_right:

    image_path = (
        ASSETS_DIR
        / "image.png"
    )

    if image_path.exists():

        st.image(
            str(image_path),
            use_container_width=True,
        )


# =========================================================
# DEMO MODE
# =========================================================

demo_left, demo_right = st.columns(
    [5, 1]
)

with demo_right:

    demo_mode = st.toggle(
        "Demo Mode",
        value=True,
    )

# =========================================================
# BACKEND STATUS
# =========================================================

try:

    database_ok = (
        check_database()
    )

    if database_ok:

        st.success(
            "🟢 RescueMesh backend connected"
        )

    else:

        st.error(
            "🔴 RescueMesh backend unavailable"
        )

except Exception as error:

    st.error(
        f"🔴 Backend connection failed: {error}"
    )


st.divider()


# =========================================================
# NAVIGATION
# =========================================================

navigation_options = [
    "Donor",
    "Driver Dispatch",
    "Pantry",
    "Operations",
    "Impact & Evaluation",
]

if demo_mode:

    navigation_options.append(
        "🧪 Demo Simulator"
    )


selected_view = st.radio(
    "Navigation",
    navigation_options,
    horizontal=True,
    label_visibility="collapsed",
)


st.divider()


# =========================================================
# ROUTING
# =========================================================

if selected_view == "Donor":

    render_donor_view()


elif selected_view == "Driver Dispatch":

    render_driver_view()


elif selected_view == "Pantry":

    render_pantry_view()


elif selected_view == "Operations":

    render_operations_view()


elif selected_view == "Impact & Evaluation":

    render_evaluation_view()


elif selected_view == "🧪 Demo Simulator":

    render_demo_view()


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "RescueMesh • Strands Agents + Amazon Bedrock "
    "+ deterministic logistics optimization"
)