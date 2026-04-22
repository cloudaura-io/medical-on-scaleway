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

variable "student_count" {
  description = "Number of student environments to provision"
  type        = number
  default     = 15
}

variable "student_start" {
  description = "Starting index for student numbering (e.g. 1 -> 01, 02, ...; 10 -> 10, 11, ...)"
  type        = number
  default     = 1
}

variable "student_prefix" {
  description = "Naming prefix for student projects (e.g. workshop-student)"
  type        = string
  default     = "workshop-student"
}

variable "instance_type" {
  description = "Scaleway instance type for each JupyterLab host"
  type        = string
  default     = "PRO2-XXS"
}

variable "workshop_repo_url" {
  description = "Git URL of the workshop repo cloned into each instance"
  type        = string
  default     = "https://github.com/cloudaura-io/medical-on-scaleway.git"
}

variable "ssh_public_key" {
  description = "Optional SSH public key registered on every student instance"
  type        = string
  default     = ""
}
