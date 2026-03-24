################################################################################
# Scaleway Medical AI Lab - Input Variables
################################################################################

variable "scw_access_key" {
  description = "Scaleway access key (SCW...)"
  type        = string
  sensitive   = true
}

variable "scw_secret_key" {
  description = "Scaleway secret key (UUID)"
  type        = string
  sensitive   = true
}

variable "scw_project_id" {
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

variable "db_password" {
  description = "Password for the lab_user PostgreSQL user"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 12
    error_message = "db_password must be at least 12 characters long."
  }
}
