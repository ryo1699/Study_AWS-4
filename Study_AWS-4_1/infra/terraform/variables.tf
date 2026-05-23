variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "ap-northeast-1"
}

variable "project_name" {
  type        = string
  description = "Name prefix for AWS resources."
  default     = "study-aws-4-1"
}

variable "db_username" {
  type        = string
  description = "RDS application username."
  default     = "app_user"
}

variable "db_password" {
  type        = string
  description = "RDS application password. Use a tfvars file or CI secret."
  sensitive   = true
}

variable "container_image" {
  type        = string
  description = "Initial container image URI. GitHub Actions updates the ECS service after pushing to ECR."
  default     = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "enable_debug_error_endpoint" {
  type        = bool
  description = "Enable /api/debug/error so CloudWatch Logs Insights can be tested with an intentional 500 error."
  default     = true
}

variable "log_level" {
  type        = string
  description = "Application log level."
  default     = "INFO"
}

variable "cpu_alarm_threshold" {
  type        = number
  description = "ECS service CPUUtilization threshold for Slack notification practice."
  default     = 5
}

variable "cpu_alarm_evaluation_periods" {
  type        = number
  description = "Number of 60 second periods used by the CPU alarm."
  default     = 1
}

variable "slack_webhook_url" {
  type        = string
  description = "Slack Incoming Webhook URL used by the CloudWatch alarm notifier. Leave empty to create the alarm without notifications."
  default     = ""
  sensitive   = true
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the bastion. Replace with your own IP range."
  default     = "0.0.0.0/32"
}

variable "bastion_key_name" {
  type        = string
  description = "Existing EC2 key pair name used to SSH into the bastion."
}
