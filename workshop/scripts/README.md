# Workshop Scripts

## fetch_openfda_labels.py

Fetches Structured Product Labeling (SPL) data from the **openFDA Drug Label API**
for a hard-coded allowlist of commonly-prescribed generic drugs and writes a
combined, trimmed JSON file to `workshop/data/openfda_labels.json`.

### openFDA endpoint

```
GET https://api.fda.gov/drug/label.json?search=openfda.generic_name:<name>&limit=1
```

No authentication is required. An optional `OPENFDA_API_KEY` environment variable
raises the rate limit (register at https://open.fda.gov/apis/authentication/).

### Kept-sections schema

Each label record is trimmed to the following sections (when present in the raw
API response):

| Section | Description |
|---------|-------------|
| `boxed_warning` | FDA "black box" warning (CRITICAL severity signal) |
| `indications_and_usage` | Approved indications |
| `contraindications` | Explicit contraindications |
| `warnings_and_cautions` | General warnings |
| `drug_interactions` | Drug interactions free-text |
| `drug_interactions_table` | Drug interactions structured table |
| `adverse_reactions` | Adverse reactions |
| `use_in_specific_populations` | Renal, hepatic, and other population guidance |
| `pregnancy` | Pregnancy use |
| `pediatric_use` | Pediatric use |
| `geriatric_use` | Geriatric use |
| `mechanism_of_action` | Mechanism of action |
| `clinical_pharmacology` | Clinical pharmacology |

Metadata from the `openfda` block: `generic_name`, `brand_name`, `rxcui`,
`application_number`, `product_ndc`, `manufacturer_name`, `set_id`.

Sections dropped at fetch time: `spl_product_data_elements`, `references`,
`how_supplied`, `clinical_studies_table`, `dosage_forms_and_strengths`,
`nonclinical_toxicology`, and any other sections not in the kept list.

### Polite-pacing convention

- 1 request per second between drugs (the default openFDA rate limit is
  40 requests per minute without an API key).
- Exponential backoff on HTTP 429 (Too Many Requests), up to 5 retries.

### How to extend the allowlist

Edit the `DEFAULT_DRUG_NAMES` list in `fetch_openfda_labels.py` and re-run:

```bash
python workshop/scripts/fetch_openfda_labels.py --output workshop/data/openfda_labels.json
```

### Usage

```bash
# Basic (no API key, polite pacing)
python workshop/scripts/fetch_openfda_labels.py --output workshop/data/openfda_labels.json

# With optional API key for higher rate limits
OPENFDA_API_KEY=your_key_here python workshop/scripts/fetch_openfda_labels.py --output workshop/data/openfda_labels.json
```

### Attribution

openFDA data is **U.S. Government work** and is in the **public domain** under
17 U.S.C. section 105 -- freely redistributable, no registration, no licence wall.

Source: U.S. Food and Drug Administration via the openFDA project
(https://open.fda.gov/license/).

**Disclaimer**: Do not rely on openFDA to make decisions regarding medical care.
While we make every effort to ensure that data is accurate, you should assume all
results are unvalidated.
