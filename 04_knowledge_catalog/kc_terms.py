"""Cymbal Shipping business glossary (plain language, for business readers)."""

GLOSSARY_ID = "cymbal-shipping-glossary"
GLOSSARY_TITLE = "Cymbal Shipping · Business Glossary"
GLOSSARY_DESC = (
    "Plain-language definitions of the terms Cymbal Shipping uses to run and measure the business: "
    "on-time delivery, commit time, the Service Guarantee, revenue at risk, aging packages, cold chain "
    "shipments, and more. Owned by Network Operations and Customer Experience."
)


def _ov(title, what, bullets, where, owner):
  items = "".join(f"<li>{b}</li>" for b in bullets)
  return (f"<h3>{title}</h3><p><strong>What it means:</strong> {what}</p><ul>{items}</ul>"
          f"<p><strong>Where to find it:</strong> {where}</p><p><strong>Owner:</strong> {owner}</p>")


# (term_id, title, short description, overview html)
TERMS = [
    ("on-time-delivery-rate", "On-Time Delivery Rate",
     "The share of packages we delivered by the time we promised. Only delays within our control count against us; "
     "weather, customs holds, recipient-not-available and address problems do not. Company target: 97.5%.",
     _ov("On-Time Delivery Rate",
         "Of the packages whose promised delivery time has passed, the share we delivered on time, or delivered late only for a reason outside our control.",
         ["Calculated as 1 minus (late packages within our control divided by packages past their commit time).",
          "Counts against us: missed sort, equipment delay, misrouted package, damaged in handling.",
          "Does not count against us: weather, customs hold, recipient not available, address correction.",
          "Company target is 97.5%. A hub or service below target needs a recovery plan.",
          "Do not confuse it with Raw On-Time Rate (Unadjusted), which counts every late package whatever the cause."],
         "Looker measure On-Time Delivery Rate in Shipments and Service Performance. Do not rebuild it from raw tables.",
         "Network Operations, Service Quality team")),
    ("commit-time", "Commit Time",
     "The date and time we promise the customer their package will be delivered. It is set by the service they bought. "
     "Also called the delivery commitment or promised delivery time.",
     _ov("Commit Time",
         "The date and time we promise delivery. A package is on time when it is delivered at or before its commit time.",
         ["Priority Overnight: by 10:30 AM the next day.",
          "Standard Overnight: by 4:30 PM the next day.",
          "2-Day: by 4:30 PM on the second day. Express Saver: by 4:30 PM on the third day.",
          "International Priority: by 12:00 PM on the third day.",
          "Ground and Home Delivery: by 8:00 PM on the fourth day. Freight Priority: by 5:00 PM on the third day."],
         "Committed Delivery date and time on every package in Shipments and Service Performance.",
         "Product Management, Service Portfolio")),
    ("service-guarantee", "Service Guarantee",
     "Our money-back promise on Express and International Priority services: if a package is late for a reason "
     "within our control, the customer can claim a refund of the shipping charge.",
     _ov("Service Guarantee",
         "If we deliver a guaranteed-service package after its commit time, and the reason was within our control, the customer can claim a full refund of the shipping charge.",
         ["Covered services: Priority Overnight, Standard Overnight, 2-Day, Express Saver, International Priority.",
          "Not covered: Ground, Home Delivery, Freight Priority.",
          "Does not apply when the delay was outside our control (weather, customs, recipient not available, address correction)."],
         "Is Covered by Service Guarantee and Is Service Guarantee Refund Eligible on every package.",
         "Customer Experience, Claims and Refunds")),
    ("revenue-at-risk", "Revenue at Risk",
     "Shipping revenue we may have to refund under the Service Guarantee: charges on guaranteed-service packages "
     "that are late, or going to be late, for a reason within our control.",
     _ov("Revenue at Risk",
         "The dollars of shipping revenue exposed to Service Guarantee refunds.",
         ["Includes packages already late and packages that are delayed and expected to miss their commit time.",
          "Only guaranteed services, and only delays within our control.",
          "It is the shipping charge, not the value of the goods inside the package."],
         "Looker measure Revenue at Risk in Shipments and Service Performance.",
         "Finance, Revenue Assurance")),
    ("delay-within-our-control", "Delay Within Our Control",
     "A delay caused by something Cymbal Shipping controls: a missed sort, an equipment delay, a misrouted package, "
     "or damage in handling. These delays count against On-Time Delivery Rate and can trigger the Service Guarantee.",
     _ov("Delay Within Our Control",
         "A late package where the cause sits inside our own operation.",
         ["Missed Sort, Equipment Delay, Misrouted, Damaged in Handling.",
          "Counts against On-Time Delivery Rate.",
          "Makes a guaranteed-service package eligible for a refund."],
         "Exception Type equals Within Our Control.",
         "Network Operations, Service Quality team")),
    ("delay-outside-our-control", "Delay Outside Our Control",
     "A delay caused by something Cymbal Shipping does not control: weather, a customs hold, the recipient not being "
     "available, or an address problem. These delays are excused from On-Time Delivery Rate.",
     _ov("Delay Outside Our Control",
         "A late package where the cause sits outside our operation.",
         ["Weather, Customs Hold, Recipient Not Available, Address Correction.",
          "Excused from On-Time Delivery Rate.",
          "Not eligible for a Service Guarantee refund."],
         "Exception Type equals Outside Our Control.",
         "Network Operations, Service Quality team")),
    ("missed-sort", "Missed Sort",
     "A package that was inside a hub but did not make it onto its planned outbound flight or truck before the sort "
     "cut-off. A missed sort is within our control.",
     _ov("Missed Sort",
         "The package reached the hub in time but was not sorted to its outbound departure before the cut-off.",
         ["Usual causes: a sort line stoppage, a late inbound trailer, or a staffing shortfall.",
          "Always a Delay Within Our Control.",
          "Recovery is normally the next sort or a diversion through the hub's Recovery Hub."],
         "Delivery Exception Reason equals Missed Sort.",
         "Hub Operations")),
    ("aging-package", "Aging Package",
     "A package that has been held at a hub for 6 hours or more. Every aging package needs a recovery plan.",
     _ov("Aging Package",
         "A package sitting at a hub for 6 hours or more since it arrived.",
         ["Measured from the live tracking record that hubs and scanners update in Spanner.",
          "Each aging package carries a recovery plan: next sort, diversion to the Recovery Hub, or priority recovery for cold chain.",
          "Cold chain aging packages are worked first."],
         "Looker measure Aging Packages and the field Is Aging Package in Live Tracking.",
         "Hub Operations, Network Control Center")),
    ("cold-chain-shipment", "Cold Chain Shipment",
     "A temperature-controlled healthcare package that must stay between 2 and 8 degrees Celsius from pickup to delivery. "
     "Also called temperature-controlled or refrigerated.",
     _ov("Cold Chain Shipment",
         "A healthcare package, such as a vaccine, biologic or lab specimen, that must be kept between 2 and 8 degrees Celsius.",
         ["Each package travels with a temperature logger.",
          "If a cold chain package is held at a hub, it is re-iced and moved to refrigerated hold.",
          "Used mainly by Healthcare and Life Sciences customers on Priority Overnight, Standard Overnight and International Priority."],
         "Is Cold Chain on every package.",
         "Healthcare Solutions, Cold Chain Desk")),
    ("temperature-excursion", "Temperature Excursion",
     "A cold chain package whose logger recorded a temperature above 8 degrees Celsius. The customer must review "
     "product quality before the product is used.",
     _ov("Temperature Excursion",
         "The package logger recorded a reading above the 8 degree Celsius limit for a cold chain shipment.",
         ["Captured from Cold Chain Temperature Logs written by the Cold Chain Desk.",
          "We record the highest temperature and the minutes spent above the limit.",
          "The account director contacts the customer the same day."],
         "Looker measure Temperature Excursions in Field Evidence.",
         "Healthcare Solutions, Cold Chain Desk")),
    ("strategic-account", "Strategic Account",
     "One of our largest named customers, with a dedicated account director. In the data this is Account Tier equals Strategic.",
     _ov("Strategic Account",
         "A customer in the top account tier set by Sales.",
         ["Each strategic account has a named account director.",
          "Tiers in order: Strategic, Enterprise, Mid-Market, Small Business.",
          "Strategic accounts are reviewed first during any service disruption."],
         "Account Tier and Is Strategic Account on every customer.",
         "Sales, Strategic Accounts")),
    ("recovery-hub", "Recovery Hub",
     "The hub that takes diverted volume when another hub cannot sort on schedule. For example, the Indianapolis Air Hub "
     "is the Recovery Hub for the Memphis SuperHub.",
     _ov("Recovery Hub",
         "The backup hub that absorbs packages when a hub falls behind.",
         ["Every hub has one assigned Recovery Hub.",
          "Diversions run on recovery flights or trucks tracked as recovery lanes in the operations database."],
         "Backup Hub Code on every hub, and the recovery lanes in the Spanner operations database.",
         "Network Control Center")),
    ("revenue-per-package", "Revenue per Package",
     "Average shipping revenue earned per package after discounts. Also called yield.",
     _ov("Revenue per Package",
         "Shipping revenue divided by the number of packages.",
         ["Shipping Revenue is what we bill the customer after discounts.",
          "Used to compare services and customers on a like-for-like basis."],
         "Looker measure Revenue per Package in Shipments and Service Performance.",
         "Finance, Revenue Management")),
    ("field-evidence", "Field Evidence",
     "Documents written by drivers and hub teams when something goes wrong with a package: hub delay notices, cold chain "
     "temperature logs, damage reports and customs notices.",
     _ov("Field Evidence",
         "The written record of what happened to a delayed or damaged package.",
         ["Captured as documents in the field-evidence bucket in Amazon S3.",
          "Read by the lakehouse as an object table, with the key facts extracted into the Field Evidence table.",
          "Explains the root cause behind a late package and whether a cold chain shipment was put at risk."],
         "Field Evidence in Shipments and Service Performance: What Happened, Root Cause, Customer Impact.",
         "Network Operations, Service Quality team")),
]
