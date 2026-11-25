view: shipments {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.shipments` ;;
  label: "Shipments"

  # ---------------------------------------------------------------- keys --
  dimension: tracking_number {
    primary_key: yes
    type: string
    label: "Tracking Number"
    description: "12-digit number that identifies one package from pickup to delivery."
    sql: ${TABLE}.tracking_number ;;
    link: {
      label: "Open this package in Shipments & Service Performance"
      url: "/explore/cymbal_shipping/shipments?fields=shipments.tracking_number,customers.customer_name,services.service_name,hubs.hub_name,shipments.package_status,shipments.service_outcome,shipments.committed_delivery_time,shipments.estimated_delivery_time,live_package_tracking.recovery_plan&f[shipments.tracking_number]={{ value }}"
    }
  }

  dimension: customer_id {
    hidden: yes
    type: string
    sql: ${TABLE}.customer_id ;;
  }

  dimension: service_code {
    hidden: yes
    type: string
    sql: ${TABLE}.service_code ;;
  }

  dimension: routing_hub_code {
    hidden: yes
    type: string
    sql: ${TABLE}.routing_hub_code ;;
  }

  # --------------------------------------------------------------- dates --
  dimension_group: ship {
    type: time
    timeframes: [raw, date, week, month, day_of_week]
    convert_tz: no
    datatype: date
    label: "Ship"
    description: "Day the package was picked up from the shipper."
    sql: ${TABLE}.ship_date ;;
  }

  dimension: reporting_period {
    type: string
    label: "Reporting Period"
    description: "This Week is Monday November 9 onward, Last Week is November 2 to 8, and Earlier is everything before. Use it to compare this week with last week."
    sql: CASE
           WHEN ${TABLE}.ship_date >= DATE '2026-11-09' THEN 'This Week'
           WHEN ${TABLE}.ship_date >= DATE '2026-11-02' THEN 'Last Week'
           ELSE 'Earlier' END ;;
    order_by_field: reporting_period_sort
  }

  dimension: reporting_period_sort {
    hidden: yes
    type: number
    sql: CASE
           WHEN ${TABLE}.ship_date >= DATE '2026-11-09' THEN 1
           WHEN ${TABLE}.ship_date >= DATE '2026-11-02' THEN 2
           ELSE 3 END ;;
  }

  dimension_group: committed_delivery {
    type: time
    timeframes: [raw, time, date, hour_of_day]
    label: "Committed Delivery"
    description: "Date and time we promised delivery (the commit time). Set by the service the customer bought."
    sql: ${TABLE}.committed_delivery_ts ;;
  }

  dimension_group: delivered {
    type: time
    timeframes: [raw, time, date]
    label: "Delivered"
    description: "Date and time the package was actually delivered. Empty while the package is still in the network."
    sql: ${TABLE}.delivered_ts ;;
  }

  dimension_group: estimated_delivery {
    type: time
    timeframes: [raw, time, date]
    label: "Estimated Delivery"
    description: "Current best estimate of when the package will be delivered."
    sql: ${TABLE}.estimated_delivery_ts ;;
  }

  # ---------------------------------------------------------- attributes --
  dimension: destination_metro {
    type: string
    label: "Destination City"
    description: "Metro area the package is going to."
    sql: ${TABLE}.destination_metro ;;
  }

  dimension: destination_state {
    type: string
    label: "Destination State"
    description: "US state the package is going to."
    map_layer_name: us_states
    sql: ${TABLE}.destination_state ;;
  }

  dimension: destination_region {
    type: string
    label: "Destination Region"
    description: "Part of the country the package is going to: Northeast, Southeast, South, Midwest, Southwest, Mountain, or West."
    sql: ${TABLE}.destination_region ;;
  }

  dimension: weight_lb {
    type: number
    label: "Weight (lb)"
    description: "Billable weight of the package in pounds."
    value_format_name: decimal_1
    sql: ${TABLE}.weight_lb ;;
  }

  dimension: is_cold_chain {
    type: yesno
    label: "Is Cold Chain"
    description: "Yes for temperature-controlled healthcare packages that must stay between 2 and 8 degrees Celsius from pickup to delivery. Also called temperature-controlled or refrigerated."
    sql: ${TABLE}.is_cold_chain ;;
  }

  dimension: is_guaranteed_service {
    type: yesno
    label: "Is Covered by Service Guarantee"
    description: "Yes when the package travels on a service covered by the Cymbal Shipping Service Guarantee (all Express and International Priority services)."
    sql: ${TABLE}.is_guaranteed_service ;;
  }

  dimension: package_status {
    type: string
    label: "Package Status"
    description: "Where the package is in its journey: Delivered, Out for Delivery, In Transit, Held at Hub, or Exception Hold."
    sql: ${TABLE}.package_status ;;
  }

  dimension: service_outcome {
    type: string
    label: "Service Outcome"
    description: "How we performed against our promise: On Time, Late · Within Our Control, Late · Outside Our Control, At Risk · Delay Expected (not due yet but already delayed), or In Transit · On Plan."
    sql: ${TABLE}.service_outcome ;;
  }

  dimension: exception_reason {
    type: string
    label: "Delivery Exception Reason"
    description: "Why a package was delayed, if it was: Missed Sort, Equipment Delay, Misrouted, Damaged in Handling, Weather, Customs Hold, Recipient Not Available, or Address Correction. Empty when nothing went wrong."
    sql: ${TABLE}.exception_reason ;;
  }

  dimension: exception_type {
    type: string
    label: "Exception Type"
    description: "Whether the cause of a delay was Within Our Control (missed sort, equipment, misroute, damage) or Outside Our Control (weather, customs, recipient not available, address correction). Only delays within our control count against On-Time Delivery Rate."
    sql: CASE ${TABLE}.exception_category
           WHEN 'Controllable' THEN 'Within Our Control'
           WHEN 'Uncontrollable' THEN 'Outside Our Control' END ;;
  }

  dimension: is_commitment_due {
    type: yesno
    label: "Is Past Commit Time"
    description: "Yes once the promised delivery time has passed, so the package can be scored as on time or late."
    sql: ${TABLE}.is_commitment_due ;;
  }

  dimension: hours_late {
    type: number
    label: "Hours Late"
    description: "Hours between the promised delivery time and the actual or expected delivery. Empty for on-time packages."
    value_format_name: decimal_1
    sql: ${TABLE}.hours_late ;;
  }

  dimension: is_guarantee_refund_eligible {
    type: yesno
    label: "Is Service Guarantee Refund Eligible"
    description: "Yes when a package on a guaranteed service is late, or is going to be late, for a reason within our control. The customer can claim a refund of the shipping charge."
    sql: ${TABLE}.is_guarantee_refund_eligible ;;
  }

  dimension: net_revenue_usd {
    hidden: yes
    type: number
    sql: ${TABLE}.net_revenue_usd ;;
  }

  # ------------------------------------------------------------ measures --
  measure: package_count {
    type: count
    label: "Packages"
    description: "Number of packages picked up. Also called volume or shipments."
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: packages_past_commit_time {
    type: count
    label: "Packages Past Commit Time"
    description: "Packages whose promised delivery time has passed. This is the denominator of On-Time Delivery Rate."
    filters: [is_commitment_due: "yes"]
    value_format_name: decimal_0
  }

  measure: late_packages_within_our_control {
    type: count
    label: "Late Packages (Within Our Control)"
    description: "Packages that missed their promised delivery time because of something we control: a missed sort, an equipment delay, a misroute, or damage in handling."
    filters: [service_outcome: "Late · Within Our Control"]
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: late_packages_outside_our_control {
    type: count
    label: "Late Packages (Outside Our Control)"
    description: "Packages that missed their promised delivery time because of weather, customs, the recipient not being available, or an address problem. These do not count against On-Time Delivery Rate."
    filters: [service_outcome: "Late · Outside Our Control"]
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: on_time_delivery_rate {
    type: number
    label: "On-Time Delivery Rate"
    description: "Official Cymbal Shipping service KPI. Share of packages past their commit time that were delivered on time, or were late only for a reason outside our control (weather, customs, recipient not available, address correction). Only delays within our control count against us. Target is 97.5%."
    value_format_name: percent_1
    sql: 1.0 - SAFE_DIVIDE(${late_packages_within_our_control}, NULLIF(${packages_past_commit_time}, 0)) ;;
    drill_fields: [hubs.hub_name, services.service_name, package_count, late_packages_within_our_control, on_time_delivery_rate]
  }

  measure: raw_on_time_rate {
    type: number
    label: "Raw On-Time Rate (Unadjusted)"
    description: "Share of packages past their commit time that arrived on time, counting every late package no matter the cause. Not the official KPI: it penalizes hubs for weather and customs delays. Use On-Time Delivery Rate for reporting."
    value_format_name: percent_1
    sql: 1.0 - SAFE_DIVIDE(${late_packages_within_our_control} + ${late_packages_outside_our_control}, NULLIF(${packages_past_commit_time}, 0)) ;;
  }

  measure: on_time_target {
    type: max
    label: "On-Time Target"
    description: "Company service target for On-Time Delivery Rate: 97.5%."
    value_format_name: percent_1
    sql: 0.975 ;;
  }

  measure: packages_with_exception {
    type: count
    label: "Packages with a Delivery Exception"
    description: "Packages that had any delivery exception recorded, whether or not it made them late."
    filters: [exception_reason: "-NULL"]
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: packages_held_at_hub {
    type: count
    label: "Packages Held at Hub"
    description: "Packages sitting at a hub right now because of a delay."
    filters: [package_status: "Held at Hub"]
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: cold_chain_packages {
    type: count
    label: "Cold Chain Packages"
    description: "Temperature-controlled healthcare packages."
    filters: [is_cold_chain: "yes"]
    value_format_name: decimal_0
  }

  measure: total_net_revenue {
    type: sum
    label: "Shipping Revenue"
    description: "Shipping charges billed to the customer after discounts, in US dollars."
    value_format_name: usd_0
    sql: ${net_revenue_usd} ;;
  }

  measure: revenue_per_package {
    type: number
    label: "Revenue per Package"
    description: "Average shipping revenue per package. Also called yield."
    value_format_name: usd
    sql: SAFE_DIVIDE(${total_net_revenue}, NULLIF(${package_count}, 0)) ;;
  }

  measure: revenue_at_risk {
    type: sum
    label: "Revenue at Risk"
    description: "Shipping revenue we may have to refund under the Service Guarantee: charges on guaranteed-service packages that are late, or going to be late, for a reason within our control."
    value_format_name: usd_0
    sql: ${net_revenue_usd} ;;
    filters: [is_guarantee_refund_eligible: "yes"]
    drill_fields: [customers.customer_name, hubs.hub_name, services.service_name, guarantee_eligible_packages, revenue_at_risk]
  }

  measure: guarantee_eligible_packages {
    type: count
    label: "Packages Eligible for a Guarantee Refund"
    description: "Guaranteed-service packages that are late, or going to be late, for a reason within our control."
    filters: [is_guarantee_refund_eligible: "yes"]
    value_format_name: decimal_0
    drill_fields: [package_detail*]
  }

  measure: average_hours_late {
    type: average
    label: "Average Hours Late"
    description: "Average number of hours late, for packages that are late."
    value_format_name: decimal_1
    sql: ${hours_late} ;;
  }

  set: package_detail {
    fields: [
      tracking_number,
      customers.customer_name,
      services.service_name,
      hubs.hub_name,
      destination_metro,
      package_status,
      service_outcome,
      exception_reason,
      committed_delivery_time,
      estimated_delivery_time,
      total_net_revenue
    ]
  }
}
