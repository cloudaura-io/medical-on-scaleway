################################################################################
# Outputs - Per-student JupyterLab host
################################################################################

output "jupyter_url" {
  description = "Full JupyterLab URL with access token"
  value       = "https://${local.effective_domain}/lab?token=${random_password.jupyter_token.result}"
  sensitive   = true
}

output "public_ip" {
  description = "Public IP address of the JupyterLab instance"
  value       = scaleway_instance_ip.workshop.address
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -o StrictHostKeyChecking=no root@${scaleway_instance_ip.workshop.address}"
}

output "jupyter_token" {
  description = "JupyterLab access token"
  value       = random_password.jupyter_token.result
  sensitive   = true
}

output "project_suffix" {
  description = "Project-derived suffix used for resource namespacing"
  value       = local.project_suffix
}
