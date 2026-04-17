################################################################################
# Scaleway Medical AI Workshop - Per-student JupyterLab host
#
# Provisions a single instance with JupyterLab behind Caddy (HTTPS),
# namespaced by student_id. Cloud-init installs all dependencies and
# starts JupyterLab as a systemd service.
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
  name_prefix = "workshop-${var.student_id}"
  common_tags = ["workshop", "medical-lab", var.student_id]
  tls_enabled = var.domain_name != ""
}

# ---- Random JupyterLab access token ----------------------------------------

resource "random_password" "jupyter_token" {
  length  = 32
  special = false
}

# ---- Scoped IAM credentials for the student instance -----------------------
# Instead of injecting admin-level access_key/secret_key into the instance,
# we create a dedicated IAM application with only the permissions the
# workshop notebooks need. The instance gets scoped credentials that are
# destroyed with tofu destroy.

resource "scaleway_iam_application" "workshop" {
  name        = "${local.name_prefix}-jupyter"
  description = "Scoped credentials for workshop Jupyter instance (${var.student_id})"
}

resource "scaleway_iam_api_key" "workshop" {
  application_id = scaleway_iam_application.workshop.id
  description    = "${local.name_prefix} jupyter API key"
  expires_at     = timeadd(timestamp(), "48h")
}

resource "scaleway_iam_policy" "workshop" {
  name           = "${local.name_prefix}-policy"
  application_id = scaleway_iam_application.workshop.id

  rule {
    project_ids = [var.project_id]
    permission_set_names = [
      "ObjectStorageFullAccess",
      "RelationalDatabasesFullAccess",
      "InferenceFullAccess",
    ]
  }

  # Generative APIs is organization-scoped (serverless, not project-bound)
  rule {
    organization_id      = var.organization_id
    permission_set_names = ["GenerativeApisFullAccess"]
  }
}

# ---- SSH key ----------------------------------------------------------------

resource "scaleway_iam_ssh_key" "workshop" {
  name       = "${local.name_prefix}-ssh"
  public_key = var.ssh_public_key
}

# ---- Security Group ---------------------------------------------------------

resource "scaleway_instance_security_group" "workshop" {
  name                    = "${local.name_prefix}-sg"
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  inbound_rule {
    action   = "accept"
    port     = 22
    protocol = "TCP"
  }

  inbound_rule {
    action   = "accept"
    port     = 443
    protocol = "TCP"
  }

  inbound_rule {
    action   = "accept"
    port     = 80
    protocol = "TCP"
  }

  tags = local.common_tags
}

# ---- Public IP --------------------------------------------------------------

resource "scaleway_instance_ip" "workshop" {
  tags = local.common_tags
}

# ---- Instance ---------------------------------------------------------------

resource "scaleway_instance_server" "workshop" {
  name  = "${local.name_prefix}-jupyter"
  type  = var.instance_type
  image = "ubuntu_jammy"
  ip_id = scaleway_instance_ip.workshop.id

  security_group_id = scaleway_instance_security_group.workshop.id

  tags = local.common_tags

  user_data = {
    cloud-init = templatefile("${path.module}/cloud-init-jupyter.yaml", {
      jupyter_token       = random_password.jupyter_token.result
      scw_access_key      = scaleway_iam_api_key.workshop.access_key
      scw_secret_key      = scaleway_iam_api_key.workshop.secret_key
      scw_organization_id = var.organization_id
      scw_project_id      = var.project_id
      scw_region          = var.region
      scw_zone            = var.zone
      student_id          = var.student_id
      domain_name         = var.domain_name
      tls_enabled         = local.tls_enabled
      workshop_repo_url   = var.workshop_repo_url
    })
  }
}
