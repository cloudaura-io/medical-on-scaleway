# Scaleway Medical AI Workshop: Drug Interaction & Population-Warning Agent

Half-day (~4 hour) hands-on workshop. Each participant provisions their own
JupyterLab host on Scaleway, then walks a sequence of notebooks that build a
**ReAct-loop drug interaction agent** backed by real FDA drug labels, pgvector,
and Mistral Small 3.2 on Scaleway Generative APIs.

## Prerequisites

- A Scaleway account with an API key (access key + secret key)
- `tofu` (OpenTofu) installed locally
- `ssh` available (for connecting to the provisioned instance)
- A modern web browser

## Quick Start (Pre-Session)

```bash
cd workshop/infrastructure

# Copy and fill in your Scaleway credentials
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your credentials

tofu init
tofu apply
```

After ~10 minutes, OpenTofu outputs a `jupyter_url`. Click it to open JupyterLab
in your browser. The first notebook (`00_setup.ipynb`) opens automatically.

**Security note:** The instance uses scoped IAM credentials (not your admin key).
OpenTofu creates a dedicated IAM application with only the permissions the
workshop needs (ObjectStorage, RelationalDatabases, Inference, GenerativeAPIs).
The API key expires in 48 hours and is destroyed with `tofu destroy`.

## What You Will Build

By the end of the workshop, you will have run end-to-end:

1. **Made your first Mistral API call** on Scaleway Generative APIs
2. **Explored real FDA drug label data** (openFDA Structured Product Labeling)
3. **Provisioned 3 Scaleway resources live from Jupyter** (Object Storage,
   Managed PostgreSQL + pgvector, Managed Inference with BGE embeddings)
4. **Built a RAG knowledge base** of section-typed drug label chunks with
   metadata-rich pgvector embeddings
5. **Tested 5 agent tools** (search_drug_kb, lookup_interactions,
   lookup_population_warnings, flag_severity, summarize_evidence)
6. **Ran a ReAct agent** that iterates through Think -> Act -> Observe,
   producing severity-first, fully-cited drug interaction reports
7. **Deployed a Gradio demo app** wrapping the agent

## Access Model

- Click the `jupyter_url` output from `tofu apply` (includes the access token)
- Accept the self-signed certificate warning in your browser
- The first notebook opens automatically
- All required artifacts (notebooks, data, IaC modules) are ready

## Security Model

- Token-based JupyterLab authentication (random 32-char token)
- HTTP via Caddy reverse proxy (HTTPS with Let's Encrypt if `domain_name` is configured)
- Scoped IAM credentials on the instance (not admin keys), 48h expiry
- Permissions limited to ObjectStorage, RelationalDatabases, Inference, GenerativeAPIs
- IAM application and API key destroyed with `tofu destroy`
- Adequate for a half-day workshop with public-domain data

## Session Run-Sheet

| Time | Activity |
|------|----------|
| 0:00 - 0:15 | Welcome, workshop mission, distribute JupyterLab URLs |
| 0:15 - 0:25 | `00_setup`, `01_first_mistral_call` |
| 0:25 - 0:50 | `02_openfda_explore`, `03_provision_pgvector_and_chunk` |
| 0:50 - 0:55 | Kick off `04`, Managed Inference `tofu apply` starts |
| 0:55 - 1:20 | **Instructor ReAct theory lecture** (during Managed Inference boot) |
| 1:20 - 1:35 | Finish `04_embeddings_and_search` |
| 1:35 - 1:45 | **Break** |
| 1:45 - 2:00 | `05_tools` |
| 2:00 - 2:20 | `06_react_agent` (baseline vs grounded comparison) |
| 2:20 - 2:30 | `07_deploy_demo_app` + demos |
| 2:30 - 2:50 | **Q&A** |
| 2:50 - 3:00 | `99_teardown` |
| 3:00 - 4:00 | **Deep-dive Q&A, free exploration** |

Total active participant time: ~1h 40min (of which ~30min is infra waits).

## Per-Student Cost (~4h session)

| Resource | Duration | Cost |
|----------|----------|------|
| Jupyter instance (PRO2-XXS) | ~6h | ~0.15 EUR |
| Object Storage (<5 MB) | ~6h | negligible |
| Managed PostgreSQL DB-DEV-S | ~3h | ~0.07 EUR |
| Managed Inference L4 (BGE) | ~2-3h | ~1.90 EUR |
| Generative APIs (Mistral) | full session | ~0.15 EUR |
| **Total** | | **~2.3 EUR / student** |

## openFDA Data Attribution

The workshop uses drug label data from the **openFDA Drug Label API**
(Structured Product Labeling, SPL). This data is U.S. Government work and
is in the **public domain** under 17 U.S.C. section 105, freely
redistributable, no registration required.

Source: U.S. Food and Drug Administration via the openFDA project
(https://open.fda.gov/license/).

**Disclaimer:** Do not rely on openFDA to make decisions regarding medical
care. While we make every effort to ensure that data is accurate, you
should assume all results are unvalidated. This workshop is for educational
purposes only.

## Troubleshooting

- **If you fall behind:** Switch to `notebooks_solutions/`. They contain
  identical, runnable copies of every notebook.
- **If a notebook fails:** Check that all previous notebooks ran successfully
  (they build on each other's state).
- **If `tofu apply` stalls:** Infrastructure provisioning can take 5-20
  minutes depending on the resource. Managed Inference is the slowest
  (~15-20 min).
- **If you see a certificate warning:** This is expected with self-signed
  TLS. Accept the warning to proceed.

## Teardown

1. **From inside JupyterLab:** Run `99_teardown.ipynb` to destroy live-provisioned
   resources (Managed Inference, PostgreSQL, Object Storage)
2. **From your local machine:** Destroy the Jupyter instance:
   ```bash
   cd workshop/infrastructure && tofu destroy
   ```
3. **Verify:** Check the Scaleway console. No resources matching your
   project_suffix should remain.

## Optional: Restrict Access to Venue IP

For tighter security, restrict the security group to your venue's public IP:

```hcl
# In workshop/infrastructure/terraform.tfvars:
# Add a variable for venue IP and update the security group inbound rules
```

## File Layout

```
workshop/
  infrastructure/     OpenTofu config for the per-student Jupyter host
  iac_snippets/       Self-contained OpenTofu modules (driven from notebooks)
    object_storage/
    postgres/
    managed_inference/
  notebooks/          Workshop notebook sequence (00-07, 99)
  notebooks_solutions/  Identical mirror for recovery
  data/               Bundled openFDA labels dataset
  scripts/            Dataset generation script
  src/                Shared Python modules (chunker, embeddings, rag, tools, react_loop)
```
