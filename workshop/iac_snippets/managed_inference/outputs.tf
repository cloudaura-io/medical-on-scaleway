output "endpoint_url" {
  description = "Managed Inference endpoint URL"
  value       = "${scaleway_inference_deployment.bge.public_endpoint[0].url}/v1"
}

output "api_key" {
  description = "API key for the Managed Inference endpoint (uses SCW_SECRET_KEY)"
  value       = var.secret_key
  sensitive   = true
}
