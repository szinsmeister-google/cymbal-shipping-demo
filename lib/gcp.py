"""Shared helpers for the Cymbal Shipping demo-as-code build (GCP REST + Looker API).

Reads all configuration from environment variables (and optionally a `.env` file
at the repository root). Never prints credentials. Tokens are fetched lazily and
cached in-process.
"""
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def _load_dotenv() -> None:
  """Load key=value pairs from repo-root `.env` without overwriting real env vars."""
  repo_root = pathlib.Path(__file__).resolve().parent.parent
  env_path = repo_root / ".env"
  if not env_path.is_file():
    return
  for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key and key not in os.environ:
      os.environ[key] = value


_load_dotenv()


def env(name: str, default: str | None = None, required: bool = False) -> str:
  """Read an environment variable with optional default or required check."""
  val = os.environ.get(name, default)
  if required and not val:
    raise RuntimeError(
        f"Missing required environment variable `{name}`. "
        "Copy `.env.example` to `.env` and set your project values."
    )
  return val or ""


PROJECT_ID = env("GCP_PROJECT_ID", "your-gcp-project-id")
PROJECT_NUM = env("GCP_PROJECT_NUMBER", "123456789012")
BQ_DATASET = env("BQ_DATASET", "cymbal_shipping")
BQ_LOCATION = env("BQ_LOCATION", "us-east1")
KC_LOCATION = env("KC_LOCATION", "us-east1")
GCLOUD = env("GCLOUD_BIN", "gcloud")

LOOKER_BASE_URL = env("LOOKER_BASE_URL", "https://your-looker-instance.cloud.looker.com").rstrip("/")
LOOKER_INSTANCE_ID = env("LOOKER_INSTANCE_ID", "your-looker-instance-id")
LOOKER_CLIENT_ID = env("LOOKER_CLIENT_ID", "")
LOOKER_CLIENT_SECRET = env("LOOKER_CLIENT_SECRET", "")
LOOKER_CONFIG_PATH = env("LOOKER_CONFIG_PATH", "")

_tok = {"v": None, "t": 0.0}


def token() -> str:
  if _tok["v"] and time.time() - _tok["t"] < 1500:
    return _tok["v"]
  _tok["v"] = subprocess.check_output(
      [GCLOUD, "auth", "print-access-token"],
      text=True,
      stderr=subprocess.DEVNULL,
  ).strip()
  _tok["t"] = time.time()
  return _tok["v"]


def api(method, url, body=None, params=None, timeout=120, user_project=True,
        extra_headers=None):
  """Call a Google Cloud REST API. Returns (status_code, parsed_json_or_text)."""
  if params:
    url = f"{url}?{urllib.parse.urlencode(params)}"
  headers = {
      "Authorization": f"Bearer {token()}",
      "Content-Type": "application/json",
  }
  if user_project and PROJECT_ID:
    headers["X-Goog-User-Project"] = PROJECT_ID
  if extra_headers:
    headers.update(extra_headers)
  data = json.dumps(body).encode("utf-8") if body is not None else None
  req = urllib.request.Request(url, data=data, headers=headers, method=method)
  try:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      raw = resp.read().decode("utf-8")
      try:
        return resp.status, (json.loads(raw) if raw else {})
      except json.JSONDecodeError:
        return resp.status, raw
  except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", "replace")
    try:
      return e.code, json.loads(raw)
    except json.JSONDecodeError:
      return e.code, raw


# ---------------------------------------------------------------- BigQuery --
def bq(sql, location=None, timeout_ms=120000, dry_run=False):
  loc = location or BQ_LOCATION
  st, res = api(
      "POST",
      f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT_ID}/queries",
      {
          "query": sql,
          "useLegacySql": False,
          "location": loc,
          "timeoutMs": timeout_ms,
          "dryRun": dry_run,
      },
  )
  if st != 200 or (isinstance(res, dict) and res.get("errors")):
    raise RuntimeError(f"BQ error ({st}): {json.dumps(res)[:1500]}")
  return res


def bq_rows(sql, location=None):
  res = bq(sql, location or BQ_LOCATION)
  fields = [f["name"] for f in res.get("schema", {}).get("fields", [])]
  return [
      dict(zip(fields, [c.get("v") for c in r["f"]]))
      for r in res.get("rows", [])
  ]


# ------------------------------------------------------------------ Looker --
_lk = {"tok": None, "base": None, "t": 0.0}


def _looker_credentials() -> tuple[str, str, str]:
  """Resolve Looker base URL and API credentials from env vars or optional JSON file."""
  base = LOOKER_BASE_URL
  cid = LOOKER_CLIENT_ID
  csec = LOOKER_CLIENT_SECRET
  if (not cid or not csec) and LOOKER_CONFIG_PATH and os.path.isfile(LOOKER_CONFIG_PATH):
    with open(LOOKER_CONFIG_PATH, encoding="utf-8") as fh:
      cfg = json.load(fh)
    base = cfg.get("base_url", base).rstrip("/")
    cid = cid or cfg.get("client_id", "")
    csec = csec or cfg.get("client_secret", "")
  if not base or not cid or not csec:
    raise RuntimeError(
        "Missing Looker credentials. Set LOOKER_BASE_URL, LOOKER_CLIENT_ID, and "
        "LOOKER_CLIENT_SECRET in `.env` (or set LOOKER_CONFIG_PATH)."
    )
  return base, cid, csec


def looker_login():
  if _lk["tok"] and time.time() - _lk["t"] < 1500:
    return _lk["base"], _lk["tok"]
  base, cid, csec = _looker_credentials()
  data = urllib.parse.urlencode({"client_id": cid, "client_secret": csec}).encode()
  req = urllib.request.Request(f"{base}/api/4.0/login", data=data, method="POST")
  _lk["tok"] = json.loads(urllib.request.urlopen(req, timeout=60).read())["access_token"]
  _lk["base"] = base
  _lk["t"] = time.time()
  return base, _lk["tok"]


def lk(method, path, body=None, params=None, timeout=120, raw_body=None,
       content_type="application/json"):
  base, tok = looker_login()
  url = f"{base}/api/4.0{path}"
  if params:
    url = f"{url}?{urllib.parse.urlencode(params)}"
  if raw_body is not None:
    data = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
  else:
    data = json.dumps(body).encode("utf-8") if body is not None else None
  req = urllib.request.Request(
      url,
      data=data,
      method=method,
      headers={"Authorization": f"token {tok}", "Content-Type": content_type},
  )
  try:
    with urllib.request.urlopen(req, timeout=timeout) as r:
      raw = r.read().decode("utf-8")
      try:
        return r.status, (json.loads(raw) if raw else {})
      except json.JSONDecodeError:
        return r.status, raw
  except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", "replace")
    try:
      return e.code, json.loads(raw)
    except json.JSONDecodeError:
      return e.code, raw
