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

    Expected payload:

        {
            "prompt": "Inspect donation 21 and plan the rescue."
        }

    The AgentCore-hosted RescueCoordinator uses remote
    RescueMesh tools. Those tools call the FastAPI backend
    running with the main RescueMesh application.
    """

    # -----------------------------------------------------
    # VALIDATE PAYLOAD
    # -----------------------------------------------------

    if not isinstance(
        payload,
        dict,
    ):
        return {
            "response":
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
        or not prompt.strip()
    ):
        return {
            "response":
                "A non-empty prompt is required."
        }

    # -----------------------------------------------------
    # CREATE AGENTCORE RESCUE COORDINATOR
    # -----------------------------------------------------

    # A fresh agent is created for every invocation.
    #
    # IMPORTANT:
    # AgentCore must use the REMOTE tools because the
    # SQLite database and deterministic optimizer live
    # on the RescueMesh backend server, not inside the
    # AgentCore Runtime container.

    agent = create_rescue_coordinator(
        tools=
            REMOTE_RESCUE_COORDINATOR_TOOLS
    )

    # -----------------------------------------------------
    # RUN STRANDS AGENT
    # -----------------------------------------------------

    result = agent(
        prompt.strip()
    )

    # -----------------------------------------------------
    # RETURN AGENTCORE RESPONSE
    # -----------------------------------------------------

    return {
        "response":
            str(result)
    }


if __name__ == "__main__":
    app.run()