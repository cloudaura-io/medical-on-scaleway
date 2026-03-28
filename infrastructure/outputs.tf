################################################################################
# Scaleway Medical AI Lab - Outputs
################################################################################

# --- PostgreSQL ---

output "database_connection_url" {
  description = "PostgreSQL connection URL for the medical_knowledge database"
  value = format(
    "postgresql://%s:%s@%s:%d/%s?sslmode=require",
    scaleway_rdb_user.lab_user.name,
    random_password.db_password.result,
    scaleway_rdb_instance.medical_db.load_balancer[0].ip,
    scaleway_rdb_instance.medical_db.load_balancer[0].port,
    scaleway_rdb_database.medical_knowledge.name,
  )
  sensitive = true
}

output "database_host" {
  description = "PostgreSQL host (IP)"
  value       = scaleway_rdb_instance.medical_db.load_balancer[0].ip
}

output "database_port" {
  description = "PostgreSQL port"
  value       = scaleway_rdb_instance.medical_db.load_balancer[0].port
}

output "database_name" {
  description = "PostgreSQL database name"
  value       = scaleway_rdb_database.medical_knowledge.name
}

output "database_password" {
  description = "Generated password for the lab_user PostgreSQL user"
  value       = random_password.db_password.result
  sensitive   = true
}

# --- Object Storage ---

output "object_storage_endpoint" {
  description = "S3-compatible endpoint for the medical documents bucket"
  value       = scaleway_object_bucket.medical_docs.endpoint
}

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
  description = "Public endpoint for the BGE embedding model (OpenAI-compatible API)"
  value       = "${scaleway_inference_deployment.embedding.public_endpoint[0].url}/v1"
}

output "inference_deployment_id" {
  description = "ID of the managed inference deployment"
  value       = scaleway_inference_deployment.embedding.id
}

# --- Voxtral Realtime (STT streaming) ---

output "voxtral_realtime_endpoint" {
  description = "Public endpoint for the Voxtral Realtime STT model"
  value       = "${scaleway_inference_deployment.voxtral_realtime.public_endpoint[0].url}/v1"
}

output "voxtral_realtime_deployment_id" {
  description = "ID of the Voxtral Realtime inference deployment"
  value       = scaleway_inference_deployment.voxtral_realtime.id
}
