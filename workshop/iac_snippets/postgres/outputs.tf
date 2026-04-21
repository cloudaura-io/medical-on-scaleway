# Use endpoint_ip / endpoint_port rather than load_balancer[0].{ip,port}: the
# scaleway provider returns load_balancer as an empty list on first apply for
# default-public-endpoint instances, which makes tofu apply fail at output
# evaluation. The deprecated endpoint_ip / endpoint_port attributes are
# populated reliably and point at the same default public endpoint.

output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${scaleway_rdb_user.workshop.name}:${random_password.db_password.result}@${scaleway_rdb_instance.workshop.endpoint_ip}:${scaleway_rdb_instance.workshop.endpoint_port}/${scaleway_rdb_database.workshop.name}"
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = scaleway_rdb_instance.workshop.endpoint_ip
}

output "port" {
  description = "Database port"
  value       = scaleway_rdb_instance.workshop.endpoint_port
}

output "database" {
  description = "Database name"
  value       = scaleway_rdb_database.workshop.name
}

output "user" {
  description = "Database user"
  value       = scaleway_rdb_user.workshop.name
}

output "password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}
