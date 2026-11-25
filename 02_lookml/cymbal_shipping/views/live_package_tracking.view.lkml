view: live_package_tracking {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.live_package_tracking` ;;
  label: "Live Tracking"

  dimension: tracking_number {
    primary_key: yes
    hidden: yes
    type: string
    sql: ${TABLE}.tracking_number ;;
  }

  dimension: current_hub_code {
    type: string
    label: "Current Hub Code"
    description: "Hub where the package is right now, or the hub it last left."
    sql: ${TABLE}.current_hub_code ;;
  }

  dimension: last_scan_type {
    type: string
    label: "Last Scan"
    description: "Plain-language description of the most recent scan on the package."
    sql: ${TABLE}.last_scan_type ;;
  }

  dimension_group: last_scan {
    type: time
    timeframes: [raw, time, date]
    label: "Last Scan"
    description: "When the package was last scanned."
    sql: ${TABLE}.last_scan_ts ;;
  }

  dimension: hub_dwell_hours {
    type: number
    label: "Hours Held at Hub"
    description: "Hours the package has been sitting at its current hub since it arrived. Also called dwell time."
    value_format_name: decimal_1
    sql: ${TABLE}.hub_dwell_hours ;;
  }

  dimension: dwell_band {
    type: string
    label: "Time Held at Hub"
    description: "How long the package has been held at its hub, grouped into bands."
    sql: CASE
           WHEN ${TABLE}.hub_dwell_hours >= 24 THEN '24+ hours'
           WHEN ${TABLE}.hub_dwell_hours >= 12 THEN '12 to 24 hours'
           WHEN ${TABLE}.hub_dwell_hours >= 6 THEN '6 to 12 hours'
           WHEN ${TABLE}.hub_dwell_hours > 0 THEN 'Under 6 hours'
           ELSE 'Moving' END ;;
    order_by_field: dwell_band_sort
  }

  dimension: dwell_band_sort {
    hidden: yes
    type: number
    sql: CASE
           WHEN ${TABLE}.hub_dwell_hours >= 24 THEN 1
           WHEN ${TABLE}.hub_dwell_hours >= 12 THEN 2
           WHEN ${TABLE}.hub_dwell_hours >= 6 THEN 3
           WHEN ${TABLE}.hub_dwell_hours > 0 THEN 4
           ELSE 5 END ;;
  }

  dimension: is_aging {
    type: yesno
    label: "Is Aging Package"
    description: "Yes when a package has been held at a hub for 6 hours or more. Aging packages need a recovery plan."
    sql: ${TABLE}.is_aging ;;
  }

  dimension: recovery_plan {
    type: string
    label: "Recovery Plan"
    description: "What operations is doing to get a delayed package moving again."
    sql: ${TABLE}.recovery_plan ;;
  }

  measure: packages_in_network {
    type: count_distinct
    sql: ${tracking_number} ;;
    label: "Packages in the Network Now"
    description: "Packages picked up but not yet delivered, from the live Spanner tracking record."
    value_format_name: decimal_0
  }

  measure: aging_packages {
    type: count
    label: "Aging Packages"
    description: "Packages held at a hub for 6 hours or more right now."
    filters: [is_aging: "yes"]
    value_format_name: decimal_0
    drill_fields: [shipments.tracking_number, customers.customer_name, services.service_name, hubs.hub_name, hub_dwell_hours, recovery_plan]
  }

  measure: average_hours_held {
    type: average
    label: "Average Hours Held at Hub"
    description: "Average hours held at the hub, for aging packages."
    value_format_name: decimal_1
    sql: ${hub_dwell_hours} ;;
    filters: [is_aging: "yes"]
  }
}
