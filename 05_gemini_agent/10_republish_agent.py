"""Re-publish the Cymbal Shipping Service Desk Gemini agent so the chat UI sees its data sources.

Why: the chat UI reads an agent's data sources from the agent's *published revision*.
If the published revision was captured before connector bindings were deployed, the UI
opens new chats with data sources turned off. Calling `:publish` snapshots the current,
deployed definition without modifying instructions, model, or connectors.

Usage:
  python3 -u 05_gemini_agent/10_republish_agent.py show
  python3 -u 05_gemini_agent/10_republish_agent.py publish
  python3 -u 05_gemini_agent/10_republish_agent.py publish <old_revision_id>   # rollback
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import PROJECT_NUM as N, api, env

DE = "https://discoveryengine.googleapis.com/v1alpha"
ENGINE = env("GEMINI_ENGINE_ID", required=True)
AGENT_ID = env("GEMINI_AGENT_ID", required=True)
AGENT = (
    f"projects/{N}/locations/global/collections/default_collection/engines/{ENGINE}"
    f"/assistants/default_assistant/agents/{AGENT_ID}"
)


def show(label):
  st, ag = api("GET", f"{DE}/{AGENT}")
  st2, v = api("GET", f"{DE}/{AGENT}:getAgentView")
  view = v.get("agentView", v) if isinstance(v, dict) else {}
  st3, rev = api("GET", f"{DE}/{AGENT}/revisions")
  revs = rev.get("agentRevisions", []) if isinstance(rev, dict) else []
  print(
      f"[{label}] agent state={ag.get('state')} sharing={ag.get('sharingConfig', {}).get('scope')} "
      f"activeRevision={ag.get('activeRevision', '').split('/')[-1]} starterPrompts={len(ag.get('starterPrompts', []))}"
  )
  print(f"[{label}] revisions: {[(r['name'].split('/')[-1], r.get('createTime', '')[11:19]) for r in revs]}")
  print(
      f"[{label}] what the chat UI sees (HTTP {st2}): data sources="
      f"{[s.get('dataStore', '').split('/')[-1] for s in view.get('dataStoreSpecs', {}).get('specs', [])]} "
      f"| suggested prompts={len(view.get('suggestedPrompts', []))} | state={view.get('state')} "
      f"| sharing={view.get('agentSharingState')} | updateTime={view.get('updateTime')}"
  )
  return ag


if __name__ == "__main__":
  mode = sys.argv[1] if len(sys.argv) > 1 else "show"
  before = show("before")
  if mode == "publish":
    body = {"revisionId": sys.argv[2]} if len(sys.argv) > 2 else {}
    st, r = api("POST", f"{DE}/{AGENT}:publish", body)
    print("publish:", st, json.dumps(r)[:400])
    if st == 200:
      show("after")
