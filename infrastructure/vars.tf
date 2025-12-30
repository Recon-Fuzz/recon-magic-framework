variable "aws_region" {
  description = "AWS region for resources."
  default     = "us-east-1"
}

variable "namespace" {
  description = "Namespace used for naming AWS resources."
}

variable "vCPU" {
  description = "CPU units for the ECS task."
}

variable "mem" {
  description = "Memory (MiB) for the ECS task."
}

variable "backend_api_url" {
  description = "Base API URL for the magic backend."
  default     = ""
}

variable "worker_permissions" {
  description = "Whether to enable dangerous permissions in the worker."
  default     = "false"
}
