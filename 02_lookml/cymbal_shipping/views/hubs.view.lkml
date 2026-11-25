view: hubs {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.hubs` ;;
  label: "Hubs"

  dimension: hub_code {
    primary_key: yes
    type: string
    label: "Hub Code"
    description: "Three-letter code of the hub that sorted the package, for example MEM for the Memphis SuperHub."
    sql: ${TABLE}.hub_code ;;
  }

  dimension: hub_name {
    type: string
    label: "Hub"
    description: "Sort hub that handled the package, for example Memphis SuperHub or Indianapolis Air Hub. Also called sort facility or sort center."
    sql: ${TABLE}.hub_name ;;
  }

  dimension: hub_type {
    type: string
    label: "Hub Type"
    description: "Role of the hub in the network: Air SuperHub, National Air Hub, Regional Air Hub, International Gateway, or Ground Hub."
    sql: ${TABLE}.hub_type ;;
  }

  dimension: region {
    type: string
    label: "Hub Region"
    description: "Operating region the hub belongs to."
    sql: ${TABLE}.region ;;
  }

  dimension: city {
    type: string
    label: "Hub City"
    description: "City where the hub operates."
    sql: ${TABLE}.city ;;
  }

  dimension: state {
    type: string
    label: "Hub State"
    description: "State where the hub operates."
    map_layer_name: us_states
    sql: ${TABLE}.state ;;
  }

  dimension: location {
    type: location
    label: "Hub Location"
    description: "Map location of the hub."
    sql_latitude: ${TABLE}.latitude ;;
    sql_longitude: ${TABLE}.longitude ;;
  }

  dimension: backup_hub_code {
    type: string
    label: "Backup Hub Code"
    description: "Hub that takes diverted volume when this hub cannot sort on schedule."
    sql: ${TABLE}.backup_hub_code ;;
  }

  dimension: daily_sort_capacity {
    type: number
    label: "Daily Sort Capacity"
    description: "Packages the hub can sort in a normal day."
    value_format_name: decimal_0
    sql: ${TABLE}.daily_sort_capacity ;;
  }
}
