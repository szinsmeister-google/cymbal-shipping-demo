"""Knowledge Catalog, third pass: the native Looker environment for Cymbal Shipping.

Looker dashboards, tiles and Looks are ingested natively into entry group @looker, and every tile is
linked to the explore it queries. This script waits for those entries, then:
  1. adds plain-language overviews to the dashboard, its tiles and the Looks
  2. links tiles to the glossary terms they measure, and ties the Data App into the same graph
  3. adds the dashboard and the Looks to the context set (bringing it to 26 total entries)

Usage: python3 04_knowledge_catalog/08_catalog_looker_environment.py [--no-wait]
Additive and idempotent. Only touches Cymbal Shipping entries.
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import KC_LOCATION as LOC, LOOKER_BASE_URL as BASE, LOOKER_INSTANCE_ID, PROJECT_ID as P, PROJECT_NUM as N, api, env

with open("native_looker_content.json", encoding="utf-8") as fh:
  C = json.load(fh)
DASH = C["dashboard_id"]
ELEMENTS = [(eid, title) for eid, typ, title in C["elements"] if typ == "vis"]
LOOKS = C["looks"]
APP_DASH = env("LOOKER_DATA_APP_DASHBOARD_ID", "")

DP = "https://dataplex.googleapis.com/v1"
SYS = "655216118709"
REF = f"projects/{SYS}/locations/global/entryLinkTypes/reference"
EGN = f"projects/{N}/locations/{LOC}/entryGroups"
EGP = f"projects/{P}/locations/{LOC}/entryGroups"
LK_EG = f"{EGN}/@looker"
DX_EG = f"{EGN}/@dataplex"
INST = f"looker.googleapis.com/projects/{P}/locations/{LOC}/instances/{LOOKER_INSTANCE_ID}"
LK = lambda rel: f"{LK_EG}/entries/{INST}/{rel}"
EXPLORE = LK("lookml_projects/cymbal_shipping/models/cymbal_shipping/explores/shipments")
TERM = lambda tid: f"{DX_EG}/entries/projects/{N}/locations/{LOC}/glossaries/cymbal-shipping-glossary/terms/{tid}"
CS_ID = "cymbal-shipping-context-set"
APPS = f"{EGN}/cymbal-shipping-apps"
DATA_APP = f"{APPS}/entries/data-app-service-performance"


def dp(method, path, body=None, params=None):
  for attempt in range(5):
    st, r = api(method, f"{DP}/{path}", body, params=params)
    if st in (429, 503) and attempt < 4:
      time.sleep(2 * (attempt + 1))
      continue
    return st, r
  return st, r


def exists(name):
  return dp("GET", name)[0] == 200


def set_overview(entry, html):
  return dp("PATCH", entry, {"name": entry, "aspects": {f"{SYS}.global.overview": {
      "aspectType": f"projects/{SYS}/locations/global/aspectTypes/overview", "data": {"content": html}}}},
            params={"updateMask": "aspects", "aspectKeys": f"{SYS}.global.overview"})[0]


def ref_link(eg, link_id, src, dst):
  dp("DELETE", f"{eg}/entryLinks/{link_id}")
  st, r = dp("POST", f"{eg}/entryLinks", {"entryLinkType": REF, "entryReferences": [
      {"name": src, "type": "SOURCE"}, {"name": dst, "type": "TARGET"}]}, params={"entryLinkId": link_id})
  if st not in (200, 409):
    print(f"   LINK FAIL {link_id}: {st} {json.dumps(r)[:260]}")
  return st in (200, 409)


def links_of(entry):
  st, r = dp("GET", f"projects/{N}/locations/{LOC}:lookupEntryLinks", params={"entry": entry, "pageSize": 100})
  return r.get("entryLinks", []) if st == 200 else []


# ------------------------------------------------------------ wait for sync --
wanted = {f"dashboard {DASH}": LK(f"dashboards/{DASH}")}
for eid, title in ELEMENTS:
  wanted[f"tile {title}"] = LK(f"dashboards/{DASH}/dashboard_elements/{eid}")
for lid, title in LOOKS:
  wanted[f"look {lid}"] = LK(f"looks/{lid}")
deadline = time.time() + (0 if "--no-wait" in sys.argv else 600)
while True:
  missing = [k for k, v in wanted.items() if not exists(v)]
  print(f"native entries present: {len(wanted) - len(missing)}/{len(wanted)}" + (f" | waiting for: {missing[:4]}" if missing else ""))
  if not missing or time.time() > deadline:
    break
  time.sleep(30)
present = {k: v for k, v in wanted.items() if k not in missing}

# ---------------------------------------------------------------- overviews --
TILE_NOTES = {
    "Packages": ("Number of packages picked up this week. Also called volume.", None),
    "On-Time Delivery Rate": ("Official service KPI shown against the 97.5% company target. Only delays within our control count against us.", "on-time-delivery-rate"),
    "Revenue at Risk": ("Shipping revenue exposed to Service Guarantee refunds this week.", "revenue-at-risk"),
    "Refund-Eligible Packages": ("Guaranteed-service packages that are late, or going to be late, for a reason within our control.", "service-guarantee"),
    "Aging Packages": ("Packages held at a hub for 6 hours or more right now, from live tracking in Spanner.", "aging-package"),
    "Temperature Excursions": ("Cold chain packages recorded above 8 degrees Celsius, from field temperature logs.", "temperature-excursion"),
    "On-Time Delivery Rate by Ship Day": ("Daily On-Time Delivery Rate since October 1, next to the raw rate that counts every late package.", "on-time-delivery-rate"),
    "On-Time Delivery Rate by Hub": ("On-Time Delivery Rate for each hub this week, against the 97.5% target.", "on-time-delivery-rate"),
    "Revenue at Risk by Customer": ("The ten customers with the most shipping revenue exposed to Service Guarantee refunds.", "revenue-at-risk"),
    "Revenue at Risk by Service": ("Revenue at Risk split by the service the customer bought.", "revenue-at-risk"),
    "Delayed Packages by Reason": ("Delayed packages by delivery exception reason, split into delays within and outside our control.", "delay-within-our-control"),
    "Aging Packages by Hub": ("Where the held packages are sitting right now.", "aging-package"),
    "Aging Package Recovery List": ("Each held package with its hours held and recovery plan, longest wait first.", "aging-package"),
    "Field Reports by Root Cause": ("What drivers and hub teams wrote down: root causes and document types from field evidence.", "field-evidence"),
}
ok = 0
if f"dashboard {DASH}" in present:
  ok += set_overview(LK(f"dashboards/{DASH}"),
                     "<h3>Cymbal Shipping Service Performance (This week)</h3>"
                     "<p>The governed Looker scorecard for how well Cymbal Shipping is serving its named accounts this week: "
                     "On-Time Delivery Rate against the 97.5% target, Revenue at Risk, Aging Packages and Temperature Excursions.</p>"
                     "<p>Every tile queries the explore <em>Shipments &amp; Service Performance</em>, so the numbers match the "
                     "Looker Data App and the Gemini agent. Cross-filtering is on: select a bar to filter every tile.</p>"
                     f"<p><strong>Open it:</strong> {BASE}/dashboards/{DASH}</p>"
                     "<p><strong>Owner:</strong> Network Operations, Service Quality team</p>") == 200
for eid, title in ELEMENTS:
  if f"tile {title}" not in present:
    continue
  note, _ = TILE_NOTES.get(title, ("", None))
  ok += set_overview(LK(f"dashboards/{DASH}/dashboard_elements/{eid}"),
                     f"<h3>{title}</h3><p>{note}</p><p>Tile on the dashboard <em>Cymbal Shipping Service Performance (This week)</em>.</p>") == 200
LOOK_NOTES = [
    "Answers: how did On-Time Delivery Rate for Priority Overnight hold up this week compared with last week, by hub? Company target is 97.5%.",
    "Answers: which Strategic healthcare customers have temperature-controlled packages aging at the Memphis SuperHub, how much revenue is at risk, and did any go out of temperature range?",
]
for (lid, title), note in zip(LOOKS, LOOK_NOTES):
  if f"look {lid}" in present:
    ok += set_overview(LK(f"looks/{lid}"), f"<h3>{title}</h3><p>{note}</p><p><strong>Open it:</strong> {BASE}/looks/{lid}</p>") == 200
if APP_DASH and exists(LK(f"dashboards/{APP_DASH}")):
  ok += set_overview(LK(f"dashboards/{APP_DASH}"),
                     "<h3>Cymbal Shipping · Service Performance (Looker Data App)</h3>"
                     "<p>The business-user app: a look-up bar, key numbers and charts that filter each other. "
                     "It runs on the same governed explore, <em>Shipments &amp; Service Performance</em>.</p>"
                     f"<p><strong>Open it:</strong> {BASE}/dashboards/{APP_DASH}</p>") == 200
print("overviews set:", ok)

# -------------------------------------------------------------------- links --
n = 0
if f"dashboard {DASH}" in present:
  n += ref_link(LK_EG, "cs-ref-dash-explore", LK(f"dashboards/{DASH}"), EXPLORE)
if APP_DASH and exists(LK(f"dashboards/{APP_DASH}")):
  n += ref_link(LK_EG, "cs-ref-appdash-explore", LK(f"dashboards/{APP_DASH}"), EXPLORE)
  n += ref_link(APPS, "cs-ref-app-native-dash", DATA_APP, LK(f"dashboards/{APP_DASH}"))
for eid, title in ELEMENTS:
  if f"tile {title}" not in present:
    continue
  tile = LK(f"dashboards/{DASH}/dashboard_elements/{eid}")
  native = [l for l in links_of(tile) if any(r.get("name") == EXPLORE for r in l.get("entryReferences", []))]
  if not native:
    n += ref_link(LK_EG, f"cs-ref-tile-{eid}-explore", tile, EXPLORE)
  _, term = TILE_NOTES.get(title, ("", None))
  if term:
    n += ref_link(LK_EG, f"cs-ref-tile-{eid}-term", tile, TERM(term))
for lid, title in LOOKS:
  if f"look {lid}" not in present:
    continue
  look = LK(f"looks/{lid}")
  if not any(any(r.get("name") == EXPLORE for r in l.get("entryReferences", [])) for l in links_of(look)):
    n += ref_link(LK_EG, f"cs-ref-look-{lid}-explore", look, EXPLORE)
print("links created:", n)

# -------------------------------------------------------------- context set --
ctx = []
if f"dashboard {DASH}" in present:
  ctx.append(("ctx-looker-dashboard", LK(f"dashboards/{DASH}"), "Cymbal Shipping Service Performance (This week) (Looker dashboard)",
              "Governed Looker scorecard: on-time delivery, revenue at risk, aging packages and temperature excursions."))
for i, (lid, title) in enumerate(LOOKS):
  if f"look {lid}" in present:
    ctx.append((f"ctx-looker-look-{i + 1}", LK(f"looks/{lid}"), f"{title} (Looker Look)", LOOK_NOTES[i]))
done = 0
for cid, target, title, desc in ctx:
  dp("DELETE", f"{EGN}/{CS_ID}/entries/{cid}")
  st, r = dp("POST", f"{EGP}/{CS_ID}/entries", {
      "entryType": f"projects/{SYS}/locations/global/entryTypes/context",
      "entrySource": {"displayName": title, "description": desc, "system": "Knowledge Catalog", "location": LOC},
      "aspects": {
          f"{SYS}.global.context": {"aspectType": f"projects/{SYS}/locations/global/aspectTypes/context", "data": {"entry": target}},
          f"{SYS}.global.overview": {"aspectType": f"projects/{SYS}/locations/global/aspectTypes/overview",
                                     "data": {"content": f"**{title}**: {desc}", "contentType": "MARKDOWN"}}}},
      params={"entryId": cid})
  done += st == 200
  if st != 200:
    print(f"   context entry {cid}: {st} {json.dumps(r)[:260]}")
st, r = dp("GET", f"{EGP}/{CS_ID}/entries", params={"pageSize": 200})
print(f"context entries added: {done}/{len(ctx)} | context set now has {len(r.get('entries', [])) if st == 200 else st} entries")

# ------------------------------------------------------------------- report --
print("\nLooker graph around the explore:")
by_type = {}
for l in links_of(EXPLORE):
  for r_ in l.get("entryReferences", []):
    if r_.get("name") != EXPLORE:
      kind = "tile" if "/dashboard_elements/" in r_["name"] else "dashboard" if "/dashboards/" in r_["name"] else "look" if "/looks/" in r_["name"] else "view" if "/views/" in r_["name"] else "other"
      by_type[kind] = by_type.get(kind, 0) + 1
print("  ", by_type)
if missing:
  print("STILL MISSING natively:", missing)
