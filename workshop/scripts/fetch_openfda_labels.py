"""Fetch and trim drug label data from the openFDA Drug Label API.

openFDA disclaimer (https://open.fda.gov/license/):
  Do not rely on openFDA to make decisions regarding medical care. While we
  make every effort to ensure that data is accurate, you should assume all
  results are unvalidated.

openFDA data is U.S. Government work and is in the public domain under
17 U.S.C. section 105. No registration or API key is required (though an
optional OPENFDA_API_KEY env var raises the rate limit).

Usage:
  python fetch_openfda_labels.py --output workshop/data/openfda_labels.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"

# Sections to keep from each label result (the rest are dropped at fetch time)
KEPT_SECTIONS: set[str] = {
    "boxed_warning",
    "indications_and_usage",
    "contraindications",
    "warnings_and_cautions",
    "drug_interactions",
    "drug_interactions_table",
    "adverse_reactions",
    "use_in_specific_populations",
    "pregnancy",
    "pediatric_use",
    "geriatric_use",
    "mechanism_of_action",
    "clinical_pharmacology",
}

# Metadata fields to keep from the openfda block
KEPT_OPENFDA_FIELDS: set[str] = {
    "generic_name",
    "brand_name",
    "rxcui",
    "application_number",
    "product_ndc",
    "manufacturer_name",
    "set_id",
}

# Hard-coded allowlist of 200 drugs curated for interaction richness.
# Includes well-known high-interaction drugs (anticoagulants, antiepileptics,
# CYP450 inhibitors/inducers) and less-obvious ones with severe profiles.
DEFAULT_DRUG_NAMES: list[str] = [
    # --- Anticoagulants & antiplatelets (high interaction, bleeding risk) ---
    "warfarin",
    "heparin",
    "enoxaparin",
    "rivaroxaban",
    "apixaban",
    "dabigatran",
    "clopidogrel",
    "prasugrel",
    "ticagrelor",
    "pimozide",
    "aspirin",
    # --- NSAIDs (bleeding, renal, CV interactions) ---
    "ibuprofen",
    "naproxen",
    "diclofenac",
    "celecoxib",
    "meloxicam",
    "indomethacin",
    "ketorolac",
    "piroxicam",
    # --- Analgesics & opioids (CNS depression, serotonin syndrome) ---
    "acetaminophen",
    "tramadol",
    "morphine",
    "oxycodone",
    "fentanyl",
    "hydrocodone",
    "codeine",
    "methadone",
    "buprenorphine",
    "tapentadol",
    # --- Antidepressants (serotonin syndrome, CYP2D6) ---
    "sertraline",
    "fluoxetine",
    "paroxetine",
    "citalopram",
    "escitalopram",
    "fluvoxamine",
    "venlafaxine",
    "duloxetine",
    "bupropion",
    "trazodone",
    "mirtazapine",
    "nortriptyline",
    "amitriptyline",
    "doxepin",
    "clomipramine",
    "imipramine",
    # --- MAOIs (tyramine crisis, serotonin syndrome) ---
    "phenelzine",
    "tranylcypromine",
    "selegiline",
    "rasagiline",
    # --- Antipsychotics ---
    "quetiapine",
    "olanzapine",
    "risperidone",
    "aripiprazole",
    "haloperidol",
    "chlorpromazine",
    "clozapine",
    "ziprasidone",
    "paliperidone",
    # --- Benzodiazepines & sedatives ---
    "diazepam",
    "alprazolam",
    "lorazepam",
    "clonazepam",
    "midazolam",
    "zolpidem",
    # --- Antiepileptics (CYP inducers/inhibitors, narrow therapeutic index) ---
    "carbamazepine",
    "phenytoin",
    "valproic acid",
    "lamotrigine",
    "levetiracetam",
    "topiramate",
    "oxcarbazepine",
    "phenobarbital",
    "gabapentin",
    "pregabalin",
    # --- Cardiovascular (narrow index, arrhythmia risk) ---
    "amiodarone",
    "digoxin",
    "diltiazem",
    "verapamil",
    "amlodipine",
    "metoprolol",
    "atenolol",
    "propranolol",
    "carvedilol",
    "sotalol",
    "flecainide",
    "dronedarone",
    "ranolazine",
    "ivabradine",
    # --- ACE inhibitors, ARBs, diuretics ---
    "lisinopril",
    "enalapril",
    "ramipril",
    "losartan",
    "valsartan",
    "irbesartan",
    "hydrochlorothiazide",
    "furosemide",
    "spironolactone",
    "eplerenone",
    "torsemide",
    # --- Statins & lipid-lowering (rhabdomyolysis risk) ---
    "atorvastatin",
    "simvastatin",
    "rosuvastatin",
    "pravastatin",
    "lovastatin",
    "ezetimibe",
    "fenofibrate",
    "gemfibrozil",
    # --- Diabetes (hypoglycemia, lactic acidosis) ---
    "metformin",
    "glipizide",
    "glyburide",
    "pioglitazone",
    "sitagliptin",
    "empagliflozin",
    "dapagliflozin",
    "canagliflozin",
    "liraglutide",
    "insulin",
    # --- Thyroid ---
    "levothyroxine",
    # --- Corticosteroids ---
    "prednisone",
    "dexamethasone",
    "methylprednisolone",
    "hydrocortisone",
    # --- Antibiotics (CYP3A4 inhibitors, QT prolongation) ---
    "clarithromycin",
    "erythromycin",
    "azithromycin",
    "amoxicillin",
    "ciprofloxacin",
    "levofloxacin",
    "moxifloxacin",
    "doxycycline",
    "trimethoprim",
    "metronidazole",
    "linezolid",
    "rifampin",
    "isoniazid",
    "nitrofurantoin",
    "sulfamethoxazole",
    # --- Antifungals (strong CYP3A4 inhibitors) ---
    "fluconazole",
    "ketoconazole",
    "itraconazole",
    "voriconazole",
    "posaconazole",
    # --- Antivirals (CYP interactions, HIV/HCV) ---
    "ritonavir",
    "cobicistat",
    "efavirenz",
    "atazanavir",
    "sofosbuvir",
    # --- GI (acid suppression alters absorption) ---
    "omeprazole",
    "esomeprazole",
    "lansoprazole",
    "pantoprazole",
    "ranitidine",
    "famotidine",
    "ondansetron",
    "metoclopramide",
    # --- Immunosuppressants (narrow index) ---
    "cyclosporine",
    "tacrolimus",
    "sirolimus",
    "mycophenolate",
    "methotrexate",
    "azathioprine",
    # --- Oncology (narrow index, severe interactions) ---
    "tamoxifen",
    "erlotinib",
    "imatinib",
    "capecitabine",
    "fluorouracil",
    "vincristine",
    # --- Mood stabilizer ---
    "lithium",
    # --- Dementia ---
    "donepezil",
    "memantine",
    "rivastigmine",
    # --- Gout ---
    "allopurinol",
    "colchicine",
    # --- Respiratory ---
    "theophylline",
    "montelukast",
    "albuterol",
    "fluticasone",
    # --- Erectile dysfunction / pulmonary HTN ---
    "sildenafil",
    "tadalafil",
    # --- Muscle relaxants ---
    "cyclobenzaprine",
    "tizanidine",
    "baclofen",
    # --- Miscellaneous high-interaction drugs ---
    "disulfiram",
    "dantrolene",
    "chloroquine",
    "hydroxychloroquine",
    "sumatriptan",
    "ergotamine",
    # --- Additional high-interaction / narrow-index drugs ---
    "clindamycin",
    "gentamicin",
    "vancomycin",
    "amphotericin b",
    "nifedipine",
    "nitroglycerin",
    "cimetidine",
    "propafenone",
    "primidone",
    "buspirone",
    "naltrexone",
    "naloxone",
]

# Pacing constants
REQUEST_DELAY_SECONDS = 1.0
BACKOFF_BASE_SECONDS = 2.0
MAX_RETRIES = 5


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _trim_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    """Trim a raw openFDA label result to only kept sections + openfda metadata."""
    trimmed: dict[str, Any] = {}

    # Keep sections
    for section in KEPT_SECTIONS:
        if section in raw_result:
            trimmed[section] = raw_result[section]

    # Keep and trim openfda metadata block
    if "openfda" in raw_result:
        raw_openfda = raw_result["openfda"]
        trimmed_openfda: dict[str, Any] = {}
        for field in KEPT_OPENFDA_FIELDS:
            if field in raw_openfda:
                trimmed_openfda[field] = raw_openfda[field]
        trimmed["openfda"] = trimmed_openfda

    return trimmed


def _fetch_single_drug(drug_name: str, api_key: str | None = None) -> dict[str, Any] | None:
    """Fetch the richest available label for a drug.

    openFDA returns many labels per drug (one per manufacturer/formulation).
    The first hit is often a sparse manufacturer entry that only has
    indications_and_usage. Cascade through progressively looser server-side
    `_exists_` filters so we end up with a label that lets the agent
    actually demonstrate interactions.
    """
    queries = [
        f"openfda.generic_name:{drug_name} AND _exists_:drug_interactions AND _exists_:warnings_and_cautions",
        f"openfda.generic_name:{drug_name} AND _exists_:drug_interactions",
        f"openfda.generic_name:{drug_name} AND _exists_:warnings_and_cautions",
        f"openfda.generic_name:{drug_name}",
    ]
    for query in queries:
        result = _fetch_with_query(query, api_key)
        if result is not None:
            return result
    logger.warning("No label found for '%s' on any cascade query", drug_name)
    return None


def _fetch_with_query(search: str, api_key: str | None) -> dict[str, Any] | None:
    """Run one openFDA search with retry-on-429. Returns None on 404 / no hits."""
    params: dict[str, str | int] = {"search": search, "limit": 1}
    if api_key:
        params["api_key"] = api_key

    for attempt in range(MAX_RETRIES):
        resp = requests.get(OPENFDA_BASE_URL, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return _trim_result(results[0])
            return None

        if resp.status_code == 429:
            backoff = BACKOFF_BASE_SECONDS * (2**attempt)
            logger.warning("Rate limited (429), backing off %.1fs (attempt %d/%d)", backoff, attempt + 1, MAX_RETRIES)
            time.sleep(backoff)
            continue

        if resp.status_code == 404:
            return None

        logger.error("HTTP %d: %s", resp.status_code, resp.text[:200])
        return None

    return None


def fetch_labels(drug_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch trimmed openFDA labels for a list of drug names.

    Args:
        drug_names: List of generic drug names to fetch. If None, uses the
            default allowlist.

    Returns:
        List of trimmed label records (one per drug that had results).
    """
    if drug_names is None:
        drug_names = DEFAULT_DRUG_NAMES

    api_key = os.environ.get("OPENFDA_API_KEY")
    results: list[dict[str, Any]] = []

    for i, drug_name in enumerate(drug_names):
        logger.info("Fetching label for '%s' (%d/%d)", drug_name, i + 1, len(drug_names))

        record = _fetch_single_drug(drug_name, api_key=api_key)
        if record is not None:
            results.append(record)

        # Polite pacing between requests (not after the last one)
        if i < len(drug_names) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Fetched %d labels out of %d requested", len(results), len(drug_names))
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the fetcher script."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Fetch drug labels from the openFDA Drug Label API.")
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to write the JSON output file",
    )
    args = parser.parse_args()

    results = fetch_labels()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %d records to %s", len(results), output_path)


if __name__ == "__main__":
    main()
