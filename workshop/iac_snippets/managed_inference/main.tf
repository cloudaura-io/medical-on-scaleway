################################################################################
# Workshop IaC Snippet: Managed Inference (BGE Multilingual Gemma2)
################################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.70"
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

resource "scaleway_inference_deployment" "bge" {
  name      = "workshop-${var.project_suffix}-bge"
  node_type = "L4-1-24G"
  model_id  = "baai/bge-multilingual-gemma2:fp16"

  public_endpoint {
    is_enabled = true
  }

  tags = ["workshop", "medical-lab", var.project_suffix]
}
