"""Stand up the operational + unstructured parts of the Cymbal Shipping stack.

1. Cloud Spanner instance `cymbal-shipping-ops` (100 processing units, Enterprise)
   with database `cymbal_shipping_ops`:
   Hubs (live operating status), PackageTracking (every in-network package),
   RecoveryLanes, and the ShippingNetwork Property Graph.
2. Optional BigQuery Spanner external dataset federation (`federate` step).
3. Field-evidence object store: GCS bucket with one text document per
   `exception_evidence` row, plus an external object table (`field_evidence_objects`)
   via a BigQuery cloud-resource connection.

Usage: python3 01_data/03_spanner_and_lake.py [spanner] [federate] [gcs]
Idempotent. Only creates demo-scoped resources.
"""
import concurrent.futures
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import BQ_DATASET as DS, BQ_LOCATION as LOC, PROJECT_ID as P, PROJECT_NUM, api, bq, bq_rows, env, token

INSTANCE = env("SPANNER_INSTANCE", "cymbal-shipping-ops")
DB = env("SPANNER_DATABASE", "cymbal_shipping_ops")
SPANNER_CONFIG = env("SPANNER_CONFIG", f"regional-{LOC}")
BUCKET = env("GCS_EVIDENCE_BUCKET", f"cymbal-shipping-field-evidence-{PROJECT_NUM}")
CONN = env("BQ_LAKE_CONNECTION", "cymbal_shipping_lake")
SP = "https://spanner.googleapis.com/v1"
INST = f"projects/{P}/instances/{INSTANCE}"
DBP = f"{INST}/databases/{DB}"

STEPS = sys.argv[1:] or ["spanner", "gcs"]


def wait_op(name, base=SP, timeout_s=300):
  t0 = time.time()
  while time.time() - t0 < timeout_s:
    st, op = api("GET", f"{base}/{name}")
    if isinstance(op, dict) and op.get("done"):
      if "error" in op:
        raise RuntimeError(op["error"])
      return op
    time.sleep(2)
  raise TimeoutError(name)


# =============================================================== SPANNER ====
DDL = [
    """CREATE TABLE Hubs (
      hub_code STRING(8) NOT NULL,
      hub_name STRING(64),
      city STRING(64),
      state STRING(2),
      region STRING(32),
      hub_type STRING(32),
      backup_hub_code STRING(8),
      sort_status STRING(32),
      status_note STRING(400),
      packages_held INT64,
      cold_chain_packages_held INT64,
      updated_at TIMESTAMP
    ) PRIMARY KEY (hub_code)""",
    """CREATE TABLE PackageTracking (
      tracking_number STRING(16) NOT NULL,
      customer_id STRING(16),
      service_code STRING(4),
      current_hub_code STRING(8),
      package_status STRING(32),
      last_scan_type STRING(64),
      last_scan_ts TIMESTAMP,
      hub_dwell_hours FLOAT64,
      is_aging BOOL,
      committed_delivery_ts TIMESTAMP,
      estimated_delivery_ts TIMESTAMP,
      recovery_plan STRING(160),
      is_cold_chain BOOL,
      updated_at TIMESTAMP
    ) PRIMARY KEY (tracking_number)""",
    "CREATE INDEX PackageTrackingByHub ON PackageTracking (current_hub_code, package_status)",
    """CREATE TABLE RecoveryLanes (
      from_hub_code STRING(8) NOT NULL,
      to_hub_code STRING(8) NOT NULL,
      lane_status STRING(32),
      next_departure_local STRING(32),
      packages_diverted INT64
    ) PRIMARY KEY (from_hub_code, to_hub_code)""",
    """CREATE PROPERTY GRAPH ShippingNetwork
      NODE TABLES (
        Hubs KEY (hub_code) LABEL Hub
          PROPERTIES (hub_code, hub_name, city, state, region, hub_type, sort_status, status_note, packages_held, cold_chain_packages_held)
      )
      EDGE TABLES (
        RecoveryLanes KEY (from_hub_code, to_hub_code)
          SOURCE KEY (from_hub_code) REFERENCES Hubs (hub_code)
          DESTINATION KEY (to_hub_code) REFERENCES Hubs (hub_code)
          LABEL RECOVERS_VIA PROPERTIES (from_hub_code, to_hub_code, lane_status, next_departure_local, packages_diverted)
      )""",
]

if "spanner" in STEPS:
  st, inst = api("GET", f"{SP}/{INST}")
  if st == 404:
    st, op = api("POST", f"{SP}/projects/{P}/instances", {
        "instanceId": INSTANCE,
        "instance": {
            "config": f"projects/{P}/instanceConfigs/{SPANNER_CONFIG}",
            "displayName": "Cymbal Shipping Ops",
            "processingUnits": 100,
            "edition": "ENTERPRISE",
            "labels": {"demo": "cymbal-shipping"},
        }})
    print("create spanner instance:", st, op.get("name", op) if isinstance(op, dict) else op)
    if st != 200:
      sys.exit(1)
    wait_op(op["name"], timeout_s=600)
    print("spanner instance ready")
  else:
    print("spanner instance exists:", inst.get("state"), inst.get("processingUnits"), inst.get("edition"))

  st, db = api("GET", f"{SP}/{DBP}")
  if st == 404:
    st, op = api("POST", f"{SP}/{INST}/databases", {
        "createStatement": f"CREATE DATABASE `{DB}`", "extraStatements": DDL})
    print("create spanner db:", st, op.get("name", op) if isinstance(op, dict) else op)
    if st != 200:
      sys.exit(1)
    wait_op(op["name"])
    print("spanner db ready")
  else:
    print("spanner db exists:", db.get("state"))

  st, sess = api("POST", f"{SP}/{DBP}/sessions", {})
  sess_name = sess["name"]

  def commit(mutations):
    st, r = api("POST", f"{SP}/{sess_name}:commit",
                {"singleUseTransaction": {"readWrite": {}}, "mutations": mutations}, timeout=300)
    if st != 200:
      raise RuntimeError(f"spanner commit {st}: {json.dumps(r)[:500]}")
    return r

  TS = "%Y-%m-%dT%H:%M:%SZ"
  # ---- Hubs with live operating status (derived from the tracking data)
  hubs = bq_rows(f"""
    SELECT h.hub_code, h.hub_name, h.city, h.state, h.region, h.hub_type, h.backup_hub_code,
           COUNTIF(t.is_aging) AS held, COUNTIF(t.is_aging AND t.is_cold_chain) AS cold_held
    FROM `{P}.{DS}.hubs` h
    LEFT JOIN `{P}.{DS}.live_package_tracking` t ON t.current_hub_code = h.hub_code
    GROUP BY 1,2,3,4,5,6,7 ORDER BY 1""", LOC)
  rows = []
  for h in hubs:
    if h["hub_code"] == "MEM":
      status = "Recovering"
      note = ("Main sort line (Matrix C, Belt 7) stopped 11:52 PM CT on Nov 9 after the sort controller lost its "
              "connection to the scan tunnel. Line restored 6:40 AM CT Nov 10 and ran at reduced speed through the "
              "Nov 10 night sort. Backlog is being cleared tonight through the Indianapolis Air Hub and the next Memphis sort.")
    else:
      status = "Normal"
      note = "Sorting on schedule."
    rows.append([h["hub_code"], h["hub_name"], h["city"], h["state"], h["region"], h["hub_type"], h["backup_hub_code"],
                 status, note, str(h["held"]), str(h["cold_held"]), "2026-11-11T13:00:00Z"])
  commit([{"insertOrUpdate": {"table": "Hubs", "columns": [
      "hub_code", "hub_name", "city", "state", "region", "hub_type", "backup_hub_code", "sort_status",
      "status_note", "packages_held", "cold_chain_packages_held", "updated_at"], "values": rows}}])
  print("Hubs rows:", len(rows))

  # ---- Recovery lanes (each hub -> its backup hub)
  div = bq_rows(f"""
    SELECT COUNTIF(recovery_plan LIKE '%Indianapolis%') AS n FROM `{P}.{DS}.live_package_tracking`
    WHERE current_hub_code = 'MEM' AND is_aging""", LOC)[0]["n"]
  lanes = []
  for h in hubs:
    if not h["backup_hub_code"]:
      continue
    active = h["hub_code"] == "MEM"
    lanes.append([h["hub_code"], h["backup_hub_code"], "Active – diverting volume" if active else "Standby",
                  "Tonight 10:40 PM CT" if active else "On request", str(div if active else 0)])
  commit([{"insertOrUpdate": {"table": "RecoveryLanes", "columns": [
      "from_hub_code", "to_hub_code", "lane_status", "next_departure_local", "packages_diverted"], "values": lanes}}])
  print("RecoveryLanes rows:", len(lanes))

  # ---- PackageTracking (every in-network package), paged out of BigQuery
  cols = ["tracking_number", "customer_id", "service_code", "current_hub_code", "package_status", "last_scan_type",
          "last_scan_ts", "hub_dwell_hours", "is_aging", "committed_delivery_ts", "estimated_delivery_ts",
          "recovery_plan", "is_cold_chain", "updated_at"]
  sql = f"""
    SELECT tracking_number, customer_id, service_code, current_hub_code, package_status, last_scan_type,
           FORMAT_TIMESTAMP('{TS}', last_scan_ts) AS last_scan_ts, hub_dwell_hours, is_aging,
           FORMAT_TIMESTAMP('{TS}', committed_delivery_ts) AS committed_delivery_ts,
           FORMAT_TIMESTAMP('{TS}', estimated_delivery_ts) AS estimated_delivery_ts,
           recovery_plan, is_cold_chain, FORMAT_TIMESTAMP('{TS}', updated_at) AS updated_at
    FROM `{P}.{DS}.live_package_tracking` ORDER BY tracking_number"""
  st, job = api("POST", f"https://bigquery.googleapis.com/bigquery/v2/projects/{P}/queries",
                {"query": sql, "useLegacySql": False, "location": LOC, "timeoutMs": 120000, "maxResults": 5000})
  if st != 200:
    sys.exit(f"bq query failed: {job}")
  job_id = job["jobReference"]["jobId"]
  total = int(job.get("totalRows", 0))
  written = 0
  page = job
  while True:
    batch = []
    for r in page.get("rows", []):
      v = [c.get("v") for c in r["f"]]
      batch.append([v[0], v[1], v[2], v[3], v[4], v[5], v[6], float(v[7]) if v[7] is not None else None,
                    v[8] == "true", v[9], v[10], v[11], v[12] == "true", v[13]])
    if batch:
      commit([{"insertOrUpdate": {"table": "PackageTracking", "columns": cols, "values": batch}}])
      written += len(batch)
      print(f"  PackageTracking {written}/{total}", flush=True)
    tok = page.get("pageToken")
    if not tok:
      break
    st, page = api("GET", f"https://bigquery.googleapis.com/bigquery/v2/projects/{P}/queries/{job_id}",
                   params={"location": LOC, "maxResults": 5000, "pageToken": tok})
    if st != 200:
      sys.exit(f"bq page failed: {page}")

  st, res = api("POST", f"{SP}/{sess_name}:executeSql", {"sql": """
    SELECT h.hub_name, h.sort_status, COUNT(t.tracking_number) AS aging, COUNTIF(t.is_cold_chain) AS cold
    FROM Hubs h JOIN PackageTracking t ON t.current_hub_code = h.hub_code
    WHERE t.is_aging GROUP BY 1, 2 ORDER BY aging DESC LIMIT 5"""})
  print("spanner check:", st, res.get("rows") if isinstance(res, dict) else res)
  st, res = api("POST", f"{SP}/{sess_name}:executeSql", {"sql": "SELECT COUNT(*) FROM PackageTracking"})
  print("spanner PackageTracking rows:", res.get("rows") if isinstance(res, dict) else res)
  api("DELETE", f"{SP}/{sess_name}")

if "federate" in STEPS:
  # Spanner external dataset: BigQuery reads the live Spanner tables in place (no copy).
  ext = "cymbal_shipping_ops_spanner"
  try:
    bq(f"""CREATE EXTERNAL SCHEMA IF NOT EXISTS `{P}.{ext}`
    OPTIONS (
      external_source = 'google-cloudspanner:/projects/{P}/instances/{INSTANCE}/databases/{DB}',
      location = '{LOC}',
      description = 'Live, read-in-place view of the Cymbal Shipping operations database in Spanner (hubs, live package tracking, recovery lanes). Nothing is copied: BigQuery queries Spanner directly.')""", location=LOC)
    print("external dataset ready:", ext)
    rows = bq_rows(f"SELECT COUNT(*) AS n, COUNTIF(is_aging) AS aging FROM `{P}.{ext}.PackageTracking`", LOC)
    print("federated read of Spanner PackageTracking:", rows)
    n = int(rows[0]["n"])
    if n > 0:
      bq(f"TRUNCATE TABLE `{P}.{DS}.live_package_tracking`", location=LOC)
      bq(f"""INSERT INTO `{P}.{DS}.live_package_tracking`
        (tracking_number, customer_id, service_code, current_hub_code, package_status, last_scan_type, last_scan_ts,
         hub_dwell_hours, is_aging, committed_delivery_ts, estimated_delivery_ts, recovery_plan, is_cold_chain, updated_at)
      SELECT tracking_number, customer_id, service_code, current_hub_code, package_status, last_scan_type, last_scan_ts,
         hub_dwell_hours, is_aging, committed_delivery_ts, estimated_delivery_ts, recovery_plan, is_cold_chain, updated_at
      FROM `{P}.{ext}.PackageTracking`""", location=LOC)
      print("replica refreshed from Spanner:", bq_rows(f"SELECT COUNT(*) AS n, COUNTIF(is_aging) AS aging FROM `{P}.{DS}.live_package_tracking`", LOC))
  except RuntimeError as e:
    print("FEDERATION NOT AVAILABLE (replica keeps its seeded copy):", str(e)[:600])

# =================================================================== GCS ====
if "gcs" in STEPS:
  st, b = api("GET", f"https://storage.googleapis.com/storage/v1/b/{BUCKET}")
  if st == 404:
    st, b = api("POST", "https://storage.googleapis.com/storage/v1/b", {
        "name": BUCKET, "location": LOC.upper(), "storageClass": "STANDARD",
        "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True},
                             "publicAccessPrevention": "enforced"},
        "labels": {"demo": "cymbal-shipping"}},
        params={"project": P})
    print("create bucket:", st, b.get("name") if isinstance(b, dict) else b)
    if st != 200:
      sys.exit(1)
  else:
    print("bucket exists:", st)

  docs = bq_rows(f"SELECT document_uri, document_text FROM `{P}.{DS}.exception_evidence`", LOC)
  print("documents to upload:", len(docs))
  tok = token()

  def upload(d):
    name = d["document_uri"].split(f"gs://{BUCKET}/", 1)[1]
    url = (f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o?uploadType=media&name="
           + urllib.parse.quote(name, safe=""))
    req = urllib.request.Request(url, data=d["document_text"].encode("utf-8"), method="POST", headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "text/plain; charset=utf-8",
        "X-Goog-User-Project": P})
    for attempt in range(4):
      try:
        with urllib.request.urlopen(req, timeout=60) as r:
          return r.status
      except urllib.error.HTTPError as e:
        if e.code in (429, 500, 502, 503) and attempt < 3:
          time.sleep(1.5 * (attempt + 1))
          continue
        return e.code
      except Exception:  # noqa: BLE001  (network hiccup -> retry)
        time.sleep(1.5 * (attempt + 1))
    return -1

  with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    codes = list(ex.map(upload, docs))
  ok = sum(1 for c in codes if c == 200)
  print(f"uploaded {ok}/{len(docs)}; other codes: {sorted(set(c for c in codes if c != 200))}")

  # BigQuery cloud-resource connection for the object table
  cbase = f"https://bigqueryconnection.googleapis.com/v1/projects/{P}/locations/{LOC}/connections"
  st, c = api("GET", f"{cbase}/{CONN}")
  if st == 404:
    st, c = api("POST", cbase, {"friendlyName": "Cymbal Shipping field-evidence lake",
                                "description": "Lets BigQuery read Cymbal Shipping field evidence documents as an object table.",
                                "cloudResource": {}}, params={"connectionId": CONN})
    print("create connection:", st)
  sa = c.get("cloudResource", {}).get("serviceAccountId") if isinstance(c, dict) else None
  print("connection service account present:", bool(sa))
  if not sa:
    sys.exit(f"no connection SA: {c}")

  # least privilege: object viewer on THIS bucket only
  st, pol = api("GET", f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/iam", params={"optionsRequestedPolicyVersion": 3})
  member = f"serviceAccount:{sa}"
  bindings = pol.get("bindings", [])
  if not any(b["role"] == "roles/storage.objectViewer" and member in b.get("members", []) for b in bindings):
    bindings.append({"role": "roles/storage.objectViewer", "members": [member]})
    pol["bindings"] = bindings
    st, r = api("PUT", f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/iam", pol)
    print("grant bucket objectViewer to connection SA:", st)
  else:
    print("bucket IAM already granted")

  ddl = f"""
  CREATE OR REPLACE EXTERNAL TABLE `{P}.{DS}.field_evidence_objects`
  WITH CONNECTION `{P}.{LOC}.{CONN}`
  OPTIONS (
    object_metadata = 'SIMPLE',
    uris = ['gs://{BUCKET}/field-evidence/*'],
    description = 'Object table over the Cymbal Shipping field-evidence documents: hub delay notices, cold chain temperature logs, driver damage reports and customs notices. One row per file. Drivers and hub teams capture the originals into the Cymbal Shipping field-evidence bucket in Amazon S3; this table reads the lakehouse landing copy so the documents can be searched and summarized with SQL and AI next to shipment data.'
  )"""
  for attempt in range(8):
    try:
      bq(ddl, location=LOC)
      print("object table created")
      break
    except RuntimeError as e:
      print("  object table not ready yet:", str(e)[:200])
      time.sleep(15)
  for attempt in range(6):
    try:
      rows = bq_rows(f"SELECT COUNT(*) AS files, SUM(size) AS bytes, MIN(updated) AS first_seen FROM `{P}.{DS}.field_evidence_objects`", LOC)
      print("object table check:", rows)
      break
    except RuntimeError as e:
      print("  object table query not ready:", str(e)[:200])
      time.sleep(15)
