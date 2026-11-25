view: exception_evidence {
  sql_table_name: `@{gcp_project_id}.@{bq_dataset}.exception_evidence` ;;
  label: "Field Evidence"

  dimension: evidence_id {
    primary_key: yes
    type: string
    label: "Evidence Document ID"
    description: "Identifier of the field evidence document."
    sql: ${TABLE}.evidence_id ;;
  }

  dimension: tracking_number {
    hidden: yes
    type: string
    sql: ${TABLE}.tracking_number ;;
  }

  dimension: document_type {
    type: string
    label: "Document Type"
    description: "Kind of field document: Hub Delay Notice, Cold Chain Temperature Log, Damage Report, Customs Hold Notice, Delivery Attempt Note, Address Correction Request, Weather Advisory, Equipment Delay Report, or Misroute Report."
    sql: ${TABLE}.document_type ;;
  }

  dimension_group: captured {
    type: time
    timeframes: [raw, time, date]
    label: "Document Captured"
    description: "When the document was written or the reading was captured."
    sql: ${TABLE}.captured_ts ;;
  }

  dimension: captured_by {
    type: string
    label: "Captured By"
    description: "Team or role that produced the document."
    sql: ${TABLE}.captured_by ;;
  }

  dimension: summary {
    type: string
    label: "What Happened"
    description: "Plain-language summary of what the field document says happened to the package."
    sql: ${TABLE}.summary ;;
  }

  dimension: root_cause {
    type: string
    label: "Root Cause"
    description: "Standardized root cause taken from the field document, for example Sort line outage (Matrix C, Belt 7)."
    sql: ${TABLE}.root_cause ;;
  }

  dimension: customer_impact {
    type: string
    label: "Customer Impact"
    description: "What the event means for the customer, for example Product quality review required."
    sql: ${TABLE}.customer_impact ;;
  }

  dimension: is_temperature_excursion {
    type: yesno
    label: "Is Temperature Excursion"
    description: "Yes when a cold chain package was recorded above its required 2 to 8 degrees Celsius range."
    sql: ${TABLE}.is_temperature_excursion ;;
  }

  dimension: max_temperature_c {
    type: number
    label: "Highest Temperature (°C)"
    description: "Highest temperature recorded by the package logger, in degrees Celsius."
    value_format_name: decimal_1
    sql: ${TABLE}.max_temperature_c ;;
  }

  dimension: minutes_out_of_range {
    type: number
    label: "Minutes Above 8°C"
    description: "Minutes the package spent above 8 degrees Celsius."
    sql: ${TABLE}.minutes_out_of_range ;;
  }

  dimension: document_text {
    type: string
    label: "Document Text"
    description: "Full text of the field evidence document."
    sql: ${TABLE}.document_text ;;
  }

  dimension: document_uri {
    type: string
    label: "Document Location"
    description: "Location of the document file in the field-evidence object store."
    sql: ${TABLE}.document_uri ;;
  }

  measure: document_count {
    type: count_distinct
    sql: ${evidence_id} ;;
    label: "Field Evidence Documents"
    description: "Number of field evidence documents."
    value_format_name: decimal_0
    drill_fields: [evidence_id, document_type, shipments.tracking_number, customers.customer_name, summary]
  }

  measure: temperature_excursions {
    type: count
    label: "Temperature Excursions"
    description: "Cold chain packages recorded above 8 degrees Celsius. Each one needs a product quality review by the customer."
    filters: [is_temperature_excursion: "yes"]
    value_format_name: decimal_0
    drill_fields: [shipments.tracking_number, customers.customer_name, max_temperature_c, minutes_out_of_range, summary]
  }

  measure: highest_temperature_c {
    type: max
    label: "Highest Temperature Recorded (°C)"
    description: "Highest logger temperature across the selected cold chain packages."
    value_format_name: decimal_1
    sql: ${max_temperature_c} ;;
  }
}
