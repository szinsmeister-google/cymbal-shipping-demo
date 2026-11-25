"""Knowledge Catalog, second pass: catalog the Looker Data App and the Gemini agent,
link them to the governed Looker explore and glossary, and add them to the context set.

Usage: python3 04_knowledge_catalog/06_catalog_app_and_agent.py [looker_dashboard_id]
Additive and idempotent. Only touches Cymbal Shipping entries.
"""
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import KC_LOCATION as LOC, LOOKER_BASE_URL, LOOKER_INSTANCE_ID, PROJECT_ID as P, PROJECT_NUM as N, api, env

DASH_ID = sys.argv[1] if len(sys.argv) > 1 else env("LOOKER_DATA_APP_DASHBOARD_ID", required=True)
DASH_URL = f"{LOOKER_BASE_URL}/dashboards/{DASH_ID}"

if os.path.isfile("ge_agent.json"):
  AGENT = json.load(open("ge_agent.json", encoding="utf-8"))
  AGENT_NAME = AGENT["name"]
  AGENT_ID = AGENT_NAME.split("/")[-1]
else:
  ENGINE_ID = env("GEMINI_ENGINE_ID", required=True)
  AGENT_ID = env("GEMINI_AGENT_ID", required=True)
  AGENT_NAME = (f"projects/{N}/locations/global/collections/default_collection/"
                f"engines/{ENGINE_ID}/assistants/default_assistant/agents/{AGENT_ID}")

APP_CID = env("GEMINI_APP_CID", "your-gemini-app-cid")
AGENT_URL = f"https://vertexaisearch.cloud.google.com/home/cid/{APP_CID}/r/agent/{AGENT_ID}/session/-"

DP = "https://dataplex.googleapis.com/v1"
SYS = "655216118709"
REF = f"projects/{SYS}/locations/global/entryLinkTypes/reference"
EGN = f"projects/{N}/locations/{LOC}/entryGroups"
EGP = f"projects/{P}/locations/{LOC}/entryGroups"
LK_EG = f"{EGN}/@looker"
DX_EG = f"{EGN}/@dataplex"
INST_RES = f"projects/{P}/locations/{LOC}/instances/{LOOKER_INSTANCE_ID}"
LK_EXPLORE = f"{LK_EG}/entries/looker.googleapis.com/{INST_RES}/lookml_projects/cymbal_shipping/models/cymbal_shipping/explores/shipments"
GLOSSARY_ID = "cymbal-shipping-glossary"
TERM = lambda tid: f"{DX_EG}/entries/projects/{N}/locations/{LOC}/glossaries/{GLOSSARY_ID}/terms/{tid}"
CS_ID = "cymbal-shipping-context-set"
APPS_EG = "cymbal-shipping-apps"
APP_E = lambda e: f"{EGN}/{APPS_EG}/entries/{e}"


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


# ---- custom entry types (project-level)
for type_id, display, desc, system in [
    ("looker-data-app", "Looker Data App",
     "A governed Looker Data App built on LookML explores and Knowledge Catalog definitions.", "Looker Data App"),
    ("gemini-agent", "Gemini Agent",
     "A Gemini agent that answers business questions through governed data connectors.", "Gemini"),
]:
  st, r = dp("POST", f"projects/{P}/locations/global/entryTypes", {
      "displayName": display, "description": desc, "platform": "Google Cloud", "system": system},
      params={"entryTypeId": type_id})
  wait_op(r)
  print(f"entry type {type_id}:", "exists" if st == 409 else st)

# ---- entry group
st, r = dp("POST", EGP, {
    "displayName": "Cymbal Shipping · Apps and Agents",
    "description": "The business-facing experiences built on the governed Cymbal Shipping service performance model: the Looker Data App and the Gemini agent."},
    params={"entryGroupId": APPS_EG})
wait_op(r)
print("entry group:", "exists" if st == 409 else st)


def upsert(entry_id, entry_type, title, desc, system, resource, html):
  name = APP_E(entry_id)
  body = {"name": name, "entryType": f"projects/{P}/locations/global/entryTypes/{entry_type}",
          "entrySource": {"displayName": title, "description": desc, "system": system, "platform": "Google Cloud",
                          "resource": resource, "location": LOC},
          "aspects": overview(html)}
  st, r = dp("POST", f"{EGP}/{APPS_EG}/entries", body, params={"entryId": entry_id})
  if st == 409:
    st, r = dp("PATCH", name, body, params={"updateMask": "entrySource,aspects"})
  print(f"  entry {entry_id}: {st} {'' if st == 200 else json.dumps(r)[:300]}")
  return st


upsert("data-app-service-performance", "looker-data-app",
       "Cymbal Shipping · Service Performance (Looker Data App)",
       "Business-user app for Cymbal Shipping service performance: on-time delivery against the 97.5% target, revenue at risk, packages held at hubs and temperature excursions. Includes a look-up bar and cross-filtering on every chart.",
       "Looker Data App", DASH_URL,
       "<h3>Cymbal Shipping · Service Performance (Looker Data App)</h3>"
       "<p>The everyday view for account directors, customer experience and network operations leaders. "
       "Every number comes from the governed Looker model <em>Shipments &amp; Service Performance</em>, so it matches "
       "what the Gemini agent and any Looker report show.</p>"
       "<ul><li>Look it up: find a customer, hub, service or tracking number, or check a business definition.</li>"
       "<li>Select any bar or point to filter the whole page.</li>"
       "<li>Key numbers: Packages, On-Time Delivery Rate, Revenue at Risk, Aging Packages, Temperature Excursions.</li></ul>"
       f"<p><strong>Open it:</strong> {DASH_URL}</p><p><strong>Owner:</strong> Network Operations, Service Quality team</p>")

upsert("agent-service-desk", "gemini-agent",
       "Cymbal Shipping Service Desk (Gemini agent)",
       "Gemini agent that answers service-performance questions in plain language. It uses the Looker connector, so answers follow the governed definitions of On-Time Delivery Rate and Revenue at Risk.",
       "Gemini", AGENT_NAME,
       "<h3>Cymbal Shipping Service Desk (Gemini agent)</h3>"
       "<p>Ask in plain language how Cymbal Shipping is serving its named accounts. The agent queries the governed Looker "
       "model <em>Shipments &amp; Service Performance</em> through the Looker connector and uses this context set for the "
       "meaning of business terms.</p>"
       "<ul><li>Example: How did on-time delivery for Priority Overnight hold up this week compared with last week, by hub?</li>"
       "<li>Example: Which Strategic healthcare customers have temperature-controlled packages aging at the Memphis SuperHub right now?</li></ul>"
       f"<p><strong>Open it:</strong> {AGENT_URL}</p><p><strong>Owner:</strong> Network Operations, Service Quality team</p>")


def ref_link(eg, link_id, src, dst):
  dp("DELETE", f"{eg}/entryLinks/{link_id}")
  st, r = dp("POST", f"{eg}/entryLinks", {"entryLinkType": REF, "entryReferences": [
      {"name": src, "type": "SOURCE"}, {"name": dst, "type": "TARGET"}]}, params={"entryLinkId": link_id})
  if st != 200:
    print(f"   LINK FAIL {link_id}: {st} {json.dumps(r)[:300]}")
  return st == 200


APPS = f"{EGN}/{APPS_EG}"
links = [
    ("cs-ref-app-explore", APP_E("data-app-service-performance"), LK_EXPLORE),
    ("cs-ref-agent-explore", APP_E("agent-service-desk"), LK_EXPLORE),
    ("cs-ref-app-term-on-time", APP_E("data-app-service-performance"), TERM("on-time-delivery-rate")),
    ("cs-ref-app-term-revenue", APP_E("data-app-service-performance"), TERM("revenue-at-risk")),
    ("cs-ref-agent-term-on-time", APP_E("agent-service-desk"), TERM("on-time-delivery-rate")),
    ("cs-ref-agent-term-revenue", APP_E("agent-service-desk"), TERM("revenue-at-risk")),
]
ok = sum(ref_link(APPS, lid, src, dst) for lid, src, dst in links)
print(f"links ok: {ok}/{len(links)}")

ctx = [
    ("ctx-data-app", APP_E("data-app-service-performance"), "Cymbal Shipping · Service Performance (Looker Data App)",
     "Business-user app on the governed Looker model, with a look-up bar and cross-filtering."),
    ("ctx-agent", APP_E("agent-service-desk"), "Cymbal Shipping Service Desk (Gemini agent)",
     "Plain-language answers through the Looker connector, using the governed definitions."),
]
ok = 0
for cid, target, title, desc in ctx:
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
    print(f"   context entry {cid}: {st} {json.dumps(r)[:300]}")
print(f"context entries ok: {ok}/{len(ctx)}")

st, r = dp("GET", f"{EGP}/{CS_ID}/entries", params={"pageSize": 100})
print("context set now has", len(r.get("entries", [])) if st == 200 else st, "entries")
