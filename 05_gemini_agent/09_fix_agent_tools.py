"""Re-bind the Cymbal Shipping Service Desk Gemini agent's connectors by tag and redeploy it.

Why: the chat UI sends no explicit data-store spec on low-code agent turns, so the
backend resolves the agent's connectors from its definition. Untagged bindings
(name + dataSource only) may not resolve on all projects; a binding carrying the
connector's `tag` resolves reliably by (dataSource, tag).

Usage:
  python3 -u 05_gemini_agent/09_fix_agent_tools.py show
  python3 -u 05_gemini_agent/09_fix_agent_tools.py apply looker
  python3 -u 05_gemini_agent/09_fix_agent_tools.py apply looker,bigquery
  python3 -u 05_gemini_agent/09_fix_agent_tools.py apply looker,spanner
  add  --instruction 05_gemini_agent/agent_instruction.txt  to replace the instruction text
  add  --no-deploy                                          to leave the change as a draft
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import PROJECT_NUM as N, api, env

DE = "https://discoveryengine.googleapis.com/v1alpha"
ENGINE = env("GEMINI_ENGINE_ID", required=True)
AGENT_ID = env("GEMINI_AGENT_ID", required=True)
AGENT = (
    f"projects/{N}/locations/global/collections/default_collection/engines/{ENGINE}"
    f"/assistants/default_assistant/agents/{AGENT_ID}"
)
C = f"projects/{N}/locations/global/collections"

BINDINGS = {
    "looker": {
        "store": f"{C}/default_collection/dataStores/{env('LOOKER_DATA_STORE_ID', 'looker_mcp_store')}",
        "name": f"{C}/{env('LOOKER_CONNECTOR_COLLECTION', 'looker_mcp')}/dataConnector",
        "dataSource": "looker_mcp",
        "tag": env("LOOKER_CONNECTOR_TAG", "looker-mcp"),
    },
    "bigquery": {
        "store": f"{C}/default_collection/dataStores/{env('BQ_DATA_STORE_ID', 'bigquery_mcp_store')}",
        "name": f"{C}/{env('BQ_CONNECTOR_COLLECTION', 'bigquery_mcp')}/dataConnector",
        "dataSource": "bigquery_mcp",
        "tag": env("BQ_CONNECTOR_TAG", "bigquery-mcp"),
    },
    "spanner": {
        "store": f"{C}/default_collection/dataStores/{env('SPANNER_DATA_STORE_ID', 'spanner_store')}",
        "name": f"{C}/{env('SPANNER_CONNECTOR_COLLECTION', 'spanner_connector')}/dataConnector",
        "dataSource": "spanner",
        "tag": env("SPANNER_CONNECTOR_TAG", "spanner-graph"),
    },
}

STARTERS = [
    "How did on-time delivery for Priority Overnight hold up this week compared with last week, by hub? Which hubs are below target?",
    (
        "Which Strategic healthcare customers have temperature-controlled packages aging at the Memphis SuperHub right now, "
        "how much revenue is at risk, and did any go out of temperature range?"
    ),
]


def summary(a):
  lc = a.get("lowCodeAgentDefinition", {})
  out = {
      "state": a.get("state"),
      "updateTime": a.get("updateTime"),
      "starterPrompts": len(a.get("starterPrompts", [])),
      "draftStarterPrompts": len(lc.get("draftStarterPrompts", [])),
  }
  for key in ("nodes", "deployedNodes"):
    n = (lc.get(key) or [{}])[0].get("llmAgentNode", {})
    out[key] = {
        "connectors": [(c.get("dataSource"), c.get("tag")) for c in n.get("dataConnectors", [])],
        "stores": [s.get("dataStore", "").split("/")[-1] for s in n.get("dataStoreSpecs", {}).get("specs", [])],
        "instruction_chars": len(n.get("instruction", "")),
    }
  return out


if __name__ == "__main__":
  mode = sys.argv[1] if len(sys.argv) > 1 else "show"
  st, agent = api("GET", f"{DE}/{AGENT}")
  assert st == 200, (st, str(agent)[:300])
  print("before:", json.dumps(summary(agent)))
  if mode != "apply":
    sys.exit(0)

  keys = [k.strip() for k in sys.argv[2].split(",") if k.strip()]
  lc = agent["lowCodeAgentDefinition"]
  node = json.loads(json.dumps(lc["nodes"][0]))
  llm = node["llmAgentNode"]
  llm["dataStoreSpecs"] = {"specs": [{"dataStore": BINDINGS[k]["store"]} for k in keys]}
  llm["dataConnectors"] = [
      {"name": BINDINGS[k]["name"], "dataSource": BINDINGS[k]["dataSource"], "tag": BINDINGS[k]["tag"]}
      for k in keys
  ]
  if "--instruction" in sys.argv:
    llm["instruction"] = open(sys.argv[sys.argv.index("--instruction") + 1], encoding="utf-8").read()
  new_lc = {
      "rootAgentId": lc.get("rootAgentId", "root_agent"),
      "nodes": [node],
      "draftStarterPrompts": [{"text": t} for t in STARTERS],
  }
  for k in ("draftDisplayName", "draftDescription", "draftIcon"):
    if k in lc:
      new_lc[k] = lc[k]
  st, r = api("PATCH", f"{DE}/{AGENT}", {"lowCodeAgentDefinition": new_lc},
              params={"updateMask": "lowCodeAgentDefinition"})
  print("update draft:", st, "" if st == 200 else json.dumps(r)[:900])
  if st != 200:
    sys.exit(1)
  if "--no-deploy" not in sys.argv:
    st, op = api("POST", f"{DE}/{AGENT}:deployLowCode", {"deployMode": "DEPLOY"})
    print("deploy:", st, json.dumps(op)[:400])
    if st != 200:
      sys.exit(2)
    name = op.get("name")
    for _ in range(40):
      if op.get("done") or not name:
        break
      time.sleep(3)
      st, op = api("GET", f"{DE}/{name}")
    print("deploy operation done:", op.get("done"), "| error:", json.dumps(op.get("error"))[:300] if op.get("error") else "-")
  st, agent = api("GET", f"{DE}/{AGENT}")
  print("after:", json.dumps(summary(agent)))
