FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca
WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=eu-north-1 \
    AWS_DEFAULT_REGION=eu-north-1

# Install dependencies first for better layer caching. Single source of truth
# is pyproject.toml — the [runtime] extra adds bedrock-agentcore + ADOT.
COPY pyproject.toml ./
COPY conversational_agent/ ./conversational_agent/
COPY fonts.json storefront.html ./
RUN uv pip install --no-cache ".[runtime]"

# Non-root user (AgentCore convention).
RUN useradd -m -u 1000 bedrock_agentcore && chown -R bedrock_agentcore:bedrock_agentcore /app
USER bedrock_agentcore

# AgentCore Runtime invokes the agent on 8080.
EXPOSE 8080

CMD ["opentelemetry-instrument", "python", "-m", "conversational_agent.agentcore_app"]
