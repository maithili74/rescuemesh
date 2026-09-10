import streamlit as st

from app.database.db import get_connection
from app.events.processor import process_event


# =========================================================
# DATABASE STATE
# =========================================================


def _get_disruption_state(operation_id):
    """
    Load only the state needed by the Demo Simulator.

    The simulator does not change database state directly.
    All mutations still go through process_event().
    """

    conn = get_connection()

    try:
        operation = conn.execute(
            """
            SELECT
                id,
                status,
                donation_id,
                rescued_lbs,
                unrescued_lbs
            FROM operations
            WHERE id = ?
            """,
            (operation_id,),
        ).fetchone()

        if operation is None:
            return None

        routes = conn.execute(
            """
            SELECT
                r.id AS route_id,
                r.driver_id,
                d.name AS driver_name,
                r.assigned_lbs,
                r.status AS route_status
            FROM driver_routes r
            JOIN drivers d
                ON d.id = r.driver_id
            WHERE r.operation_id = ?
            ORDER BY r.id
            """,
            (operation_id,),
        ).fetchall()

        stops = conn.execute(
            """
            SELECT
                s.id AS stop_id,
                s.route_id,
                s.pantry_id,
                p.name AS pantry_name,
                s.quantity_lbs,
                s.status AS stop_status,

                r.driver_id,
                d.name AS driver_name,
                r.status AS route_status

            FROM delivery_stops s

            JOIN driver_routes r
                ON r.id = s.route_id

            JOIN drivers d
                ON d.id = r.driver_id

            JOIN pantries p
                ON p.id = s.pantry_id

            WHERE r.operation_id = ?

            ORDER BY
                r.id,
                s.stop_order
            """,
            (operation_id,),
        ).fetchall()

        pantries = conn.execute(
            """
            SELECT
                id,
                name,
                max_capacity_lbs,
                available_capacity_lbs
            FROM pantries
            ORDER BY name
            """
        ).fetchall()

        return {
            "operation": dict(operation),
            "routes": [
                dict(row)
                for row in routes
            ],
            "stops": [
                dict(row)
                for row in stops
            ],
            "pantries": [
                dict(row)
                for row in pantries
            ],
        }

    finally:
        conn.close()


# =========================================================
# EVENT EXECUTION
# =========================================================


def _run_demo_event(
    operation_id,
    event_type,
    payload,
    label,
):
    """
    Send a simulated external event through the real
    RescueMesh event processor.
    """

    try:
        result = process_event(
            operation_id=operation_id,
            event_type=event_type,
            payload=payload,
        )

        st.session_state[
            "last_disruption_result"
        ] = {
            "ok": True,
            "label": label,
            "event_type": event_type,
            "result": result,
        }

    except Exception as error:
        st.session_state[
            "last_disruption_result"
        ] = {
            "ok": False,
            "label": label,
            "event_type": event_type,
            "error": str(error),
        }

    st.cache_data.clear()
    st.rerun()


# =========================================================
# RESULT MESSAGE
# =========================================================


def _render_last_result():
    feedback = st.session_state.get(
        "last_disruption_result"
    )

    if not feedback:
        return

    if not feedback["ok"]:
        st.error(
            f"{feedback['label']} failed: "
            f"{feedback['error']}"
        )
        return

    response = feedback["result"]

    backend_result = (
        response.get("result", {})
        if isinstance(response, dict)
        else {}
    )

    status = backend_result.get(
        "status",
        response.get("status", "processed"),
    )

    if status in {
        "requires_human_escalation",
        "awaiting_human",
    }:
        st.warning(
            "⚠️ Disruption processed. "
            "RescueMesh could not safely recover the "
            "entire rescue autonomously, so human "
            "review is required."
        )

    elif status in {
        "in_transit_replanned",
        "replanned",
        "operation_started",
    }:
        st.success(
            "✅ Disruption processed and RescueMesh "
            "found a safe replacement plan."
        )

    else:
        st.success(
            f"✅ Event processed successfully: {status}"
        )

    with st.expander(
        "View backend event result",
        expanded=False,
    ):
        st.json(response)


# =========================================================
# MAIN UI
# =========================================================


def render_disruption_controls(operation_id):
    """
    Render hackathon-only disruption controls.

    These represent external events that would normally
    arrive from a driver app, pantry system, SMS link,
    or operations integration.
    """

    state = _get_disruption_state(
        operation_id
    )

    if state is None:
        st.error(
            f"Operation {operation_id} "
            "could not be found."
        )
        return

    operation = state["operation"]
    routes = state["routes"]
    stops = state["stops"]
    pantries = state["pantries"]

    st.divider()

    st.subheader(
        "⚠️ Disruption Simulator"
    )

    st.caption(
        "Simulate real-world failures. "
        "Every action below is sent through "
        "RescueMesh's real backend event processor."
    )

    _render_last_result()

    (
        pantry_closed_tab,
        delivery_failed_tab,
        driver_cancel_tab,
        capacity_tab,
    ) = st.tabs(
        [
            "🏚 Pantry Closed",
            "❌ Delivery Failed",
            "🚫 Driver Cancelled",
            "📉 Capacity Change",
        ]
    )

    # =====================================================
    # 1. PANTRY CLOSED
    # =====================================================

    with pantry_closed_tab:

        st.write(
            "Use this when an assigned pantry "
            "suddenly becomes unavailable."
        )

        active_stops = [
            stop
            for stop in stops
            if (
                stop["stop_status"] == "pending"
                and
                stop["route_status"]
                not in {
                    "cancelled",
                    "completed",
                }
            )
        ]

        # One pantry may appear in more than one stop.
        pantry_choices = {}

        for stop in active_stops:
            pantry_choices[
                stop["pantry_id"]
            ] = {
                "id":
                    stop["pantry_id"],

                "name":
                    stop["pantry_name"],

                "quantity_lbs":
                    stop["quantity_lbs"],

                "driver_name":
                    stop["driver_name"],

                "route_status":
                    stop["route_status"],
            }

        pantry_choices = list(
            pantry_choices.values()
        )

        if not pantry_choices:

            st.info(
                "There are currently no pending "
                "pantry destinations that can be closed."
            )

        else:

            selected_pantry = st.selectbox(
                "Assigned pantry",
                pantry_choices,
                format_func=lambda item: (
                    f"{item['name']} — "
                    f"{item['quantity_lbs']:.0f} lbs — "
                    f"{item['driver_name']} — "
                    f"{item['route_status']}"
                ),
                key=
                    f"closed_pantry_{operation_id}",
            )

            st.caption(
                "Before pickup: tests normal replanning. "
                "After pickup: tests in-transit recovery."
            )

            if st.button(
                "Simulate Pantry Closed",
                type="primary",
                use_container_width=True,
                key=
                    f"simulate_pantry_closed_{operation_id}",
            ):

                _run_demo_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "PANTRY_CLOSED",

                    payload={
                        "pantry_id":
                            selected_pantry["id"],
                    },

                    label=
                        (
                            f"{selected_pantry['name']} "
                            "closed"
                        ),
                )

    # =====================================================
    # 2. DELIVERY FAILED
    # =====================================================

    with delivery_failed_tab:

        st.write(
            "Use this after food has been picked up "
            "when the driver cannot complete a drop-off."
        )

        delivery_failure_stops = [
            stop
            for stop in stops
            if (
                stop["route_status"] == "picked_up"
                and
                stop["stop_status"] == "pending"
            )
        ]

        if not delivery_failure_stops:

            st.info(
                "No delivery can currently be failed. "
                "The driver must Accept and Pick Up "
                "the food first."
            )

        else:

            failed_stop = st.selectbox(
                "Drop-off that failed",
                delivery_failure_stops,
                format_func=lambda stop: (
                    f"{stop['driver_name']} → "
                    f"{stop['pantry_name']} — "
                    f"{stop['quantity_lbs']:.0f} lbs"
                ),
                key=
                    f"delivery_failed_stop_{operation_id}",
            )

            if st.button(
                "Simulate Delivery Failed",
                type="primary",
                use_container_width=True,
                key=
                    f"simulate_delivery_failed_{operation_id}",
            ):

                _run_demo_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "DELIVERY_FAILED",

                    payload={
                        "stop_id":
                            failed_stop["stop_id"],
                    },

                    label=
                        (
                            "Delivery failed at "
                            f"{failed_stop['pantry_name']}"
                        ),
                )

    # =====================================================
    # 3. DRIVER CANCELLED
    # =====================================================

    with driver_cancel_tab:

        st.write(
            "Use this when an assigned driver becomes "
            "unavailable before collecting the food."
        )

        cancellable_routes = [
            route
            for route in routes
            if (
                route["route_status"]
                not in {
                    "picked_up",
                    "completed",
                    "cancelled",
                }
            )
        ]

        if not cancellable_routes:

            st.info(
                "There is no driver that can currently "
                "cancel before pickup."
            )

        else:

            cancelled_route = st.selectbox(
                "Driver",
                cancellable_routes,
                format_func=lambda route: (
                    f"{route['driver_name']} — "
                    f"{route['assigned_lbs']:.0f} lbs — "
                    f"{route['route_status']}"
                ),
                key=
                    f"cancel_driver_{operation_id}",
            )

            if st.button(
                "Simulate Driver Cancelled",
                type="primary",
                use_container_width=True,
                key=
                    f"simulate_driver_cancelled_{operation_id}",
            ):

                _run_demo_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "DRIVER_CANCELLED",

                    payload={
                        "driver_id":
                            cancelled_route[
                                "driver_id"
                            ],
                    },

                    label=
                        (
                            f"{cancelled_route['driver_name']} "
                            "cancelled"
                        ),
                )

    # =====================================================
    # 4. PANTRY CAPACITY CHANGE
    # =====================================================

    with capacity_tab:

        st.write(
            "Use this when a pantry reports that its "
            "total receiving capacity has changed."
        )

        if not pantries:

            st.info(
                "No pantries are available."
            )

        else:

            capacity_pantry = st.selectbox(
                "Pantry",
                pantries,
                format_func=lambda pantry: (
                    f"{pantry['name']} — "
                    f"max "
                    f"{pantry['max_capacity_lbs']:.0f} lbs — "
                    f"available "
                    f"{pantry['available_capacity_lbs']:.0f} lbs"
                ),
                key=
                    f"capacity_pantry_{operation_id}",
            )

            current_max = float(
                capacity_pantry[
                    "max_capacity_lbs"
                ]
            )

            current_available = float(
                capacity_pantry[
                    "available_capacity_lbs"
                ]
            )

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Current Total Capacity",
                    f"{current_max:.0f} lbs",
                )

            with col2:
                st.metric(
                    "Currently Available",
                    f"{current_available:.0f} lbs",
                )

            new_capacity = st.number_input(
                "New total capacity (lbs)",
                min_value=0.0,
                max_value=5000.0,
                value=current_max,
                step=10.0,
                key=
                    f"new_capacity_{operation_id}_"
                    f"{capacity_pantry['id']}",
            )

            st.caption(
                "This changes the pantry's total "
                "capacity. RescueMesh decides whether "
                "the existing allocation is still valid "
                "or must be replanned."
            )

            if st.button(
                "Simulate Capacity Change",
                type="primary",
                use_container_width=True,
                key=
                    f"simulate_capacity_change_{operation_id}",
            ):

                _run_demo_event(
                    operation_id=
                        operation_id,

                    event_type=
                        "PANTRY_CAPACITY_CHANGED",

                    payload={
                        "pantry_id":
                            capacity_pantry["id"],

                        "new_max_capacity_lbs":
                            float(new_capacity),
                    },

                    label=
                        (
                            f"{capacity_pantry['name']} "
                            "capacity changed"
                        ),
                )