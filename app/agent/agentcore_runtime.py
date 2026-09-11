from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp,
)

from app.agent.rescue_coordinator import (
    create_rescue_coordinator,
)
from app.tools.remote_tools import (
    REMOTE_RESCUE_COORDINATOR_TOOLS,
)

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload, context):
    """
    Amazon Bedrock AgentCore Runtime entrypoint.

    AgentCore receives a JSON payload such as:

        {
            "prompt": "Inspect donation 21 and plan the rescue."
        }

    The request is passed to the same RescueMesh Strands
    RescueCoordinator used by the existing application.
    """

    if not isinstance(
        payload,
        dict,
    ):
        return {
            "error":
                "Payload must be a JSON object."
        }

    prompt = payload.get(
        "prompt",
        "",
    )

    if (
        not isinstance(
            prompt,
            str,
        )
        or
        not prompt.strip()
    ):
        return {
            "error":
                "'prompt' must be a non-empty string."
        }

    # Fresh agent for this invocation.
    # This prevents unrelated RescueMesh requests from
    # sharing accidental conversational state.
    agent = create_rescue_coordinator(
        tools=REMOTE_RESCUE_COORDINATOR_TOOLS,
    )

    result = agent(
        prompt.strip()
    )

    return {
        "response":
            str(result)
    }


if __name__ == "__main__":
    app.run()