from strands import Agent
from strands.models import BedrockModel


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

    Local RescueMesh:
        uses the normal Python tools.

    AgentCore:
        supplies the HTTP-backed remote tools.
    """

    # Import the heavy/local RescueMesh tool stack ONLY
    # when the caller did not provide another tool set.
    #
    # AgentCore passes REMOTE_RESCUE_COORDINATOR_TOOLS,
    # so this local import never happens in AgentCore.
    if tools is None:
        from app.tools import (
            RESCUE_COORDINATOR_TOOLS,
        )

        tools = RESCUE_COORDINATOR_TOOLS

    bedrock_model = BedrockModel(
        model_id=(
            "us.anthropic."
            "claude-haiku-4-5-20251001-v1:0"
        ),
        region_name="us-east-1",
        temperature=0.0,
    )

    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
    )


class _LazyLocalAgent:
    """
    Preserve the existing:

        from app.agent.rescue_coordinator import agent

    interface without creating the local agent at module
    import time.

    This keeps AgentCore lightweight while preserving the
    existing RescueMesh application behavior.
    """

    def __init__(self):
        self._agent = None

    def _get_agent(self):
        if self._agent is None:
            self._agent = (
                create_rescue_coordinator()
            )

        return self._agent

    def __call__(
        self,
        *args,
        **kwargs,
    ):
        return self._get_agent()(
            *args,
            **kwargs,
        )

    def __getattr__(
        self,
        name,
    ):
        return getattr(
            self._get_agent(),
            name,
        )


agent = _LazyLocalAgent()