output "bucket_name" {
  description = "Name of the Object Storage bucket"
  value       = scaleway_object_bucket.workshop.name
}

output "bucket_endpoint" {
  description = "S3-compatible endpoint URL"
  value       = "https://s3.${var.region}.scw.cloud"
}
