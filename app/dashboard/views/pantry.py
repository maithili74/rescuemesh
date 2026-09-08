import streamlit as st


def render_pantry_view():
    st.header(
        "Pantry Portal"
    )

    st.caption(
        "Manage capacity, incoming food "
        "and delivery confirmations."
    )

    st.info(
        "Pantry operations will be connected "
        "to the RescueMesh event system next."
    )