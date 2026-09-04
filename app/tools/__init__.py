from app.tools.state_tools import (
    inspect_donation,
    inspect_network_state,
    inspect_operation,
    inspect_operation_events,
)

from app.tools.planning_tools import (
    plan_rescue,
)

from app.tools.execution_tools import (
    process_rescue_event,
)

from app.tools.escalation_tools import (
    inspect_pending_escalations,
    inspect_escalation,
    approve_human_escalation,
    reject_human_escalation,
)


# Tools the autonomous RescueCoordinator is allowed to use.
RESCUE_COORDINATOR_TOOLS = [
    inspect_donation,
    inspect_network_state,
    inspect_operation,
    inspect_operation_events,
    plan_rescue,
    inspect_pending_escalations,
    inspect_escalation,
]


# All Strands wrappers.
# Useful for testing, but NOT passed directly to the autonomous agent.
RESCUEMESH_TOOLS = [
    inspect_donation,
    inspect_network_state,
    inspect_operation,
    inspect_operation_events,
    plan_rescue,
    process_rescue_event,
    inspect_pending_escalations,
    inspect_escalation,
    approve_human_escalation,
    reject_human_escalation,
]