################################################################################
# Scaleway Medical AI Lab - Outputs
################################################################################

# --- Load Balancer (main entry point) ---

output "lb_public_ip" {
  description = "Public IP of the Load Balancer - the main entry point"
  value       = scaleway_lb_ip.main.ip_address
}

output "base_url" {
  description = "Base URL for the workshop (HTTPS if domain set, HTTP otherwise)"
  value       = local.base_url
}

output "domain_name" {
  description = "Domain name for the workshop (empty if HTTP-only)"
  value       = var.domain_name
}

output "landing_url" {
  description = "URL for the landing page"
  value       = "${local.base_url}/"
}

output "showcase1_url" {
  description = "URL for Showcase 1 - Consultation Assistant"
  value       = "${local.base_url}/consultation-assistant/"
}

output "showcase2_url" {
  description = "URL for Showcase 2 - Document Intelligence"
  value       = "${local.base_url}/document-intelligence/"
}

output "showcase3_url" {
  description = "URL for Showcase 3 - Research Agent"
  value       = "${local.base_url}/research-agent/"
}

# --- SSH ---

output "ssh_commands" {
  description = "SSH commands for accessing instances via LB"
  value = {
    app = "ssh -p 2201 root@${local.tls_enabled ? var.domain_name : scaleway_lb_ip.main.ip_address}"
    gpu = "ssh -p 2202 root@${local.tls_enabled ? var.domain_name : scaleway_lb_ip.main.ip_address}"
  }
}

# --- Container Registry ---

output "registry_endpoint" {
  description = "Scaleway Container Registry endpoint for pushing images"
  value       = "rg.fr-par.scw.cloud/${scaleway_registry_namespace.main.name}"
}

# --- Networking ---

output "gateway_public_ip" {
  description = "Public IP of the NAT gateway"
  value       = scaleway_vpc_public_gateway_ip.main.address
}

output "app_private_ip" {
  description = "Private IP of the application instance"
  value       = scaleway_ipam_ip.app.address
}

output "gpu_private_ip" {
  description = "Private IP of the GPU instance"
  value       = scaleway_ipam_ip.gpu.address
}

# --- PostgreSQL ---

output "database_connection_url" {
  description = "PostgreSQL connection URL via private network"
  value = format(
    "postgresql://%s:%s@%s:%d/%s?sslmode=require",
    scaleway_rdb_user.lab_user.name,
    random_password.db_password.result,
    scaleway_rdb_instance.medical_db.private_network[0].ip,
    scaleway_rdb_instance.medical_db.private_network[0].port,
    scaleway_rdb_database.medical_knowledge.name,
  )
  sensitive = true
}

output "database_host" {
  description = "PostgreSQL private IP"
  value       = scaleway_rdb_instance.medical_db.private_network[0].ip
}

output "database_port" {
  description = "PostgreSQL port on private network"
  value       = scaleway_rdb_instance.medical_db.private_network[0].port
}

output "database_name" {
  description = "PostgreSQL database name"
  value       = scaleway_rdb_database.medical_knowledge.name
}

# --- Object Storage ---

output "object_storage_bucket_name" {
  description = "Name of the object storage bucket"
  value       = scaleway_object_bucket.medical_docs.name
}

output "object_storage_api_endpoint" {
  description = "S3 API endpoint (region-scoped)"
  value       = scaleway_object_bucket.medical_docs.api_endpoint
}

# --- Managed Inference ---

output "inference_endpoint" {
  description = "Private endpoint for the BGE embedding model"
  value       = "${scaleway_inference_deployment.embedding.private_endpoint[0].url}/v1"
}

# --- Voxtral Realtime ---

output "voxtral_realtime_endpoint" {
  description = "Voxtral Realtime vLLM endpoint via private network"
  value       = "http://${scaleway_ipam_ip.gpu.address}:8000/v1"
}
