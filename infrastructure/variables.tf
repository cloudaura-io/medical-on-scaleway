################################################################################
# Scaleway Medical AI Lab - Input Variables
################################################################################

variable "access_key" {
  description = "Scaleway access key (SCW...)"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Scaleway secret key (UUID)"
  type        = string
  sensitive   = true
}

variable "organization_id" {
  description = "Scaleway organization ID (UUID)"
  type        = string
  sensitive   = true
}

variable "project_id" {
  description = "Scaleway project ID (UUID)"
  type        = string
}

variable "domain_name" {
  description = "Domain name for Let's Encrypt TLS. Leave empty for HTTP-only (no domain needed)."
  type        = string
  default     = ""
}

variable "student_id" {
  description = "Unique student identifier used to namespace all resources (e.g. student-01)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.student_id))
    error_message = "student_id must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "region" {
  description = "Scaleway region"
  type        = string
  default     = "fr-par"
}

variable "zone" {
  description = "Scaleway availability zone"
  type        = string
  default     = "fr-par-1"
}

variable "embedding_model_id" {
  description = "Scaleway Managed Inference model UUID for BGE embeddings"
  type        = string
  default     = "d58efec4-b667-48e2-8ad8-bcc26c175ae6"
}
