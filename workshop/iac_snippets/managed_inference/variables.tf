variable "access_key" {
  description = "Scaleway access key"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Scaleway secret key"
  type        = string
  sensitive   = true
}

variable "organization_id" {
  description = "Scaleway organization ID"
  type        = string
  sensitive   = true
}

variable "project_id" {
  description = "Scaleway project ID"
  type        = string
}

variable "student_id" {
  description = "Unique student identifier"
  type        = string
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
