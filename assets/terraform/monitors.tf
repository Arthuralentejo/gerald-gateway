# =============================================================================
# Gerald Gateway - Datadog Monitors (Terraform)
# =============================================================================
#
# This file defines alerts for the Gerald Gateway BNPL service.
#
# Alert Categories:
# 1. Business Alerts (Product/Finance visibility)
# 2. Technical Alerts (Engineering/SRE on-call)
#
# Usage:
#   terraform init
#   terraform plan -var="datadog_api_key=xxx" -var="datadog_app_key=xxx"
#   terraform apply
# =============================================================================

terraform {
  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.40"
    }
  }
}

provider "datadog" {
  api_key = var.datadog_api_key
  app_key = var.datadog_app_key
}

# =============================================================================
# Business Alerts (Product/Finance)
# =============================================================================

# Alert: Approval rate dropped >20% vs 24h baseline
# Why: Signals broken risk logic, upstream data issues, or user quality change
resource "datadog_monitor" "approval_rate_drop" {
  name    = "${var.service_name} - Approval rate drop >20% vs 24h baseline"
  type    = "query alert"
  message = <<-EOT
    ## Approval Rate Alert

    Approval rate has dropped more than 20% compared to the 24-hour baseline.

    **Possible causes:**
    - Risk scoring logic bug (check recent deploys)
    - Bank API returning incomplete/invalid data
    - Significant change in user quality (new marketing channel?)

    **Diagnostic steps:**
    1. Check score distribution: `SELECT percentile_cont(0.5) FROM bnpl_decisions`
    2. Compare factor distributions to baseline
    3. Check `gerald_bank_fetch_failures_total` for data issues
    4. Review recent code changes

    @pagerduty-${var.pagerduty_service} @slack-${var.slack_channel_oncall}
    Notify: @${var.product_team_email}
  EOT

  query = <<-EOQ
    (sum:gerald_decision_total{outcome:approved}.as_rate() /
     (sum:gerald_decision_total{outcome:approved}.as_rate() +
      sum:gerald_decision_total{outcome:declined}.as_rate())) /
    (moving_rollup(sum:gerald_decision_total{outcome:approved}.as_rate(), 86400, 'avg') /
     moving_rollup((sum:gerald_decision_total{outcome:approved}.as_rate() +
                    sum:gerald_decision_total{outcome:declined}.as_rate()), 86400, 'avg'))
    < 0.8
  EOQ

  monitor_thresholds {
    critical = 0.8
    warning  = 0.9
  }

  notify_no_data    = false
  require_full_window = true
  evaluation_delay  = 300

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:business",
    "severity:high"
  ]
}

# Alert: Average credit limit dropped >30% vs 7-day baseline
# Why: Over-conservative scoring hurts revenue
resource "datadog_monitor" "credit_limit_drop" {
  name    = "${var.service_name} - Avg credit limit drop >30% vs 7d baseline"
  type    = "query alert"
  message = <<-EOT
    ## Credit Limit Alert

    Average credit limit has dropped more than 30% compared to the 7-day baseline.

    **Possible causes:**
    - Scoring thresholds changed (check SCORING_* env vars)
    - User quality degradation
    - Bug in credit limit calculation

    **Impact:**
    - Reduced Cornerstore revenue per user
    - Users may not be able to make desired purchases

    Notify: @${var.product_team_email} @${var.finance_team_email}
  EOT

  query = <<-EOQ
    avg:gerald_avg_credit_limit_dollars{*} /
    moving_rollup(avg:gerald_avg_credit_limit_dollars{*}, 604800, 'avg')
    < 0.7
  EOQ

  monitor_thresholds {
    critical = 0.7
    warning  = 0.8
  }

  notify_no_data    = false
  require_full_window = true

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:business",
    "severity:medium"
  ]
}

# =============================================================================
# Technical Alerts (Engineering/SRE)
# =============================================================================

# Alert: Error rate >2% over 5 minutes
# Why: Indicates service degradation or bugs
resource "datadog_monitor" "error_rate" {
  name    = "${var.service_name} - Error rate >2% (5m)"
  type    = "query alert"
  message = <<-EOT
    ## High Error Rate Alert

    Error rate has exceeded 2% over the last 5 minutes.

    **Diagnostic steps:**
    1. Check application logs for stack traces
    2. Verify database connectivity
    3. Check Bank API health (`gerald_bank_fetch_failures_total`)
    4. Review recent deploys

    @pagerduty-${var.pagerduty_service}
  EOT

  query = <<-EOQ
    sum(last_5m):sum:gerald_http_requests_total{status:5*}.as_count() /
    sum:gerald_http_requests_total{*}.as_count() * 100 > 2
  EOQ

  monitor_thresholds {
    critical = 2
    warning  = 1
  }

  notify_no_data    = false
  require_full_window = true

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:technical",
    "severity:critical"
  ]
}

# Alert: Bank API failure rate >10% over 10 minutes
# Why: Upstream dependency is failing, blocking all decisions
resource "datadog_monitor" "bank_api_failures" {
  name    = "${var.service_name} - Bank API failure rate >10% (10m)"
  type    = "query alert"
  message = <<-EOT
    ## Bank API Failure Alert

    Bank API failure rate has exceeded 10% over the last 10 minutes.

    **Impact:**
    - Users cannot get BNPL decisions
    - All approval requests will fail

    **Diagnostic steps:**
    1. Check Bank API status page
    2. Verify network connectivity to Bank API
    3. Check for timeout issues (`gerald_bank_fetch_failures_total{error_type:timeout}`)
    4. Review Bank API response codes

    @pagerduty-${var.pagerduty_service}
  EOT

  query = <<-EOQ
    sum(last_10m):sum:gerald_bank_fetch_failures_total{*}.as_count() /
    sum:gerald_bank_fetch_total{*}.as_count() * 100 > 10
  EOQ

  monitor_thresholds {
    critical = 10
    warning  = 5
  }

  notify_no_data    = false
  require_full_window = true

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:technical",
    "severity:critical",
    "dependency:bank-api"
  ]
}

# Alert: Webhook retry queue >100 items
# Why: Ledger webhook delivery is backing up
resource "datadog_monitor" "webhook_queue_depth" {
  name    = "${var.service_name} - Webhook queue depth >100"
  type    = "query alert"
  message = <<-EOT
    ## Webhook Queue Alert

    Webhook queue depth has exceeded 100 items.

    **Impact:**
    - Ledger notifications are delayed
    - Financial records may be out of sync

    **Diagnostic steps:**
    1. Check Ledger API health
    2. Verify webhook endpoint is responding
    3. Check `gerald_webhook_failures_total` for delivery failures
    4. Consider temporarily increasing retry workers

    @slack-${var.slack_channel_oncall}
  EOT

  query = "avg(last_5m):avg:gerald_webhook_queue_depth{*} > 100"

  monitor_thresholds {
    critical = 100
    warning  = 50
  }

  notify_no_data    = false
  require_full_window = false

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:technical",
    "severity:medium",
    "dependency:ledger"
  ]
}

# Alert: Decision latency p95 >5s
# Why: Slow responses impact user experience
resource "datadog_monitor" "decision_latency" {
  name    = "${var.service_name} - Decision latency p95 >5s"
  type    = "query alert"
  message = <<-EOT
    ## High Latency Alert

    Decision API p95 latency has exceeded 5 seconds.

    **Possible causes:**
    - Database slow queries
    - Bank API slow responses
    - Resource contention

    **Diagnostic steps:**
    1. Check database query performance
    2. Check `gerald_bank_fetch_latency_seconds` for upstream slowness
    3. Review CPU/memory usage
    4. Check for lock contention

    @slack-${var.slack_channel_oncall}
  EOT

  query = "avg(last_5m):avg:gerald_decision_latency_seconds.95percentile{*} > 5"

  monitor_thresholds {
    critical = 5
    warning  = 2.5
  }

  notify_no_data    = false
  require_full_window = false

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:technical",
    "severity:medium"
  ]
}

# Alert: No decisions in last 15 minutes (during business hours)
# Why: Service may be completely down
resource "datadog_monitor" "no_traffic" {
  name    = "${var.service_name} - No decisions in 15m (business hours)"
  type    = "query alert"
  message = <<-EOT
    ## No Traffic Alert

    No BNPL decisions have been made in the last 15 minutes during business hours.

    **Possible causes:**
    - Service is down
    - Load balancer misconfiguration
    - Upstream routing issue

    **Diagnostic steps:**
    1. Check if service is running (`kubectl get pods` or equivalent)
    2. Verify health endpoint: `curl /v1/health`
    3. Check load balancer logs
    4. Verify DNS resolution

    @pagerduty-${var.pagerduty_service}
  EOT

  query = "sum(last_15m):sum:gerald_decision_total{*}.as_count() < 1"

  monitor_thresholds {
    critical = 1
  }

  notify_no_data    = true
  no_data_timeframe = 20
  require_full_window = false

  # Only alert during business hours (9am-9pm UTC, Mon-Fri)
  restricted_roles = []

  tags = [
    "service:${var.service_name}",
    "team:bnpl",
    "alert-type:technical",
    "severity:critical"
  ]
}
