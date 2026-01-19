# =============================================================================
# Gerald Gateway - Terraform Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Required Variables (no defaults)
# -----------------------------------------------------------------------------

variable "datadog_api_key" {
  type        = string
  description = "Datadog API key for authentication"
  sensitive   = true
}

variable "datadog_app_key" {
  type        = string
  description = "Datadog application key for authentication"
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Service Configuration
# -----------------------------------------------------------------------------

variable "service_name" {
  type        = string
  description = "Name of the service (used in monitor names and tags)"
  default     = "gerald-gateway"
}

variable "environment" {
  type        = string
  description = "Deployment environment (e.g., production, staging)"
  default     = "production"
}

# -----------------------------------------------------------------------------
# Notification Configuration
# -----------------------------------------------------------------------------

variable "pagerduty_service" {
  type        = string
  description = "PagerDuty service name for critical alerts"
  default     = "gerald-oncall"
}

variable "slack_channel_oncall" {
  type        = string
  description = "Slack channel for on-call notifications"
  default     = "gerald-alerts"
}

variable "product_team_email" {
  type        = string
  description = "Product team email for business alerts"
  default     = "product-bnpl@gerald.com"
}

variable "finance_team_email" {
  type        = string
  description = "Finance team email for revenue-related alerts"
  default     = "finance-bnpl@gerald.com"
}

# -----------------------------------------------------------------------------
# Alert Thresholds (can be overridden per environment)
# -----------------------------------------------------------------------------

variable "approval_rate_drop_threshold" {
  type        = number
  description = "Threshold for approval rate drop alert (0.8 = 20% drop)"
  default     = 0.8
}

variable "credit_limit_drop_threshold" {
  type        = number
  description = "Threshold for credit limit drop alert (0.7 = 30% drop)"
  default     = 0.7
}

variable "error_rate_threshold" {
  type        = number
  description = "Error rate threshold percentage"
  default     = 2
}

variable "bank_api_failure_threshold" {
  type        = number
  description = "Bank API failure rate threshold percentage"
  default     = 10
}

variable "webhook_queue_threshold" {
  type        = number
  description = "Webhook queue depth threshold"
  default     = 100
}

variable "decision_latency_threshold" {
  type        = number
  description = "Decision latency p95 threshold in seconds"
  default     = 5
}
