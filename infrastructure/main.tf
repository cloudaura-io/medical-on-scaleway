################################################################################
# Scaleway Medical AI Lab - Terraform Infrastructure
################################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = ">= 2.70.0"
    }
  }
}

provider "scaleway" {
  access_key = var.scw_access_key
  secret_key = var.scw_secret_key
  project_id = var.scw_project_id
  region     = "fr-par"
  zone       = "fr-par-1"
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
  volume_size_in_gb = 10

  tags = ["workshop", "medical-lab", var.student_id]
}

resource "scaleway_rdb_database" "medical_knowledge" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "medical_knowledge"
}

resource "scaleway_rdb_user" "lab_user" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "lab_user"
  password    = var.db_password
  is_admin    = false
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
  node_type = "L4-1-24G"
  model_id  = "bge-multilingual-gemma2"

  accept_eula = true

  public_endpoint {
    is_enabled = true
  }

  tags = ["workshop", "medical-lab", var.student_id]
}
