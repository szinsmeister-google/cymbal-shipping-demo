"""Wire Cymbal Shipping into Knowledge Catalog.

1. Business glossary terms (+ overviews): 14 plain-language definitions
2. Overviews on the native BigQuery, Looker and Spanner entries
3. Cataloged upstream source: Amazon S3 field-evidence bucket (custom entries)
4. Entry links: joins, term definitions, and cross-system references
5. Context set `cymbal-shipping-context-set`

Idempotent. Only touches Cymbal Shipping entries.
Usage: python3 04_knowledge_catalog/04_wire_knowledge_catalog.py [glossary] [overviews] [s3] [links] [contextset]
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from lib.gcp import BQ_DATASET as DS, KC_LOCATION as LOC, LOOKER_INSTANCE_ID, PROJECT_ID as P, PROJECT_NUM as N, api, env
from kc_terms import GLOSSARY_DESC, GLOSSARY_ID, GLOSSARY_TITLE, TERMS

DP = "https://dataplex.googleapis.com/v1"
SYS = "655216118709"  # Google-managed Dataplex / Knowledge Catalog system project
STEPS = sys.argv[1:] or ["glossary", "overviews", "s3", "links", "contextset"]

SPANNER_INSTANCE = env("SPANNER_INSTANCE", "cymbal-shipping-ops")
SPANNER_DATABASE = env("SPANNER_DATABASE", "cymbal_shipping_ops")

REF = f"projects/{SYS}/locations/global/entryLinkTypes/reference"
SJ = f"projects/{SYS}/locations/global/entryLinkTypes/schema-join"
DEF = f"projects/{SYS}/locations/global/entryLinkTypes/definition"

EGN = f"projects/{N}/locations/{LOC}/entryGroups"       # numeric form (entry names)
EGP = f"projects/{P}/locations/{LOC}/entryGroups"       # id form (create calls)
BQ_EG = f"{EGN}/@bigquery"
LK_EG = f"{EGN}/@looker"
SP_EG = f"{EGN}/@spanner"
DX_EG = f"{EGN}/@dataplex"

BQ_T = lambda t: f"{BQ_EG}/entries/bigquery.googleapis.com/projects/{P}/datasets/{DS}/tables/{t}"
INST_RES = f"projects/{P}/locations/{LOC}/instances/{LOOKER_INSTANCE_ID}"
LK_MODEL = f"{LK_EG}/entries/looker.googleapis.com/{INST_RES}/lookml_projects/cymbal_shipping/models/cymbal_shipping"
LK_EXPLORE = f"{LK_MODEL}/explores/shipments"
LK_V = lambda v: f"{LK_MODEL}/views/{v}"
SP_DB = f"{SP_EG}/entries/spanner.googleapis.com/projects/{P}/instances/{SPANNER_INSTANCE}/databases/{SPANNER_DATABASE}"
SP_T = lambda t: f"{SP_DB}/tables/{t}"
TERM = lambda tid: f"{DX_EG}/entries/projects/{N}/locations/{LOC}/glossaries/{GLOSSARY_ID}/terms/{tid}"
S3_EG_ID = "cymbal-shipping-aws-s3"
S3_E = lambda e: f"{EGN}/{S3_EG_ID}/entries/{e}"
CS_ID = "cymbal-shipping-context-set"


def dp(method, path, body=None, params=None):
  for attempt in range(5):
    st, r = api(method, f"{DP}/{path}", body, params=params)
    if st in (429, 503) and attempt < 4:
      time.sleep(2 * (attempt + 1))
      continue
    return st, r
  return st, r


def wait_op(r):
  if isinstance(r, dict) and "/operations/" in r.get("name", ""):
    for _ in range(40):
      st, op = dp("GET", r["name"])
      if isinstance(op, dict) and op.get("done"):
        return op
      time.sleep(1.5)
  return r


def overview(html):
  return {f"{SYS}.global.overview": {
      "aspectType": f"projects/{SYS}/locations/global/aspectTypes/overview",
      "data": {"content": html}}}


def set_overview(entry, html):
  st, r = dp("PATCH", entry, {"name": entry, "aspects": overview(html)},
             params={"updateMask": "aspects", "aspectKeys": f"{SYS}.global.overview"})
  return st, r


def link(eg, link_id, link_type, refs, aspects=None):
  dp("DELETE", f"{eg}/entryLinks/{link_id}")
  body = {"entryLinkType": link_type, "entryReferences": refs}
  if aspects:
    body["aspects"] = aspects
  st, r = dp("POST", f"{eg}/entryLinks", body, params={"entryLinkId": link_id})
  if st != 200:
    print(f"   LINK FAIL {link_id}: {st} {json.dumps(r)[:260]}")
  return st


def ref_link(eg, link_id, src, dst):
  return link(eg, link_id, REF, [{"name": src, "type": "SOURCE"}, {"name": dst, "type": "TARGET"}])


# ================================================================ GLOSSARY ==
if "glossary" in STEPS:
  print("== glossary")
  st, g = dp("GET", f"projects/{P}/locations/{LOC}/glossaries/{GLOSSARY_ID}")
  if st == 404:
    st, r = dp("POST", f"projects/{P}/locations/{LOC}/glossaries",
               {"displayName": GLOSSARY_TITLE, "description": GLOSSARY_DESC}, params={"glossaryId": GLOSSARY_ID})
    wait_op(r)
    print("  created glossary", st)
  gl_entry = f"{DX_EG}/entries/projects/{N}/locations/{LOC}/glossaries/{GLOSSARY_ID}"
  st, _ = set_overview(gl_entry, f"<h3>{GLOSSARY_TITLE}</h3><p>{GLOSSARY_DESC}</p>")
  print("  glossary overview:", st)
  for tid, title, desc, html in TERMS:
    st, r = dp("POST", f"projects/{P}/locations/{LOC}/glossaries/{GLOSSARY_ID}/terms",
               {"displayName": title, "description": desc,
                "parent": f"projects/{P}/locations/{LOC}/glossaries/{GLOSSARY_ID}"}, params={"termId": tid})
    if st == 409:
      st, r = dp("PATCH", f"projects/{P}/locations/{LOC}/glossaries/{GLOSSARY_ID}/terms/{tid}",
                 {"displayName": title, "description": desc}, params={"updateMask": "displayName,description"})
    wait_op(r)
    ok = False
    st2 = 0
    for _ in range(8):   # term entry appears in @dataplex shortly after the term is created
      st2, _r = set_overview(TERM(tid), html)
      if st2 == 200:
        ok = True
        break
      time.sleep(2)
    print(f"  term {tid}: {st} overview={'ok' if ok else st2}")

# =============================================================== OVERVIEWS ==
BQ_OV = {
    "shipments": "<h3>Shipments</h3><p>One row for every package Cymbal Shipping picked up for a named account since October 1, 2026: the service bought, the promised delivery time, what actually happened, any delivery exception, and the shipping charge.</p><p><strong>Use it for:</strong> on-time delivery, late packages by cause, and revenue exposed to the Service Guarantee. For official numbers use the Looker model <em>Shipments &amp; Service Performance</em>, which applies the governed definitions.</p><p><strong>Connects to:</strong> customers, services, hubs, live package tracking (from Spanner) and field evidence (from the S3 document lake).</p>",
    "customers": "<h3>Customers</h3><p>Cymbal Shipping named accounts: who the shipper is, their industry, their account tier (Strategic, Enterprise, Mid-Market, Small Business) and the account director who owns the relationship.</p>",
    "services": "<h3>Services</h3><p>The Cymbal Shipping service catalog: how fast each service is, the commit time we promise, and whether the Service Guarantee applies.</p>",
    "hubs": "<h3>Hubs</h3><p>Cymbal Shipping sort hubs and gateways, with the Recovery Hub that covers for each one during a disruption. The Memphis SuperHub is the largest; the Indianapolis Air Hub is its Recovery Hub.</p>",
    "live_package_tracking": "<h3>Live Package Tracking</h3><p>Where every in-network package is right now, how long it has been held at its hub, and the plan to get it moving. The hubs and scanners write this to the Spanner operations database (<code>cymbal_shipping_ops.PackageTracking</code>); BigQuery reads Spanner in place through the external dataset <code>cymbal_shipping_ops_spanner</code> and keeps this copy for fast analysis.</p><p><strong>Use it for:</strong> Aging Packages (held 6 hours or more) and recovery plans.</p>",
    "exception_evidence": "<h3>Field Evidence</h3><p>What the people on the ground wrote down when a package was delayed or damaged: hub delay notices, cold chain temperature logs, driver damage reports and customs notices. One row per document, with a plain-language summary, the root cause, and for cold chain packages the highest temperature recorded.</p><p><strong>Where it comes from:</strong> documents captured into the Cymbal Shipping field-evidence bucket in Amazon S3, read by the lakehouse through the object table <code>field_evidence_objects</code>.</p>",
    "field_evidence_objects": "<h3>Field Evidence Documents (object table)</h3><p>One row per field document file: hub delay notices, cold chain temperature logs, damage reports and customs notices. This is unstructured data. It lets the document text be searched and summarized with SQL and AI alongside shipment data. The key facts are extracted into <code>exception_evidence</code>.</p>",
}
LK_OV = {
    "explore": "<h3>Shipments &amp; Service Performance (Looker Explore)</h3><p>The governed place to answer questions about Cymbal Shipping service performance for named accounts: packages moved, On-Time Delivery Rate against the 97.5% target, packages held at a hub right now, and Revenue at Risk under the Service Guarantee.</p><p>It joins shipment history in BigQuery, live package tracking from Spanner, and field evidence from the S3 document lake, and applies the business definitions from the Cymbal Shipping Business Glossary so every tool reports the same number.</p><p><strong>Used by:</strong> the Cymbal Shipping Service Performance app in Looker and the Cymbal Shipping Gemini agent.</p>",
    "shipments": "<h3>Shipments (Looker view)</h3><p>Governed measures for service performance: Packages, On-Time Delivery Rate, Raw On-Time Rate (Unadjusted), Late Packages within and outside our control, Shipping Revenue, Revenue per Package and Revenue at Risk.</p>",
    "customers": "<h3>Customers (Looker view)</h3><p>Customer, Industry, Account Tier and Account Director for every named account.</p>",
    "services": "<h3>Services (Looker view)</h3><p>Service and Service Family, with the days and time of day we promise delivery.</p>",
    "hubs": "<h3>Hubs (Looker view)</h3><p>Hub, Hub Type, Hub Region and the Recovery Hub for each hub.</p>",
    "live_package_tracking": "<h3>Live Tracking (Looker view)</h3><p>Aging Packages, Hours Held at Hub, Last Scan and Recovery Plan for packages still in the network. Source of record: Spanner.</p>",
    "exception_evidence": "<h3>Field Evidence (Looker view)</h3><p>What Happened, Root Cause, Customer Impact and Temperature Excursions, taken from field documents in the S3 document lake.</p>",
}
SP_OV = {
    "PackageTracking": "<h3>PackageTracking (Spanner)</h3><p>The live tracking record for every package in the Cymbal Shipping network. Hubs and handheld scanners write to it in real time: where the package is, its last scan, how long it has been held, and the recovery plan. This is the operational system of record; BigQuery reads it in place for analysis.</p>",
    "Hubs": "<h3>Hubs (Spanner)</h3><p>Live operating status of each sort hub: whether it is sorting normally or recovering, the status note from the Network Control Center, and how many packages are held.</p>",
    "RecoveryLanes": "<h3>RecoveryLanes (Spanner)</h3><p>The recovery route from each hub to its Recovery Hub, with the next departure and how many packages are being diverted.</p>",
}
if "overviews" in STEPS:
  print("== overviews")
  for t, html in BQ_OV.items():
    print("  bq", t, set_overview(BQ_T(t), html)[0])
  print("  looker explore", set_overview(LK_EXPLORE, LK_OV["explore"])[0])
  for v in ["shipments", "customers", "services", "hubs", "live_package_tracking", "exception_evidence"]:
    print("  looker view", v, set_overview(LK_V(v), LK_OV[v])[0])
  for t, html in SP_OV.items():
    st, r = set_overview(SP_T(t), html)
    print("  spanner", t, st, "" if st == 200 else json.dumps(r)[:200])

# ============================================================ S3 (custom) ==
S3_BUCKET = "s3-bucket-cymbal-shipping-field-evidence"
S3_COLLECTIONS = [
    ("s3-hub-delay-notices", "Hub Delay Notices (S3 folder)",
     "Notices written by Night Sort Operations when packages miss a sort, with the cause and the recovery plan.",
     "hub-delay-notices/"),
    ("s3-cold-chain-temperature-logs", "Cold Chain Temperature Logs (S3 folder)",
     "Temperature logger read-outs for temperature-controlled healthcare packages held at a hub, written by the Cold Chain Desk.",
     "cold-chain-temperature-logs/"),
    ("s3-driver-and-customs-reports", "Driver and Customs Reports (S3 folder)",
     "Driver damage reports, delivery attempt notes, address correction requests and customs hold notices.",
     "driver-and-customs-reports/"),
]
if "s3" in STEPS:
  print("== amazon s3 source (cataloged)")
  st, r = dp("POST", f"projects/{P}/locations/global/entryTypes", {
      "displayName": "Amazon S3 Location",
      "description": "A bucket or folder in Amazon S3 that is cataloged as a source for the lakehouse.",
      "platform": "AWS", "system": "Amazon S3"}, params={"entryTypeId": "aws-s3-location"})
  wait_op(r)
  print("  entry type aws-s3-location:", st if st != 409 else "exists")
  st, r = dp("POST", EGP, {
      "displayName": "Cymbal Shipping · Field Evidence in Amazon S3",
      "description": "The Amazon S3 bucket where Cymbal Shipping drivers and hub teams capture field evidence documents. Cataloged here so the lakehouse and AI agents know where unstructured evidence originates."},
      params={"entryGroupId": S3_EG_ID})
  wait_op(r)
  print("  entry group:", st if st != 409 else "exists")

  def upsert(entry_id, title, desc, resource, html):
    name = S3_E(entry_id)
    body = {"name": name, "entryType": f"projects/{P}/locations/global/entryTypes/aws-s3-location",
            "entrySource": {"displayName": title, "description": desc, "system": "Amazon S3", "platform": "AWS",
                            "resource": resource, "location": "us-east-1"},
            "aspects": overview(html)}
    st, r = dp("POST", f"{EGP}/{S3_EG_ID}/entries", body, params={"entryId": entry_id})
    if st == 409:
      st, r = dp("PATCH", name, body, params={"updateMask": "entrySource,aspects"})
    print(f"  entry {entry_id}: {st} {'' if st == 200 else json.dumps(r)[:200]}")

  upsert(S3_BUCKET, "cymbal-shipping-field-evidence (Amazon S3 bucket)",
         "Amazon S3 bucket (AWS us-east-1) where drivers and hub teams capture field evidence: hub delay notices, cold chain temperature logs, damage reports and customs notices.",
         "s3://cymbal-shipping-field-evidence",
         "<h3>cymbal-shipping-field-evidence (Amazon S3)</h3><p>Where field evidence starts. Handheld devices and hub systems write documents here in AWS us-east-1. The lakehouse reads them as the object table <code>field_evidence_objects</code> and extracts the key facts into <code>exception_evidence</code>, so the reason behind a late package sits next to the shipment record.</p>")
  for eid, title, desc, prefix in S3_COLLECTIONS:
    upsert(eid, title, desc, f"s3://cymbal-shipping-field-evidence/{prefix}", f"<h3>{title}</h3><p>{desc}</p>")

# =================================================================== LINKS ==
if "links" in STEPS:
  print("== links")
  n_ok = 0
  joins = [
      ("cs-sj-ship-cust", "shipments", "customer_id", "customers", "customer_id"),
      ("cs-sj-ship-svc", "shipments", "service_code", "services", "service_code"),
      ("cs-sj-ship-hub", "shipments", "routing_hub_code", "hubs", "hub_code"),
      ("cs-sj-ship-track", "shipments", "tracking_number", "live_package_tracking", "tracking_number"),
      ("cs-sj-ship-evid", "shipments", "tracking_number", "exception_evidence", "tracking_number"),
      ("cs-sj-evid-obj", "exception_evidence", "document_uri", "field_evidence_objects", "uri"),
      ("cs-sj-track-hub", "live_package_tracking", "current_hub_code", "hubs", "hub_code"),
  ]
  for lid, t1, f1, t2, f2 in joins:
    st = link(BQ_EG, lid, SJ, [{"name": BQ_T(t1)}, {"name": BQ_T(t2)}], aspects={
        f"{SYS}.global.schema-join": {
            "aspectType": f"projects/{SYS}/locations/global/aspectTypes/schema-join",
            "data": {"joins": [{"source": {"name": t1, "fields": [f1]}, "target": {"name": t2, "fields": [f2]},
                                "description": f"{t1}.{f1} = {t2}.{f2}", "type": "JOIN", "inferenceSource": "USER"}],
                     "userManaged": True}}})
    n_ok += st == 200

  refs = []
  views = ["shipments", "customers", "services", "hubs", "live_package_tracking", "exception_evidence"]
  for v in views:
    refs.append((LK_EG, f"cs-ref-view-{v[:12].replace('_', '-')}-bq", LK_V(v), BQ_T(v)))
    refs.append((LK_EG, f"cs-ref-exp-view-{v[:12].replace('_', '-')}", LK_EXPLORE, LK_V(v)))
  refs += [
      (LK_EG, "cs-ref-exp-bq-shipments", LK_EXPLORE, BQ_T("shipments")),
      (BQ_EG, "cs-ref-track-spanner", BQ_T("live_package_tracking"), SP_T("PackageTracking")),
      (BQ_EG, "cs-ref-hubs-spanner", BQ_T("hubs"), SP_T("Hubs")),
      (SP_EG, "cs-ref-sp-track-hubs", SP_T("PackageTracking"), SP_T("Hubs")),
      (SP_EG, "cs-ref-sp-lanes-hubs", SP_T("RecoveryLanes"), SP_T("Hubs")),
      (BQ_EG, "cs-ref-obj-s3", BQ_T("field_evidence_objects"), S3_E(S3_BUCKET)),
      (BQ_EG, "cs-ref-evid-obj", BQ_T("exception_evidence"), BQ_T("field_evidence_objects")),
  ]
  for eid, _t, _d, _p in S3_COLLECTIONS:
    refs.append((f"{EGN}/{S3_EG_ID}", f"cs-ref-{eid}-bucket", S3_E(eid), S3_E(S3_BUCKET)))
  for eg, lid, src, dst in refs:
    n_ok += ref_link(eg, lid, src, dst) == 200

  defs = [
      ("on-time-delivery-rate", LK_EG, LK_V("shipments"), "on_time_delivery_rate"),
      ("on-time-delivery-rate", BQ_EG, BQ_T("shipments"), "service_outcome"),
      ("commit-time", BQ_EG, BQ_T("shipments"), "committed_delivery_ts"),
      ("commit-time", BQ_EG, BQ_T("services"), "commit_time_local"),
      ("service-guarantee", BQ_EG, BQ_T("services"), "is_guaranteed_service"),
      ("service-guarantee", BQ_EG, BQ_T("shipments"), "is_guaranteed_service"),
      ("revenue-at-risk", LK_EG, LK_V("shipments"), "revenue_at_risk"),
      ("revenue-at-risk", BQ_EG, BQ_T("shipments"), "is_guarantee_refund_eligible"),
      ("delay-within-our-control", BQ_EG, BQ_T("shipments"), "exception_category"),
      ("delay-outside-our-control", BQ_EG, BQ_T("shipments"), "exception_category"),
      ("missed-sort", BQ_EG, BQ_T("shipments"), "exception_reason"),
      ("aging-package", BQ_EG, BQ_T("live_package_tracking"), "is_aging"),
      ("aging-package", LK_EG, LK_V("live_package_tracking"), "aging_packages"),
      ("aging-package", SP_EG, SP_T("PackageTracking"), "is_aging"),
      ("cold-chain-shipment", BQ_EG, BQ_T("shipments"), "is_cold_chain"),
      ("temperature-excursion", BQ_EG, BQ_T("exception_evidence"), "is_temperature_excursion"),
      ("temperature-excursion", LK_EG, LK_V("exception_evidence"), "temperature_excursions"),
      ("strategic-account", BQ_EG, BQ_T("customers"), "customer_tier"),
      ("recovery-hub", BQ_EG, BQ_T("hubs"), "backup_hub_code"),
      ("recovery-hub", SP_EG, SP_T("RecoveryLanes"), "to_hub_code"),
      ("revenue-per-package", LK_EG, LK_V("shipments"), "revenue_per_package"),
      ("field-evidence", BQ_EG, BQ_T("exception_evidence"), "summary"),
      ("field-evidence", f"{EGN}/{S3_EG_ID}", S3_E(S3_BUCKET), None),
  ]
  n_def = n_fallback = 0
  for i, (tid, eg, entry, col) in enumerate(defs):
    lid = f"cs-def-{i:02d}-{tid[:22]}"
    st = 0
    if col:
      dp("DELETE", f"{eg}/entryLinks/{lid}")
      st, r = dp("POST", f"{eg}/entryLinks", {"entryLinkType": DEF, "entryReferences": [
          {"name": entry, "path": f"Schema.{col}", "type": "SOURCE"},
          {"name": TERM(tid), "type": "TARGET"}]}, params={"entryLinkId": lid})
      if st == 200:
        n_def += 1
      else:
        print(f"   definition link {lid} -> {st} {json.dumps(r)[:200]}")
    if st != 200:
      n_fallback += ref_link(eg, lid, entry, TERM(tid)) == 200
  print(f"  links ok: joins+refs={n_ok}, column definitions={n_def}, term references (fallback)={n_fallback}")

# ============================================================= CONTEXT SET ==
if "contextset" in STEPS:
  print("== context set")
  st, cs = dp("GET", f"{EGP}/{CS_ID}")
  if st == 404:
    st, r = dp("POST", EGP, {
        "displayName": "Cymbal Shipping · Service Performance",
        "description": "Everything an agent or analyst needs to answer service-performance questions for Cymbal Shipping named accounts: the governed Looker model, shipment history in BigQuery, live tracking in Spanner, field evidence from Amazon S3, and the business glossary that defines on-time delivery, the Service Guarantee and revenue at risk.",
        "type": "context-set"}, params={"entryGroupId": CS_ID})
    wait_op(r)
    time.sleep(2)
    print("  created context set:", st, "" if st == 200 else json.dumps(r)[:300])
  rep = f"{DX_EG}/entries/projects/{N}/locations/{LOC}/entryGroups/{CS_ID}"
  md = (
      "# Cymbal Shipping · Service Performance\n\n"
      "Use this context set to answer questions about how well Cymbal Shipping is serving its named accounts.\n\n"
      "**Start with the governed Looker model** *Shipments & Service Performance*. It already applies the business definitions, so every tool reports the same number.\n\n"
      "- **On-Time Delivery Rate** counts only delays within our control. Target 97.5%.\n"
      "- **Revenue at Risk** is the shipping revenue exposed to Service Guarantee refunds.\n"
      "- **Aging Packages** are held at a hub for 6 hours or more, from live tracking in Spanner.\n"
      "- **Temperature Excursions** come from cold chain temperature logs in the Amazon S3 field-evidence bucket.\n\n"
      "**Where the data lives:** shipment history in BigQuery · live package tracking in Spanner · field evidence documents in Amazon S3, read by the lakehouse as an object table · definitions in the Cymbal Shipping Business Glossary.")
  st, r = dp("PATCH", rep, {"name": rep, "aspects": {f"{SYS}.global.overview": {
      "aspectType": f"projects/{SYS}/locations/global/aspectTypes/overview",
      "data": {"content": md, "contentType": "MARKDOWN"}}}}, params={"updateMask": "aspects"})
  print("  representative entry overview:", st, "" if st == 200 else json.dumps(r)[:300])

  ctx = [
      ("ctx-looker-explore", LK_EXPLORE, "Shipments & Service Performance (Looker Explore)",
       "Governed Looker model for service performance. Start here: it applies the official definitions of On-Time Delivery Rate and Revenue at Risk."),
      ("ctx-looker-view-shipments", LK_V("shipments"), "Shipments (Looker view)",
       "Governed measures: Packages, On-Time Delivery Rate, Revenue at Risk, Shipping Revenue."),
      ("ctx-looker-view-live-tracking", LK_V("live_package_tracking"), "Live Tracking (Looker view)",
       "Aging Packages, Hours Held at Hub and Recovery Plan, sourced from Spanner."),
      ("ctx-looker-view-field-evidence", LK_V("exception_evidence"), "Field Evidence (Looker view)",
       "What Happened, Root Cause and Temperature Excursions, from field documents in Amazon S3."),
      ("ctx-bq-shipments", BQ_T("shipments"), "shipments (BigQuery)",
       "Every package picked up for a named account since October 1, 2026, with the promise we made and what happened."),
      ("ctx-bq-customers", BQ_T("customers"), "customers (BigQuery)", "Named accounts with industry, account tier and account director."),
      ("ctx-bq-services", BQ_T("services"), "services (BigQuery)", "Service catalog with commit times and Service Guarantee coverage."),
      ("ctx-bq-hubs", BQ_T("hubs"), "hubs (BigQuery)", "Sort hubs and the Recovery Hub that covers for each."),
      ("ctx-bq-live-tracking", BQ_T("live_package_tracking"), "live_package_tracking (BigQuery, from Spanner)",
       "Live status of every in-network package, read from the Spanner operations database."),
      ("ctx-bq-field-evidence", BQ_T("exception_evidence"), "exception_evidence (BigQuery, from S3 documents)",
       "Facts extracted from field evidence documents: summary, root cause, temperature readings."),
      ("ctx-bq-field-evidence-objects", BQ_T("field_evidence_objects"), "field_evidence_objects (object table)",
       "The field evidence document files themselves, as unstructured data."),
      ("ctx-spanner-package-tracking", SP_T("PackageTracking"), "PackageTracking (Spanner)",
       "Operational system of record for live package tracking, written by hubs and scanners in real time."),
      ("ctx-spanner-hubs", SP_T("Hubs"), "Hubs (Spanner)", "Live operating status of each hub."),
      ("ctx-s3-field-evidence", S3_E(S3_BUCKET), "cymbal-shipping-field-evidence (Amazon S3)",
       "Where drivers and hub teams capture field evidence documents."),
      ("ctx-term-on-time", TERM("on-time-delivery-rate"), "On-Time Delivery Rate (glossary term)",
       "Official definition: only delays within our control count against us. Target 97.5%."),
      ("ctx-term-revenue-at-risk", TERM("revenue-at-risk"), "Revenue at Risk (glossary term)",
       "Shipping revenue exposed to Service Guarantee refunds."),
      ("ctx-term-service-guarantee", TERM("service-guarantee"), "Service Guarantee (glossary term)",
       "Money-back promise on Express and International Priority services."),
      ("ctx-term-aging-package", TERM("aging-package"), "Aging Package (glossary term)", "Held at a hub for 6 hours or more."),
      ("ctx-term-cold-chain", TERM("cold-chain-shipment"), "Cold Chain Shipment (glossary term)",
       "Temperature-controlled healthcare package, 2 to 8 degrees Celsius."),
      ("ctx-term-temperature-excursion", TERM("temperature-excursion"), "Temperature Excursion (glossary term)",
       "Cold chain package recorded above 8 degrees Celsius."),
      ("ctx-term-strategic-account", TERM("strategic-account"), "Strategic Account (glossary term)",
       "Largest named customers with a dedicated account director."),
  ]
  ok = 0
  for cid, target, title, desc in ctx:
    dp("DELETE", f"{EGN}/{CS_ID}/entryLinks/{cid}")
    dp("DELETE", f"{EGN}/{CS_ID}/entries/{cid}")
    st, r = dp("POST", f"{EGP}/{CS_ID}/entries", {
        "entryType": f"projects/{SYS}/locations/global/entryTypes/context",
        "entrySource": {"displayName": title, "description": desc, "system": "Knowledge Catalog", "location": LOC},
        "aspects": {
            f"{SYS}.global.context": {"aspectType": f"projects/{SYS}/locations/global/aspectTypes/context",
                                      "data": {"entry": target}},
            f"{SYS}.global.overview": {"aspectType": f"projects/{SYS}/locations/global/aspectTypes/overview",
                                       "data": {"content": f"**{title}**: {desc}", "contentType": "MARKDOWN"}}}},
        params={"entryId": cid})
    ok += st == 200
    if st != 200:
      print(f"   context entry {cid}: {st} {json.dumps(r)[:240]}")
  print(f"  context entries ok: {ok}/{len(ctx)}")
