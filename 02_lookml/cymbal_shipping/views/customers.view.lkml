view: customers {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.customers` ;;
  label: "Customers"

  dimension: customer_id {
    primary_key: yes
    type: string
    label: "Customer Account Number"
    description: "Cymbal Shipping account number for the shipper."
    sql: ${TABLE}.customer_id ;;
  }

  dimension: customer_name {
    type: string
    label: "Customer"
    description: "Name of the shipper, the business that pays for the shipment. Also called account or shipper."
    sql: ${TABLE}.customer_name ;;
  }

  dimension: industry_vertical {
    type: string
    label: "Industry"
    description: "Industry the customer operates in: Healthcare & Life Sciences, Technology & Electronics, Retail & E-commerce, Automotive & Industrial, or Financial & Legal Documents."
    sql: ${TABLE}.industry_vertical ;;
  }

  dimension: customer_tier {
    type: string
    label: "Account Tier"
    description: "Account tier set by Sales. Strategic accounts are our largest named customers and have a dedicated account director; then Enterprise, Mid-Market, and Small Business."
    sql: ${TABLE}.customer_tier ;;
    order_by_field: customer_tier_sort
  }

  dimension: customer_tier_sort {
    hidden: yes
    type: number
    sql: CASE ${TABLE}.customer_tier WHEN 'Strategic' THEN 1 WHEN 'Enterprise' THEN 2 WHEN 'Mid-Market' THEN 3 ELSE 4 END ;;
  }

  dimension: is_strategic_account {
    type: yesno
    label: "Is Strategic Account"
    description: "Yes for customers in the Strategic account tier."
    sql: ${TABLE}.customer_tier = 'Strategic' ;;
  }

  dimension: account_director {
    type: string
    label: "Account Director"
    description: "Cymbal Shipping account director who owns the customer relationship."
    sql: ${TABLE}.account_director ;;
  }

  dimension: hq_city {
    type: string
    label: "Customer HQ City"
    description: "City of the customer headquarters."
    sql: ${TABLE}.hq_city ;;
  }

  dimension: hq_state {
    type: string
    label: "Customer HQ State"
    description: "State of the customer headquarters."
    map_layer_name: us_states
    sql: ${TABLE}.hq_state ;;
  }

  dimension: primary_hub_code {
    type: string
    label: "Customer Primary Hub Code"
    description: "Hub that normally sorts most of this customer's volume."
    sql: ${TABLE}.primary_hub_code ;;
  }

  measure: customer_count {
    type: count_distinct
    label: "Customers"
    description: "Number of distinct customers."
    sql: ${customer_id} ;;
    drill_fields: [customer_name, industry_vertical, customer_tier, account_director]
  }
}
