import streamlit as st


def status_badge(
    status,
):
    status = (
        status
        or "unknown"
    )

    labels = {
        "available":
            "Available",

        "planned":
            "Planned",

        "active":
            "Active",

        "awaiting_human":
            "Needs Human",

        "completed":
            "Completed",

        "completed_partial":
            "Partial Completion",

        "cancelled":
            "Cancelled",

        "superseded":
            "Superseded",

        "manual_resolution":
            "Manual Resolution",
    }

    return labels.get(
        status,
        status.replace(
            "_",
            " ",
        ).title(),
    )


def render_database_status(
    database_ok,
):
    if database_ok:
        st.caption(
            "🟢 RescueMesh backend connected"
        )

    else:
        st.error(
            "🔴 RescueMesh database is unavailable."
        )