terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.8"
    }
  }
}

provider "scaleway" {
  access_key      = var.access_key
  secret_key      = var.secret_key
  organization_id = var.organization_id
  region          = var.region
  zone            = var.zone
}

locals {
  student_indices = toset([for i in range(var.student_count) : format("%02d", var.student_start + i)])
}

resource "scaleway_account_project" "student" {
  for_each = local.student_indices

  name        = "${var.student_prefix}-${each.key}"
  description = "Workshop environment for student ${each.key}"
}

module "student" {
  source   = "../infrastructure"
  for_each = local.student_indices

  project_id        = scaleway_account_project.student[each.key].id
  organization_id   = var.organization_id
  region            = var.region
  zone              = var.zone
  instance_type     = var.instance_type
  domain_name       = ""
  workshop_repo_url = var.workshop_repo_url
  ssh_public_key    = var.ssh_public_key
}
