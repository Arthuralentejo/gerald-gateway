"""Prometheus metrics for business and technical monitoring."""

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import Counter, Histogram, Gauge, REGISTRY, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST


decision_total = Counter(
    "gerald_decision_total",
    "Total number of BNPL decisions made",
    ["outcome"],
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

_approved_count = 0
_total_count = 0
_credit_limit_sum = 0

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
    ["error_type"],
)

bank_fetch_total = Counter(
    "gerald_bank_fetch_total",
    "Total number of bank API requests",
    ["status"],
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


def record_decision(approved: bool, credit_limit_cents: int) -> None:
    global _approved_count, _total_count, _credit_limit_sum

    outcome = "approved" if approved else "declined"
    decision_total.labels(outcome=outcome).inc()

    _total_count += 1
    if approved:
        _approved_count += 1
        _credit_limit_sum += credit_limit_cents

    if _total_count > 0:
        approval_rate_gauge.set(_approved_count / _total_count)
    if _approved_count > 0:
        avg_credit_limit_gauge.set((_credit_limit_sum / _approved_count) / 100)

    bucket = _get_credit_limit_bucket(credit_limit_cents)
    credit_limit_bucket.labels(bucket=bucket, outcome=outcome).inc()


def _get_credit_limit_bucket(credit_limit_cents: int) -> str:
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
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        decision_latency.observe(duration)


@contextmanager
def track_webhook_latency() -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        webhook_latency.observe(duration)


@contextmanager
def track_bank_fetch_latency() -> Generator[None, None, None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        bank_fetch_latency.observe(duration)


def record_bank_fetch_success() -> None:
    bank_fetch_total.labels(status="success").inc()


def record_bank_fetch_failure(error_type: str) -> None:
    bank_fetch_total.labels(status="failure").inc()
    bank_fetch_failures.labels(error_type=error_type).inc()


def record_webhook_retry() -> None:
    webhook_retries.inc()


def record_webhook_success() -> None:
    webhook_success.inc()


def record_webhook_failure() -> None:
    webhook_failures.inc()


def record_http_request(method: str, endpoint: str, status: int, duration: float) -> None:
    http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    http_request_latency.labels(method=method, endpoint=endpoint).observe(duration)


def get_metrics() -> bytes:
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
