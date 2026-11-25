"""Seed the Cymbal Shipping BigQuery dataset.

Creates dataset `cymbal_shipping` (or `$BQ_DATASET`) and tables:
  hubs, services, customers, shipments
All data is synthetic and frozen "as of" 2026-11-11 13:00 UTC (8:00 AM ET).
Idempotent: uses CREATE OR REPLACE.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import BQ_DATASET as DS, BQ_LOCATION as LOC, PROJECT_ID as P, api, bq, bq_rows

AS_OF = "TIMESTAMP '2026-11-11 13:00:00+00'"

# ---------------------------------------------------------------- dataset --
st, r = api("GET", f"https://bigquery.googleapis.com/bigquery/v2/projects/{P}/datasets/{DS}")
if st == 404:
  st, r = api("POST", f"https://bigquery.googleapis.com/bigquery/v2/projects/{P}/datasets", {
      "datasetReference": {"projectId": P, "datasetId": DS},
      "location": LOC,
      "friendlyName": "Cymbal Shipping · Service Performance Lakehouse",
      "description": (
          "Cymbal Shipping strategic-accounts service performance data: every "
          "package shipped for our named accounts, the service we promised, "
          "whether we delivered on time, and the revenue covered by our "
          "service guarantee. Combines shipment history (BigQuery), live "
          "package tracking replicated from Spanner, and driver / hub field "
          "evidence documents from the object-storage lake. Synthetic demo data."),
      "labels": {"demo": "cymbal-shipping"},
  })
  print("create dataset:", st, r.get("id") if isinstance(r, dict) else r)
  if st != 200:
    sys.exit(1)
else:
  print("dataset exists:", st, r.get("location"))

q = lambda sql: bq(sql, location=LOC)

# ------------------------------------------------------------------- hubs --
q(f"""
CREATE OR REPLACE TABLE `{P}.{DS}.hubs` (
  hub_code STRING NOT NULL OPTIONS(description='Three-letter hub code used on every scan and routing label (for example MEM = Memphis SuperHub).'),
  hub_name STRING OPTIONS(description='Business name of the sort hub.'),
  city STRING OPTIONS(description='City where the hub operates.'),
  state STRING OPTIONS(description='Two-letter US state of the hub.'),
  region STRING OPTIONS(description='Cymbal Shipping operating region the hub belongs to.'),
  hub_type STRING OPTIONS(description='Role of the hub in the network: Air SuperHub, National Air Hub, Regional Air Hub, International Gateway, or Ground Hub.'),
  daily_sort_capacity INT64 OPTIONS(description='Packages the hub can sort in a normal 24-hour operating day.'),
  latitude FLOAT64 OPTIONS(description='Hub latitude.'),
  longitude FLOAT64 OPTIONS(description='Hub longitude.'),
  backup_hub_code STRING OPTIONS(description='Hub that takes diverted volume when this hub cannot sort on schedule (recovery routing).')
) OPTIONS(description='Cymbal Shipping sort hubs and gateways. One row per hub. Used to see where packages are sorted and which hub covers for another during a disruption.');
""")
q(f"""
INSERT INTO `{P}.{DS}.hubs` VALUES
 ('MEM','Memphis SuperHub','Memphis','TN','South','Air SuperHub',1450000,35.0424,-89.9767,'IND'),
 ('IND','Indianapolis Air Hub','Indianapolis','IN','Midwest','National Air Hub',820000,39.7173,-86.2944,'MEM'),
 ('OAK','Oakland Regional Hub','Oakland','CA','West','Regional Air Hub',310000,37.7213,-122.2208,'AFW'),
 ('EWR','Newark Regional Hub','Newark','NJ','Northeast','Regional Air Hub',360000,40.6895,-74.1745,'IND'),
 ('AFW','Fort Worth Regional Hub','Fort Worth','TX','Southwest','Regional Air Hub',330000,32.9876,-97.3188,'MEM'),
 ('DEN','Denver Regional Hub','Denver','CO','Mountain','Regional Air Hub',240000,39.8561,-104.6737,'AFW'),
 ('MIA','Miami Gateway','Miami','FL','Southeast','International Gateway',210000,25.7959,-80.2870,'MEM'),
 ('ANC','Anchorage Gateway','Anchorage','AK','Pacific','International Gateway',190000,61.1743,-149.9962,'OAK'),
 ('ORD','Chicago Ground Hub','Chicago','IL','Midwest','Ground Hub',540000,41.9742,-87.9073,'IND'),
 ('ATL','Atlanta Ground Hub','Atlanta','GA','Southeast','Ground Hub',480000,33.6407,-84.4277,'MEM');
""")

# --------------------------------------------------------------- services --
q(f"""
CREATE OR REPLACE TABLE `{P}.{DS}.services` (
  service_code STRING NOT NULL OPTIONS(description='Two-letter service code printed on the shipping label.'),
  service_name STRING OPTIONS(description='Service the customer bought, as it appears on the invoice (for example Priority Overnight).'),
  service_family STRING OPTIONS(description='Service family used in management reporting: Express, Ground, International, or Freight.'),
  commit_days INT64 OPTIONS(description='Number of days after pickup by which we promise delivery.'),
  commit_time_local STRING OPTIONS(description='Local time of day by which we promise delivery on the commit day.'),
  is_guaranteed_service BOOL OPTIONS(description='True when the service carries the Cymbal Shipping Service Guarantee: if we are late for a reason within our control, the customer can claim a refund of the shipping charge.'),
  list_rate_usd NUMERIC OPTIONS(description='Average published rate per package for this service before customer discounts.'),
  sort_order INT64 OPTIONS(description='Display order from fastest to slowest service.')
) OPTIONS(description='Cymbal Shipping service catalog. One row per service. Tells you how fast each service is, what we promise, and whether the Service Guarantee applies.');
""")
q(f"""
INSERT INTO `{P}.{DS}.services` VALUES
 ('PO','Priority Overnight','Express',1,'10:30',TRUE,118.00,1),
 ('SO','Standard Overnight','Express',1,'16:30',TRUE,86.00,2),
 ('2D','2-Day','Express',2,'16:30',TRUE,54.00,3),
 ('ES','Express Saver','Express',3,'16:30',TRUE,38.00,4),
 ('IP','International Priority','International',3,'12:00',TRUE,240.00,5),
 ('GD','Ground','Ground',4,'20:00',FALSE,19.00,6),
 ('HD','Home Delivery','Ground',4,'20:00',FALSE,17.00,7),
 ('FR','Freight Priority','Freight',3,'17:00',FALSE,640.00,8);
""")

# -------------------------------------------------------------- customers --
CUSTOMERS = [
    # id, name, vertical, tier, primary hub, hq city, hq state, weekday packages, account director
    ("C1001", "Meridian Pharma", "Healthcare & Life Sciences", "Strategic", "MEM", "Nashville", "TN", 1450, "Priya Raman"),
    ("C1002", "Aurora Biologics", "Healthcare & Life Sciences", "Strategic", "MEM", "St. Louis", "MO", 1180, "Priya Raman"),
    ("C1003", "Northstar Medical Devices", "Healthcare & Life Sciences", "Strategic", "IND", "Minneapolis", "MN", 1320, "Marcus Bell"),
    ("C1004", "Pinecrest Diagnostics", "Healthcare & Life Sciences", "Enterprise", "MEM", "Birmingham", "AL", 760, "Priya Raman"),
    ("C1005", "Clearwater Specialty Pharmacy", "Healthcare & Life Sciences", "Enterprise", "MEM", "Little Rock", "AR", 640, "Dana Whitfield"),
    ("C1006", "Summit Orthopedics Supply", "Healthcare & Life Sciences", "Enterprise", "DEN", "Denver", "CO", 520, "Marcus Bell"),
    ("C1007", "Harborview Clinical Labs", "Healthcare & Life Sciences", "Mid-Market", "EWR", "Newark", "NJ", 310, "Dana Whitfield"),
    ("C1008", "Bluegrass Veterinary Supply", "Healthcare & Life Sciences", "Mid-Market", "MEM", "Lexington", "KY", 280, "Dana Whitfield"),
    ("C1009", "Solstice Electronics", "Technology & Electronics", "Strategic", "OAK", "San Jose", "CA", 1540, "Elena Vasquez"),
    ("C1010", "Brightline Semiconductor", "Technology & Electronics", "Strategic", "AFW", "Austin", "TX", 980, "Elena Vasquez"),
    ("C1011", "Cascade Devices", "Technology & Electronics", "Enterprise", "OAK", "Portland", "OR", 720, "Tom Okafor"),
    ("C1012", "Vector Robotics", "Technology & Electronics", "Enterprise", "IND", "Pittsburgh", "PA", 560, "Tom Okafor"),
    ("C1013", "Lumen Audio", "Technology & Electronics", "Mid-Market", "EWR", "Boston", "MA", 340, "Tom Okafor"),
    ("C1014", "Pixel & Pine Gadgets", "Technology & Electronics", "Small Business", "OAK", "Sacramento", "CA", 150, "Inside Sales"),
    ("C1015", "Harbor & Main Outfitters", "Retail & E-commerce", "Strategic", "ORD", "Chicago", "IL", 2260, "Jordan Ellis"),
    ("C1016", "Juniper Home Goods", "Retail & E-commerce", "Strategic", "ATL", "Atlanta", "GA", 1980, "Jordan Ellis"),
    ("C1017", "Marigold Beauty", "Retail & E-commerce", "Enterprise", "EWR", "New York", "NY", 1120, "Sofia Marchetti"),
    ("C1018", "Trailhead Sporting Co.", "Retail & E-commerce", "Enterprise", "DEN", "Salt Lake City", "UT", 940, "Sofia Marchetti"),
    ("C1019", "Little Sprout Kids", "Retail & E-commerce", "Enterprise", "ATL", "Charlotte", "NC", 860, "Sofia Marchetti"),
    ("C1020", "Copper Kettle Kitchenware", "Retail & E-commerce", "Mid-Market", "ORD", "Milwaukee", "WI", 430, "Jordan Ellis"),
    ("C1021", "Saltwater Surf Shop", "Retail & E-commerce", "Small Business", "MIA", "Miami", "FL", 170, "Inside Sales"),
    ("C1022", "Paper Lantern Books", "Retail & E-commerce", "Small Business", "OAK", "Oakland", "CA", 140, "Inside Sales"),
    ("C1023", "Bluebonnet Auto Parts", "Automotive & Industrial", "Strategic", "AFW", "Dallas", "TX", 1260, "Hank Morales"),
    ("C1024", "Atlas Precision Tools", "Automotive & Industrial", "Enterprise", "IND", "Cincinnati", "OH", 780, "Hank Morales"),
    ("C1025", "Ironwood Machinery", "Automotive & Industrial", "Enterprise", "ORD", "Detroit", "MI", 690, "Hank Morales"),
    ("C1026", "Gulf Coast Fasteners", "Automotive & Industrial", "Mid-Market", "AFW", "Houston", "TX", 360, "Renee Dubois"),
    ("C1027", "Redline Performance Parts", "Automotive & Industrial", "Mid-Market", "MEM", "Memphis", "TN", 330, "Renee Dubois"),
    ("C1028", "Tri-County Tractor Supply", "Automotive & Industrial", "Small Business", "MEM", "Jackson", "MS", 160, "Inside Sales"),
    ("C1029", "Lakeshore Legal Services", "Financial & Legal Documents", "Enterprise", "ORD", "Chicago", "IL", 410, "Grace Liu"),
    ("C1030", "First Meridian Title & Escrow", "Financial & Legal Documents", "Enterprise", "MEM", "Nashville", "TN", 380, "Grace Liu"),
    ("C1031", "Beacon Hill Advisors", "Financial & Legal Documents", "Mid-Market", "EWR", "Boston", "MA", 240, "Grace Liu"),
    ("C1032", "Evergreen Mortgage Group", "Financial & Legal Documents", "Mid-Market", "OAK", "Seattle", "WA", 220, "Grace Liu"),
    ("C1033", "Pacific Rim Imports", "Retail & E-commerce", "Enterprise", "ANC", "Seattle", "WA", 540, "Sofia Marchetti"),
    ("C1034", "Tropic Fresh Exports", "Retail & E-commerce", "Mid-Market", "MIA", "Miami", "FL", 300, "Sofia Marchetti"),
    ("C1035", "Keystone Aerospace Components", "Automotive & Industrial", "Strategic", "IND", "Indianapolis", "IN", 890, "Hank Morales"),
    ("C1036", "Delta Crossing Medical Supply", "Healthcare & Life Sciences", "Enterprise", "MEM", "Jackson", "MS", 590, "Dana Whitfield"),
]
rows = ",\n".join(
    "('%s','%s','%s','%s','%s','%s','%s',%d,'%s')" % tuple(str(x).replace("'", "\\'") if not isinstance(x, int) else x for x in c)
    for c in CUSTOMERS)
q(f"""
CREATE OR REPLACE TABLE `{P}.{DS}.customers` (
  customer_id STRING NOT NULL OPTIONS(description='Cymbal Shipping account number for the shipper.'),
  customer_name STRING OPTIONS(description='Name of the shipper (the business that pays for the shipment).'),
  industry_vertical STRING OPTIONS(description='Industry the shipper operates in. Healthcare & Life Sciences shippers frequently send time- and temperature-sensitive packages.'),
  customer_tier STRING OPTIONS(description='Account tier set by Sales: Strategic (named accounts with a dedicated account director), Enterprise, Mid-Market, or Small Business.'),
  primary_hub_code STRING OPTIONS(description='Hub that normally sorts most of this shipper\\'s volume.'),
  hq_city STRING OPTIONS(description='Shipper headquarters city.'),
  hq_state STRING OPTIONS(description='Shipper headquarters state.'),
  typical_weekday_packages INT64 OPTIONS(description='Packages this shipper typically tenders on a normal weekday.'),
  account_director STRING OPTIONS(description='Cymbal Shipping account director responsible for the relationship.')
) OPTIONS(description='Cymbal Shipping named accounts. One row per shipper, with its industry, account tier, and the account director who owns the relationship.');
""")
q(f"INSERT INTO `{P}.{DS}.customers` VALUES\n{rows};")

# ---------------------------------------------------------------- helpers --
# Service mix by vertical (cumulative probability bands).
MIX = {
    "Healthcare & Life Sciences": [("PO", .44), ("SO", .20), ("2D", .14), ("IP", .07), ("GD", .12), ("ES", .03)],
    "Technology & Electronics": [("2D", .25), ("GD", .24), ("PO", .15), ("SO", .12), ("IP", .10), ("ES", .09), ("HD", .05)],
    "Retail & E-commerce": [("HD", .40), ("GD", .34), ("2D", .12), ("ES", .08), ("SO", .03), ("PO", .02), ("IP", .01)],
    "Automotive & Industrial": [("GD", .38), ("FR", .14), ("2D", .16), ("ES", .11), ("SO", .10), ("PO", .11)],
    "Financial & Legal Documents": [("PO", .52), ("SO", .24), ("2D", .15), ("IP", .09)],
}
mix_rows = []
for v, items in MIX.items():
  lo = 0.0
  for code, p in items:
    hi = round(lo + p, 6)
    last = (code == items[-1][0])
    mix_rows.append(f"STRUCT('{v}' AS v, '{code}' AS service_code, {lo} AS lo, {1.01 if last else hi} AS hi)")
    lo = hi
MIX_SQL = "[" + ",\n ".join(mix_rows) + "]"

DEST = [  # metro, state, region, weight
    ("New York", "NY", "Northeast", 9), ("Boston", "MA", "Northeast", 4), ("Philadelphia", "PA", "Northeast", 4),
    ("Washington", "DC", "Northeast", 4), ("Atlanta", "GA", "Southeast", 6), ("Miami", "FL", "Southeast", 5),
    ("Charlotte", "NC", "Southeast", 3), ("Orlando", "FL", "Southeast", 3), ("Nashville", "TN", "South", 3),
    ("Memphis", "TN", "South", 2), ("New Orleans", "LA", "South", 2), ("Chicago", "IL", "Midwest", 7),
    ("Detroit", "MI", "Midwest", 3), ("Minneapolis", "MN", "Midwest", 3), ("Columbus", "OH", "Midwest", 3),
    ("Dallas", "TX", "Southwest", 6), ("Houston", "TX", "Southwest", 6), ("Phoenix", "AZ", "Southwest", 4),
    ("Denver", "CO", "Mountain", 3), ("Salt Lake City", "UT", "Mountain", 2), ("Los Angeles", "CA", "West", 9),
    ("San Francisco", "CA", "West", 5), ("Seattle", "WA", "West", 4), ("Portland", "OR", "West", 2),
]
tot = sum(d[3] for d in DEST)
lo = 0.0
dest_rows = []
for m, s, rgn, w in DEST:
  hi = round(lo + w / tot, 6)
  last = (m == DEST[-1][0])
  dest_rows.append(f"STRUCT('{m}' AS metro, '{s}' AS st, '{rgn}' AS region, {lo} AS lo, {1.01 if last else hi} AS hi)")
  lo = hi
DEST_SQL = "[" + ",\n ".join(dest_rows) + "]"

HUBW = [("MEM", 30), ("IND", 16), ("ORD", 11), ("ATL", 10), ("EWR", 8), ("AFW", 8), ("OAK", 7), ("DEN", 4), ("MIA", 3), ("ANC", 3)]
tot = sum(h[1] for h in HUBW)
lo = 0.0
hub_rows = []
for h, w in HUBW:
  hi = round(lo + w / tot, 6)
  last = (h == HUBW[-1][0])
  hub_rows.append(f"STRUCT('{h}' AS hub, {lo} AS lo, {1.01 if last else hi} AS hi)")
  lo = hi
HUB_SQL = "[" + ",\n ".join(hub_rows) + "]"

R = lambda salt: f"(MOD(ABS(FARM_FINGERPRINT(CONCAT(k, '{salt}'))), 1000000) / 1000000.0)"

# -------------------------------------------------------------- shipments --
SHIP_SQL = f"""
CREATE OR REPLACE TABLE `{P}.{DS}.shipments`
PARTITION BY ship_date
CLUSTER BY routing_hub_code, customer_id, service_code
OPTIONS(description='One row per package Cymbal Shipping picked up for a named account since October 1, 2026. Shows the service bought, the delivery promise (commit time), what actually happened, any delivery exception, and the shipping charge. This is the system of analysis for on-time delivery and Service Guarantee exposure. Snapshot as of November 11, 2026 8:00 AM ET.')
AS
WITH base AS (
  SELECT
    d AS ship_date,
    c.customer_id, c.industry_vertical, c.customer_tier, c.primary_hub_code,
    CONCAT(CAST(d AS STRING), '|', c.customer_id, '|', CAST(n AS STRING)) AS k
  FROM UNNEST(GENERATE_DATE_ARRAY(DATE '2026-10-01', DATE '2026-11-10')) AS d
  CROSS JOIN `{P}.{DS}.customers` c
  CROSS JOIN UNNEST(GENERATE_ARRAY(1, CAST(ROUND(
      c.typical_weekday_packages
      * CASE EXTRACT(DAYOFWEEK FROM d) WHEN 1 THEN 0.10 WHEN 7 THEN 0.32 WHEN 2 THEN 1.06 WHEN 6 THEN 0.94 ELSE 1.0 END
      * (1 + 0.0045 * DATE_DIFF(d, DATE '2026-10-01', DAY))
      * (0.93 + 0.14 * (MOD(ABS(FARM_FINGERPRINT(CONCAT(CAST(d AS STRING), c.customer_id))), 1000) / 1000.0))
    ) AS INT64))) AS n
),
drawn AS (
  SELECT b.*,
    {R('svc')} AS r_svc, {R('hub1')} AS r_hub1, {R('hub2')} AS r_hub2, {R('dst')} AS r_dst,
    {R('exc')} AS r_exc, {R('code')} AS r_code, {R('late')} AS r_late, {R('hrs')} AS r_hrs,
    {R('wt')} AS r_wt, {R('rev')} AS r_rev, {R('cold')} AS r_cold, {R('pick')} AS r_pick,
    {R('early')} AS r_early, {R('org')} AS r_org
  FROM base b
),
svc AS (
  SELECT d.*, m.service_code
  FROM drawn d
  JOIN UNNEST({MIX_SQL}) m
    ON m.v = d.industry_vertical AND d.r_svc >= m.lo AND d.r_svc < m.hi
),
routed AS (
  SELECT s.*,
    CASE
      WHEN s.service_code = 'IP' THEN IF(s.r_hub2 < 0.45, 'MEM', IF(s.r_hub2 < 0.72, 'MIA', 'ANC'))
      WHEN s.service_code IN ('GD','HD','FR') AND s.primary_hub_code IN ('ORD','ATL') THEN s.primary_hub_code
      WHEN s.r_hub1 < 0.66 THEN s.primary_hub_code
      ELSE h.hub
    END AS routing_hub_code,
    dst.metro AS destination_metro, dst.st AS destination_state, dst.region AS destination_region
  FROM svc s
  JOIN UNNEST({HUB_SQL}) h ON s.r_hub2 >= h.lo AND s.r_hub2 < h.hi
  JOIN UNNEST({DEST_SQL}) dst ON s.r_dst >= dst.lo AND s.r_dst < dst.hi
),
priced AS (
  SELECT r.*, sv.service_name, sv.service_family, sv.commit_days, sv.commit_time_local,
    sv.is_guaranteed_service, sv.list_rate_usd,
    -- probability of a delay we control (missed sort, equipment, misroute, damage)
    (CASE sv.service_family WHEN 'Express' THEN 0.015 WHEN 'Ground' THEN 0.021 WHEN 'International' THEN 0.028 ELSE 0.034 END
     + CASE
         WHEN r.routing_hub_code = 'MEM' AND r.ship_date = DATE '2026-11-09' AND sv.service_family IN ('Express','International') THEN 0.265
         WHEN r.routing_hub_code = 'MEM' AND r.ship_date = DATE '2026-11-10' AND sv.service_family IN ('Express','International') THEN 0.185
         WHEN r.routing_hub_code = 'MEM' AND r.ship_date IN (DATE '2026-11-09', DATE '2026-11-10') THEN 0.045
         WHEN r.routing_hub_code = 'MEM' AND r.ship_date = DATE '2026-11-08' AND sv.service_family = 'Express' THEN 0.02
         ELSE 0 END) AS p_ctrl,
    -- probability of a delay outside our control (weather, customs, recipient)
    (CASE sv.service_family WHEN 'Express' THEN 0.011 WHEN 'Ground' THEN 0.019 WHEN 'International' THEN 0.062 ELSE 0.018 END
     + CASE
         WHEN r.routing_hub_code = 'DEN' AND r.ship_date IN (DATE '2026-10-27', DATE '2026-10-28') THEN 0.23
         WHEN r.routing_hub_code = 'EWR' AND r.ship_date = DATE '2026-10-13' THEN 0.11
         WHEN r.destination_region = 'Mountain' AND r.ship_date IN (DATE '2026-10-27', DATE '2026-10-28') THEN 0.09
         ELSE 0 END) AS p_unctrl
  FROM routed r
  JOIN `{P}.{DS}.services` sv USING (service_code)
),
exc AS (
  SELECT p.*,
    CASE
      WHEN p.r_exc < p.p_ctrl THEN 'Controllable'
      WHEN p.r_exc < p.p_ctrl + p.p_unctrl THEN 'Uncontrollable'
    END AS exception_category
  FROM priced p
),
coded AS (
  SELECT e.*,
    CASE
      WHEN e.exception_category = 'Controllable' THEN
        CASE
          WHEN e.routing_hub_code = 'MEM' AND e.ship_date IN (DATE '2026-11-09', DATE '2026-11-10') AND e.r_code < 0.93 THEN 'Missed Sort'
          WHEN e.r_code < 0.36 THEN 'Missed Sort'
          WHEN e.r_code < 0.62 THEN 'Equipment Delay'
          WHEN e.r_code < 0.84 THEN 'Misrouted'
          ELSE 'Damaged in Handling' END
      WHEN e.exception_category = 'Uncontrollable' THEN
        CASE
          WHEN (e.routing_hub_code = 'DEN' OR e.destination_region = 'Mountain') AND e.ship_date IN (DATE '2026-10-27', DATE '2026-10-28') AND e.r_code < 0.9 THEN 'Weather'
          WHEN e.routing_hub_code = 'EWR' AND e.ship_date = DATE '2026-10-13' AND e.r_code < 0.85 THEN 'Weather'
          WHEN e.service_code = 'IP' AND e.r_code < 0.72 THEN 'Customs Hold'
          WHEN e.r_code < 0.30 THEN 'Weather'
          WHEN e.r_code < 0.68 THEN 'Recipient Not Available'
          ELSE 'Address Correction' END
    END AS exception_reason
  FROM exc e
),
timed AS (
  SELECT c.*,
    TIMESTAMP(DATETIME(c.ship_date, TIME(15 + CAST(FLOOR(c.r_pick * 5) AS INT64), CAST(FLOOR(c.r_org * 60) AS INT64), 0)), 'America/New_York') AS pickup_ts,
    TIMESTAMP(DATETIME(DATE_ADD(c.ship_date, INTERVAL c.commit_days DAY), PARSE_TIME('%H:%M', c.commit_time_local)), 'America/New_York') AS committed_delivery_ts,
    -- does the exception actually make the package late?
    (c.exception_category IS NOT NULL AND c.r_late < IF(c.exception_reason IN ('Missed Sort','Weather','Customs Hold'), 0.96, 0.82)) AS causes_delay,
    CASE
      WHEN c.exception_reason = 'Missed Sort' AND c.routing_hub_code = 'MEM' AND c.ship_date IN (DATE '2026-11-09', DATE '2026-11-10') THEN 14 + c.r_hrs * 34
      WHEN c.exception_reason = 'Customs Hold' THEN 10 + c.r_hrs * 62
      WHEN c.exception_reason = 'Weather' THEN 6 + c.r_hrs * 30
      WHEN c.exception_reason IN ('Missed Sort','Equipment Delay','Misrouted') THEN 3 + c.r_hrs * 23
      ELSE 2 + c.r_hrs * 26 END AS delay_hours
  FROM coded c
),
planned AS (
  SELECT t.*,
    IF(t.causes_delay,
       TIMESTAMP_ADD(t.committed_delivery_ts, INTERVAL CAST(ROUND(t.delay_hours * 60) AS INT64) MINUTE),
       TIMESTAMP_SUB(t.committed_delivery_ts, INTERVAL CAST(ROUND((0.4 + t.r_early * 5.5) * 60) AS INT64) MINUTE)) AS planned_delivery_ts
  FROM timed t
),
numbered AS (
  SELECT p.*, ROW_NUMBER() OVER (ORDER BY FARM_FINGERPRINT(CONCAT(p.k, 'trk')), p.k) AS rn
  FROM planned p
)
SELECT
  -- 12-digit tracking number; rn * odd-non-multiple-of-5 is a bijection mod 10^10, so numbers never collide
  CONCAT('78', LPAD(CAST(MOD(rn * 7919999 + 1234567, 10000000000) AS STRING), 10, '0')) AS tracking_number,
  ship_date,
  pickup_ts,
  customer_id,
  service_code,
  routing_hub_code,
  destination_metro,
  destination_state,
  destination_region,
  ROUND(CASE service_family WHEN 'Freight' THEN 180 + r_wt * 900 WHEN 'Ground' THEN 1 + r_wt * 44 ELSE 0.5 + r_wt * r_wt * 28 END, 1) AS weight_lb,
  (industry_vertical = 'Healthcare & Life Sciences' AND service_code IN ('PO','SO','IP') AND r_cold < 0.58) AS is_cold_chain,
  is_guaranteed_service,
  CAST(ROUND(list_rate_usd
      * (0.72 + 0.62 * r_rev)
      * CASE customer_tier WHEN 'Strategic' THEN 0.78 WHEN 'Enterprise' THEN 0.86 WHEN 'Mid-Market' THEN 0.94 ELSE 1.0 END
      * IF(industry_vertical = 'Healthcare & Life Sciences' AND service_code IN ('PO','SO','IP') AND r_cold < 0.58, 1.55, 1.0), 2) AS NUMERIC) AS net_revenue_usd,
  committed_delivery_ts,
  IF(planned_delivery_ts <= {AS_OF}, planned_delivery_ts, NULL) AS delivered_ts,
  planned_delivery_ts AS estimated_delivery_ts,
  exception_reason,
  exception_category,
  (committed_delivery_ts <= {AS_OF}) AS is_commitment_due,
  CASE
    WHEN planned_delivery_ts <= {AS_OF} THEN 'Delivered'
    WHEN causes_delay AND exception_reason IN ('Missed Sort','Equipment Delay','Weather','Misrouted') THEN 'Held at Hub'
    WHEN causes_delay THEN 'Exception Hold'
    WHEN TIMESTAMP_DIFF(planned_delivery_ts, {AS_OF}, HOUR) <= 9 AND pickup_ts < TIMESTAMP_SUB({AS_OF}, INTERVAL 10 HOUR) THEN 'Out for Delivery'
    ELSE 'In Transit'
  END AS package_status,
  CASE
    WHEN NOT causes_delay AND planned_delivery_ts <= {AS_OF} THEN 'On Time'
    WHEN NOT causes_delay THEN 'In Transit · On Plan'
    WHEN committed_delivery_ts <= {AS_OF} AND exception_category = 'Controllable' THEN 'Late · Within Our Control'
    WHEN committed_delivery_ts <= {AS_OF} THEN 'Late · Outside Our Control'
    ELSE 'At Risk · Delay Expected'
  END AS service_outcome,
  IF(causes_delay, ROUND(delay_hours, 1), NULL) AS hours_late,
  (is_guaranteed_service AND causes_delay AND exception_category = 'Controllable') AS is_guarantee_refund_eligible
FROM numbered;
"""
res = q(SHIP_SQL)
print("shipments created; bytes:", res.get("totalBytesProcessed"))

for r in bq_rows(f"""
SELECT COUNT(*) AS n, COUNT(DISTINCT tracking_number) AS distinct_trk, MIN(ship_date) AS d0, MAX(ship_date) AS d1,
       ROUND(SUM(net_revenue_usd)) AS rev, COUNTIF(exception_reason IS NOT NULL) AS exc
FROM `{P}.{DS}.shipments`""", LOC):
  print(r)
