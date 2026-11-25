"""Native Looker content for Cymbal Shipping, so Knowledge Catalog shows a rich Looker environment:
a user-defined dashboard (14 tiles on the governed explore) and two saved Looks.

Knowledge Catalog ingests Looker dashboards, tiles and Looks natively (entry group @looker),
and links every tile to the explore it queries.

Usage: python3 02_lookml/07_native_looker_dashboard.py [--rebuild]
Additive. Only touches content titled below, inside the shared folder "Cymbal Shipping".
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import LOOKER_BASE_URL, lk

M, E = "cymbal_shipping", "shipments"
FOLDER_NAME = "Cymbal Shipping"
DASH_TITLE = "Cymbal Shipping Service Performance (This week)"
REBUILD = "--rebuild" in sys.argv
PURPLE, ORANGE, LILAC, INK = "#4D148C", "#FF6600", "#CDBFE0", "#1B1524"
TW = {"shipments.reporting_period": "This Week"}

print("session -> production:", lk("PATCH", "/session", {"workspace_id": "production"})[0])

# ------------------------------------------------------------------ folder --
st, kids = lk("GET", "/folders/1/children", params={"fields": "id,name"})
folder = next((f for f in kids if f.get("name") == FOLDER_NAME), None) if isinstance(kids, list) else None
if not folder:
  st, folder = lk("POST", "/folders", {"name": FOLDER_NAME, "parent_id": "1"})
  print("create folder:", st, folder.get("id") if isinstance(folder, dict) else folder)
  if st != 200:
    sys.exit("could not create folder")
FOLDER_ID = str(folder["id"])
print("folder:", FOLDER_ID, FOLDER_NAME)

# ------------------------------------------------------------- vis configs --
COLORS = {"collection_id": "looker_2026", "custom": {
    "id": "cymbal-shipping", "label": "Cymbal Shipping", "type": "categorical",
    "stops": [{"color": c, "offset": i} for i, c in enumerate(
        [PURPLE, ORANGE, "#8E63C7", "#2A0A52", LILAC, "#008052", "#8A8494"])]}}
BASE = {"modern2026": True, "defaults_version": 1, "label_color": [INK], "color_application": COLORS,
        "show_view_names": False}


def single(title, color=INK, **extra):
  v = {"type": "single_value", "custom_color_enabled": True, "custom_color": color,
       "show_single_value_title": True, "single_value_title": title, "show_comparison": False,
       "enable_conditional_formatting": False, "alignment": "left"}
  v.update(BASE); v.update(extra)
  return v


def cartesian(kind, series_colors=None, **extra):
  v = {"type": kind, "x_axis_gridlines": False, "y_axis_gridlines": True, "show_y_axis_labels": False,
       "show_y_axis_ticks": True, "show_x_axis_label": False, "show_x_axis_ticks": True,
       "y_axis_scale_mode": "linear", "plot_size_by_field": False, "trellis": "", "stacking": "",
       "limit_displayed_rows": False, "legend_position": "center", "point_style": "none",
       "show_value_labels": True, "label_density": 25, "x_axis_scale": "auto", "y_axis_combined": True,
       "ordering": "none", "show_null_labels": False, "show_totals_labels": False, "show_silhouette": False,
       "totals_color": "#808080", "series_colors": series_colors or {}}
  v.update(BASE); v.update(extra)
  return v


def grid(**extra):
  v = {"type": "looker_grid", "show_row_numbers": False, "transpose": False, "truncate_text": True,
       "hide_totals": False, "hide_row_totals": False, "size_to_fit": True, "table_theme": "modern",
       "limit_displayed_rows": False, "enable_conditional_formatting": False, "header_text_alignment": "left",
       "header_font_size": 12, "rows_font_size": 12, "header_font_color": INK, "header_text_color": INK,
       "cell_text_color": INK, "header_background_color": "#F8F4FC"}
  v.update(BASE); v.update(extra)
  return v


TARGET_LINE = [{"reference_type": "line", "line_value": "0.975", "range_start": "max", "range_end": "min",
                "margin_top": "deviation", "margin_value": "mean", "margin_bottom": "deviation",
                "label_position": "right", "color": "#B84300", "label": "Target 97.5%"}]

# (title, query, vis_config, (row, col, width, height))
TILES = [
    ("Packages",
     dict(fields=["shipments.package_count"], filters=TW),
     single("Packages"), (2, 0, 4, 4)),
    ("On-Time Delivery Rate",
     dict(fields=["shipments.on_time_delivery_rate", "shipments.on_time_target"], filters=TW),
     single("On-Time Delivery Rate", PURPLE, show_comparison=True, comparison_type="value",
            show_comparison_label=True, comparison_label="Target"), (2, 4, 4, 4)),
    ("Revenue at Risk",
     dict(fields=["shipments.revenue_at_risk"], filters=TW),
     single("Revenue at Risk", "#B84300"), (2, 8, 4, 4)),
    ("Refund-Eligible Packages",
     dict(fields=["shipments.guarantee_eligible_packages"], filters=TW),
     single("Refund-Eligible Packages"), (2, 12, 4, 4)),
    ("Aging Packages",
     dict(fields=["live_package_tracking.aging_packages"], filters=TW),
     single("Aging Packages"), (2, 16, 4, 4)),
    ("Temperature Excursions",
     dict(fields=["exception_evidence.temperature_excursions"], filters=TW),
     single("Temperature Excursions", "#B84300"), (2, 20, 4, 4)),
    ("On-Time Delivery Rate by Ship Day",
     dict(fields=["shipments.ship_date", "shipments.on_time_delivery_rate", "shipments.raw_on_time_rate"],
          sorts=["shipments.ship_date"], limit="100"),
     cartesian("looker_line", {"shipments.on_time_delivery_rate": PURPLE, "shipments.raw_on_time_rate": "#B5ACC0"},
               show_value_labels=False, interpolation="linear", show_null_points=False,
               legend_position="center", reference_lines=TARGET_LINE,
               series_labels={"shipments.on_time_delivery_rate": "On-Time Delivery Rate (official)",
                              "shipments.raw_on_time_rate": "Raw On-Time Rate (every late package counts)"}),
     (6, 0, 14, 8)),
    ("On-Time Delivery Rate by Hub",
     dict(fields=["hubs.hub_name", "shipments.on_time_delivery_rate"], filters=TW,
          sorts=["shipments.on_time_delivery_rate"], limit="20"),
     cartesian("looker_bar", {"shipments.on_time_delivery_rate": PURPLE}, reference_lines=TARGET_LINE,
               hide_legend=True),
     (6, 14, 10, 8)),
    ("Revenue at Risk by Customer",
     dict(fields=["customers.customer_name", "shipments.revenue_at_risk"],
          filters={**TW, "shipments.revenue_at_risk": ">0"}, sorts=["shipments.revenue_at_risk desc"], limit="10"),
     cartesian("looker_bar", {"shipments.revenue_at_risk": PURPLE}, hide_legend=True), (14, 0, 8, 8)),
    ("Revenue at Risk by Service",
     dict(fields=["services.service_name", "shipments.revenue_at_risk"],
          filters={**TW, "shipments.revenue_at_risk": ">0"}, sorts=["shipments.revenue_at_risk desc"], limit="10"),
     cartesian("looker_column", {"shipments.revenue_at_risk": PURPLE}, hide_legend=True), (14, 8, 8, 8)),
    ("Delayed Packages by Reason",
     dict(fields=["shipments.exception_reason", "shipments.exception_type", "shipments.packages_with_exception"],
          pivots=["shipments.exception_type"], filters={**TW, "shipments.exception_reason": "-NULL"},
          sorts=["shipments.exception_type desc", "shipments.packages_with_exception desc 0"], limit="20"),
     cartesian("looker_bar", {"Within Our Control - shipments.packages_with_exception": ORANGE,
                              "Outside Our Control - shipments.packages_with_exception": LILAC},
               stacking="normal", show_value_labels=False,
               series_labels={"Within Our Control - shipments.packages_with_exception": "Within our control",
                              "Outside Our Control - shipments.packages_with_exception": "Outside our control"}),
     (14, 16, 8, 8)),
    ("Aging Packages by Hub",
     dict(fields=["hubs.hub_name", "live_package_tracking.aging_packages"],
          filters={**TW, "live_package_tracking.is_aging": "yes"},
          sorts=["live_package_tracking.aging_packages desc"], limit="20"),
     cartesian("looker_bar", {"live_package_tracking.aging_packages": PURPLE}, hide_legend=True), (22, 0, 8, 8)),
    ("Aging Package Recovery List",
     dict(fields=["shipments.tracking_number", "customers.customer_name", "services.service_name", "hubs.hub_name",
                  "live_package_tracking.hub_dwell_hours", "shipments.is_cold_chain",
                  "live_package_tracking.recovery_plan"],
          filters={**TW, "live_package_tracking.is_aging": "yes"},
          sorts=["live_package_tracking.hub_dwell_hours desc"], limit="100"),
     grid(), (22, 8, 16, 8)),
    ("Field Reports by Root Cause",
     dict(fields=["exception_evidence.root_cause", "exception_evidence.document_type",
                  "exception_evidence.document_count", "exception_evidence.temperature_excursions"],
          filters={**TW, "exception_evidence.root_cause": "-NULL"},
          sorts=["exception_evidence.document_count desc"], limit="25"),
     grid(), (30, 0, 24, 7)),
]

FILTERS = [
    ("Account Tier", "customers.customer_tier", {"type": "button_group", "display": "inline"}),
    ("Industry", "customers.industry_vertical", {"type": "tag_list", "display": "popover"}),
    ("Customer", "customers.customer_name", {"type": "tag_list", "display": "popover"}),
    ("Hub", "hubs.hub_name", {"type": "tag_list", "display": "popover"}),
    ("Service", "services.service_name", {"type": "tag_list", "display": "popover"}),
]
LISTEN = [{"dashboard_filter_name": n, "field": f} for n, f, _ in FILTERS]


def make_query(q, vis):
  body = {"model": M, "view": E, "limit": "500", "vis_config": vis}
  body.update(q)
  st, r = lk("POST", "/queries", body)
  if st != 200:
    sys.exit(f"query failed: {st} {json.dumps(r)[:500]}")
  return r["id"]


# --------------------------------------------------------------- dashboard --
st, found = lk("GET", "/dashboards/search", params={"title": DASH_TITLE, "folder_id": FOLDER_ID, "fields": "id,title,deleted"})
existing = [d for d in (found if isinstance(found, list) else []) if not d.get("deleted")]
if existing and not REBUILD:
  print("dashboard already exists:", [d["id"] for d in existing], "(pass --rebuild to recreate)")
  dash_id = str(existing[0]["id"])
else:
  for d in existing:
    print("rebuild: deleting previous dashboard", d["id"], lk("DELETE", f"/dashboards/{d['id']}")[0])
  st, d = lk("POST", "/dashboards", {
      "title": DASH_TITLE, "folder_id": FOLDER_ID,
      "description": "Governed scorecard for Cymbal Shipping service performance this week: On-Time Delivery Rate against the 97.5% target, Revenue at Risk under the Service Guarantee, Aging Packages held at hubs, and Temperature Excursions on cold chain shipments. Every tile uses the Shipments & Service Performance explore, so the numbers match the Data App and the Gemini agent.",
      "preferred_viewer": "dashboards-next", "crossfilter_enabled": True, "filters_location_top": True,
      "background_color": "#FBF9FD", "title_color": INK, "tile_background_color": "#FFFFFF",
      "tile_text_color": INK, "text_tile_text_color": INK, "load_configuration": "cache_run"})
  if st != 200:
    sys.exit(f"dashboard create failed: {st} {json.dumps(d)[:500]}")
  dash_id = str(d["id"])
  print("dashboard created:", dash_id)

  for row, (name, dim, ui) in enumerate(FILTERS):
    st, f = lk("POST", "/dashboard_filters", {
        "dashboard_id": dash_id, "name": name, "title": name, "type": "field_filter", "model": M, "explore": E,
        "dimension": dim, "default_value": "", "allow_multiple_values": True, "required": False, "row": row,
        "ui_config": ui})
    print(f"  filter {name}: {st} {'' if st == 200 else json.dumps(f)[:300]}")

  positions = {}
  st, t = lk("POST", "/dashboard_elements", {
      "dashboard_id": dash_id, "type": "text", "title_text": "Cymbal Shipping Service Performance",
      "subtitle_text": "Governed metrics from the Shipments & Service Performance explore · data as of Wed, Nov 11, 8:00 AM ET",
      "body_text": ""})
  print("  text tile:", st, "" if st == 200 else json.dumps(t)[:300])
  if st == 200:
    positions[str(t["id"])] = (0, 0, 24, 2)

  for title, q, vis, pos in TILES:
    qid = make_query(q, vis)
    body = {"dashboard_id": dash_id, "type": "vis", "title": title, "query_id": qid,
            "title_hidden": vis.get("type") == "single_value",
            "result_maker": {"query_id": qid, "filterables": [{"model": M, "view": E, "name": "", "listen": LISTEN}]}}
    st, el = lk("POST", "/dashboard_elements", body)
    if st != 200:
      print(f"  element with result_maker failed ({st} {json.dumps(el)[:200]}); retrying plain")
      st, el = lk("POST", "/dashboard_elements", {"dashboard_id": dash_id, "type": "vis", "title": title, "query_id": qid})
    print(f"  tile {title}: {st} id={el.get('id') if isinstance(el, dict) else el}")
    if st == 200:
      positions[str(el["id"])] = pos

  st, d = lk("GET", f"/dashboards/{dash_id}")
  lay = (d.get("dashboard_layouts") or [{}])[0]
  moved = 0
  for c in lay.get("dashboard_layout_components") or []:
    pos = positions.get(str(c.get("dashboard_element_id")))
    if not pos:
      continue
    st, r = lk("PATCH", f"/dashboard_layout_components/{c['id']}", {"row": pos[0], "column": pos[1], "width": pos[2], "height": pos[3]})
    moved += st == 200
    if st != 200:
      print("   layout component failed:", st, json.dumps(r)[:200])
  print(f"  layout: {moved}/{len(positions)} tiles placed ({lay.get('type')})")

# ---------------------------------------------------------- verify + Looks --
st, d = lk("GET", f"/dashboards/{dash_id}")
els = d.get("dashboard_elements", [])
print("\ndashboard", dash_id, "|", d.get("title"), "| crossfilter:", d.get("crossfilter_enabled"), "| filters:", [f.get("name") for f in d.get("dashboard_filters", [])])
for e in els:
  rm = e.get("result_maker") or {}
  listens = sum(len(f.get("listen") or []) for f in (rm.get("filterables") or []))
  rows = "-"
  if e.get("query_id"):
    st, res = lk("GET", f"/queries/{e['query_id']}/run/json", params={"limit": 3, "cache": "true"}, timeout=180)
    rows = (json.dumps(res[0])[:150] if isinstance(res, list) and res else str(res)[:150])
  print(f"  el {e.get('id')} {e.get('type'):4s} | {e.get('title') or e.get('title_text')} | listens={listens} | {rows}")

LOOKS = [
    ("Cymbal Shipping · Priority Overnight On-Time Delivery by Hub (this week vs last week)",
     "On-Time Delivery Rate for Priority Overnight by hub, this week compared with last week. Company target is 97.5%.",
     dict(fields=["hubs.hub_name", "shipments.reporting_period", "shipments.on_time_delivery_rate"],
          pivots=["shipments.reporting_period"],
          filters={"services.service_name": "Priority Overnight", "shipments.reporting_period": "This Week,Last Week"},
          sorts=["shipments.reporting_period desc", "shipments.on_time_delivery_rate 0"], limit="50"),
     grid(show_row_numbers=True)),
    ("Cymbal Shipping · Strategic Healthcare Cold Chain Packages Aging at Memphis",
     "Strategic healthcare customers with temperature-controlled packages held 6 hours or more at the Memphis SuperHub: packages, revenue at risk and temperature excursions.",
     dict(fields=["customers.customer_name", "customers.account_director", "live_package_tracking.aging_packages",
                  "live_package_tracking.average_hours_held", "shipments.revenue_at_risk",
                  "exception_evidence.temperature_excursions", "exception_evidence.highest_temperature_c"],
          filters={"customers.customer_tier": "Strategic", "customers.industry_vertical": "Healthcare & Life Sciences",
                   "hubs.hub_name": "Memphis SuperHub", "shipments.is_cold_chain": "Yes",
                   "live_package_tracking.is_aging": "Yes"},
          sorts=["shipments.revenue_at_risk desc"], limit="50"),
     grid(show_row_numbers=True)),
]
out = {"folder_id": FOLDER_ID, "dashboard_id": dash_id, "elements": [(str(e.get("id")), e.get("type"), e.get("title")) for e in els], "looks": []}
for title, desc, q, vis in LOOKS:
  st, found = lk("GET", "/looks/search", params={"title": title, "folder_id": FOLDER_ID, "fields": "id,title,deleted"})
  ex = [l for l in (found if isinstance(found, list) else []) if not l.get("deleted")]
  if ex:
    look_id = str(ex[0]["id"])
    print("look exists:", look_id, title)
  else:
    qid = make_query(q, vis)
    st, l = lk("POST", "/looks", {"title": title, "description": desc, "folder_id": FOLDER_ID, "query_id": qid, "is_run_on_load": True})
    print("look created:", st, l.get("id") if isinstance(l, dict) else l, "|", title, "" if st == 200 else json.dumps(l)[:300])
    look_id = str(l.get("id")) if st == 200 else None
  if look_id:
    st, res = lk("GET", f"/looks/{look_id}/run/json", params={"limit": 3}, timeout=180)
    print("   rows:", json.dumps(res)[:400])
    out["looks"].append((look_id, title))
with open("native_looker_content.json", "w", encoding="utf-8") as fh:
  json.dump(out, fh, indent=1)
print(f"\n{LOOKER_BASE_URL}/dashboards/{dash_id}")
for lid, t in out["looks"]:
  print(f"{LOOKER_BASE_URL}/looks/{lid} | {t}")
