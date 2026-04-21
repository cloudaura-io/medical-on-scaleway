################################################################################
# Workshop IaC Snippet: Managed PostgreSQL with pgvector
#
# Note: pgvector extension must be enabled post-apply via psycopg in the
# notebook (CREATE EXTENSION IF NOT EXISTS vector). The Scaleway RDB API
# does not support extension management directly.
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

# Password meeting Scaleway rules: min 1 uppercase, lowercase, digit, special
resource "random_password" "db_password" {
  length           = 24
  special          = true
  override_special = "!@#$%"
  min_upper        = 1
  min_lower        = 1
  min_numeric      = 1
  min_special      = 1
}

resource "scaleway_rdb_instance" "workshop" {
  name           = "workshop-${var.project_suffix}-pg"
  node_type      = "DB-DEV-S"
  engine         = "PostgreSQL-16"
  is_ha_cluster  = false
  disable_backup = true

  tags = ["workshop", "medical-lab", var.project_suffix]
}

resource "scaleway_rdb_database" "workshop" {
  instance_id = scaleway_rdb_instance.workshop.id
  name        = "workshop"
}

resource "scaleway_rdb_user" "workshop" {
  instance_id = scaleway_rdb_instance.workshop.id
  name        = "workshop"
  password    = random_password.db_password.result
  is_admin    = true
}

resource "scaleway_rdb_privilege" "workshop" {
  instance_id   = scaleway_rdb_instance.workshop.id
  user_name     = scaleway_rdb_user.workshop.name
  database_name = scaleway_rdb_database.workshop.name
  permission    = "all"
}
