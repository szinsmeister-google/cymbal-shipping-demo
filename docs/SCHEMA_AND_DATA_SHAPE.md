# Cymbal Shipping — Schema & Data Shape Ground-Truth Catalog

This document is the verified, ground-truth technical catalog for the **Cymbal Shipping** demo-as-code repository. Every table name, column, data type, row count, DDL statement, LookML measure, Knowledge Catalog object, and golden metric below is extracted directly from the runnable scripts and verified query outputs in this repository.

- **Synthetic Data Snapshot ("As Of"):** `2026-11-11 13:00:00 UTC` (Wednesday, November 11, 2026, 8:00 AM ET)
- **Date Range Covered:** `2026-10-01` through `2026-11-10` (41 ship days)
- **Reporting Periods (LookML `shipments.reporting_period`):**
  - `This Week`: `ship_date >= 2026-11-09` (`62,707` packages)
  - `Last Week`: `2026-11-02` to `2026-11-08` (`160,615` packages)
  - `Earlier`: `2026-10-01` to `2026-11-01` (`660,597` packages)
- **Embedded Operational Incidents (Deterministic via `FARM_FINGERPRINT`):**
  1. **Memphis SuperHub (`MEM`) Sort Line Outage (Controllable — Nov 9–10, 2026):** Matrix C, Belt 7 stopped at 11:52 PM CT on Nov 9 when the sort controller lost its connection to the scan tunnel; restored at 6:40 AM CT Nov 10 at reduced speed. Elevates controllable `Missed Sort` probability (`+26.5%` Nov 9, `+18.5%` Nov 10 on Express/International), driving Memphis Priority Overnight OTD down from `98.7%` to `73.3%`.
  2. **Denver Regional Hub (`DEN`) / Mountain Snowstorm (Uncontrollable — Oct 27–28, 2026):** Elevates uncontrollable `Weather` delay probability (`+23%` at DEN, `+9%` Mountain destination). Excused from official On-Time Delivery Rate (`98.3%`), while unadjusted Raw On-Time Rate drops to `89.0%`.
  3. **Newark Regional Hub (`EWR`) Weather Event (Uncontrollable — Oct 13, 2026):** `+11%` uncontrollable `Weather` probability.

---

## 1. BigQuery Analytical Lakehouse (`<GCP_PROJECT_ID>.cymbal_shipping`, region `us-east1`)

### Summary of Tables & Verified Row Counts

| Table / Object | Kind | Partitioning / Clustering | Columns | Verified Rows | Source / Role |
| :--- | :--- | :--- | ---: | ---: | :--- |
| `hubs` | Native Table | None | 10 | **10** | Sort hubs, gateways, capacities, backup recovery hubs |
| `services` | Native Table | None | 8 | **8** | Service catalog, commit SLA days/times, guarantee flag |
| `customers` | Native Table | None | 9 | **36** | Named accounts across 5 verticals & 4 commercial tiers |
| `shipments` | Native Table | Partition: `ship_date`; Cluster: `routing_hub_code, customer_id, service_code` | 23 | **883,919** | Package-level system of analysis (pickup, commit, outcome, revenue) |
| `live_package_tracking` | Native Table (Spanner replica) | Cluster: `current_hub_code, package_status` | 14 | **55,922** | Every in-network (undelivered) package, dwell hours, aging flag, recovery plan |
| `exception_evidence` | Native Table (extracted facts) | None | 14 | **863** | Structured facts + full text extracted from unstructured field reports |
| `field_evidence_objects` | External Object Table | `object_metadata = 'SIMPLE'` | Standard Object Table schema | **863 files** (`614,678` bytes) | Unstructured field-evidence files over GCS landing copy of Amazon S3 bucket |

---

### 1.1 `cymbal_shipping.hubs` (10 rows)

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `hub_code` | `STRING` | NOT NULL | Three-letter hub code (`MEM`, `IND`, `OAK`, `EWR`, `AFW`, `DEN`, `MIA`, `ANC`, `ORD`, `ATL`) |
| `hub_name` | `STRING` | NULLABLE | Business name (e.g., `Memphis SuperHub`, `Indianapolis Air Hub`) |
| `city` | `STRING` | NULLABLE | City where the hub operates |
| `state` | `STRING` | NULLABLE | Two-letter US state |
| `region` | `STRING` | NULLABLE | Operating region (`South`, `Midwest`, `West`, `Northeast`, `Southwest`, `Mountain`, `Southeast`, `Pacific`) |
| `hub_type` | `STRING` | NULLABLE | `Air SuperHub`, `National Air Hub`, `Regional Air Hub`, `International Gateway`, or `Ground Hub` |
| `daily_sort_capacity` | `INT64` | NULLABLE | Packages sortable in a normal 24-hour day (`190,000` to `1,450,000`) |
| `latitude` | `FLOAT64` | NULLABLE | Hub latitude |
| `longitude` | `FLOAT64` | NULLABLE | Hub longitude |
| `backup_hub_code` | `STRING` | NULLABLE | Assigned Recovery Hub for diversion routing (e.g., `MEM` → `IND`) |

### 1.2 `cymbal_shipping.services` (8 rows)

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `service_code` | `STRING` | NOT NULL | Two-letter code: `PO`, `SO`, `2D`, `ES`, `IP`, `GD`, `HD`, `FR` |
| `service_name` | `STRING` | NULLABLE | `Priority Overnight`, `Standard Overnight`, `2-Day`, `Express Saver`, `International Priority`, `Ground`, `Home Delivery`, `Freight Priority` |
| `service_family` | `STRING` | NULLABLE | `Express`, `International`, `Ground`, or `Freight` |
| `commit_days` | `INT64` | NULLABLE | Promised delivery days after pickup (`1`, `2`, `3`, or `4`) |
| `commit_time_local` | `STRING` | NULLABLE | Local commit cutoff (`10:30`, `12:00`, `16:30`, `17:00`, `20:00`) |
| `is_guaranteed_service` | `BOOL` | NULLABLE | `TRUE` for Express & International Priority (5 services); `FALSE` for Ground, Home Delivery, Freight Priority |
| `list_rate_usd` | `NUMERIC` | NULLABLE | Published base rate (`$17.00` to `$640.00`) |
| `sort_order` | `INT64` | NULLABLE | Display order (`1` to `8`, fastest to slowest) |

### 1.3 `cymbal_shipping.customers` (36 rows)

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | `STRING` | NOT NULL | Account ID (`C1001`–`C1036`) |
| `customer_name` | `STRING` | NULLABLE | Shipper name (e.g., `Meridian Pharma`, `Aurora Biologics`, `Northstar Medical Devices`) |
| `industry_vertical` | `STRING` | NULLABLE | `Healthcare & Life Sciences`, `Technology & Electronics`, `Retail & E-commerce`, `Automotive & Industrial`, `Financial & Legal Documents` |
| `customer_tier` | `STRING` | NULLABLE | `Strategic`, `Enterprise`, `Mid-Market`, `Small Business` |
| `primary_hub_code` | `STRING` | NULLABLE | Primary sorting hub code |
| `hq_city` | `STRING` | NULLABLE | Headquarters city |
| `hq_state` | `STRING` | NULLABLE | Headquarters state |
| `typical_weekday_packages` | `INT64` | NULLABLE | Baseline weekday volume (`140` to `2,260`) |
| `account_director` | `STRING` | NULLABLE | Assigned relationship owner (e.g., `Priya Raman`, `Marcus Bell`, `Elena Vasquez`) |

### 1.4 `cymbal_shipping.shipments` (883,919 rows)

- **Partitioned by:** `ship_date`
- **Clustered by:** `routing_hub_code, customer_id, service_code`

| Column | Type | Description |
| :--- | :--- | :--- |
| `tracking_number` | `STRING` | Unique 12-digit bijection (`78` + 10 digits) |
| `ship_date` | `DATE` | Pickup date (`2026-10-01` to `2026-11-10`) |
| `pickup_ts` | `TIMESTAMP` | Pickup timestamp (`America/New_York`, 3:00–8:00 PM) |
| `customer_id` | `STRING` | FK to `customers.customer_id` |
| `service_code` | `STRING` | FK to `services.service_code` |
| `routing_hub_code` | `STRING` | FK to `hubs.hub_code` |
| `destination_metro` | `STRING` | Destination metro (24 US metros) |
| `destination_state` | `STRING` | Destination US state |
| `destination_region` | `STRING` | Destination operating region |
| `weight_lb` | `FLOAT64` | Billable package weight (lb) |
| `is_cold_chain` | `BOOL` | `TRUE` for temperature-controlled Healthcare packages (`2–8°C`) on `PO`/`SO`/`IP` |
| `is_guaranteed_service` | `BOOL` | Copied from `services.is_guaranteed_service` |
| `net_revenue_usd` | `NUMERIC` | Billed shipping charge after tier discount & cold chain surcharge |
| `committed_delivery_ts` | `TIMESTAMP` | Promised delivery deadline (commit time) |
| `delivered_ts` | `TIMESTAMP` | Actual delivery timestamp (`NULL` if still in network as of snapshot) |
| `estimated_delivery_ts` | `TIMESTAMP` | Planned / current best estimated delivery timestamp |
| `exception_reason` | `STRING` | `Missed Sort`, `Equipment Delay`, `Misrouted`, `Damaged in Handling`, `Weather`, `Customs Hold`, `Recipient Not Available`, `Address Correction`, or `NULL` |
| `exception_category` | `STRING` | `Controllable`, `Uncontrollable`, or `NULL` |
| `is_commitment_due` | `BOOL` | `committed_delivery_ts <= TIMESTAMP '2026-11-11 13:00:00+00'` |
| `package_status` | `STRING` | `Delivered`, `Out for Delivery`, `In Transit`, `Held at Hub`, or `Exception Hold` |
| `service_outcome` | `STRING` | `On Time`, `In Transit · On Plan`, `Late · Within Our Control`, `Late · Outside Our Control`, or `At Risk · Delay Expected` |
| `hours_late` | `FLOAT64` | Delay duration in hours (`NULL` if on plan/on time) |
| `is_guarantee_refund_eligible` | `BOOL` | `is_guaranteed_service AND causes_delay AND exception_category = 'Controllable'` |

### 1.5 `cymbal_shipping.live_package_tracking` (55,922 rows)

- **Clustered by:** `current_hub_code, package_status`
- **System of Record:** Cloud Spanner `cymbal_shipping_ops.PackageTracking` (federated via `cymbal_shipping_ops_spanner` external dataset and materialized in BigQuery for analytical speed).

| Column | Type | Description |
| :--- | :--- | :--- |
| `tracking_number` | `STRING` | NOT NULL; matches `shipments.tracking_number` |
| `customer_id` | `STRING` | Shipper account ID |
| `service_code` | `STRING` | Two-letter service code |
| `current_hub_code` | `STRING` | Hub holding or last transiting the package (`NULL` when Out for Delivery) |
| `package_status` | `STRING` | `In Transit`, `Out for Delivery`, `Held at Hub`, or `Exception Hold` |
| `last_scan_type` | `STRING` | Plain-language scan text (e.g., `Sort delayed – held at hub`) |
| `last_scan_ts` | `TIMESTAMP` | Timestamp of most recent scan |
| `hub_dwell_hours` | `FLOAT64` | Hours held at current hub (`0.0` when moving) |
| `is_aging` | `BOOL` | `TRUE` when `package_status = 'Held at Hub'` AND `dwell >= 6.0 hours` (`>= 360 min`) |
| `committed_delivery_ts` | `TIMESTAMP` | Promised delivery deadline |
| `estimated_delivery_ts` | `TIMESTAMP` | Current ETA |
| `recovery_plan` | `STRING` | Operational recovery instruction (e.g., `Priority recovery · re-iced, first flight via Indianapolis Air Hub`) |
| `is_cold_chain` | `BOOL` | Temperature-controlled flag |
| `updated_at` | `TIMESTAMP` | Operational refresh timestamp |

### 1.6 `cymbal_shipping.exception_evidence` (863 rows)

| Column | Type | Description |
| :--- | :--- | :--- |
| `evidence_id` | `STRING` | NOT NULL (`EV-204001`–`EV-204863`) |
| `tracking_number` | `STRING` | Matches `shipments.tracking_number` |
| `document_type` | `STRING` | One of 9 types: `Cold Chain Temperature Log`, `Hub Delay Notice`, `Damage Report`, `Customs Hold Notice`, `Delivery Attempt Note`, `Address Correction Request`, `Weather Advisory`, `Equipment Delay Report`, `Misroute Report` |
| `captured_ts` | `TIMESTAMP` | Capture timestamp |
| `captured_by` | `STRING` | Originating team (`Cold Chain Desk`, `Night Sort Operations`, `Delivery Driver`, etc.) |
| `hub_code` | `STRING` | Related hub code |
| `summary` | `STRING` | Plain-language extracted summary |
| `root_cause` | `STRING` | Standardized root cause (e.g., `Sort line outage (Matrix C, Belt 7)`) |
| `customer_impact` | `STRING` | Business impact (`Product quality review required`, `Claim opened`, etc.) |
| `is_temperature_excursion` | `BOOL` | `TRUE` when `Cold Chain Temperature Log` AND `max_temperature_c > 8.0` (`65` total rows) |
| `max_temperature_c` | `FLOAT64` | Peak logger reading in °C (Cold Chain logs only) |
| `minutes_out_of_range` | `INT64` | Minutes above 8.0°C (Cold Chain logs only) |
| `document_text` | `STRING` | Full unstructured text of the field evidence document |
| `document_uri` | `STRING` | `gs://<GCS_EVIDENCE_BUCKET>/field-evidence/YYYY/MM/DD/<HUB>/<type>_<tracking>.txt` |

### 1.7 External Object Table: `cymbal_shipping.field_evidence_objects` (863 files, 614,678 bytes)

```sql
CREATE OR REPLACE EXTERNAL TABLE `<GCP_PROJECT_ID>.cymbal_shipping.field_evidence_objects`
WITH CONNECTION `<GCP_PROJECT_ID>.us-east1.cymbal_shipping_lake`
OPTIONS (
  object_metadata = 'SIMPLE',
  uris = ['gs://<GCS_EVIDENCE_BUCKET>/field-evidence/*']
);
```

- Models the lakehouse landing copy of the upstream Amazon S3 bucket `s3://cymbal-shipping-field-evidence/` (cataloged in Knowledge Catalog with 3 prefixes: `hub-delay-notices/`, `cold-chain-temperature-logs/`, `driver-and-customs-reports/`).

---

## 2. Cloud Spanner Operational Database & Property Graph

- **Instance:** `cymbal-shipping-ops` (`regional-us-east1`, `100` processing units, `ENTERPRISE` edition)
- **Database:** `cymbal_shipping_ops`
- **BigQuery External Schema (Zero-Copy Read-In-Place):** `cymbal_shipping_ops_spanner` (`external_source = 'google-cloudspanner:/projects/<GCP_PROJECT_ID>/instances/cymbal-shipping-ops/databases/cymbal_shipping_ops'`)

### Verified Tables, Index, & Property Graph DDL

1. **`Hubs`** (`10` rows, `PRIMARY KEY (hub_code)`):
   - Columns: `hub_code STRING(8) NOT NULL`, `hub_name STRING(64)`, `city STRING(64)`, `state STRING(2)`, `region STRING(32)`, `hub_type STRING(32)`, `backup_hub_code STRING(8)`, `sort_status STRING(32)` (`Recovering` for `MEM`, `Normal` for other 9 hubs), `status_note STRING(400)`, `packages_held INT64`, `cold_chain_packages_held INT64`, `updated_at TIMESTAMP`.
2. **`PackageTracking`** (`55,922` rows, `PRIMARY KEY (tracking_number)`):
   - Columns: `tracking_number STRING(16) NOT NULL`, `customer_id STRING(16)`, `service_code STRING(4)`, `current_hub_code STRING(8)`, `package_status STRING(32)`, `last_scan_type STRING(64)`, `last_scan_ts TIMESTAMP`, `hub_dwell_hours FLOAT64`, `is_aging BOOL`, `committed_delivery_ts TIMESTAMP`, `estimated_delivery_ts TIMESTAMP`, `recovery_plan STRING(160)`, `is_cold_chain BOOL`, `updated_at TIMESTAMP`.
   - Secondary Index: `CREATE INDEX PackageTrackingByHub ON PackageTracking (current_hub_code, package_status)`
   - Top aging hubs verified directly in Spanner: `Memphis SuperHub` (`2,592` aging, `751` cold chain), `Chicago Ground Hub` (`234`, `1`), `Atlanta Ground Hub` (`204`, `1`), `Indianapolis Air Hub` (`142`, `9`), `Oakland Regional Hub` (`104`, `1`).
3. **`RecoveryLanes`** (`10` rows, `PRIMARY KEY (from_hub_code, to_hub_code)`):
   - Columns: `from_hub_code STRING(8) NOT NULL`, `to_hub_code STRING(8) NOT NULL`, `lane_status STRING(32)` (`Active – diverting volume` for `MEM -> IND`; `Standby` for other 9), `next_departure_local STRING(32)` (`Tonight 10:40 PM CT` for `MEM -> IND`), `packages_diverted INT64`.
4. **Spanner Property Graph (`ShippingNetwork`):**

```sql
CREATE PROPERTY GRAPH ShippingNetwork
  NODE TABLES (
    Hubs KEY (hub_code) LABEL Hub
      PROPERTIES (hub_code, hub_name, city, state, region, hub_type, sort_status, status_note, packages_held, cold_chain_packages_held)
  )
  EDGE TABLES (
    RecoveryLanes KEY (from_hub_code, to_hub_code)
      SOURCE KEY (from_hub_code) REFERENCES Hubs (hub_code)
      DESTINATION KEY (to_hub_code) REFERENCES Hubs (hub_code)
      LABEL RECOVERS_VIA PROPERTIES (from_hub_code, to_hub_code, lane_status, next_departure_local, packages_diverted)
  )
```

---

## 3. LookML Semantic Layer (`02_lookml/cymbal_shipping/`)

- **Project / Model:** `cymbal_shipping` (label: `Cymbal Shipping`, `week_start_day: monday`, `datagroup: cymbal_shipping_default` with `max_cache_age: "1 hour"`)
- **Explore:** `shipments` (label: `Shipments & Service Performance`)
- **Joins (all `left_outer` from `shipments`):**
  - `customers` (`many_to_one` on `customer_id`)
  - `services` (`many_to_one` on `service_code`)
  - `hubs` (`many_to_one` on `routing_hub_code = hub_code`)
  - `live_package_tracking` (`one_to_one` on `tracking_number`)
  - `exception_evidence` (`one_to_one` on `tracking_number`)

### All 22 Governed LookML Measures

| View | Measure | Type | Formula / Filter Logic |
| :--- | :--- | :--- | :--- |
| `shipments` | `package_count` | `count` | Total packages picked up |
| `shipments` | `packages_past_commit_time` | `count` | Filter: `is_commitment_due: "yes"` (OTD denominator) |
| `shipments` | `late_packages_within_our_control` | `count` | Filter: `service_outcome: "Late · Within Our Control"` |
| `shipments` | `late_packages_outside_our_control` | `count` | Filter: `service_outcome: "Late · Outside Our Control"` |
| `shipments` | `on_time_delivery_rate` | `number` | `1.0 - SAFE_DIVIDE(${late_packages_within_our_control}, NULLIF(${packages_past_commit_time}, 0))` (Official KPI; target `97.5%`) |
| `shipments` | `raw_on_time_rate` | `number` | `1.0 - SAFE_DIVIDE(${late_packages_within_our_control} + ${late_packages_outside_our_control}, NULLIF(${packages_past_commit_time}, 0))` (Unadjusted) |
| `shipments` | `on_time_target` | `max` | Constant `0.975` (`97.5%`) |
| `shipments` | `packages_with_exception` | `count` | Filter: `exception_reason: "-NULL"` |
| `shipments` | `packages_held_at_hub` | `count` | Filter: `package_status: "Held at Hub"` |
| `shipments` | `cold_chain_packages` | `count` | Filter: `is_cold_chain: "yes"` |
| `shipments` | `total_net_revenue` | `sum` | `SUM(${net_revenue_usd})` |
| `shipments` | `revenue_per_package` | `number` | `SAFE_DIVIDE(${total_net_revenue}, NULLIF(${package_count}, 0))` |
| `shipments` | `revenue_at_risk` | `sum` | `SUM(${net_revenue_usd})` filtered on `is_guarantee_refund_eligible: "yes"` |
| `shipments` | `guarantee_eligible_packages` | `count` | Filter: `is_guarantee_refund_eligible: "yes"` |
| `shipments` | `average_hours_late` | `average` | `AVG(${hours_late})` |
| `customers` | `customer_count` | `count_distinct` | `COUNT(DISTINCT ${customer_id})` |
| `live_package_tracking` | `packages_in_network` | `count_distinct` | `COUNT(DISTINCT ${tracking_number})` |
| `live_package_tracking` | `aging_packages` | `count` | Filter: `is_aging: "yes"` (`>= 6.0` hours held at hub) |
| `live_package_tracking` | `average_hours_held` | `average` | `AVG(${hub_dwell_hours})` filtered on `is_aging: "yes"` |
| `exception_evidence` | `document_count` | `count_distinct` | `COUNT(DISTINCT ${evidence_id})` |
| `exception_evidence` | `temperature_excursions` | `count` | Filter: `is_temperature_excursion: "yes"` (`> 8.0°C`) |
| `exception_evidence` | `highest_temperature_c` | `max` | `MAX(${max_temperature_c})` |

### Native Looker Content & Looker Data App
- **Native Looker Dashboard (`02_lookml/07_native_looker_dashboard.py`):** `"Cymbal Shipping Service Performance (This week)"` in folder `Cymbal Shipping` — 1 header text tile + **14 vis tiles** (6 KPI single-value tiles, 6 cartesian charts, 2 grids), **5 dashboard filters** (`Account Tier`, `Industry`, `Customer`, `Hub`, `Service`), cross-filtering enabled.
- **2 Saved Looks:**
  1. `Cymbal Shipping · Priority Overnight On-Time Delivery by Hub (this week vs last week)`
  2. `Cymbal Shipping · Strategic Healthcare Cold Chain Packages Aging at Memphis`
- **Looker Data App (`03_looker_data_app/app.js`, Toolkit `1.3.0`):** Single-file web component (`cymbal-shipping-service-performance`) featuring Look-it-up search bar, verified double-check marks, 14-term embedded glossary, 5 KPI cards, 5 cross-filtered charts, Aging Package `app-grid`, Field Reports feed, and tracking-number lookup drawer.

---

## 4. Knowledge Catalog Governance Fabric (region `us-east1`)

### 4.1 Business Glossary (`cymbal-shipping-glossary` — 14 Terms)
1. `on-time-delivery-rate` (Target `97.5%`, controllable delays only)
2. `commit-time` (Promised delivery day & local cutoff)
3. `service-guarantee` (Money-back promise on 5 Express/International services)
4. `revenue-at-risk` (Refund-eligible shipping charges)
5. `delay-within-our-control` (`Missed Sort`, `Equipment Delay`, `Misrouted`, `Damaged in Handling`)
6. `delay-outside-our-control` (`Weather`, `Customs Hold`, `Recipient Not Available`, `Address Correction`)
7. `missed-sort` (Missed outbound flight/truck cut-off; controllable)
8. `aging-package` (`>= 6.0` hours held at hub in Spanner)
9. `cold-chain-shipment` (Healthcare `2–8°C` logger-tracked shipment)
10. `temperature-excursion` (Cold chain reading `> 8.0°C` in field logs)
11. `strategic-account` (`Account Tier = Strategic`, dedicated Account Director)
12. `recovery-hub` (Backup hub absorbing diverted volume, e.g., `MEM` → `IND`)
13. `revenue-per-package` (Yield = `Shipping Revenue / Packages`)
14. `field-evidence` (Unstructured driver/hub notes from Amazon S3)

### 4.2 Context Set (`cymbal-shipping-context-set` — 26 Entries)
- **Pass 1 (`04_wire_knowledge_catalog.py` — 21 entries):**
  - 4 Looker semantic entries: Explore `shipments`, views `shipments`, `live_package_tracking`, `exception_evidence`
  - 7 BigQuery entries: `shipments`, `customers`, `services`, `hubs`, `live_package_tracking`, `exception_evidence`, `field_evidence_objects`
  - 2 Cloud Spanner entries: `PackageTracking`, `Hubs`
  - 1 Amazon S3 entry: `cymbal-shipping-field-evidence`
  - 7 Headline Glossary Terms: `on-time-delivery-rate`, `revenue-at-risk`, `service-guarantee`, `aging-package`, `cold-chain-shipment`, `temperature-excursion`, `strategic-account`
- **Pass 2 (`06_catalog_app_and_agent.py` — +2 entries → 23):**
  - `Cymbal Shipping · Service Performance (Looker Data App)`
  - `Cymbal Shipping Service Desk (Gemini agent)`
- **Pass 3 (`08_catalog_looker_environment.py` — +3 entries → 26 total):**
  - Native Looker dashboard `Cymbal Shipping Service Performance (This week)`
  - 2 Saved Looks (Priority Overnight by Hub; Strategic Healthcare Cold Chain Aging at Memphis)

### 4.3 Graph Links & Custom Entry Groups
- **BigQuery `schema-join` links (7):** `shipments↔customers`, `shipments↔services`, `shipments↔hubs`, `shipments↔live_package_tracking`, `shipments↔exception_evidence`, `exception_evidence↔field_evidence_objects`, `live_package_tracking↔hubs`.
- **Cross-system `reference` links:** Looker Explore/Views/Dashboard/Tiles/Looks ↔ BigQuery tables ↔ Spanner (`PackageTracking`, `Hubs`, `RecoveryLanes`) ↔ Amazon S3 (`cymbal-shipping-aws-s3` bucket + 3 folders) ↔ Apps & Agents (`cymbal-shipping-apps`).
- **Glossary `definition` links:** `22` column-level schema definition links across Looker, BigQuery, and Spanner + `1` entry-level fallback reference (`field-evidence` → S3 bucket).

### 4.4 Autonomous Enrichment Agent (55 Proposals)
- **Source Files (`04_knowledge_catalog/enrichment_sources/`, 6 files across 5 signal categories):**
  1. `pipelines/memphis_hub_sla_and_refund_pipeline.py` (Python ETL production constants: `0.975`, `6.0h`, `8.0°C`, controllable vs. excused tuples)
  2. `pipelines/legacy_hub_dispatch_alerts.py` (Legacy conflict script: `4.0h`, `INCLUDE_WEATHER_IN_SLA_BREACH = True`, `7.5°C`)
  3. `dataform/fct_customer_sla_and_cold_chain_risk.sqlx` (Dataform incremental mart + `cold_chain_risk_band` CASE logic)
  4. `data_semantics/sql/02_views_and_filter_conventions.sql` (Authoritative BI/Finance SQL views)
  5. `data_semantics/graph/cymbal_shipping_network_lineage_graph.gql` (ISO GQL Property Graph definition)
  6. `docs/cymbal_shipping_service_guarantee_and_cold_chain_sop.md` (`POL-OPS-2026-MEM07` SOP)
- **Human-in-the-Loop (HITL) Discrepancies Caught & Resolved across 55 Staged Proposals:**
  - Aging dwell threshold: rejects legacy `4.0h` → enforces governed **`6.0h`**.
  - Weather & Customs delays: rejects legacy unexcused counting → enforces **excused** under Service Guarantee.
  - Cold chain excursion ceiling: rejects legacy `7.5°C` warning → enforces **`> 8.0°C`** excursion standard.

---

## 5. Gemini Agent (`Cymbal Shipping Service Desk`) & Verified Golden Numbers

- **Runtime:** Low-code Agent Designer (`discoveryengine.googleapis.com/v1alpha`), model `gemini-2.5-flash`.
- **Instruction Pattern (`05_gemini_agent/agent_instruction.txt`):** Knowledge Catalog glossary lookup first → Looker connector only (never raw BigQuery/Spanner SQL) → Saved Looks first → plain-language summary + compact table + "How this was measured" citation.
- **Connector Bindings (`09_fix_agent_tools.py` + `10_republish_agent.py`):** Tag-resolved `looker_mcp` connector (plus optional `bigquery_mcp` and `spanner` bindings), followed by `:deployLowCode` and `:publish` so the chat UI loads the active revision's data sources.

### Verified Topline Metrics (from `cymbal_shipping` LookML Explore)

| Reporting Period | Packages | Official OTD Rate | Raw OTD Rate | Revenue at Risk | Aging Packages (6+ hrs) | Temp Excursions (>8°C) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **This Week** (Nov 9–10) | `62,707` | **`88.5%`** | `87.6%` | **`$343,270`** (`$343,269.93`) | **`3,304`** | **`65`** |
| **Last Week** (Nov 2–8) | `160,615` | `98.4%` | `96.9%` | `$128,452` (`$128,452.04`) | `288` | `0` |
| **Earlier** (Oct 1–Nov 1) | `660,597` | `98.4%` | `96.8%` | `$537,878` (`$537,878.02`) | `0` | `0` |
| **Total (41 days)** | **`883,919`** | — | — | `$1,009,600` | `3,592` | **`65`** |

### Verified Memphis SuperHub Strategic Healthcare Exposure (Prompt 2)

| Customer | Account Director | Aging Cold Chain Pkgs | Avg Hours Held | Revenue at Risk | Temp Excursions | Peak Temp |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **Meridian Pharma** | Priya Raman | `202` | `21.9` | `$27,888` (`$27,887.89`) | `20` | `11.1°C` |
| **Aurora Biologics** | Priya Raman | `147` | `22.5` | `$21,231` (`$21,231.19`) | `7` | `10.3°C` |
| **Northstar Medical Devices** | Marcus Bell | `36` | `25.4` | `$7,875` (`$7,874.83`) | `7` | `10.9°C` |
| **Total** | | **`385`** | | **`$56,994`** (`$56,993.91`) | **`34`** | **`11.1°C`** |
