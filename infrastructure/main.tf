################################################################################
# Scaleway Medical AI Lab - VPC-Enclosed Infrastructure
#
# Architecture:
#   Internet -> Public Load Balancer -> VPC / Private Network
#     |---- PLAY2-NANO (Docker Compose: Caddy landing + 3 showcase images)
#     |---- L4 GPU (vLLM Voxtral Realtime STT)
#     |---- Managed PostgreSQL (pgvector)
#     |---- Managed Inference (BGE embeddings)
#   Public Gateway provides NAT for outbound internet access.
#   Container Registry stores pre-built showcase Docker images.
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

locals {
  project_suffix   = substr(var.project_id, 0, 8)
  name_prefix      = "medical-lab-${local.project_suffix}"
  common_tags      = ["workshop", "medical-lab", local.project_suffix]
  vpc_cidr         = "172.16.32.0/22"
  sslip_domain     = "${replace(scaleway_lb_ip.main.ip_address, ".", "-")}.sslip.io"
  effective_domain = var.domain_name != "" ? var.domain_name : local.sslip_domain
  base_url         = "https://${local.effective_domain}"

  ssh_tunnels = {
    app = { ip = scaleway_ipam_ip.app.address, port = 2201 }
    gpu = { ip = scaleway_ipam_ip.gpu.address, port = 2202 }
  }
}

################################################################################
# Random - database password
################################################################################

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "-_."
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
}

################################################################################
# VPC and Private Network
################################################################################

resource "scaleway_vpc" "main" {
  name   = local.name_prefix
  region = var.region
  tags   = local.common_tags
}

resource "scaleway_vpc_private_network" "main" {
  name   = local.name_prefix
  vpc_id = scaleway_vpc.main.id
  region = var.region

  ipv4_subnet {
    subnet = local.vpc_cidr
  }

  tags = local.common_tags
}

################################################################################
# Public Gateway - NAT for outbound internet access
################################################################################

resource "scaleway_vpc_public_gateway_ip" "main" {}

resource "scaleway_vpc_public_gateway" "main" {
  name            = "${local.name_prefix}-gw"
  type            = "VPC-GW-S"
  ip_id           = scaleway_vpc_public_gateway_ip.main.id
  bastion_enabled = false
  enable_smtp     = false
  tags            = local.common_tags
}

resource "scaleway_vpc_gateway_network" "main" {
  gateway_id         = scaleway_vpc_public_gateway.main.id
  private_network_id = scaleway_vpc_private_network.main.id
  enable_masquerade  = true

  ipam_config {
    push_default_route = true
  }
}

################################################################################
# Container Registry - pre-built showcase Docker images
################################################################################

resource "scaleway_registry_namespace" "main" {
  name        = local.name_prefix
  region      = var.region
  description = "Docker images for Medical AI Lab showcases"
  is_public   = false
}

################################################################################
# IPAM IP reservations - static private IPs for instances
################################################################################

resource "scaleway_ipam_ip" "app" {
  source {
    private_network_id = scaleway_vpc_private_network.main.id
  }
  tags = concat(local.common_tags, ["app"])
}

resource "scaleway_ipam_ip" "gpu" {
  source {
    private_network_id = scaleway_vpc_private_network.main.id
  }
  tags = concat(local.common_tags, ["gpu"])
}

################################################################################
# Managed PostgreSQL (pgvector for RAG knowledge base)
################################################################################

resource "scaleway_rdb_instance" "medical_db" {
  name           = local.name_prefix
  node_type      = "DB-DEV-S"
  engine         = "PostgreSQL-16"
  is_ha_cluster  = false
  disable_backup = true
  volume_type    = "lssd"

  private_network {
    pn_id       = scaleway_vpc_private_network.main.id
    enable_ipam = true
  }

  tags = local.common_tags
}

resource "scaleway_rdb_database" "medical_knowledge" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "medical_knowledge"
}

resource "scaleway_rdb_user" "lab_user" {
  instance_id = scaleway_rdb_instance.medical_db.id
  name        = "lab_user"
  password    = random_password.db_password.result
  is_admin    = false
}

resource "scaleway_rdb_privilege" "lab_user_privileges" {
  instance_id   = scaleway_rdb_instance.medical_db.id
  user_name     = scaleway_rdb_user.lab_user.name
  database_name = scaleway_rdb_database.medical_knowledge.name
  permission    = "all"
}

################################################################################
# Object Storage (medical documents, PDFs, raw data)
# No versioning or lifecycle rules - this is a throwaway workshop bucket
# destroyed after the session. Production should enable versioning.
################################################################################

resource "scaleway_object_bucket" "medical_docs" {
  name   = local.name_prefix
  region = var.region

  tags = {
    workshop = "medical-lab"
    project  = local.project_suffix
  }
}

################################################################################
# Managed Inference - BGE Multilingual Gemma2 Embedding Model
################################################################################

resource "scaleway_inference_deployment" "embedding" {
  name      = "${local.name_prefix}-embedding"
  node_type = "L4"
  model_id  = var.embedding_model_id

  accept_eula = true

  public_endpoint {
    is_enabled = false
  }

  private_endpoint {
    private_network_id = scaleway_vpc_private_network.main.id
  }

  tags = local.common_tags
}

################################################################################
# Scoped IAM - dedicated credentials for application containers
# Limits blast radius vs injecting the account-level secret key.
################################################################################

resource "scaleway_iam_application" "workshop_app" {
  name        = "${local.name_prefix}-app"
  description = "Scoped credentials for workshop showcase containers"
}

resource "scaleway_iam_api_key" "workshop_app" {
  application_id = scaleway_iam_application.workshop_app.id
  description    = "${local.name_prefix} container API key"
  expires_at     = timeadd(timestamp(), "2160h") # 90 days
}

resource "scaleway_iam_policy" "workshop_app" {
  name           = "${local.name_prefix}-policy"
  application_id = scaleway_iam_application.workshop_app.id

  rule {
    project_ids = [var.project_id]
    permission_set_names = [
      "ContainerRegistryReadOnly",
      "ObjectStorageFullAccess",
      "InferenceFullAccess",
    ]
  }

  # Generative APIs is organization-scoped (serverless, not project-bound)
  rule {
    organization_id = var.organization_id
    permission_set_names = [
      "GenerativeApisFullAccess",
    ]
  }
}

################################################################################
# Application Compute Instance (PLAY2-NANO)
# Pulls pre-built images from Container Registry, runs via Docker Compose
################################################################################

resource "scaleway_instance_security_group" "app" {
  name                    = "${local.name_prefix}-app"
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  # SSH via LB (LB connects from VPC CIDR)
  inbound_rule {
    action   = "accept"
    port     = 22
    protocol = "TCP"
    ip_range = local.vpc_cidr
  }

  inbound_rule {
    action   = "accept"
    port     = 80
    protocol = "TCP"
    ip_range = local.vpc_cidr
  }

  tags = local.common_tags
}

resource "scaleway_instance_server" "app" {
  name  = "${local.name_prefix}-app"
  type  = "PLAY2-NANO"
  image = "ubuntu_jammy"

  # No public IP - outbound via NAT gateway only (avoids asymmetric routing).
  # SSH access via LB on port 2201.
  enable_dynamic_ip = false

  security_group_id = scaleway_instance_security_group.app.id

  root_volume {
    size_in_gb = 20
  }

  user_data = {
    cloud-init = templatefile("${path.module}/cloud-init-app.yaml", {
      scw_secret_key       = var.secret_key
      scw_access_key       = var.access_key
      scw_project_id       = var.project_id
      registry_namespace   = scaleway_registry_namespace.main.name
      db_host              = scaleway_rdb_instance.medical_db.private_network[0].ip
      db_port              = scaleway_rdb_instance.medical_db.private_network[0].port
      db_password          = random_password.db_password.result
      db_user              = scaleway_rdb_user.lab_user.name
      db_name              = scaleway_rdb_database.medical_knowledge.name
      inference_endpoint   = "${scaleway_inference_deployment.embedding.private_endpoint[0].url}/v1"
      inference_hostname   = replace(scaleway_inference_deployment.embedding.private_endpoint[0].url, "https://", "")
      inference_private_ip = scaleway_inference_deployment.embedding.private_ip[0].address
      voxtral_private_ip   = scaleway_ipam_ip.gpu.address
      s3_bucket            = scaleway_object_bucket.medical_docs.name
    })
  }

  tags = local.common_tags

  depends_on = [scaleway_vpc_gateway_network.main]
}

resource "scaleway_instance_private_nic" "app" {
  server_id          = scaleway_instance_server.app.id
  private_network_id = scaleway_vpc_private_network.main.id
  ipam_ip_ids        = [scaleway_ipam_ip.app.id]
}

################################################################################
# GPU Instance - Voxtral Realtime STT (self-hosted vLLM)
################################################################################

resource "scaleway_instance_security_group" "voxtral_gpu" {
  name                    = "${local.name_prefix}-voxtral-gpu"
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  # SSH via LB (LB connects from VPC CIDR)
  inbound_rule {
    action   = "accept"
    port     = 22
    protocol = "TCP"
    ip_range = local.vpc_cidr
  }

  inbound_rule {
    action   = "accept"
    port     = 8000
    protocol = "TCP"
    ip_range = local.vpc_cidr
  }

  tags = local.common_tags
}

resource "scaleway_instance_server" "voxtral_gpu" {
  name  = "${local.name_prefix}-voxtral-gpu"
  type  = "L4-1-24G"
  image = "ubuntu_noble_gpu_os_13_nvidia"

  # No public IP - outbound via NAT gateway only (avoids asymmetric routing
  # that breaks Docker image pulls). SSH access via LB on port 2202.
  enable_dynamic_ip = false

  security_group_id = scaleway_instance_security_group.voxtral_gpu.id

  root_volume {
    size_in_gb = 100
  }

  user_data = {
    cloud-init = file("${path.module}/cloud-init-vllm.yaml")
  }

  tags = local.common_tags

  depends_on = [scaleway_vpc_gateway_network.main]
}

resource "scaleway_instance_private_nic" "voxtral_gpu" {
  server_id          = scaleway_instance_server.voxtral_gpu.id
  private_network_id = scaleway_vpc_private_network.main.id
  ipam_ip_ids        = [scaleway_ipam_ip.gpu.id]
}

################################################################################
# Public Load Balancer
#
# When domain_name is set:
#   Port 443: HTTPS (TLS terminated at LB via Let's Encrypt)
#   Port 80:  HTTP -> HTTPS redirect (via Caddy X-Forwarded-Proto check)
# When domain_name is empty (participant self-service):
#   Port 80:  HTTP only (no TLS, no domain needed)
#
# Path-based routing via Caddy on the app instance:
#   /                         -> landing page
#   /consultation-assistant/* -> showcase1 :8001
#   /document-intelligence/*  -> showcase2 :8002
#   /drug-interactions/*      -> showcase3 :8003
#
# SSH via TCP passthrough:
#   Port 2201 -> app instance
#   Port 2202 -> GPU instance
#
################################################################################

resource "scaleway_lb_ip" "main" {}

resource "scaleway_lb" "main" {
  ip_ids = [scaleway_lb_ip.main.id]
  name   = local.name_prefix
  type   = "LB-S"

  private_network {
    private_network_id = scaleway_vpc_private_network.main.id
  }

  tags = local.common_tags
}

resource "scaleway_lb_certificate" "main" {
  lb_id = scaleway_lb.main.id
  name  = "${local.name_prefix}-le-${substr(sha256(local.effective_domain), 0, 8)}"

  letsencrypt {
    common_name = local.effective_domain
  }

  lifecycle {
    create_before_destroy = true
  }
}

# --- Backend (single - Caddy on port 80 handles all path routing) ---

resource "scaleway_lb_backend" "app" {
  lb_id            = scaleway_lb.main.id
  name             = "app-caddy"
  forward_protocol = "http"
  forward_port     = 80

  server_ips = [scaleway_ipam_ip.app.address]

  health_check_http {
    uri = "/healthz"
  }
  health_check_timeout = "5s"
  health_check_delay   = "10s"
}

# --- HTTP frontend (port 80) ---

resource "scaleway_lb_frontend" "http" {
  lb_id        = scaleway_lb.main.id
  name         = "http"
  backend_id   = scaleway_lb_backend.app.id
  inbound_port = 80
}

resource "scaleway_lb_frontend" "https" {
  lb_id           = scaleway_lb.main.id
  name            = "https"
  backend_id      = scaleway_lb_backend.app.id
  inbound_port    = 443
  certificate_ids = [scaleway_lb_certificate.main.id]
}

# --- SSH via LB (TCP passthrough, avoids asymmetric routing) ---

resource "scaleway_lb_backend" "ssh" {
  for_each         = local.ssh_tunnels
  lb_id            = scaleway_lb.main.id
  name             = "ssh-${each.key}"
  forward_protocol = "tcp"
  forward_port     = 22

  server_ips = [each.value.ip]

  health_check_tcp {}
  health_check_timeout = "5s"
  health_check_delay   = "30s"
}

resource "scaleway_lb_frontend" "ssh" {
  for_each     = local.ssh_tunnels
  lb_id        = scaleway_lb.main.id
  name         = "ssh-${each.key}"
  backend_id   = scaleway_lb_backend.ssh[each.key].id
  inbound_port = each.value.port
}
