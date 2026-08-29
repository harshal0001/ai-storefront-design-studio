"""BedrockAgentCoreApp wrapper for container deployment.

Container entrypoint: registers ``runtime.invoke`` as the AgentCore HTTP handler.
Dev uses ``server.py`` (FastAPI) instead.
"""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from .runtime import invoke as agent_invoke

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    message = payload.get("message") or payload.get("prompt") or ""
    session_id = payload.get("session_id")
    merchant_id = payload.get("merchant_id") or payload.get("merchantId")
    return agent_invoke(message, session_id, merchant_id=merchant_id)


if __name__ == "__main__":
    app.run()
