################################################################################
# Workshop IaC Snippet: Object Storage Bucket
################################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.70"
    }
  }
}

provider "scaleway" {
  access_key      = var.access_key
  secret_key      = var.secret_key
  organization_id = var.organization_id
  project_id      = var.project_id
  region          = var.region
  zone            = var.zone
}

resource "scaleway_object_bucket" "workshop" {
  name   = "workshop-${var.student_id}-data"
  region = var.region
  tags = {
    workshop   = "true"
    student_id = var.student_id
  }
}
