"""Legacy Hub Dispatch Alert Script (CONTAINS RULE DISCREPANCY FOR HITL REVIEW).

Repository: kc-enrichment-marketing-analytics / pipelines/legacy_hub_dispatch_alerts.py
"""

# DISCREPANCY NOTICE (Flagged by Knowledge Catalog Enrichment Agent):
# 1. Legacy local hub script uses `LEGACY_DWELL_HOURS = 4.0` instead of the governed
#    `AGING_DWELL_THRESHOLD_HOURS = 6.0` defined in the Service Guarantee policy.
# 2. Legacy script counts ALL late packages (`raw_late_flag = True`, including Weather
#    and Customs holds) toward refund exposure instead of filtering to
#    `delay_within_control = True` (`is_guarantee_refund_eligible = True`).

LEGACY_DWELL_HOURS: float = 4.0
INCLUDE_WEATHER_IN_SLA_BREACH: bool = True
COLD_CHAIN_WARNING_CELSIUS: float = 7.5
