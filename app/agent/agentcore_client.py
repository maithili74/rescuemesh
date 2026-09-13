import json
import os
import uuid

import boto3


def _read_response_body(response):
    """
    Read the response returned by AgentCore Runtime
    and convert it into plain text.
    """

    body = response.get(
        "response"
    )

    if body is None:
        raise RuntimeError(
            "AgentCore returned no response body."
        )

    if hasattr(body, "read"):
        raw = body.read()

        if isinstance(raw, bytes):
            return raw.decode("utf-8")

        return str(raw)

    chunks = []

    for chunk in body:
        if isinstance(chunk, bytes):
            chunks.append(
                chunk.decode("utf-8")
            )
        else:
            chunks.append(
                str(chunk)
            )

    return "".join(chunks)


def invoke_rescue_coordinator(
    prompt: str,
):
    """
    Invoke the RescueMesh RescueCoordinator running
    in Amazon Bedrock AgentCore Runtime.
    """

    runtime_arn = os.getenv(
        "AGENTCORE_RUNTIME_ARN",
        "",
    ).strip()

    if not runtime_arn:
        raise RuntimeError(
            "AGENTCORE_RUNTIME_ARN is not configured."
        )

    region = os.getenv(
        "AWS_REGION",
        "us-east-1",
    )

    qualifier = os.getenv(
        "AGENTCORE_QUALIFIER",
        "DEFAULT",
    )

    client = boto3.client(
        "bedrock-agentcore",
        region_name=region,
    )

    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=str(
            uuid.uuid4()
        ),
        qualifier=qualifier,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(
            {
                "prompt": prompt,
            }
        ).encode("utf-8"),
    )

    response_text = _read_response_body(
        response
    )

    try:
        response_json = json.loads(
            response_text
        )

    except json.JSONDecodeError:
        return response_text

    if isinstance(
        response_json,
        dict,
    ):
        return str(
            response_json.get(
                "response",
                response_json,
            )
        )

    return str(
        response_json
    )