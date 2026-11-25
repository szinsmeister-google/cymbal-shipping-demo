# Cymbal Shipping · Service Performance (Looker Data App)

`app.js` is a governed Looker Data App built with **Looker Data Apps Toolkit 1.3.0** (`cymbal-shipping-service-performance`). Every KPI, chart, table, and lookup card queries the same production LookML explore (`cymbal_shipping` / `shipments`), so numbers match the native Looker dashboard and the Gemini agent to the penny.

## What ships inside `app.js`

- **Look-it-up bar & instant shortcuts:** Type a customer name, sort hub, service, 12-digit tracking number (for example `7815 4378 2857`), or a business term (`on-time`, `revenue at risk`, `aging`) to open a verified answer card or filter the entire page.
- **Verified double-check marks:** Key metrics (`On-Time Delivery Rate`, `Revenue at Risk`) and glossary cards display a Luminous verification badge linking directly to the 14-term Cymbal Shipping Business Glossary definitions governed in Knowledge Catalog.
- **5 Governed KPI Cards:** Packages shipped, On-time delivery rate (against the 97.5% target), Revenue at risk (Service Guarantee refund exposure), Held 6+ hours at a hub (live Spanner tracking), and Temperature excursions (>8.0°C from Amazon S3 field logs).
- **Full cross-filtering across 5 interactive charts:**
  1. On-time delivery rate by ship day (official governed rate vs. unadjusted raw rate, with 97.5% target reference line)
  2. On-time delivery rate by hub (orange highlight for hubs below 97.5% target)
  3. Revenue at risk by customer
  4. Revenue at risk by service
  5. Delayed packages by reason (split visually into Within Our Control vs. Outside Our Control)
- **Operational recovery & unstructured field evidence:**
  - **Packages held 6+ hours right now** (`app-grid` sorted by dwell hours descending, showing live Spanner recovery plans)
  - **What the field reports say** (unstructured driver and hub notes extracted from the object-storage lake, with clickable package drill-down)

## Deploying `app.js` with Looker Data Apps Toolkit 1.3.0

1. Confirm the `cymbal_shipping` LookML project is deployed to production (`python3 02_lookml/deploy_lookml.py`).
2. Ensure your Looker instance has **Looker Data Apps** enabled (Toolkit 1.3.0 runtime at `/runtime/data-app.js`).
3. Create a Data App dashboard in your Looker `Cymbal Shipping` folder and upload `03_looker_data_app/app.js` using the Looker Data Apps CLI or Extension/Data Apps uploader (configured with your local, gitignored `data-apps-config.json`).
4. Record the resulting dashboard ID in `.env` as `LOOKER_DATA_APP_DASHBOARD_ID`, then register it in Knowledge Catalog:

```bash
python3 04_knowledge_catalog/06_catalog_app_and_agent.py "$LOOKER_DATA_APP_DASHBOARD_ID"
```
