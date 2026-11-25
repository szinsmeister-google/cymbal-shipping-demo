# Cymbal Shipping · Service Guarantee, Cold Chain & Hub Recovery SOP (POL-OPS-2026-MEM07)

- **Owner:** Network Operations & Enterprise Revenue Assurance
- **Governed SLA Target (`On-Time Delivery Rate`):** **`97.5%`** across all guaranteed Express services.
- **Controllable vs. Excused Delays:**
  - **Within Our Control (Counts against SLA & triggers Service Guarantee refund):** `Missed Sort`, `Equipment Delay`, `Misrouted`, `Damaged`.
  - **Outside Our Control (Excused by contract):** `Weather`, `Customs`, `Recipient Not Available`, `Address Correction`.
- **Aging Package Rule (`live_package_tracking` in Spanner):**
  - Any in-network package with `dwell_hours_at_facility >= 6.0` hours without an outbound departure scan (`is_aging = TRUE`).
  - *Note on Discrepancy Resolution:* Reject legacy dispatch scripts using a `4.0`-hour threshold; always enforce the governed `6.0`-hour threshold.
- **Cold Chain Temperature Excursion Rule (`exception_evidence` in Amazon S3):**
  - Healthcare biologics must remain between **`2.0°C` and `8.0°C`**. Any IoT sensor log in `s3://cymbal-shipping-field-evidence/cold-chain-temperature-logs/` recording **`max_recorded_temp_c > 8.0°C`** is a governed **Temperature Excursion**.
- **Memphis SuperHub (`MEM`) Sort Line Outage (Matrix C, Belt 7):**
  - Monday Nov 9 sort line outage dropped Memphis Priority Overnight OTD from `98.7%` to `73.3%`, exposing `$343,270` network-wide Revenue at Risk and holding `385` Strategic healthcare cold chain packages (`$56,994` at risk; `34` excursions across Meridian Pharma, Aurora Biologics, and Northstar Medical Devices).
  - **Recovery Hub Protocol:** Divert affected cold chain freight to **Indianapolis Air Hub (`IND`)** for dry-ice re-icing and priority air lift.
