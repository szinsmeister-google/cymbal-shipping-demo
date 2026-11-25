"""Create or update the Cymbal Shipping Service Desk Gemini agent with the Looker connector.

Reads the production "Looks-first" instruction from `./agent_instruction.txt`,
binds the Looker MCP data connector and data store from `.env`, and writes
the created agent metadata to `ge_agent.json` (gitignored).

Usage: python3 05_gemini_agent/05_deploy_gemini_agent.py
Additive only: does not modify the engine, default assistant, or other agents.
"""
import base64
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import PROJECT_NUM as N, api, env

DE = "https://discoveryengine.googleapis.com/v1alpha"
ENGINE = env("GEMINI_ENGINE_ID", required=True)
LOOKER_DS_ID = env("LOOKER_DATA_STORE_ID", required=True)
LOOKER_CONN_COLL = env("LOOKER_CONNECTOR_COLLECTION", required=True)
LOOKER_CONN_TAG = env("LOOKER_CONNECTOR_TAG", "")

ASSISTANT = f"projects/{N}/locations/global/collections/default_collection/engines/{ENGINE}/assistants/default_assistant"
LOOKER_DS = f"projects/{N}/locations/global/collections/default_collection/dataStores/{LOOKER_DS_ID}"
LOOKER_CONNECTOR = f"projects/{N}/locations/global/collections/{LOOKER_CONN_COLL}/dataConnector"

NAME = "Cymbal Shipping Service Desk"
DESCRIPTION = (
    "Answers service-performance questions for Cymbal Shipping named accounts using the governed Looker "
    "model and the business definitions in Knowledge Catalog: on-time delivery, packages held at a hub, "
    "cold chain exposure, and revenue at risk under the Service Guarantee."
)

PROMPT_1 = "How did on-time delivery for Priority Overnight hold up this week compared with last week, by hub? Which hubs are below target?"
PROMPT_2 = (
    "Which Strategic healthcare customers have temperature-controlled packages aging at the Memphis SuperHub right now, "
    "how much revenue is at risk, and did any go out of temperature range?"
)
STARTERS = [PROMPT_1, PROMPT_2]

INSTRUCTION_PATH = pathlib.Path(__file__).resolve().parent / "agent_instruction.txt"
INSTRUCTION = INSTRUCTION_PATH.read_text(encoding="utf-8")

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" fill="none">
  <circle cx="64" cy="64" r="60" fill="#4D148C"/>
  <path d="M30 78 L62 78 L62 96 L100 64 L62 32 L62 50 L30 50 Z" fill="#FF6600"/>
  <rect x="22" y="58" width="16" height="12" rx="3" fill="#FFFFFF" fill-opacity="0.92"/>
</svg>"""
ICON_URI = "data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode()

connector_ref = {"name": LOOKER_CONNECTOR, "dataSource": "looker_mcp"}
if LOOKER_CONN_TAG:
  connector_ref["tag"] = LOOKER_CONN_TAG

node = {
    "id": "root_agent",
    "displayName": "Root agent",
    "llmAgentNode": {
        "description": DESCRIPTION,
        "model": "gemini-2.5-flash",
        "instruction": INSTRUCTION,
        "dataStoreSpecs": {"specs": [{"dataStore": LOOKER_DS}]},
        "dataConnectors": [connector_ref],
    },
}
body = {
    "displayName": NAME,
    "description": DESCRIPTION,
    "icon": {"uri": ICON_URI},
    "starterPrompts": [{"text": t} for t in STARTERS],
    "lowCodeAgentDefinition": {"nodes": [node], "rootAgentId": "root_agent"},
}

if __name__ == "__main__":
  st, lst = api("GET", f"{DE}/{ASSISTANT}/agents", params={"pageSize": 100})
  existing = next((a for a in lst.get("agents", []) if a.get("displayName") == NAME), None) if st == 200 else None
  if existing:
    name = existing["name"]
    st, r = api("PATCH", f"{DE}/{name}", body, params={
        "updateMask": "displayName,description,icon,starterPrompts,lowCodeAgentDefinition"})
    print("update agent:", st, json.dumps(r)[:600] if st != 200 else name)
  else:
    st, r = api("POST", f"{DE}/{ASSISTANT}/agents", body)
    print("create agent:", st, json.dumps(r)[:900] if st != 200 else r.get("name"))
    if st != 200:
      sys.exit(1)
    name = r["name"]
  for _ in range(10):
    st, a = api("GET", f"{DE}/{name}")
    lc = a.get("lowCodeAgentDefinition", {})
    print("  state:", a.get("state"), "| deployed nodes:", len(lc.get("deployedNodes", [])), "| failure:",
          a.get("deploymentFailureReason") or a.get("creationFailureReason") or "-")
    if a.get("state") in ("ENABLED", "DEPLOYMENT_FAILED", "CREATION_FAILED", "PRIVATE", "DISABLED", "CONFIGURED"):
      break
    time.sleep(3)
  a.pop("icon", None)
  with open("ge_agent.json", "w", encoding="utf-8") as fh:
    json.dump(a, fh, indent=1)
  print("agent id:", name.split("/")[-1])
  print("keys:", sorted(a.keys()))
