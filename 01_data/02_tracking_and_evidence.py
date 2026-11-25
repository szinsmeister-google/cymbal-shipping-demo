"""Create live_package_tracking (Spanner replica) and exception_evidence (field
evidence facts) in BigQuery `cymbal_shipping`. Idempotent."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib.gcp import BQ_DATASET as DS, BQ_LOCATION as LOC, PROJECT_ID as P, PROJECT_NUM, bq, bq_rows, env

AS_OF = "TIMESTAMP '2026-11-11 13:00:00+00'"
BUCKET = env("GCS_EVIDENCE_BUCKET", f"cymbal-shipping-field-evidence-{PROJECT_NUM}")
q = lambda sql: bq(sql, location=LOC)
H = lambda salt: f"(MOD(ABS(FARM_FINGERPRINT(CONCAT(s.tracking_number, '{salt}'))), 1000000) / 1000000.0)"

# ------------------------------------------------- live_package_tracking --
q(f"""
CREATE OR REPLACE TABLE `{P}.{DS}.live_package_tracking` (
  tracking_number STRING NOT NULL OPTIONS(description='12-digit tracking number. Matches shipments.tracking_number.'),
  customer_id STRING OPTIONS(description='Account number of the shipper.'),
  service_code STRING OPTIONS(description='Two-letter service code of the package.'),
  current_hub_code STRING OPTIONS(description='Hub where the package is right now, or the hub it last left. Empty once the package is on a delivery vehicle.'),
  package_status STRING OPTIONS(description='Where the package is in its journey right now: In Transit, Out for Delivery, Held at Hub, or Exception Hold.'),
  last_scan_type STRING OPTIONS(description='Plain-language description of the most recent scan on the package.'),
  last_scan_ts TIMESTAMP OPTIONS(description='Time of the most recent scan.'),
  hub_dwell_hours FLOAT64 OPTIONS(description='Hours the package has been sitting at its current hub since it arrived. Zero when the package is moving.'),
  is_aging BOOL OPTIONS(description='True when the package has been held at a hub for 6 hours or more (an Aging Package).'),
  committed_delivery_ts TIMESTAMP OPTIONS(description='Date and time we promised delivery (the commit time).'),
  estimated_delivery_ts TIMESTAMP OPTIONS(description='Current best estimate of when the package will be delivered.'),
  recovery_plan STRING OPTIONS(description='What operations is doing to get a delayed package moving again.'),
  is_cold_chain BOOL OPTIONS(description='True for temperature-controlled healthcare packages that must stay between 2 and 8 degrees Celsius.'),
  updated_at TIMESTAMP OPTIONS(description='When this tracking record was last refreshed from the operational system.')
)
CLUSTER BY current_hub_code, package_status
OPTIONS(description='Live status of every package that is still in the Cymbal Shipping network (picked up but not yet delivered). Replicated from the Spanner operations database (cymbal_shipping_ops.PackageTracking), which the hubs and scanners write to in real time. Use it to see what is held at a hub right now and for how long.');
""")
q(f"""
INSERT INTO `{P}.{DS}.live_package_tracking`
WITH s AS (
  SELECT sh.*, h.hub_name, bh.hub_name AS backup_hub_name
  FROM `{P}.{DS}.shipments` sh
  JOIN `{P}.{DS}.hubs` h ON h.hub_code = sh.routing_hub_code
  LEFT JOIN `{P}.{DS}.hubs` bh ON bh.hub_code = h.backup_hub_code
  WHERE sh.delivered_ts IS NULL
),
x AS (
  SELECT s.*,
    {H('a')} AS r1, {H('b')} AS r2, {H('c')} AS r3,
    LEAST(TIMESTAMP_ADD(s.pickup_ts, INTERVAL CAST(300 + {H('arr')} * 180 AS INT64) MINUTE), TIMESTAMP_SUB({AS_OF}, INTERVAL 20 MINUTE)) AS hub_arrival_ts
  FROM s
)
SELECT
  tracking_number, customer_id, service_code,
  IF(package_status IN ('Held at Hub','In Transit'), routing_hub_code, NULL) AS current_hub_code,
  package_status,
  CASE
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Missed Sort' THEN 'Sort delayed – held at hub'
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Weather' THEN 'Weather delay – held at hub'
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Equipment Delay' THEN 'Equipment delay – held at hub'
    WHEN package_status = 'Held at Hub' THEN 'Rerouting – held at hub'
    WHEN package_status = 'Exception Hold' AND exception_reason = 'Customs Hold' THEN 'Clearance delay – held by customs'
    WHEN package_status = 'Exception Hold' AND exception_reason = 'Recipient Not Available' THEN 'Delivery attempted – recipient not available'
    WHEN package_status = 'Exception Hold' AND exception_reason = 'Address Correction' THEN 'Address correction requested'
    WHEN package_status = 'Exception Hold' THEN 'Damage inspection in progress'
    WHEN package_status = 'Out for Delivery' THEN 'On vehicle for delivery'
    WHEN r1 < 0.45 THEN 'Departed hub'
    WHEN r1 < 0.80 THEN 'In transit to destination'
    ELSE 'Arrived at destination facility'
  END AS last_scan_type,
  CASE
    WHEN package_status = 'Held at Hub' THEN hub_arrival_ts
    WHEN package_status = 'Exception Hold' THEN GREATEST(pickup_ts, TIMESTAMP_SUB({AS_OF}, INTERVAL CAST(60 + r2 * 1140 AS INT64) MINUTE))
    WHEN package_status = 'Out for Delivery' THEN TIMESTAMP_SUB({AS_OF}, INTERVAL CAST(25 + r2 * 150 AS INT64) MINUTE)
    ELSE GREATEST(pickup_ts, TIMESTAMP_SUB({AS_OF}, INTERVAL CAST(15 + r2 * 330 AS INT64) MINUTE))
  END AS last_scan_ts,
  IF(package_status = 'Held at Hub', ROUND(TIMESTAMP_DIFF({AS_OF}, hub_arrival_ts, MINUTE) / 60.0, 1), 0.0) AS hub_dwell_hours,
  (package_status = 'Held at Hub' AND TIMESTAMP_DIFF({AS_OF}, hub_arrival_ts, MINUTE) >= 360) AS is_aging,
  committed_delivery_ts,
  estimated_delivery_ts,
  CASE
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Missed Sort' AND is_cold_chain THEN CONCAT('Priority recovery · re-iced, first flight via ', backup_hub_name)
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Missed Sort' AND r3 < 0.58 THEN CONCAT('Diverted to ', backup_hub_name, ' · tonight 10:40 PM')
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Missed Sort' THEN CONCAT('Next ', hub_name, ' sort · tonight 11:15 PM')
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Weather' THEN 'Holding for road reopening'
    WHEN package_status = 'Held at Hub' AND exception_reason = 'Equipment Delay' THEN 'Moved to replacement aircraft / trailer'
    WHEN package_status = 'Held at Hub' THEN 'Re-labeled and routed to correct hub'
    WHEN exception_reason = 'Customs Hold' THEN 'Broker working with shipper on paperwork'
    WHEN exception_reason = 'Recipient Not Available' THEN 'Redelivery scheduled next business day'
    WHEN exception_reason = 'Address Correction' THEN 'Waiting for shipper to confirm address'
    WHEN package_status = 'Exception Hold' THEN 'Inspection, then claim or redelivery'
    ELSE 'On plan – no action needed'
  END AS recovery_plan,
  is_cold_chain,
  {AS_OF} AS updated_at
FROM x;
""")

# ----------------------------------------------------- exception_evidence --
q(f"""
CREATE OR REPLACE TABLE `{P}.{DS}.exception_evidence` (
  evidence_id STRING NOT NULL OPTIONS(description='Identifier of the field evidence document.'),
  tracking_number STRING OPTIONS(description='Tracking number of the package the document is about. Matches shipments.tracking_number.'),
  document_type STRING OPTIONS(description='Kind of document: Hub Delay Notice, Cold Chain Temperature Log, Damage Report, Customs Hold Notice, Delivery Attempt Note, Address Correction Request, Weather Advisory, Equipment Delay Report, or Misroute Report.'),
  captured_ts TIMESTAMP OPTIONS(description='When the document was written or the reading was captured.'),
  captured_by STRING OPTIONS(description='Team or role that produced the document.'),
  hub_code STRING OPTIONS(description='Hub the document relates to.'),
  summary STRING OPTIONS(description='Plain-language summary of what the document says happened to the package.'),
  root_cause STRING OPTIONS(description='Standardized root cause taken from the document, for example Sort line outage (Matrix C, Belt 7).'),
  customer_impact STRING OPTIONS(description='What the event means for the shipper, for example Product quality review required.'),
  is_temperature_excursion BOOL OPTIONS(description='True when a cold chain package was recorded outside its required 2 to 8 degrees Celsius range.'),
  max_temperature_c FLOAT64 OPTIONS(description='Highest temperature recorded by the package logger, in degrees Celsius. Only for cold chain packages.'),
  minutes_out_of_range INT64 OPTIONS(description='Minutes the package spent above 8 degrees Celsius. Only for cold chain packages.'),
  document_text STRING OPTIONS(description='Full text of the field evidence document.'),
  document_uri STRING OPTIONS(description='Location of the document file in the field-evidence object store. Matches field_evidence_objects.uri.')
)
OPTIONS(description='Facts extracted from unstructured field evidence: hub delay notices, cold chain temperature logs, driver damage reports, and customs notices. One row per document. Drivers and hub teams capture the original files into the Cymbal Shipping field-evidence bucket in Amazon S3; the lakehouse landing copy is read through the object table field_evidence_objects. Use it to understand why a package is late and whether a temperature-controlled shipment was put at risk.');
""")
q(f"""
INSERT INTO `{P}.{DS}.exception_evidence`
WITH s AS (
  SELECT sh.*, h.hub_name, bh.hub_name AS backup_hub_name, sv.service_name, c.customer_name,
         t.hub_dwell_hours, t.recovery_plan
  FROM `{P}.{DS}.shipments` sh
  JOIN `{P}.{DS}.hubs` h ON h.hub_code = sh.routing_hub_code
  LEFT JOIN `{P}.{DS}.hubs` bh ON bh.hub_code = h.backup_hub_code
  JOIN `{P}.{DS}.services` sv USING (service_code)
  JOIN `{P}.{DS}.customers` c USING (customer_id)
  LEFT JOIN `{P}.{DS}.live_package_tracking` t USING (tracking_number)
  WHERE sh.exception_reason IS NOT NULL AND sh.ship_date >= DATE '2026-10-31'
),
picked AS (
  SELECT s.*, {H('pick')} AS r_pick, {H('t1')} AS r1, {H('t2')} AS r2, {H('t3')} AS r3, {H('t4')} AS r4
  FROM s
),
sel AS (
  SELECT * FROM picked
  WHERE CASE
    WHEN routing_hub_code = 'MEM' AND ship_date >= DATE '2026-11-09' AND exception_reason = 'Missed Sort' AND is_cold_chain THEN r_pick < 0.30
    WHEN routing_hub_code = 'MEM' AND ship_date >= DATE '2026-11-09' AND exception_reason = 'Missed Sort' THEN r_pick < 0.085
    WHEN exception_reason IN ('Damaged in Handling','Customs Hold') THEN r_pick < 0.11
    ELSE r_pick < 0.035 END
),
typed AS (
  SELECT sel.*,
    (routing_hub_code = 'MEM' AND ship_date >= DATE '2026-11-09' AND exception_reason = 'Missed Sort') AS is_mem_incident,
    REGEXP_REPLACE(FORMAT_TIMESTAMP('%b %e', committed_delivery_ts, 'America/New_York'), r'\\s+', ' ') AS commit_day,
    REGEXP_REPLACE(FORMAT_TIMESTAMP('%b %e by %l:%M %p ET', estimated_delivery_ts, 'America/New_York'), r'\\s+', ' ') AS new_eta,
    IF(ship_date <= DATE '2026-11-09',
       'The main sort line (Matrix C, Belt 7) stopped at 11:52 PM CT on Nov 9 when the sort controller lost its connection to the scan tunnel. This package was already inside the building but could not be sorted to its outbound flight before the cut-off.',
       'The main sort line (Matrix C, Belt 7) stopped on the night of Nov 9 and ran at reduced speed through the Nov 10 night sort while the backlog was cleared. This package arrived during the recovery and could not be sorted to its outbound flight before the cut-off.') AS incident_text,
    CASE
      WHEN routing_hub_code = 'MEM' AND ship_date >= DATE '2026-11-09' AND exception_reason = 'Missed Sort' AND is_cold_chain THEN 'Cold Chain Temperature Log'
      WHEN exception_reason = 'Missed Sort' THEN 'Hub Delay Notice'
      WHEN exception_reason = 'Equipment Delay' THEN 'Equipment Delay Report'
      WHEN exception_reason = 'Misrouted' THEN 'Misroute Report'
      WHEN exception_reason = 'Damaged in Handling' THEN 'Damage Report'
      WHEN exception_reason = 'Customs Hold' THEN 'Customs Hold Notice'
      WHEN exception_reason = 'Recipient Not Available' THEN 'Delivery Attempt Note'
      WHEN exception_reason = 'Address Correction' THEN 'Address Correction Request'
      ELSE 'Weather Advisory' END AS document_type,
    -- cold chain logger readings while held: longer holds drift warmer
    ROUND(CASE WHEN COALESCE(hub_dwell_hours, 0) >= 24 AND r1 < 0.46 THEN 8.3 + r2 * 2.9
               WHEN COALESCE(hub_dwell_hours, 0) >= 24 THEN 6.4 + r2 * 1.5
               WHEN r1 < 0.06 THEN 8.1 + r2 * 1.2
               ELSE 4.2 + r2 * 3.1 END, 1) AS max_temp_c
  FROM sel
),
facts AS (
  SELECT t.*,
    (t.document_type = 'Cold Chain Temperature Log' AND t.max_temp_c > 8.0) AS is_excursion,
    IF(t.document_type = 'Cold Chain Temperature Log' AND t.max_temp_c > 8.0, CAST(18 + r3 * 96 AS INT64), 0) AS mins_out,
    CASE
      WHEN is_mem_incident THEN 'Sort line outage (Matrix C, Belt 7)'
      WHEN exception_reason = 'Missed Sort' THEN 'Late inbound trailer missed sort cut-off'
      WHEN exception_reason = 'Equipment Delay' THEN IF(r4 < 0.5, 'Aircraft maintenance hold', 'Trailer breakdown en route')
      WHEN exception_reason = 'Misrouted' THEN 'Label scanned to wrong outbound lane'
      WHEN exception_reason = 'Damaged in Handling' THEN IF(r4 < 0.6, 'Carton crushed during unload', 'Liquid leak from adjacent package')
      WHEN exception_reason = 'Customs Hold' THEN IF(r4 < 0.55, 'Commercial invoice missing or incomplete', 'Declared value under review')
      WHEN exception_reason = 'Recipient Not Available' THEN IF(r4 < 0.5, 'Business closed at delivery attempt', 'No one available to sign')
      WHEN exception_reason = 'Address Correction' THEN IF(r4 < 0.5, 'Suite number missing', 'Street address does not match ZIP code')
      ELSE IF(routing_hub_code = 'DEN', 'Snow and ice – highway closure', 'Severe weather – ground stop') END AS root_cause
  FROM typed t
)
SELECT
  CONCAT('EV-', LPAD(CAST(ROW_NUMBER() OVER (ORDER BY ship_date, tracking_number) + 204000 AS STRING), 6, '0')) AS evidence_id,
  tracking_number,
  document_type,
  CASE
    WHEN is_mem_incident THEN TIMESTAMP_ADD(TIMESTAMP(DATETIME(DATE_ADD(ship_date, INTERVAL 1 DAY), TIME(3, 20, 0)), 'America/Chicago'), INTERVAL CAST(r4 * 380 AS INT64) MINUTE)
    ELSE TIMESTAMP_ADD(pickup_ts, INTERVAL CAST(420 + r4 * 1500 AS INT64) MINUTE)
  END AS captured_ts,
  CASE document_type
    WHEN 'Cold Chain Temperature Log' THEN 'Cold Chain Desk'
    WHEN 'Hub Delay Notice' THEN 'Night Sort Operations'
    WHEN 'Equipment Delay Report' THEN 'Linehaul & Air Operations'
    WHEN 'Misroute Report' THEN 'Hub Quality Team'
    WHEN 'Damage Report' THEN 'Delivery Driver'
    WHEN 'Customs Hold Notice' THEN 'Customs Brokerage'
    WHEN 'Delivery Attempt Note' THEN 'Delivery Driver'
    WHEN 'Address Correction Request' THEN 'Customer Support'
    ELSE 'Network Control Center' END AS captured_by,
  routing_hub_code AS hub_code,
  CASE
    WHEN document_type = 'Cold Chain Temperature Log' AND is_excursion THEN FORMAT('Temperature-controlled package from %s was held at %s after the sort line outage. The logger recorded a high of %.1f°C and %d minutes above the 8°C limit. The shipper must review product quality before use.', customer_name, hub_name, max_temp_c, mins_out)
    WHEN document_type = 'Cold Chain Temperature Log' THEN FORMAT('Temperature-controlled package from %s was held at %s after the sort line outage. It stayed within the required 2–8°C range (high of %.1f°C) and was re-iced for priority recovery.', customer_name, hub_name, max_temp_c)
    WHEN is_mem_incident THEN FORMAT('%s package from %s missed its outbound flight at %s because the main sort line stopped overnight. It is being recovered through %s.', service_name, customer_name, hub_name, COALESCE(backup_hub_name, 'the next scheduled sort'))
    WHEN document_type = 'Hub Delay Notice' THEN FORMAT('%s package from %s reached %s after the sort cut-off and moved on the next sort.', service_name, customer_name, hub_name)
    WHEN document_type = 'Equipment Delay Report' THEN FORMAT('%s package from %s was delayed leaving %s: %s.', service_name, customer_name, hub_name, LOWER(root_cause))
    WHEN document_type = 'Misroute Report' THEN FORMAT('%s package from %s was sent to the wrong outbound lane at %s and had to be re-labeled.', service_name, customer_name, hub_name)
    WHEN document_type = 'Damage Report' THEN FORMAT('Driver reported damage on a %s package from %s bound for %s: %s. Photos taken and a claim was opened.', service_name, customer_name, destination_metro, LOWER(root_cause))
    WHEN document_type = 'Customs Hold Notice' THEN FORMAT('International package from %s is held by customs: %s. Our broker is working with the shipper.', customer_name, LOWER(root_cause))
    WHEN document_type = 'Delivery Attempt Note' THEN FORMAT('Driver attempted delivery in %s for %s: %s. Redelivery is scheduled.', destination_metro, customer_name, LOWER(root_cause))
    WHEN document_type = 'Address Correction Request' THEN FORMAT('Delivery to %s for %s is on hold: %s. Waiting for the shipper to confirm.', destination_metro, customer_name, LOWER(root_cause))
    ELSE FORMAT('%s package from %s was delayed at %s by weather: %s.', service_name, customer_name, hub_name, LOWER(root_cause))
  END AS summary,
  root_cause,
  CASE
    WHEN document_type = 'Cold Chain Temperature Log' AND is_excursion THEN 'Product quality review required'
    WHEN document_type = 'Cold Chain Temperature Log' THEN 'Delayed – product within temperature range'
    WHEN document_type = 'Damage Report' THEN 'Claim opened'
    WHEN document_type = 'Customs Hold Notice' THEN 'Paperwork needed from shipper'
    WHEN document_type = 'Address Correction Request' THEN 'Address confirmation needed from shipper'
    ELSE 'Delivery delayed' END AS customer_impact,
  IF(document_type = 'Cold Chain Temperature Log', is_excursion, NULL) AS is_temperature_excursion,
  IF(document_type = 'Cold Chain Temperature Log', max_temp_c, NULL) AS max_temperature_c,
  IF(document_type = 'Cold Chain Temperature Log', mins_out, NULL) AS minutes_out_of_range,
  CASE
    WHEN document_type = 'Cold Chain Temperature Log' THEN FORMAT('''CYMBAL SHIPPING · COLD CHAIN TEMPERATURE LOG
Hub: %s (%s)
Tracking number: %s        Service: %s
Shipper: %s        Destination: %s, %s
Logger ID: TL-%d

Required range: 2.0°C to 8.0°C

Readings while the package was held at the hub
  Lowest reading:  %.1f°C
  Highest reading: %.1f°C
  Time above 8.0°C: %d minutes

Result: %s

Why the package was held
%s

Action taken
Gel packs were replaced and the package was moved to refrigerated hold R-2.

Recovery plan
%s. New estimated delivery: %s.

Prepared by: Cold Chain Desk, Memphis SuperHub''',
      hub_name, routing_hub_code, tracking_number, service_name, customer_name, destination_metro, destination_state,
      CAST(400000 + r4 * 99999 AS INT64), 2.6 + r3 * 1.4, max_temp_c, mins_out,
      IF(is_excursion, 'TEMPERATURE EXCURSION – shipper must review product quality before use.', 'WITHIN RANGE – no excursion recorded.'),
      incident_text,
      COALESCE(recovery_plan, 'Priority recovery on the first available flight'), new_eta)
    WHEN is_mem_incident THEN FORMAT('''CYMBAL SHIPPING · HUB DELAY NOTICE
Hub: %s (%s)
Tracking number: %s        Service: %s
Shipper: %s        Destination: %s, %s
Promised delivery: %s

What happened
%s This is a missed sort and is within our control.

Current handling
The package is in secure hold area H-14 and is scanned every 4 hours.

Recovery plan
%s. New estimated delivery: %s.

Service Guarantee
This shipment is covered by the Cymbal Shipping Service Guarantee. The shipper may claim a refund of the shipping charge.

Prepared by: Night Sort Operations, Memphis SuperHub''',
      hub_name, routing_hub_code, tracking_number, service_name, customer_name, destination_metro, destination_state, commit_day,
      incident_text,
      COALESCE(recovery_plan, 'Moving on the next scheduled sort'), new_eta)
    ELSE FORMAT('''CYMBAL SHIPPING · %s
Hub: %s (%s)
Tracking number: %s        Service: %s
Shipper: %s        Destination: %s, %s
Promised delivery: %s

What happened
%s.

Next step
%s. Current estimated delivery: %s.

Prepared by: Cymbal Shipping field operations''',
      UPPER(document_type), hub_name, routing_hub_code, tracking_number, service_name, customer_name, destination_metro, destination_state, commit_day,
      root_cause, COALESCE(recovery_plan, 'Package is moving again on the next available departure'), new_eta)
  END AS document_text,
  CONCAT('gs://{BUCKET}/field-evidence/', FORMAT_DATE('%Y/%m/%d', ship_date), '/', routing_hub_code, '/',
         REPLACE(LOWER(document_type), ' ', '-'), '_', tracking_number, '.txt') AS document_uri
FROM facts;
""")

for title, sql in [
    ("live tracking by status", f"SELECT package_status, COUNT(*) n, COUNTIF(is_aging) aging, ROUND(AVG(hub_dwell_hours),1) avg_dwell, ROUND(MAX(hub_dwell_hours),1) max_dwell FROM `{P}.{DS}.live_package_tracking` GROUP BY 1 ORDER BY 2 DESC"),
    ("aging by hub", f"SELECT current_hub_code, COUNT(*) n, COUNTIF(is_cold_chain) cold FROM `{P}.{DS}.live_package_tracking` WHERE is_aging GROUP BY 1 ORDER BY 2 DESC"),
    ("evidence by type", f"SELECT document_type, COUNT(*) n, COUNTIF(is_temperature_excursion) excursions, ROUND(AVG(max_temperature_c),1) avg_max_c FROM `{P}.{DS}.exception_evidence` GROUP BY 1 ORDER BY 2 DESC"),
    ("evidence root causes", f"SELECT root_cause, COUNT(*) n FROM `{P}.{DS}.exception_evidence` GROUP BY 1 ORDER BY 2 DESC"),
    ("sample doc", f"SELECT document_uri, summary, document_text FROM `{P}.{DS}.exception_evidence` WHERE is_temperature_excursion ORDER BY evidence_id LIMIT 1"),
    ("sample doc2", f"SELECT document_uri, summary, document_text FROM `{P}.{DS}.exception_evidence` WHERE document_type = 'Hub Delay Notice' AND hub_code='MEM' ORDER BY evidence_id DESC LIMIT 1"),
]:
  print("\n##", title)
  for r in bq_rows(sql, LOC):
    print("  ", " | ".join(str(v) for v in r.values()))
