"""Structured logging and metrics for the AgentCore runtime container.

Uses aws-lambda-powertools Logger in standalone mode (no Lambda context required).
The container already ships aws-opentelemetry-distro for X-Ray trace propagation;
this module adds structured JSON logging with correlation IDs and merchant context.
"""

from __future__ import annotations

from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(
    service="design-studio-agent",
    log_uncaught_exceptions=True,
)

metrics = Metrics(
    namespace="DesignStudio",
    service="design-studio-agent",
)

__all__ = ["logger", "metrics", "MetricUnit"]
