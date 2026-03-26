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

variable "student_id" {
  description = "Unique student identifier used to namespace all resources (e.g. student-01)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.student_id))
    error_message = "student_id must contain only lowercase letters, numbers, and hyphens."
  }
}

