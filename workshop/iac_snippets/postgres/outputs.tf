output "connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${scaleway_rdb_user.workshop.name}:${random_password.db_password.result}@${scaleway_rdb_instance.workshop.load_balancer[0].ip}:${scaleway_rdb_instance.workshop.load_balancer[0].port}/${scaleway_rdb_database.workshop.name}"
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = scaleway_rdb_instance.workshop.load_balancer[0].ip
}

output "port" {
  description = "Database port"
  value       = scaleway_rdb_instance.workshop.load_balancer[0].port
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
