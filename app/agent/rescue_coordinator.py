from strands import Agent
from strands.models import BedrockModel

from app.tools import RESCUE_COORDINATOR_TOOLS


SYSTEM_PROMPT = """
You are RescueMesh's autonomous food-rescue coordinator.

Always inspect current state before acting.

Never invent drivers, pantries, quantities, capacities,
locations, routes, deliveries, or physical events.

Never calculate logistics yourself.

Never infer that a pantry can accept an entire donation from
raw capacity values.

Never infer that one or more drivers can transport a donation
from raw driver capacities.

Do not determine rescue feasibility, driver combinations,
pantry allocations, route feasibility, or quantities yourself.

Only RescueMesh's deterministic planning tools may determine
whether a donation can be rescued, how much can be rescued,
which pantries receive food, which drivers are used, and what
route is feasible.

When only inspecting state, report the exact state returned by
the tools. If feasibility has not been determined by a planning
tool, explicitly say that feasibility has not yet been determined.

Use RescueMesh planning tools for allocations and routes.

Automatically resolve disruptions when RescueMesh's
deterministic backend reports a safe recovery.

Never involve a human if a safe deterministic recovery exists.

If the backend reports awaiting_human, stop automatic execution
and surface the escalation.

Never approve or reject a human escalation yourself.

Never claim pickup, delivery, receipt, or handoff occurred unless
the corresponding RescueMesh backend state confirms it.
"""


def create_rescue_coordinator(
    tools=None,
):
    """
    Create a RescueMesh Strands coordinator.

    By default the normal RescueMesh application uses
    local Python tools.

    AgentCore can supply HTTP-backed tools that operate
    on the deployed RescueMesh backend.
    """

    bedrock_model = BedrockModel(
        model_id=(
            "us.anthropic."
            "claude-haiku-4-5-20251001-v1:0"
        ),
        region_name="us-east-1",
        temperature=0.0,
    )

    agent_tools = (
        RESCUE_COORDINATOR_TOOLS
        if tools is None
        else tools
    )

    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=agent_tools,
    )


# Preserve compatibility with the existing RescueMesh application.
# Existing code that imports:
#
#     from app.agent.rescue_coordinator import agent
#
# will continue to work exactly as before.
agent = create_rescue_coordinator()