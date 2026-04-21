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
  project_id      = var.project_id
  region          = var.region
  zone            = var.zone
}

# Random suffix avoids Scaleway S3 name tombstones (names stay reserved
# up to 48h after deletion, blocking destroy-then-reapply cycles).
resource "random_id" "bucket" {
  byte_length = 4
}

resource "scaleway_object_bucket" "workshop" {
  name          = "workshop-${var.project_suffix}-data-${random_id.bucket.hex}"
  region        = var.region
  force_destroy = true
  tags = {
    workshop       = "true"
    project_suffix = var.project_suffix
  }
}
