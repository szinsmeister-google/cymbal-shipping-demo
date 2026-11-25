# Cymbal Shipping Service Desk — Demo Prompts & Golden Benchmarks

Use these prompts in the **Cymbal Shipping Service Desk** Gemini agent (all numbers grounded in the synthetic snapshot as of **Wednesday, November 11, 2026 at 8:00 AM ET**).

---

## Prompt 1: Priority Overnight On-Time Delivery by Hub (This Week vs. Last Week)

> **Prompt:**
> `How did on-time delivery for Priority Overnight hold up this week compared with last week, by hub? Which hubs are below target?`

### What this proves
- The Gemini agent resolves **On-Time Delivery Rate** (`97.5%` target; only controllable delays count; Weather, Customs, Recipient Not Available, and Address Correction are excused) from the Knowledge Catalog Business Glossary and Looker semantic model (`cymbal_shipping` / `shipments`).
- Using the Looks-first instruction (`agent_instruction.txt`), it runs the governed Saved Look (`Cymbal Shipping · Priority Overnight On-Time Delivery by Hub (this week vs last week)`) and returns exact numbers matching the Looker Data App.

### Verified Golden Benchmark
- **Below 97.5% Target This Week (2 hubs):**
  - **Memphis SuperHub:** `73.3%` this week vs. `98.7%` last week (`2,637` packages past commit, `703` late within our control)
  - **Anchorage Gateway:** `94.9%` this week vs. `99.2%` last week (`98` packages past commit, `5` late within our control)
- **At or Above Target (8 hubs):**
  - Newark Regional Hub (`98.2%` vs. `98.6%`)
  - Atlanta Ground Hub (`98.5%` vs. `98.4%`)
  - Miami Gateway (`98.7%` vs. `98.9%`)
  - Indianapolis Air Hub (`98.7%` vs. `98.5%`)
  - Chicago Ground Hub (`98.7%` vs. `98.6%`)
  - Oakland Regional Hub (`98.8%` vs. `98.7%`)
  - Fort Worth Regional Hub (`98.9%` vs. `98.6%`)
  - Denver Regional Hub (`99.0%` vs. `98.9%`)

---

## Prompt 2: Strategic Healthcare Cold Chain Exposure at Memphis SuperHub

> **Prompt:**
> `Which Strategic healthcare customers have temperature-controlled packages aging at the Memphis SuperHub right now, how much revenue is at risk, and did any go out of temperature range?`

### What this proves
- Joins three live modalities through one governed LookML explore: **BigQuery** shipment history (`is_cold_chain`, `revenue_at_risk`), **Cloud Spanner** live operational tracking (`is_aging >= 6.0 hours`, `average_hours_held`), and **Amazon S3 / Lakehouse Object Table** cold chain temperature logs (`temperature_excursions > 8.0°C`, `highest_temperature_c`).

### Verified Golden Benchmark (`385` packages · `$56,994` Revenue at Risk · `34` excursions)

| Customer | Account Director | Aging Packages (6+ hrs) | Avg Hours Held | Revenue at Risk | Temp Excursions (>8°C) | Peak Temp |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **Meridian Pharma** | Priya Raman | 202 | 21.9 | $27,888 | 20 | 11.1°C |
| **Aurora Biologics** | Priya Raman | 147 | 22.5 | $21,231 | 7 | 10.3°C |
| **Northstar Medical Devices** | Marcus Bell | 36 | 25.4 | $7,875 | 7 | 10.9°C |
| **Total** | | **385** | | **$56,994** | **34** | **11.1°C** |

---

## Prompt 3 (Follow-up): Root Cause from Unstructured Field Reports

> **Prompt:**
> `Why are those packages delayed at Memphis, and what do the field reports say?`

### Verified Golden Benchmark
- Primary root cause across Memphis this week: **`Sort line outage (Matrix C, Belt 7)`** — `460` field evidence documents (`276` Cold Chain Temperature Logs recording `65` total network excursions + `184` Hub Delay Notices).
- Narrative detail from field documents: Matrix C, Belt 7 stopped at 11:52 PM CT on Monday, Nov 9 when the sort controller lost connection to the scan tunnel, restored at 6:40 AM CT Nov 10 at reduced speed, with affected cold chain freight re-iced and diverted to the **Indianapolis Air Hub (`IND`)** recovery lane.

---

## Prompt 4 (Governance Proof): Why Governed OTD Beats Raw OTD

> **Prompt:**
> `Show Denver Regional Hub's official On-Time Delivery Rate versus Raw On-Time Rate by ship week from October 19 to November 9.`

### Verified Golden Benchmark
- **Week of Oct 19:** Official `98.4%` vs. Raw `96.9%`
- **Week of Oct 26 (Mountain snowstorm Oct 27–28):** Official **`98.3%`** (above 97.5% target because weather delays are excused) vs. Raw **`89.0%`** (a 9.3-point false alarm if an ungrounded agent writes naive SQL!)
- **Week of Nov 2:** Official `98.5%` vs. Raw `97.4%`
