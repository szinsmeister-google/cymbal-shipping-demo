-- =========================================================================
-- Repository: kc-enrichment-bi-finance
-- File: data_semantics/sql/02_views_and_filter_conventions.sql
-- Purpose: Authoritative SQL filter conventions for Cymbal Shipping BI & Finance
-- =========================================================================

-- 1. Governed On-Time Delivery Rate (Excuses Weather, Customs, Recipient Unavailable, Address)
-- Target: 97.5% across Priority Overnight and guaranteed services
CREATE OR REPLACE VIEW `YOUR_GCP_PROJECT_ID.cymbal_shipping.v_governed_hub_otd` AS
SELECT
  h.hub_id,
  h.hub_name,
  s.reporting_period,
  s.service_type,
  COUNT(s.tracking_number) AS total_packages,
  COUNTIF(s.is_on_time_governed) AS on_time_packages,
  ROUND(100.0 * SAFE_DIVIDE(COUNTIF(s.is_on_time_governed), COUNT(s.tracking_number)), 1) AS on_time_delivery_rate_pct,
  SUM(CASE WHEN s.is_guarantee_refund_eligible THEN s.shipping_charge_usd ELSE 0 END) AS revenue_at_risk_usd
FROM `YOUR_GCP_PROJECT_ID.cymbal_shipping.shipments` AS s
JOIN `YOUR_GCP_PROJECT_ID.cymbal_shipping.hubs` AS h
  ON s.origin_hub_id = h.hub_id
GROUP BY 1, 2, 3, 4;

-- 2. Strategic Healthcare Cold Chain Aging & Excursion Exposure at Memphis SuperHub (MEM)
CREATE OR REPLACE VIEW `YOUR_GCP_PROJECT_ID.cymbal_shipping.v_strategic_cold_chain_exposure` AS
SELECT
  c.customer_name,
  c.account_director,
  COUNT(DISTINCT s.tracking_number) AS aging_cold_chain_packages,
  SUM(CASE WHEN s.is_guarantee_refund_eligible THEN s.shipping_charge_usd ELSE 0 END) AS revenue_at_risk_usd,
  COUNTIF(e.has_temp_excursion) AS temperature_excursions,
  MAX(e.max_recorded_temp_c) AS peak_recorded_temp_c
FROM `YOUR_GCP_PROJECT_ID.cymbal_shipping.shipments` AS s
JOIN `YOUR_GCP_PROJECT_ID.cymbal_shipping.customers` AS c
  ON s.customer_id = c.customer_id
JOIN `YOUR_GCP_PROJECT_ID.cymbal_shipping.live_package_tracking` AS l
  ON s.tracking_number = l.tracking_number
LEFT JOIN `YOUR_GCP_PROJECT_ID.cymbal_shipping.exception_evidence` AS e
  ON s.tracking_number = e.tracking_number
WHERE c.account_tier = 'Strategic'
  AND c.industry_vertical = 'Healthcare'
  AND s.is_cold_chain = TRUE
  AND l.is_aging = TRUE
  AND l.current_hub_id = 'MEM'
GROUP BY 1, 2;
