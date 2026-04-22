output "students" {
  description = "Per-student connection details (jupyter_url is sensitive)"
  sensitive   = true

  value = {
    for k in local.student_indices : "${var.student_prefix}-${k}" => {
      jupyter_url = module.student[k].jupyter_url
      public_ip   = module.student[k].public_ip
      ssh_command = module.student[k].ssh_command
      project_id  = scaleway_account_project.student[k].id
    }
  }
}
