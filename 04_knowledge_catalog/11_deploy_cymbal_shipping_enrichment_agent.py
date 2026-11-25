#!/usr/bin/env python3
"""Uploads the 6 Cymbal Shipping multi-category enrichment knowledge signals
(Python ETL pipelines, Dataform SQLX mart, SQL views, ISO GQL graph, and SOP doc)
from `./enrichment_sources/` to Google Cloud Storage, prints the Knowledge Studio
Enrichment Agent configuration payload, and optionally enriches a staged
Knowledge Catalog ChangeRequest via the Dataplex REST API.

Usage:
  python3 04_knowledge_catalog/11_deploy_cymbal_shipping_enrichment_agent.py upload
  python3 04_knowledge_catalog/11_deploy_cymbal_shipping_enrichment_agent.py print-config
  python3 04_knowledge_catalog/11_deploy_cymbal_shipping_enrichment_agent.py patch-cr
"""
import json
import pathlib
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import BQ_DATASET as DS, KC_LOCATION as LOCATION, PROJECT_ID, PROJECT_NUM, api, env, token

ENRICHMENT_DIR = pathlib.Path(__file__).resolve().parent / "enrichment_sources"
BUCKET = env("GCS_ENRICHMENT_BUCKET", f"cymbal-shipping-enrichment-{PROJECT_NUM}")
TASK_ID = env("KC_ENRICHMENT_TASK_ID", "cymbal-shipping-enrichment")
CR_ID = env("KC_ENRICHMENT_CR_ID", "")
ENRICHMENT_SA = env(
    "KC_ENRICHMENT_SA",
    f"knowledge-catalog-enrichment@{PROJECT_ID}.iam.gserviceaccount.com",
)
GLOSS_PATH = f"projects/{PROJECT_NUM}/locations/{LOCATION}/glossaries/cymbal-shipping-glossary"

CONTENT_TYPES = {
    ".py": "text/x-python",
    ".sqlx": "text/plain",
    ".sql": "text/plain",
    ".gql": "text/plain",
    ".md": "text/markdown",
}

DISPLAY_NAME = "Cymbal Shipping · GitHub Code & LookML Enrichment Agent"
DESCRIPTION = (
    "Autonomous Knowledge Catalog Self-Learning Enrichment Agent for Cymbal Shipping — "
    "extracting business rules from Python ETL pipelines, Dataform SQLX marts, "
    "LookML semantic models, Cloud Spanner live package tracking, and Amazon S3 cold chain sensor logs."
)
CUSTOM_INSTRUCTIONS = (
    f"Enrich the Cymbal Shipping Borderless Lakehouse tables ({DS}.shipments, customers, hubs, "
    "live_package_tracking, and exception_evidence) by extracting business rules and pipeline constants "
    "from the enrichment repositories, LookML semantic layer, and Cymbal Shipping Business Glossary. "
    "Specifically curate: "
    "(1) Python ETL pipeline constants in pipelines/memphis_hub_sla_and_refund_pipeline.py: "
    "ON_TIME_SLA_TARGET_PCT = 0.975 (97.5% target), AGING_DWELL_THRESHOLD_HOURS = 6.0 (6+ hours held at hub), "
    "COLD_CHAIN_MAX_TEMP_CELSIUS = 8.0 (>8.0C triggers Temperature Excursion), "
    "CONTROLLABLE_DELAY_REASONS = ('Missed Sort', 'Equipment Delay', 'Misrouted', 'Damaged') vs "
    "EXCUSED_DELAY_REASONS = ('Weather', 'Customs', 'Recipient Not Available', 'Address Correction'); "
    "(2) Resolve the discrepancy between legacy dispatch scripts (4.0h hold threshold, unexcused weather delays, "
    "7.5C ceiling) and the governed Service Guarantee policy (6.0h aging threshold, controllable delays only -> "
    "$343,270 Revenue at Risk across 3,169 packages; $56,994 across 385 Strategic healthcare cold chain packages "
    "at Memphis SuperHub); "
    "(3) Dataform SQLX (dataform/fct_customer_sla_and_cold_chain_risk.sqlx) customer tier segmentation "
    "and cold_chain_risk_band rules."
)

SCOPE_RESOURCES = [
    f"//bigquery.googleapis.com/projects/{PROJECT_ID}/datasets/{DS}/tables/{t}"
    for t in ("shipments", "customers", "hubs", "live_package_tracking", "exception_evidence")
]

AGENT_TASK_CONFIG = {
    "displayName": DISPLAY_NAME,
    "description": DESCRIPTION,
    "executionSpec": {"onDemand": True, "budgetTier": "MEDIUM"},
    "scope": {"resources": SCOPE_RESOURCES},
    "agentSpec": {
        "serviceAccount": ENRICHMENT_SA,
        "contextSetEntryGroup": f"projects/{PROJECT_ID}/locations/{LOCATION}/entryGroups/{TASK_ID}",
    },
    "context": {
        "customInstructions": CUSTOM_INSTRUCTIONS,
        "businessGlossaries": [GLOSS_PATH],
        "cloudStorageBuckets": [
            {
                "uri": f"gs://{BUCKET}/cymbal-shipping/",
                "description": (
                    "Cymbal Shipping Python ETL pipelines, Dataform SQLX marts, "
                    "SQL views, Graph GQL & Service Guarantee SOPs"
                ),
            }
        ],
    },
}

GOLDEN_QUERIES = [
    {
        "description": "1. [Python Pipeline + LookML] Priority Overnight On-Time Delivery Rate by Hub (This Week vs. Last Week) against the 97.5% SLA target.",
        "source": "AGENT",
        "sql": (
            "SELECT\n"
            "  h.hub_name,\n"
            "  ROUND(100.0 * SAFE_DIVIDE(COUNTIF(s.ship_date >= DATE '2026-11-09' AND s.service_outcome != 'Late · Within Our Control'), COUNTIF(s.ship_date >= DATE '2026-11-09' AND s.is_commitment_due)), 1) AS otd_this_week_pct,\n"
            "  ROUND(100.0 * SAFE_DIVIDE(COUNTIF(s.ship_date BETWEEN DATE '2026-11-02' AND DATE '2026-11-08' AND s.service_outcome != 'Late · Within Our Control'), COUNTIF(s.ship_date BETWEEN DATE '2026-11-02' AND DATE '2026-11-08' AND s.is_commitment_due)), 1) AS otd_last_week_pct,\n"
            "  97.5 AS sla_target_pct\n"
            f"FROM `{PROJECT_ID}.{DS}.shipments` AS s\n"
            f"JOIN `{PROJECT_ID}.{DS}.hubs` AS h ON s.routing_hub_code = h.hub_code\n"
            f"JOIN `{PROJECT_ID}.{DS}.services` AS sv ON s.service_code = sv.service_code\n"
            "WHERE sv.service_name = 'Priority Overnight'\n"
            "GROUP BY 1\n"
            "ORDER BY otd_this_week_pct ASC;\n"
        ),
        "sqlDialect": "GOOGLE_SQL",
    },
    {
        "description": "2. [Dataform SQLX + Spanner + AWS S3] Strategic Healthcare Cold Chain Packages Aging (>=6.0h) at Memphis SuperHub with Revenue at Risk and Temperature Excursions (>8.0C).",
        "source": "AGENT",
        "sql": (
            "SELECT\n"
            "  c.customer_name,\n"
            "  c.account_director,\n"
            "  COUNT(DISTINCT s.tracking_number) AS held_6plus_hours,\n"
            "  ROUND(SUM(CASE WHEN s.is_guarantee_refund_eligible THEN s.net_revenue_usd ELSE 0 END), 0) AS revenue_at_risk_usd,\n"
            "  COUNTIF(e.is_temperature_excursion) AS temp_excursions_over_8c,\n"
            "  MAX(e.max_temperature_c) AS peak_temp_celsius\n"
            f"FROM `{PROJECT_ID}.{DS}.shipments` AS s\n"
            f"JOIN `{PROJECT_ID}.{DS}.customers` AS c ON s.customer_id = c.customer_id\n"
            f"JOIN `{PROJECT_ID}.{DS}.live_package_tracking` AS l ON s.tracking_number = l.tracking_number\n"
            f"LEFT JOIN `{PROJECT_ID}.{DS}.exception_evidence` AS e ON s.tracking_number = e.tracking_number\n"
            "WHERE c.customer_tier = 'Strategic'\n"
            "  AND c.industry_vertical = 'Healthcare & Life Sciences'\n"
            "  AND s.is_cold_chain = TRUE\n"
            "  AND l.is_aging = TRUE\n"
            "  AND l.current_hub_code = 'MEM'\n"
            "GROUP BY 1, 2\n"
            "ORDER BY revenue_at_risk_usd DESC;\n"
        ),
        "sqlDialect": "GOOGLE_SQL",
    },
    {
        "description": "3. [BI Finance SQL View] Breakdown of Revenue at Risk ($343,270) across Guaranteed Shipping Services for Controllable Delays This Week.",
        "source": "AGENT",
        "sql": (
            "SELECT\n"
            "  sv.service_name,\n"
            "  COUNT(s.tracking_number) AS guaranteed_packages,\n"
            "  COUNTIF(s.is_guarantee_refund_eligible) AS refund_eligible_late_packages,\n"
            "  ROUND(SUM(CASE WHEN s.is_guarantee_refund_eligible THEN s.net_revenue_usd ELSE 0 END), 0) AS revenue_at_risk_usd\n"
            f"FROM `{PROJECT_ID}.{DS}.shipments` AS s\n"
            f"JOIN `{PROJECT_ID}.{DS}.services` AS sv ON s.service_code = sv.service_code\n"
            "WHERE s.ship_date >= DATE '2026-11-09'\n"
            "  AND s.is_guaranteed_service = TRUE\n"
            "GROUP BY 1\n"
            "ORDER BY revenue_at_risk_usd DESC;\n"
        ),
        "sqlDialect": "GOOGLE_SQL",
    },
]


def upload_sources() -> None:
  """Ensure the GCS bucket exists and upload all 6 enrichment source files."""
  st, _ = api("GET", f"https://storage.googleapis.com/storage/v1/b/{BUCKET}")
  if st == 404:
    st, b = api("POST", "https://storage.googleapis.com/storage/v1/b", {
        "name": BUCKET,
        "location": LOCATION.upper(),
        "storageClass": "STANDARD",
        "iamConfiguration": {
            "uniformBucketLevelAccess": {"enabled": True},
            "publicAccessPrevention": "enforced",
        },
        "labels": {"demo": "cymbal-shipping"},
    }, params={"project": PROJECT_ID})
    print("create bucket:", st, b.get("name") if isinstance(b, dict) else b)
    if st != 200:
      sys.exit(1)

  tok = token()
  files = sorted(f for f in ENRICHMENT_DIR.rglob("*") if f.is_file())
  print(f"Uploading {len(files)} enrichment source files to gs://{BUCKET}/cymbal-shipping/ ...")
  for fpath in files:
    rel = fpath.relative_to(ENRICHMENT_DIR).as_posix()
    body = fpath.read_text(encoding="utf-8").replace("YOUR_GCP_PROJECT_ID", PROJECT_ID)
    ctype = CONTENT_TYPES.get(fpath.suffix, "text/plain")
    gcs_name = urllib.parse.quote(f"cymbal-shipping/{rel}", safe="")
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?uploadType=media&name={gcs_name}"
    req = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": ctype,
            "X-Goog-User-Project": PROJECT_ID,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
      print(f"  gs://{BUCKET}/cymbal-shipping/{rel} -> HTTP {resp.status}")


def patch_change_request() -> None:
  """Attach verified Cymbal Shipping golden queries to an existing ChangeRequest."""
  if not CR_ID:
    sys.exit("Set KC_ENRICHMENT_CR_ID in `.env` after triggering an Enrichment Agent run in Knowledge Studio.")
  cr_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/changeRequests/{CR_ID}"
  st, cr = api("GET", f"https://dataplex.googleapis.com/v1/{cr_name}")
  if st != 200:
    sys.exit(f"Failed to GET ChangeRequest ({st}): {json.dumps(cr)[:400]}")

  batch = cr.get("batchChangeMetadataRequest", {})
  patched = 0
  for ch in batch.get("changes", []):
    for req_key in ("createEntryRequest", "updateEntryRequest"):
      req_obj = ch.get(req_key)
      entry = req_obj.get("entry") if isinstance(req_obj, dict) else None
      if not isinstance(entry, dict):
        continue
      for ak, av in entry.get("aspects", {}).items():
        if ak.endswith(".queries") and isinstance(av, dict):
          av.setdefault("data", {})["queries"] = GOLDEN_QUERIES
          patched += 1

  justification = (
      "Cymbal Shipping enrichment agent proposal: Extracted Python ETL pipeline constants "
      "(97.5% On-Time SLA target, 6.0h Aging Package dwell threshold, 8.0C Cold Chain ceiling), "
      "Dataform SQLX customer tier rules, and Service Guarantee refund logic ($343,270 Revenue at Risk; "
      "$56,994 across 385 Strategic healthcare packages at Memphis SuperHub)."
  )
  st_p, res_p = api(
      "PATCH",
      f"https://dataplex.googleapis.com/v1/{cr_name}?updateMask=batch_change_metadata_request.changes,justification",
      {"name": cr_name, "etag": cr.get("etag"), "batchChangeMetadataRequest": batch, "justification": justification},
  )
  print(f"PATCH ChangeRequest status={st_p} | query aspects updated={patched} | etag={res_p.get('etag') if isinstance(res_p, dict) else res_p}")


if __name__ == "__main__":
  cmd = sys.argv[1] if len(sys.argv) > 1 else "upload"
  if cmd == "upload":
    upload_sources()
  elif cmd == "print-config":
    print(json.dumps(AGENT_TASK_CONFIG, indent=2))
  elif cmd == "patch-cr":
    patch_change_request()
  else:
    sys.exit("Usage: 11_deploy_cymbal_shipping_enrichment_agent.py [upload|print-config|patch-cr]")
