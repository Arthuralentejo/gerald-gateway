"""Prometheus metrics for the Gerald Gateway service."""

from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


# Business metrics
decision_total = Counter(
    "gerald_decision_total",
    "Total number of BNPL decisions made",
    ["outcome"],  # approved, declined
)

credit_limit_bucket = Counter(
    "gerald_credit_limit_bucket",
    "Credit limits granted by bucket",
    ["bucket", "outcome"],
)

approval_rate_gauge = Gauge(
    "gerald_approval_rate_1h",
    "Current 1-hour rolling approval rate",
)

avg_credit_limit_gauge = Gauge(
    "gerald_avg_credit_limit_dollars",
    "Average credit limit granted in dollars",
)


# Technical metrics
decision_latency = Histogram(
    "gerald_decision_latency_seconds",
    "Decision request latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

webhook_latency = Histogram(
    "gerald_webhook_latency_seconds",
    "Webhook delivery latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

bank_fetch_failures = Counter(
    "gerald_bank_fetch_failures_total",
    "Total number of bank API failures",
    ["error_type"],  # timeout, error, not_found
)

webhook_retries = Counter(
    "gerald_webhook_retry_total",
    "Total number of webhook retries",
)

webhook_queue_depth = Gauge(
    "gerald_webhook_queue_depth",
    "Current webhook queue depth",
)


def record_decision(approved: bool, credit_limit_cents: int) -> None:
    """Record a decision in metrics."""
    outcome = "approved" if approved else "declined"
    decision_total.labels(outcome=outcome).inc()

    # Determine bucket
    if credit_limit_cents == 0:
        bucket = "0"
    elif credit_limit_cents <= 10000:
        bucket = "100"
    elif credit_limit_cents <= 20000:
        bucket = "100-200"
    elif credit_limit_cents <= 30000:
        bucket = "200-300"
    elif credit_limit_cents <= 40000:
        bucket = "300-400"
    elif credit_limit_cents <= 50000:
        bucket = "400-500"
    else:
        bucket = "500-600"

    credit_limit_bucket.labels(bucket=bucket, outcome=outcome).inc()


def get_metrics() -> bytes:
    """Get current metrics in Prometheus format."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get the content type for metrics response."""
    return CONTENT_TYPE_LATEST
