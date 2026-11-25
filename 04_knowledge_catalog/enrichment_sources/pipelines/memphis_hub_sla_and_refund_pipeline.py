"""Cymbal Shipping Network Operations & Hub Close ETL Pipeline.

Repository: kc-enrichment-bi-finance / pipelines/memphis_hub_sla_and_refund_pipeline.py
"""
import dataclasses


# =========================================================================
# Pipeline Constants & Business Rules
# =========================================================================

DEFAULT_PROJECT_ID = "YOUR_GCP_PROJECT_ID"
DEFAULT_DATASET_ID = "cymbal_shipping"
SCORECARD_TABLE_ID = "shipments"

# Company-wide On-Time Delivery Rate target (97.5% SLA benchmark)
ON_TIME_SLA_TARGET_PCT: float = 0.975

# Minimum hub dwell time (hours) before an in-network package is flagged as an Aging Package
# NOTE: Governed Service Desk standard is 6.0 hours (legacy sort script used 4.0 hours)
AGING_DWELL_THRESHOLD_HOURS: float = 6.0

# Cold chain healthcare logger threshold (2.0C to 8.0C safe range; >8.0C = Temperature Excursion)
COLD_CHAIN_MIN_TEMP_CELSIUS: float = 2.0
COLD_CHAIN_MAX_TEMP_CELSIUS: float = 8.0

# Delay classifications for On-Time Delivery Rate and Service Guarantee Refund eligibility
CONTROLLABLE_DELAY_REASONS: tuple[str, ...] = (
    "Missed Sort",
    "Equipment Delay",
    "Misrouted",
    "Damaged",
)
EXCUSED_DELAY_REASONS: tuple[str, ...] = (
    "Weather",
    "Customs",
    "Recipient Not Available",
    "Address Correction",
)

# Express & International services backed by the money-back Service Guarantee
GUARANTEED_SERVICES: tuple[str, ...] = (
    "Priority Overnight",
    "Standard Overnight",
    "2-Day",
    "Express Saver",
    "International Priority",
)


@dataclasses.dataclass(frozen=True)
class HubCloseJobConfig:
    """Runtime configuration for the Weekly Hub SLA & Revenue at Risk ETL pipeline."""

    project_id: str = DEFAULT_PROJECT_ID
    dataset_id: str = DEFAULT_DATASET_ID
    target_table_id: str = SCORECARD_TABLE_ID
    sla_target_pct: float = ON_TIME_SLA_TARGET_PCT
    aging_dwell_hours: float = AGING_DWELL_THRESHOLD_HOURS
    cold_chain_max_c: float = COLD_CHAIN_MAX_TEMP_CELSIUS
    dry_run: bool = False

    @property
    def target_fqn(self) -> str:
        return f"{self.project_id}.{self.dataset_id}.{self.target_table_id}"


def build_hub_sla_scorecard_sql(config: HubCloseJobConfig) -> str:
    """Constructs the governed BigQuery SQL query for hub SLA and Revenue at Risk."""
    return f"""
SELECT
  h.hub_name,
  s.service_type,
  COUNT(s.tracking_number) AS total_packages,
  SAFE_DIVIDE(
    COUNTIF(s.is_on_time_governed),
    COUNT(s.tracking_number)
  ) AS governed_on_time_rate,
  SUM(CASE WHEN s.is_guarantee_refund_eligible THEN s.shipping_charge_usd ELSE 0 END) AS revenue_at_risk_usd
FROM `{config.project_id}.{config.dataset_id}.shipments` AS s
JOIN `{config.project_id}.{config.dataset_id}.hubs` AS h
  ON s.origin_hub_id = h.hub_id
WHERE s.reporting_period = 'This Week'
GROUP BY 1, 2
"""
