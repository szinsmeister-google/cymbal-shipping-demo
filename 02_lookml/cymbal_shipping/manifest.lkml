project_name: "cymbal_shipping"

# Cymbal Shipping · Service Performance semantic model.
# Governed business definitions live here once and are reused by Looker,
# the Gemini agent (Looker connector) and Knowledge Catalog.

constant: gcp_project_id {
  value: "YOUR_GCP_PROJECT_ID"
  export: override_optional
}

constant: bq_dataset {
  value: "cymbal_shipping"
  export: override_optional
}
