################################################################################
# Scaleway Medical AI Lab - OpenTofu Infrastructure
################################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.70.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = ">= 3.0.0"
    }
  }
}

provider "scaleway" {
  access_key      = var.access_key
  secret_key      = var.secret_key
  organization_id = var.organization_id
  project_id      = var.project_id
  region          = "fr-par"
  zone            = "fr-par-1"
}

################################################################################
# Managed PostgreSQL (pgvector for RAG knowledge base)
################################################################################

resource "scaleway_rdb_instance" "medical_db" {
  name           = "medical-lab-${var.student_id}"
  node_type      = "DB-DEV-S"
  engine         = "PostgreSQL-16"
  is_ha_cluster  = false
  disable_backup = true

  volume_type = "lssd"

  load_balancer {}

  tags = ["workshop", "medical-lab", var.student_id]
}

resource "scaleway_rdb_database" "medical_knowledge" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "medical_knowledge"
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "-_."
}

resource "scaleway_rdb_user" "lab_user" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "lab_user"
  password    = random_password.db_password.result
  is_admin    = false
}

data "http" "my_ip" {
  url = "https://ifconfig.me/ip"
}

resource "scaleway_rdb_acl" "medical_db_acl" {
  instance_id = scaleway_rdb_instance.medical_db.id

  acl_rules {
    ip          = "${trimspace(data.http.my_ip.response_body)}/32"
    description = "Current workstation IP"
  }
}

resource "scaleway_rdb_privilege" "lab_user_privileges" {
  instance_id   = scaleway_rdb_instance.medical_db.id
  user_name     = scaleway_rdb_user.lab_user.name
  database_name = scaleway_rdb_database.medical_knowledge.name
  permission    = "all"

  depends_on = [
    scaleway_rdb_user.lab_user,
    scaleway_rdb_database.medical_knowledge,
  ]
}

################################################################################
# Object Storage (medical documents, PDFs, raw data)
################################################################################

resource "scaleway_object_bucket" "medical_docs" {
  name   = "medical-lab-${var.student_id}"
  region = "fr-par"

  tags = {
    workshop = "medical-lab"
    student  = var.student_id
  }
}

################################################################################
# Managed Inference - BGE Multilingual Gemma2 Embedding Model
# Dedicated instance for patient data privacy (no shared endpoints)
################################################################################

resource "scaleway_inference_deployment" "embedding" {
  name      = "medical-embedding-${var.student_id}"
  node_type = "L4"
  model_id  = "d58efec4-b667-48e2-8ad8-bcc26c175ae6" # baai/bge-multilingual-gemma2:fp32

  accept_eula = true

  public_endpoint {
    is_enabled = true
  }

  tags = ["workshop", "medical-lab", var.student_id]
}
