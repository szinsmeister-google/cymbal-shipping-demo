view: services {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.services` ;;
  label: "Services"

  dimension: service_code {
    primary_key: yes
    type: string
    label: "Service Code"
    description: "Two-letter service code printed on the shipping label."
    sql: ${TABLE}.service_code ;;
  }

  dimension: service_name {
    type: string
    label: "Service"
    description: "Service the customer bought: Priority Overnight, Standard Overnight, 2-Day, Express Saver, International Priority, Ground, Home Delivery, or Freight Priority."
    sql: ${TABLE}.service_name ;;
    order_by_field: sort_order
  }

  dimension: service_family {
    type: string
    label: "Service Family"
    description: "Group of services used in management reporting: Express, Ground, International, or Freight."
    sql: ${TABLE}.service_family ;;
  }

  dimension: commit_days {
    type: number
    label: "Days to Deliver"
    description: "Number of days after pickup by which we promise delivery."
    sql: ${TABLE}.commit_days ;;
  }

  dimension: commit_time_local {
    type: string
    label: "Commit Time of Day"
    description: "Local time of day by which we promise delivery on the commit day."
    sql: ${TABLE}.commit_time_local ;;
  }

  dimension: sort_order {
    hidden: yes
    type: number
    sql: ${TABLE}.sort_order ;;
  }
}
