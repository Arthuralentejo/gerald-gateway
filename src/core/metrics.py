"""Prometheus metrics for the Gerald Gateway service.

Metrics are organized into two categories:

Business Metrics (for Product/Finance):
- gerald_decision_total: Decisions by outcome
- gerald_credit_limit_bucket: Credit limits by bucket
- gerald_approval_rate_1h: Rolling approval rate
- gerald_avg_credit_limit_dollars: Average credit limit

Technical Metrics (for Engineering/SRE):
- gerald_decision_latency_seconds: Decision request latency
- gerald_webhook_latency_seconds: Webhook delivery latency
- gerald_bank_fetch_failures_total: Bank API failures
- gerald_bank_fetch_latency_seconds: Bank API latency
- gerald_webhook_retry_total: Webhook retries
- gerald_webhook_queue_depth: Webhook queue depth
- gerald_http_requests_total: HTTP requests by endpoint/status
"""

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


# =============================================================================
# Business Metrics (Product/Finance dashboards)
# =============================================================================

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
    "Current 1-hour rolling approval rate (0.0-1.0)",
)

avg_credit_limit_gauge = Gauge(
    "gerald_avg_credit_limit_dollars",
    "Average credit limit granted in dollars",
)

# Track totals for computing rates
_approved_count = 0
_total_count = 0
_credit_limit_sum = 0


# =============================================================================
# Technical Metrics (Engineering/SRE dashboards)
# =============================================================================

decision_latency = Histogram(
    "gerald_decision_latency_seconds",
    "Decision request latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

webhook_latency = Histogram(
    "gerald_webhook_latency_seconds",
    "Webhook delivery latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

bank_fetch_latency = Histogram(
    "gerald_bank_fetch_latency_seconds",
    "Bank API fetch latency in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

bank_fetch_failures = Counter(
    "gerald_bank_fetch_failures_total",
    "Total number of bank API failures",
    ["error_type"],  # timeout, error, not_found
)

bank_fetch_total = Counter(
    "gerald_bank_fetch_total",
    "Total number of bank API requests",
    ["status"],  # success, failure
)

webhook_retries = Counter(
    "gerald_webhook_retry_total",
    "Total number of webhook retries",
)

webhook_failures = Counter(
    "gerald_webhook_failures_total",
    "Total number of webhook delivery failures (after all retries)",
)

webhook_success = Counter(
    "gerald_webhook_success_total",
    "Total number of successful webhook deliveries",
)

webhook_queue_depth = Gauge(
    "gerald_webhook_queue_depth",
    "Current webhook queue depth",
)

http_requests_total = Counter(
    "gerald_http_requests_total",
    "Total HTTP requests by endpoint and status",
    ["method", "endpoint", "status"],
)

http_request_latency = Histogram(
    "gerald_http_request_latency_seconds",
    "HTTP request latency by endpoint",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)


# =============================================================================
# Helper Functions
# =============================================================================

def record_decision(approved: bool, credit_limit_cents: int) -> None:
    """Record a decision in metrics."""
    global _approved_count, _total_count, _credit_limit_sum

    outcome = "approved" if approved else "declined"
    decision_total.labels(outcome=outcome).inc()

    # Track for rate calculation
    _total_count += 1
    if approved:
        _approved_count += 1
        _credit_limit_sum += credit_limit_cents

    # Update gauges
    if _total_count > 0:
        approval_rate_gauge.set(_approved_count / _total_count)
    if _approved_count > 0:
        avg_credit_limit_gauge.set((_credit_limit_sum / _approved_count) / 100)

    # Determine bucket
    bucket = _get_credit_limit_bucket(credit_limit_cents)
    credit_limit_bucket.labels(bucket=bucket, outcome=outcome).inc()


def _get_credit_limit_bucket(credit_limit_cents: int) -> str:
    """Map credit limit to bucket label."""
    if credit_limit_cents == 0:
        return "0"
    elif credit_limit_cents <= 10000:
        return "100"
    elif credit_limit_cents <= 20000:
        return "100-200"
    elif credit_limit_cents <= 30000:
        return "200-300"
    elif credit_limit_cents <= 40000:
        return "300-400"
    elif credit_limit_cents <= 50000:
        return "400-500"
    else:
        return "500-600"


@contextmanager
def track_decision_latency() -> Generator[None, None, None]:
    """Context manager to track decision latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        decision_latency.observe(duration)


@contextmanager
def track_webhook_latency() -> Generator[None, None, None]:
    """Context manager to track webhook latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        webhook_latency.observe(duration)


@contextmanager
def track_bank_fetch_latency() -> Generator[None, None, None]:
    """Context manager to track bank API fetch latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        bank_fetch_latency.observe(duration)


def record_bank_fetch_success() -> None:
    """Record a successful bank API fetch."""
    bank_fetch_total.labels(status="success").inc()


def record_bank_fetch_failure(error_type: str) -> None:
    """Record a bank API fetch failure."""
    bank_fetch_total.labels(status="failure").inc()
    bank_fetch_failures.labels(error_type=error_type).inc()


def record_webhook_retry() -> None:
    """Record a webhook retry attempt."""
    webhook_retries.inc()


def record_webhook_success() -> None:
    """Record a successful webhook delivery."""
    webhook_success.inc()


def record_webhook_failure() -> None:
    """Record a failed webhook delivery (after all retries)."""
    webhook_failures.inc()


def record_http_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """Record an HTTP request."""
    http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    http_request_latency.labels(method=method, endpoint=endpoint).observe(duration)


def get_metrics() -> bytes:
    """Get current metrics in Prometheus format."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Get the content type for metrics response."""
    return CONTENT_TYPE_LATEST
