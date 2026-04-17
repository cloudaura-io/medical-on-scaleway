################################################################################
# Scaleway Medical AI Workshop - Per-student JupyterLab host variables
# Variable names mirror /infrastructure/variables.tf so a single
# terraform.tfvars file can be reused across both directories.
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
  description = "Unique student identifier used to namespace all resources (e.g. stv0r)"
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

variable "domain_name" {
  description = "Optional domain name for Let's Encrypt TLS. When set, Caddy obtains a real cert (requires a DNS A record pointing at the instance public IP). When empty, JupyterLab is served over plain HTTP on :80."
  type        = string
  default     = ""
}

variable "instance_type" {
  description = "Scaleway instance type for the JupyterLab host. PRO2-XXS = 2 vCPU / 8 GB / ~12 EUR/mo. DEV1-M = 3 vCPU / 4 GB cheaper option."
  type        = string
  default     = "PRO2-XXS"
}

variable "workshop_repo_url" {
  description = "Optional Git URL of the workshop repo. Cloud-init will git clone it into /home/jupyter/workshop if set. Leave empty to provision an empty directory you populate manually via rsync/scp."
  type        = string
  default     = ""
}

variable "ssh_public_key" {
  description = "SSH public key (e.g. contents of ~/.ssh/id_ed25519.pub) installed on the instance for the root user."
  type        = string
}
