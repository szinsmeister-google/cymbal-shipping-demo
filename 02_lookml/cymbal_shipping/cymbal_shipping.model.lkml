connection: "default_bigquery_connection"
label: "Cymbal Shipping"

include: "/views/*.view.lkml"

week_start_day: monday

datagroup: cymbal_shipping_default {
  max_cache_age: "1 hour"
}
persist_with: cymbal_shipping_default

explore: shipments {
  label: "Shipments & Service Performance"
  description: "The one place to answer questions about Cymbal Shipping service performance for named accounts: how many packages we moved, whether we delivered when we promised, which packages are held at a hub right now, and how much shipping revenue is exposed to Service Guarantee refunds. Combines shipment history (BigQuery), live package tracking (Spanner), and field evidence documents (object-storage lake)."

  join: customers {
    type: left_outer
    relationship: many_to_one
    sql_on: ${shipments.customer_id} = ${customers.customer_id} ;;
  }

  join: services {
    type: left_outer
    relationship: many_to_one
    sql_on: ${shipments.service_code} = ${services.service_code} ;;
  }

  join: hubs {
    type: left_outer
    relationship: many_to_one
    sql_on: ${shipments.routing_hub_code} = ${hubs.hub_code} ;;
  }

  join: live_package_tracking {
    type: left_outer
    relationship: one_to_one
    sql_on: ${shipments.tracking_number} = ${live_package_tracking.tracking_number} ;;
  }

  join: exception_evidence {
    type: left_outer
    relationship: one_to_one
    sql_on: ${shipments.tracking_number} = ${exception_evidence.tracking_number} ;;
  }
}
