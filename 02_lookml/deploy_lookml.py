"""Create (or update) the `cymbal_shipping` LookML project on your Looker
instance, validate it, commit, and deploy it to production.

Reads the `.lkml` files directly from `./cymbal_shipping/`, substitutes
`YOUR_GCP_PROJECT_ID` and `default_bigquery_connection` from `.env`,
and pushes via the Looker REST API (dev workspace).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import BQ_DATASET, PROJECT_ID, env, lk

PROJECT = "cymbal_shipping"
MODEL = "cymbal_shipping"
DB_CONNECTION = env("LOOKER_DB_CONNECTION", "default_bigquery_connection")
LOCAL = pathlib.Path(__file__).resolve().parent / PROJECT
DEPLOY = "--no-deploy" not in sys.argv


def load_lookml_files() -> dict[str, str]:
  """Read all LookML files under `./cymbal_shipping/` and apply env substitutions."""
  files = {}
  for path in sorted(LOCAL.rglob("*.lkml")):
    rel = path.relative_to(LOCAL).as_posix()
    content = path.read_text(encoding="utf-8")
    if rel == "manifest.lkml":
      content = content.replace("YOUR_GCP_PROJECT_ID", PROJECT_ID)
      content = content.replace('value: "cymbal_shipping"', f'value: "{BQ_DATASET}"')
    elif rel == "cymbal_shipping.model.lkml":
      content = content.replace('connection: "default_bigquery_connection"', f'connection: "{DB_CONNECTION}"')
    files[rel] = content
  return files


FILES = load_lookml_files()
print(f"loaded {len(FILES)} LookML files from {LOCAL}")
print("rest -> dev:", lk("PATCH", "/session", {"workspace_id": "dev"})[0])

# project (bare git repo hosted on the Looker instance)
st, p = lk("GET", f"/projects/{PROJECT}")
if st == 404:
  st, p = lk("POST", "/projects", {"name": PROJECT})
  print("create project:", st)
  if st != 200:
    sys.exit(f"could not create project: {p}")
if not p.get("git_remote_url"):
  st, p = lk("PATCH", f"/projects/{PROJECT}", {"git_service_name": "bare"})
  print("bare git:", st, p.get("git_remote_url") if isinstance(p, dict) else p)

# files
st, files = lk("GET", f"/projects/{PROJECT}/files")
existing = [f.get("path") for f in files] if isinstance(files, list) else []
if not any(e.startswith("views/") for e in existing):
  lk("POST", f"/projects/{PROJECT}/directories", {"path": "views"})
for rel, content in FILES.items():
  method = "PUT" if rel in existing else "POST"
  st, r = lk(method, f"/projects/{PROJECT}/files", {"path": rel, "content": content})
  if st != 200 and method == "POST":
    st, r = lk("PUT", f"/projects/{PROJECT}/files", {"path": rel, "content": content})
  print(f"  {method:4s} {rel}: {st} {'' if st == 200 else json.dumps(r)[:200]}")

# model configuration
st, m = lk("GET", f"/lookml_models/{MODEL}")
body = {"name": MODEL, "project_name": PROJECT, "allowed_db_connection_names": [DB_CONNECTION]}
if st == 404:
  st, m = lk("POST", "/lookml_models", body)
  print("create model config:", st)
elif m.get("project_name") != PROJECT:
  sys.exit(f"model name {MODEL} already belongs to project {m.get('project_name')}")

# validate
st, v = lk("POST", f"/projects/{PROJECT}/validate", timeout=300)
errs = (v.get("errors") or []) if isinstance(v, dict) else []
print("validate:", st, "issues:", len(errs))
for e in errs[:40]:
  print("   ", e.get("severity"), e.get("file_path"), e.get("line_number"), "-", (e.get("message") or "")[:240])
if st != 200 or [e for e in errs if e.get("severity") == "error"]:
  sys.exit("LookML has errors; not deploying")

# dev-mode smoke query (governed vs raw on-time, revenue at risk)
st, rows = lk("POST", "/queries/run/json", {
    "model": MODEL, "view": "shipments",
    "fields": ["shipments.reporting_period", "shipments.package_count", "shipments.on_time_delivery_rate",
               "shipments.raw_on_time_rate", "shipments.revenue_at_risk", "live_package_tracking.aging_packages",
               "exception_evidence.temperature_excursions"],
    "sorts": ["shipments.reporting_period"], "limit": "10"}, timeout=300)
print("dev smoke query:", st)
print(json.dumps(rows, indent=1)[:1600])
if st != 200 or not isinstance(rows, list) or (rows and "looker_error" in rows[0]):
  sys.exit("smoke query failed; not deploying")

if not DEPLOY:
  sys.exit(0)

# commit + deploy
st, br = lk("GET", f"/projects/{PROJECT}/git_branch")
print("branch:", st, {k: br.get(k) for k in ("name", "ahead_count", "behind_count", "commit_at", "message", "error")} if isinstance(br, dict) else br)
for path, body in [
    (f"/projects/{PROJECT}/commit", {"message": "Cymbal Shipping service performance model"}),
    (f"/projects/{PROJECT}/git/commit", {"message": "Cymbal Shipping service performance model"}),
    (f"/projects/{PROJECT}/git_commit", {"message": "Cymbal Shipping service performance model"}),
]:
  st, r = lk("POST", path, body)
  print("commit try", path, "->", st, json.dumps(r)[:200])
  if st in (200, 201, 204):
    break
st, d = lk("POST", f"/projects/{PROJECT}/deploy_to_production", timeout=300)
print("deploy_to_production:", st, json.dumps(d)[:300])

lk("PATCH", "/session", {"workspace_id": "production"})
st, m = lk("GET", f"/lookml_models/{MODEL}")
print("production model explores:", [e.get("name") for e in (m.get("explores") or [])] if isinstance(m, dict) else m)
st, rows = lk("POST", "/queries/run/json", {
    "model": MODEL, "view": "shipments",
    "fields": ["shipments.reporting_period", "shipments.package_count", "shipments.on_time_delivery_rate"],
    "limit": "5"}, timeout=300)
print("production smoke query:", st, json.dumps(rows)[:500])
