/**
 * @title Cymbal Shipping · Service Performance
 * @description Business-user view of Cymbal Shipping service performance: on-time delivery against the 97.5% target, revenue at risk under the Service Guarantee, packages held at hubs and cold chain temperature excursions, with a look-up bar and cross-filtering on every chart.
 * @toolkit-version       1.3.0
 * @looker-dashboard-id   <LOOKER_DATA_APP_DASHBOARD_ID>
 * @looker-instance       <LOOKER_BASE_URL>
 * @created-at            2026-11-11T14:53:16Z
 * @created-by            Sean Zinsmeister
 * @updated-at            2026-11-11T16:35:22Z
 * @updated-by            Sean Zinsmeister
 */

import { DataApp, html, nothing } from '/runtime/data-app.js';

export const elementName = 'cymbal-shipping-service-performance';

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const MODEL = 'cymbal_shipping';
const EXPLORE = 'shipments';
const TARGET = 0.975;

const INK = '#1B1524';
const PURPLE = '#4D148C';
const ORANGE = '#FF6600';
const ORANGE_INK = '#B84300';
const QUIET_BAR = '#CDBFE0';
const FONT = '"Google Sans Flex", "Google Sans", "Google Sans Text", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Everything a person can filter the page by. One value per entry. */
const DIMS = {
  hub: { field: 'hubs.hub_name', label: 'Hub' },
  customer: { field: 'customers.customer_name', label: 'Customer' },
  service: { field: 'services.service_name', label: 'Service' },
  reason: { field: 'shipments.exception_reason', label: 'Delay reason' },
  shipDay: { field: 'shipments.ship_date', label: 'Shipped' },
  industry: { field: 'customers.industry_vertical', label: 'Industry' },
  tier: { field: 'customers.customer_tier', label: 'Account tier' },
  director: { field: 'customers.account_director', label: 'Account director' },
  coldChain: { field: 'shipments.is_cold_chain', label: 'Temperature-controlled', flag: true },
  aging: { field: 'live_package_tracking.is_aging', label: 'Held 6+ hours', flag: true },
};

const PERIODS = {
  this: {
    label: 'This week', filter: 'This Week', phrase: 'this week', range: 'Since Monday, Nov 9',
    compare: 'Last Week', compareLabel: 'vs last week',
  },
  last: {
    label: 'Last week', filter: 'Last Week', phrase: 'last week', range: 'Nov 2 to Nov 8',
    compare: 'Earlier', compareLabel: 'vs the weeks before',
  },
  all: {
    label: 'Last 6 weeks', filter: null, phrase: 'over the last 6 weeks', range: 'Oct 1 to Nov 10',
    compare: null, compareLabel: '',
  },
};

/** Orange = counts against on-time delivery. Quiet lilac = excused. */
const REASON_COLORS = {
  'Missed Sort': ORANGE,
  'Equipment Delay': ORANGE,
  'Misrouted': ORANGE,
  'Damaged in Handling': ORANGE,
  'Weather': QUIET_BAR,
  'Customs Hold': QUIET_BAR,
  'Recipient Not Available': QUIET_BAR,
  'Address Correction': QUIET_BAR,
};

const REPORT_FIELDS = [
  'exception_evidence.evidence_id',
  'exception_evidence.captured_date',
  'exception_evidence.document_type',
  'exception_evidence.summary',
  'exception_evidence.root_cause',
  'exception_evidence.max_temperature_c',
  'customers.customer_name',
  'hubs.hub_name',
  'shipments.tracking_number',
];

const PACKAGE_FIELDS = [
  'shipments.tracking_number',
  'customers.customer_name',
  'customers.customer_tier',
  'customers.account_director',
  'services.service_name',
  'services.commit_time_local',
  'hubs.hub_name',
  'shipments.package_status',
  'shipments.service_outcome',
  'shipments.exception_reason',
  'shipments.ship_date',
  'shipments.committed_delivery_date',
  'shipments.estimated_delivery_date',
  'shipments.delivered_date',
  'shipments.destination_metro',
  'shipments.destination_state',
  'shipments.is_cold_chain',
  'shipments.is_guarantee_refund_eligible',
  'live_package_tracking.hub_dwell_hours',
  'live_package_tracking.recovery_plan',
  'live_package_tracking.last_scan_type',
  'exception_evidence.document_type',
  'exception_evidence.summary',
  'exception_evidence.root_cause',
  'exception_evidence.customer_impact',
  'exception_evidence.max_temperature_c',
  'exception_evidence.minutes_out_of_range',
  'exception_evidence.document_uri',
];

/** Plain-language definitions, copied from the Cymbal Shipping business glossary. */
const GLOSSARY = /*__GLOSSARY__*/[
  {
    "id": "on-time-delivery-rate",
    "title": "On-Time Delivery Rate",
    "short": "The share of packages we delivered by the time we promised. Only delays within our control count against us; weather, customs holds, recipient-not-available and address problems do not. Company target: 97.5%.",
    "bullets": [
      "Calculated as 1 minus (late packages within our control divided by packages past their commit time).",
      "Counts against us: missed sort, equipment delay, misrouted package, damaged in handling.",
      "Does not count against us: weather, customs hold, recipient not available, address correction."
    ],
    "owner": "Network Operations, Service Quality team",
    "keys": "on time otd late lateness service level performance what counts definition"
  },
  {
    "id": "commit-time",
    "title": "Commit Time",
    "short": "The date and time we promise the customer their package will be delivered. It is set by the service they bought. Also called the delivery commitment or promised delivery time.",
    "bullets": [
      "Priority Overnight: by 10:30 AM the next day.",
      "Standard Overnight: by 4:30 PM the next day.",
      "2-Day: by 4:30 PM on the second day. Express Saver: by 4:30 PM on the third day."
    ],
    "owner": "Product Management, Service Portfolio",
    "keys": "promised delivery commitment deadline promise"
  },
  {
    "id": "service-guarantee",
    "title": "Service Guarantee",
    "short": "Our money-back promise on Express and International Priority services: if a package is late for a reason within our control, the customer can claim a refund of the shipping charge.",
    "bullets": [
      "Covered services: Priority Overnight, Standard Overnight, 2-Day, Express Saver, International Priority.",
      "Not covered: Ground, Home Delivery, Freight Priority.",
      "Does not apply when the delay was outside our control (weather, customs, recipient not available, address correction)."
    ],
    "owner": "Customer Experience, Claims and Refunds",
    "keys": "money back refund guarantee"
  },
  {
    "id": "revenue-at-risk",
    "title": "Revenue at Risk",
    "short": "Shipping revenue we may have to refund under the Service Guarantee: charges on guaranteed-service packages that are late, or going to be late, for a reason within our control.",
    "bullets": [
      "Includes packages already late and packages that are delayed and expected to miss their commit time.",
      "Only guaranteed services, and only delays within our control.",
      "It is the shipping charge, not the value of the goods inside the package."
    ],
    "owner": "Finance, Revenue Assurance",
    "keys": "refund exposure dollars risk money"
  },
  {
    "id": "delay-within-our-control",
    "title": "Delay Within Our Control",
    "short": "A delay caused by something Cymbal Shipping controls: a missed sort, an equipment delay, a misrouted package, or damage in handling. These delays count against On-Time Delivery Rate and can trigger the Service Guarantee.",
    "bullets": [
      "Missed Sort, Equipment Delay, Misrouted, Damaged in Handling.",
      "Counts against On-Time Delivery Rate.",
      "Makes a guaranteed-service package eligible for a refund."
    ],
    "owner": "Network Operations, Service Quality team",
    "keys": "controllable our fault counts against"
  },
  {
    "id": "delay-outside-our-control",
    "title": "Delay Outside Our Control",
    "short": "A delay caused by something Cymbal Shipping does not control: weather, a customs hold, the recipient not being available, or an address problem. These delays are excused from On-Time Delivery Rate.",
    "bullets": [
      "Weather, Customs Hold, Recipient Not Available, Address Correction.",
      "Excused from On-Time Delivery Rate.",
      "Not eligible for a Service Guarantee refund."
    ],
    "owner": "Network Operations, Service Quality team",
    "keys": "weather customs excused not our fault"
  },
  {
    "id": "missed-sort",
    "title": "Missed Sort",
    "short": "A package that was inside a hub but did not make it onto its planned outbound flight or truck before the sort cut-off. A missed sort is within our control.",
    "bullets": [
      "Usual causes: a sort line stoppage, a late inbound trailer, or a staffing shortfall.",
      "Always a Delay Within Our Control.",
      "Recovery is normally the next sort or a diversion through the hub's Recovery Hub."
    ],
    "owner": "Hub Operations",
    "keys": "sort cut off missed flight"
  },
  {
    "id": "aging-package",
    "title": "Aging Package",
    "short": "A package that has been held at a hub for 6 hours or more. Every aging package needs a recovery plan.",
    "bullets": [
      "Measured from the live tracking record that hubs and scanners update in Spanner.",
      "Each aging package carries a recovery plan: next sort, diversion to the Recovery Hub, or priority recovery for cold chain.",
      "Cold chain aging packages are worked first."
    ],
    "owner": "Hub Operations, Network Control Center",
    "keys": "held stuck dwell waiting"
  },
  {
    "id": "cold-chain-shipment",
    "title": "Cold Chain Shipment",
    "short": "A temperature-controlled healthcare package that must stay between 2 and 8 degrees Celsius from pickup to delivery. Also called temperature-controlled or refrigerated.",
    "bullets": [
      "Each package travels with a temperature logger.",
      "If a cold chain package is held at a hub, it is re-iced and moved to refrigerated hold.",
      "Used mainly by Healthcare and Life Sciences customers on Priority Overnight, Standard Overnight and International Priority."
    ],
    "owner": "Healthcare Solutions, Cold Chain Desk",
    "keys": "temperature controlled refrigerated"
  },
  {
    "id": "temperature-excursion",
    "title": "Temperature Excursion",
    "short": "A cold chain package whose logger recorded a temperature above 8 degrees Celsius. The customer must review product quality before the product is used.",
    "bullets": [
      "Captured from Cold Chain Temperature Logs written by the Cold Chain Desk.",
      "We record the highest temperature and the minutes spent above the limit.",
      "The account director contacts the customer the same day."
    ],
    "owner": "Healthcare Solutions, Cold Chain Desk",
    "keys": "out of range too warm above 8"
  },
  {
    "id": "strategic-account",
    "title": "Strategic Account",
    "short": "One of our largest named customers, with a dedicated account director. In the data this is Account Tier equals Strategic.",
    "bullets": [
      "Each strategic account has a named account director.",
      "Tiers in order: Strategic, Enterprise, Mid-Market, Small Business.",
      "Strategic accounts are reviewed first during any service disruption."
    ],
    "owner": "Sales, Strategic Accounts",
    "keys": "top key named account tier"
  },
  {
    "id": "recovery-hub",
    "title": "Recovery Hub",
    "short": "The hub that takes diverted volume when another hub cannot sort on schedule. For example, the Indianapolis Air Hub is the Recovery Hub for the Memphis SuperHub.",
    "bullets": [
      "Every hub has one assigned Recovery Hub.",
      "Diversions run on recovery flights or trucks tracked as recovery lanes in the operations database."
    ],
    "owner": "Network Control Center",
    "keys": "backup diversion"
  },
  {
    "id": "revenue-per-package",
    "title": "Revenue per Package",
    "short": "Average shipping revenue earned per package after discounts. Also called yield.",
    "bullets": [
      "Shipping Revenue is what we bill the customer after discounts.",
      "Used to compare services and customers on a like-for-like basis."
    ],
    "owner": "Finance, Revenue Management",
    "keys": "yield"
  },
  {
    "id": "field-evidence",
    "title": "Field Evidence",
    "short": "Documents written by drivers and hub teams when something goes wrong with a package: hub delay notices, cold chain temperature logs, damage reports and customs notices.",
    "bullets": [
      "Captured as documents in the field-evidence bucket in Amazon S3.",
      "Read by the lakehouse as an object table, with the key facts extracted into the Field Evidence table.",
      "Explains the root cause behind a late package and whether a cold chain shipment was put at risk."
    ],
    "owner": "Network Operations, Service Quality team",
    "keys": "field reports documents drivers notes"
  }
];

const SHORTCUTS = [
  {
    kind: 'question', icon: 'bulb', kindLabel: 'Question', label: 'Which hubs are below target?',
    keys: 'hubs below target on time worst behind missing', ask: 'hubs',
  },
  {
    kind: 'preset', icon: 'thermo', kindLabel: 'Shortcut', label: 'Strategic healthcare packages held in Memphis',
    keys: 'healthcare cold chain temperature controlled held memphis aging pharma strategic accounts',
    sel: { hub: 'Memphis SuperHub', industry: 'Healthcare & Life Sciences', tier: 'Strategic', coldChain: true, aging: true },
    title: 'Strategic healthcare customers with temperature-controlled packages held 6+ hours at Memphis SuperHub',
  },
  {
    kind: 'question', icon: 'bulb', kindLabel: 'Question', label: 'Who should we call first?',
    keys: 'customers most revenue at risk call first exposed affected account directors', ask: 'customers',
  },
];

const FLAG_ENTRIES = [
  {
    kind: 'flag', icon: 'thermo', kindLabel: 'Filter', label: 'Temperature-controlled packages',
    sub: 'Cold chain shipments that must stay between 2 and 8°C',
    keys: 'cold chain refrigerated temperature controlled healthcare', apply: { coldChain: true },
  },
  {
    kind: 'flag', icon: 'clock', kindLabel: 'Filter', label: 'Packages held 6+ hours',
    sub: 'Aging packages sitting at a hub right now',
    keys: 'aging held stuck dwell waiting backlog', apply: { aging: true },
  },
];

const TRY_CHIPS = [
  SHORTCUTS[0],
  SHORTCUTS[1],
  SHORTCUTS[2],
  { kind: 'termRef', icon: 'book', label: 'What counts as on time?', termId: 'on-time-delivery-rate' },
  { kind: 'package', icon: 'package', label: 'Track 7815 4378 2857', tracking: '781543782857' },
];

const KIND_RANK = {
  customer: 10, hub: 11, service: 12, term: 20, question: 22, preset: 23, flag: 24,
  director: 30, industry: 31, tier: 32, reason: 33,
};

const ICONS = {
  search: 'M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  close: 'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  check: 'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  clock: 'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z',
  package: 'M20 2H4c-1 0-2 .9-2 2v3.01c0 .72.43 1.34 1 1.69V20c0 1.1 1.1 2 2 2h14c.9 0 2-.9 2-2V8.7c.57-.35 1-.97 1-1.69V4c0-1.1-1-2-2-2zm-1 18H5V9h14v11zm1-13H4V4h16v3zM9 12h6v2H9z',
  business: 'M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z',
  place: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 0 1 0-5 2.5 2.5 0 0 1 0 5z',
  truck: 'M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9 1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z',
  book: 'M21 5c-1.11-.35-2.33-.5-3.5-.5-1.95 0-4.05.4-5.5 1.5-1.45-1.1-3.55-1.5-5.5-1.5S2.45 4.9 1 6v14.65c0 .25.25.5.5.5.1 0 .15-.05.25-.05C3.1 20.45 5.05 20 6.5 20c1.95 0 4.05.4 5.5 1.5 1.35-.85 3.8-1.5 5.5-1.5 1.65 0 3.35.3 4.75 1.05.1.05.15.05.25.05.25 0 .5-.25.5-.5V6c-.6-.45-1.25-.75-2-1zm0 13.5c-1.1-.35-2.3-.5-3.5-.5-1.7 0-4.15.65-5.5 1.5V8c1.35-.85 3.8-1.5 5.5-1.5 1.2 0 2.4.15 3.5.5v11.5z',
  bulb: 'M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7zm2.85 11.1-.85.6V16h-4v-2.3l-.85-.6A4.997 4.997 0 0 1 7 9c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.63-.8 3.16-2.15 4.1z',
  thermo: 'M15 13V5c0-1.66-1.34-3-3-3S9 3.34 9 5v8c-1.21.91-2 2.37-2 4 0 2.76 2.24 5 5 5s5-2.24 5-5c0-1.63-.79-3.09-2-4zm-4-8c0-.55.45-1 1-1s1 .45 1 1h-1v1h1v2h-1v1h1v2h-2V5z',
  person: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  filter: 'M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z',
  doc: 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
  touch: 'M9 11.24V7.5a2.5 2.5 0 0 1 5 0v3.74c1.21-.81 2-2.18 2-3.74C16 5.01 13.99 3 11.5 3S7 5.01 7 7.5c0 1.56.79 2.93 2 3.74zm9.84 4.63-4.54-2.26c-.17-.07-.35-.11-.54-.11H13v-6c0-.83-.67-1.5-1.5-1.5S10 6.67 10 7.5v10.74l-3.43-.72c-.08-.01-.15-.03-.24-.03-.31 0-.59.13-.79.33l-.79.8 4.94 4.94c.27.27.65.44 1.06.44h6.79c.75 0 1.33-.55 1.44-1.28l.75-5.27c.01-.07.02-.14.02-.2 0-.62-.38-1.16-.91-1.38z',
};

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function toNum(v) {
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
}
function fmtInt(v) {
  const n = toNum(v);
  return n == null ? '–' : Math.round(n).toLocaleString('en-US');
}
function fmtUsd(v) {
  const n = toNum(v);
  return n == null ? '–' : '$' + Math.round(n).toLocaleString('en-US');
}
function fmtPct(v) {
  const n = toNum(v);
  return n == null ? '–' : (n * 100).toFixed(1) + '%';
}
function dayParts(v) {
  if (typeof v === 'number' && v > 100000) {
    const d = new Date(v);
    return [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()];
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v == null ? '' : v));
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}
function isoDay(v) {
  const p = dayParts(v);
  return p ? `${p[0]}-${String(p[1]).padStart(2, '0')}-${String(p[2]).padStart(2, '0')}` : null;
}
function fmtDay(v, withWeekday) {
  const p = dayParts(v);
  if (!p) return v == null ? '' : String(v);
  const text = `${MONTHS[p[1] - 1]} ${p[2]}`;
  if (!withWeekday) return text;
  return `${WEEKDAYS[new Date(Date.UTC(p[0], p[1] - 1, p[2])).getUTCDay()]}, ${text}`;
}
function fmtTracking(v) {
  return String(v == null ? '' : v).replace(/\D/g, '').replace(/(\d{4})(?=\d)/g, '$1 ');
}
function fmtClock(hhmm) {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(hhmm || ''));
  if (!m) return '';
  const h = Number(m[1]);
  return `${h % 12 || 12}:${m[2]} ${h >= 12 ? 'PM' : 'AM'}`;
}
function norm(s) {
  return String(s == null ? '' : s).toLowerCase().replace(/[^a-z0-9&]+/g, ' ').trim();
}
function lookerValue(v) {
  const s = String(v);
  return /[,"]/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s;
}
function isYes(v) {
  return v === true || /^(yes|true)$/i.test(String(v == null ? '' : v));
}
function rowsOf(settled) {
  return settled && settled.status === 'fulfilled' && Array.isArray(settled.value) ? settled.value : [];
}
function mix(a, b) {
  const out = { ...a };
  for (const key of Object.keys(b)) {
    const av = out[key];
    const bv = b[key];
    const plain = (x) => x && typeof x === 'object' && !Array.isArray(x);
    out[key] = plain(av) && plain(bv) ? mix(av, bv) : bv;
  }
  return out;
}
function selLabel(key, value) {
  if (DIMS[key].flag) return DIMS[key].label;
  return key === 'shipDay' ? fmtDay(value, true) : String(value);
}

function icon(name, size = 20) {
  return html`<svg class="cs-ic" viewBox="0 0 24 24" width=${size} height=${size} fill="currentColor" aria-hidden="true"><path d=${ICONS[name] || ''}></path></svg>`;
}

/** Luminous "verified number" mark: the metric uses the governed definition. */
function verifiedMark(statement) {
  return html`
    <span class="cs-verified" role="img" tabindex="0" aria-label="Verified. ${statement}">
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
        <path d="m1.8 12.6 4.4 4.4 9.2-9.6M11.4 16.6l.4.4 9.6-9.6" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path>
      </svg>
      <span class="cs-verified-tip" aria-hidden="true">
        <span class="cs-verified-tip-title">Verified</span>
        <span>${statement}</span>
        <span class="cs-verified-tip-meta">Business glossary in Knowledge Catalog · calculated in Looker</span>
      </span>
    </span>`;
}

/* ------------------------------------------------------------------ */
/* Chart styling (Luminous: quiet structure, dotted grid, 4px bar tips) */
/* ------------------------------------------------------------------ */

const AXIS_LABEL = { color: 'rgba(27,21,36,0.62)', fontSize: '12px', fontWeight: '400' };
const VALUE_LABEL = { color: INK, fontSize: '12px', fontWeight: '500', textOutline: 'none' };
const BAR_SHAPE = { borderRadius: 4, borderWidth: 0, pointPadding: 0.12, groupPadding: 0.04 };
const LINE_SHAPE = { lineWidth: 2.5, marker: { enabled: true, symbol: 'circle', radius: 4 } };

const TARGET_LINE = {
  value: TARGET,
  color: ORANGE_INK,
  dashStyle: 'Dash',
  width: 1.5,
  zIndex: 5,
};

const CHART_BASE = {
  chart: { style: { fontFamily: FONT }, backgroundColor: 'transparent', spacingRight: 28 },
  tooltip: {
    backgroundColor: '#FFFFFF',
    borderColor: 'rgba(27,21,36,0.45)',
    borderWidth: 1,
    borderRadius: 12,
    shadow: false,
    style: { color: INK, fontSize: '13px' },
  },
  legend: { itemStyle: { color: 'rgba(27,21,36,0.72)', fontSize: '12px', fontWeight: '400' } },
  xAxis: { lineColor: 'rgba(27,21,36,0.30)', tickLength: 0, labels: { style: AXIS_LABEL } },
  yAxis: {
    gridLineColor: 'rgba(27,21,36,0.18)',
    gridLineDashStyle: 'Dot',
    title: { text: null },
    labels: { style: AXIS_LABEL, overflow: 'allow' },
  },
};

const TREND_OPTIONS = mix(CHART_BASE, {
  chart: {
    events: {
      click(e) {
        const hits = (this.series || [])
          .map((s) => (s.visible && s.searchPoint ? s.searchPoint(e, true) : null))
          .filter(Boolean);
        if (!hits.length) return;
        const near = hits.some((p) => Math.abs(this.plotTop + p.plotY - e.chartY) <= 36);
        if (near && hits[0].firePointEvent) hits[0].firePointEvent('click', e);
      },
    },
  },
  colors: [PURPLE, 'rgba(27,21,36,0.30)'],
  legend: {
    enabled: true,
    align: 'left',
    verticalAlign: 'top',
    padding: 0,
    margin: 10,
    symbolWidth: 18,
    labelFormatter() {
      return this.index === 0 ? 'On-time delivery rate (official)' : 'If every late package counted, whatever the cause';
    },
  },
  xAxis: {
    tickInterval: 7,
    labels: {
      rotation: 0,
      formatter() {
        return fmtDay(this.value);
      },
    },
  },
  yAxis: {
    max: 1,
    softMin: 0.9,
    tickInterval: 0.05,
    endOnTick: false,
    labels: {
      formatter() {
        return `${Math.round(this.value * 100)}%`;
      },
    },
    plotLines: [TARGET_LINE],
  },
  plotOptions: {
    line: LINE_SHAPE,
    series: LINE_SHAPE,
  },
});

const HUB_OPTIONS = mix(CHART_BASE, {
  legend: { enabled: false },
  yAxis: {
    min: 0,
    max: 1.16,
    endOnTick: false,
    tickPositions: [0, 0.25, 0.5, 0.75, 1],
    labels: {
      formatter() {
        return `${Math.round(this.value * 100)}%`;
      },
    },
    plotLines: [TARGET_LINE],
  },
  plotOptions: {
    bar: BAR_SHAPE,
    series: {
      borderRadius: 4,
      borderWidth: 0,
      pointPadding: 0.12,
      groupPadding: 0.04,
      dataLabels: {
        enabled: true,
        crop: false,
        overflow: 'allow',
        backgroundColor: 'rgba(255,255,255,0.94)',
        padding: 2,
        borderRadius: 3,
        style: VALUE_LABEL,
        formatter() {
          return fmtPct(this.y);
        },
      },
    },
  },
});

const MONEY_BAR_OPTIONS = mix(CHART_BASE, {
  legend: { enabled: false },
  xAxis: { labels: { style: { width: '176px' } } },
  yAxis: { maxPadding: 0.2 },
  plotOptions: {
    bar: BAR_SHAPE,
    series: {
      borderRadius: 4,
      borderWidth: 0,
      pointPadding: 0.12,
      groupPadding: 0.04,
      dataLabels: {
        enabled: true,
        crop: false,
        overflow: 'allow',
        style: VALUE_LABEL,
        formatter() {
          return fmtUsd(this.y);
        },
      },
    },
  },
});

const COUNT_BAR_OPTIONS = mix(CHART_BASE, {
  legend: { enabled: false },
  xAxis: { labels: { style: { width: '176px' } } },
  yAxis: { maxPadding: 0.2 },
  plotOptions: {
    bar: BAR_SHAPE,
    series: {
      borderRadius: 4,
      borderWidth: 0,
      pointPadding: 0.12,
      groupPadding: 0.04,
      dataLabels: {
        enabled: true,
        crop: false,
        overflow: 'allow',
        style: VALUE_LABEL,
        formatter() {
          return fmtInt(this.y);
        },
      },
    },
  },
});

const HELD_COLUMNS = [
  {
    field: 'shipments.tracking_number', headerName: 'Tracking number', width: 150, cellClass: 'cs-mono',
    valueFormatter: (p) => fmtTracking(p.value),
  },
  { field: 'customers.customer_name', headerName: 'Customer', flex: 1, minWidth: 170 },
  { field: 'services.service_name', headerName: 'Service', width: 165 },
  { field: 'hubs.hub_name', headerName: 'Hub', width: 175 },
  {
    field: 'live_package_tracking.hub_dwell_hours', headerName: 'Hours held', width: 115, type: 'rightAligned',
    valueFormatter: (p) => (toNum(p.value) == null ? '' : toNum(p.value).toFixed(1)),
  },
  {
    field: 'shipments.is_cold_chain', headerName: 'Cold chain', width: 115,
    valueFormatter: (p) => (isYes(p.value) ? 'Yes' : ''),
  },
  { field: 'live_package_tracking.recovery_plan', headerName: 'Recovery plan', flex: 2.2, minWidth: 300 },
];

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const STYLE = html`
  <style>
    cymbal-shipping-service-performance {
      display: block;
      --cs-purple: #4D148C;
      --cs-purple-deep: #2A0A52;
      --cs-purple-soft: #8E63C7;
      --cs-lilac: #EFE7F8;
      --cs-lilac-wash: #F8F4FC;
      --cs-orange: #FF6600;
      --cs-orange-ink: #B84300;
      --cs-orange-wash: #FFF3EA;
      --cs-ink: #1B1524;
      --cs-ink-72: rgba(27, 21, 36, 0.74);
      --cs-ink-60: rgba(27, 21, 36, 0.62);
      --cs-ink-48: rgba(27, 21, 36, 0.48);
      --cs-line: rgba(27, 21, 36, 0.10);
      --cs-line-strong: rgba(27, 21, 36, 0.20);
      --cs-bg: #FBF9FD;
      --cs-card: #FFFFFF;
      --cs-positive: #008052;
      --cs-critical: #C5221F;
      --cs-font: "Google Sans Flex", "Google Sans", "Google Sans Text", Roboto, "Helvetica Neue", Arial, sans-serif;
      --cs-mono: "Google Sans Code", ui-monospace, "SF Mono", Menlo, monospace;

      --app-primary: #4D148C;
      --app-chart-1: #4D148C;
      --app-chart-2: #FF6600;
      --app-chart-3: #8E63C7;
      --app-chart-4: #2A0A52;
      --app-chart-5: #CDBFE0;
      --app-chart-6: #008052;
      --app-chart-7: #8A8494;
      --app-chart-unselected: #E2DCEA;
      --app-bg: #FBF9FD;
      --app-card-bg: #FFFFFF;
      --app-border: rgba(27, 21, 36, 0.10);
      --app-title: #1B1524;
      --app-text: #1B1524;
      --app-muted: rgba(27, 21, 36, 0.62);
      --app-success: #008052;
      --app-danger: #C5221F;
      --app-radius: 20px;
    }

    .cs-root {
      font-family: var(--cs-font);
      color: var(--cs-ink);
      background: var(--cs-bg);
      padding: 20px 28px 32px;
      box-sizing: border-box;
      min-height: 100%;
      -webkit-font-smoothing: antialiased;
    }
    .cs-root *, .cs-root *::before, .cs-root *::after { box-sizing: border-box; }
    .cs-root button { font-family: var(--cs-font); }
    .cs-root button:focus-visible, .cs-root input:focus-visible, .cs-verified:focus-visible {
      outline: 2px solid var(--cs-purple);
      outline-offset: 2px;
    }
    .cs-ic { flex: none; display: block; }

    /* App bar */
    .cs-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
    .cs-brand { display: flex; align-items: center; gap: 14px; }
    .cs-logo { font-size: 27px; line-height: 1; font-weight: 800; letter-spacing: -0.04em; white-space: nowrap; }
    .cs-logo .a { color: var(--cs-purple); }
    .cs-logo .b { color: var(--cs-orange); }
    .cs-bar-div { width: 1px; height: 24px; background: var(--cs-line-strong); }
    .cs-bar-title { font-size: 17px; line-height: 24px; color: var(--cs-ink-72); }
    .cs-asof {
      display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 14px 0 12px;
      border-radius: 9999px; background: var(--cs-card); border: 1px solid var(--cs-line);
      font-size: 13px; font-weight: 500; color: var(--cs-ink-72); white-space: nowrap;
    }
    .cs-asof-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cs-positive); box-shadow: 0 0 0 3px rgba(0, 128, 82, 0.16); }

    /* Look it up */
    .cs-look {
      position: relative; border-radius: 28px; padding: 24px 28px 22px; margin-bottom: 16px;
      border: 1px solid var(--cs-line);
      background:
        radial-gradient(900px 260px at 0% -30%, rgba(77, 20, 140, 0.11), transparent 62%),
        radial-gradient(760px 240px at 100% -40%, rgba(255, 102, 0, 0.10), transparent 60%),
        var(--cs-card);
    }
    .cs-look-h { margin: 0; font-size: 28px; line-height: 36px; font-weight: 400; letter-spacing: -0.01em; }
    .cs-look-sub { margin: 2px 0 16px; font-size: 14px; line-height: 20px; color: var(--cs-ink-60); }
    .cs-search { position: relative; max-width: 780px; }
    .cs-search-box {
      display: flex; align-items: center; gap: 12px; height: 56px; padding: 0 8px 0 18px;
      border-radius: 28px; background: var(--cs-card); border: 1px solid var(--cs-line-strong);
      color: var(--cs-ink-60); transition: box-shadow 0.15s, border-color 0.15s;
    }
    .cs-search-box:focus-within { border-color: var(--cs-purple); box-shadow: 0 0 0 3px rgba(77, 20, 140, 0.14); }
    .cs-search-box input {
      flex: 1; min-width: 0; border: 0; outline: 0; background: transparent;
      font: 400 16px/24px var(--cs-font); color: var(--cs-ink);
    }
    .cs-search-box input:focus-visible { outline: 0; }
    .cs-search-box input::placeholder { color: var(--cs-ink-48); }
    .cs-icon-btn {
      width: 40px; height: 40px; border-radius: 50%; border: 0; background: transparent; color: var(--cs-ink-60);
      display: inline-flex; align-items: center; justify-content: center; cursor: pointer; flex: none;
    }
    .cs-icon-btn:hover { background: rgba(27, 21, 36, 0.06); }
    .cs-suggest {
      position: absolute; z-index: 40; top: calc(100% + 6px); left: 0; right: 0; padding: 8px;
      background: var(--cs-card); border: 1px solid var(--cs-line); border-radius: 20px;
      box-shadow: 0 10px 30px rgba(42, 10, 82, 0.16); max-height: 400px; overflow: auto;
    }
    .cs-suggest-item {
      display: flex; align-items: center; gap: 12px; width: 100%; padding: 8px 12px; border: 0; border-radius: 12px;
      background: transparent; text-align: left; cursor: pointer; color: var(--cs-ink); font-size: 14px;
    }
    .cs-suggest-item.is-active, .cs-suggest-item:hover { background: var(--cs-lilac-wash); }
    .cs-suggest-item[disabled] { cursor: default; opacity: 0.7; }
    .cs-suggest-ic {
      width: 32px; height: 32px; border-radius: 10px; background: var(--cs-lilac); color: var(--cs-purple);
      display: inline-flex; align-items: center; justify-content: center; flex: none;
    }
    .cs-suggest-main { flex: 1; min-width: 0; }
    .cs-suggest-label { font-weight: 500; line-height: 20px; }
    .cs-suggest-sub { font-size: 12px; line-height: 16px; color: var(--cs-ink-60); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .cs-suggest-kind { font-size: 11px; line-height: 16px; font-weight: 500; color: var(--cs-ink-60); padding: 2px 8px; border-radius: 9999px; background: rgba(27, 21, 36, 0.05); flex: none; }
    .cs-suggest-empty { padding: 12px; font-size: 14px; line-height: 20px; color: var(--cs-ink-60); }
    .cs-try { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 14px; }
    .cs-try-label { font-size: 12px; font-weight: 500; color: var(--cs-ink-60); margin-right: 2px; }
    .cs-chip {
      display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 12px 0 10px;
      border-radius: 8px; border: 1px solid var(--cs-line-strong); background: var(--cs-card);
      color: var(--cs-ink); font-size: 13px; font-weight: 500; cursor: pointer; transition: background 0.12s, border-color 0.12s;
    }
    .cs-chip:hover { background: var(--cs-lilac-wash); border-color: var(--cs-purple-soft); }
    .cs-chip .cs-ic { color: var(--cs-purple); }

    /* Answer */
    .cs-answer {
      position: relative; margin-top: 16px; max-width: 1040px; padding: 18px 56px 16px 20px;
      background: var(--cs-card); border: 1px solid var(--cs-line); border-radius: 20px;
      animation: cs-rise 0.22s ease-out;
    }
    @keyframes cs-rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
    @media (prefers-reduced-motion: reduce) { .cs-answer { animation: none; } }
    .cs-answer-close { position: absolute; top: 8px; right: 8px; }
    .cs-eyebrow { font-size: 12px; line-height: 16px; font-weight: 500; color: var(--cs-purple); }
    .cs-answer-title { margin: 2px 0 0; font-size: 17px; line-height: 24px; font-weight: 540; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
    .cs-answer-text { margin: 6px 0 0; font-size: 14px; line-height: 20px; color: var(--cs-ink-72); max-width: 80ch; }
    .cs-answer-list { margin: 8px 0 0; padding-left: 18px; font-size: 14px; line-height: 20px; color: var(--cs-ink-72); max-width: 80ch; }
    .cs-answer-list li { margin: 2px 0; }
    .cs-answer-foot { margin-top: 10px; font-size: 12px; line-height: 16px; color: var(--cs-ink-60); display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
    .cs-rank { margin: 10px -12px 0; display: grid; gap: 2px; }
    .cs-rank-row {
      display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(90px, 1fr) minmax(150px, auto); gap: 16px; align-items: center;
      width: 100%; padding: 9px 12px; border: 0; border-radius: 12px; background: transparent; color: var(--cs-ink);
      text-align: left; cursor: pointer;
    }
    .cs-rank-row:hover { background: var(--cs-lilac-wash); }
    .cs-rank-name { font-size: 14px; line-height: 20px; font-weight: 500; }
    .cs-rank-sub { font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-rank-bar { height: 6px; border-radius: 3px; background: rgba(27, 21, 36, 0.08); overflow: hidden; }
    .cs-rank-bar > span { display: block; height: 100%; border-radius: 3px; background: var(--cs-purple); }
    .cs-rank-bar.is-bad > span { background: var(--cs-orange); }
    .cs-rank-val { text-align: right; font-size: 15px; line-height: 20px; font-weight: 500; font-variant-numeric: tabular-nums; }
    .cs-rank-val small { display: block; font-size: 12px; line-height: 16px; font-weight: 400; color: var(--cs-ink-60); }
    .cs-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px 24px; margin: 14px 0 0; }
    .cs-fact dt { font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-fact dd { margin: 2px 0 0; font-size: 14px; line-height: 20px; font-weight: 500; }
    .cs-fact dd small { display: block; font-size: 12px; line-height: 16px; font-weight: 400; color: var(--cs-ink-60); }
    .cs-fact.is-wide { grid-column: 1 / -1; }
    .cs-note { margin-top: 14px; padding: 12px 14px; border-radius: 14px; background: var(--cs-orange-wash); border: 1px solid rgba(255, 102, 0, 0.22); }
    .cs-note.is-quiet { background: var(--cs-lilac-wash); border-color: var(--cs-line); }
    .cs-note p { margin: 6px 0 0; font-size: 14px; line-height: 20px; }
    .cs-note .cs-note-meta { font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-pill { display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 10px; border-radius: 9999px; font-size: 12px; font-weight: 500; white-space: nowrap; }
    .cs-pill.is-bad { background: #FDE7E5; color: #A51D1A; }
    .cs-pill.is-warn { background: #FFEBDC; color: var(--cs-orange-ink); }
    .cs-pill.is-good { background: #DDF4E6; color: #00663F; }
    .cs-pill.is-info { background: var(--cs-lilac); color: var(--cs-purple); }
    .cs-spinner { width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--cs-lilac); border-top-color: var(--cs-purple); animation: cs-spin 0.7s linear infinite; flex: none; }
    @keyframes cs-spin { to { transform: rotate(360deg); } }

    /* Controls */
    .cs-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 10px; margin-bottom: 14px; min-height: 40px; }
    .cs-seg { display: inline-flex; border: 1px solid var(--cs-line-strong); border-radius: 9999px; overflow: hidden; background: var(--cs-card); }
    .cs-seg button {
      height: 38px; padding: 0 16px; border: 0; border-right: 1px solid var(--cs-line-strong); background: transparent;
      font-size: 14px; font-weight: 500; color: var(--cs-ink); cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
    }
    .cs-seg button:last-child { border-right: 0; }
    .cs-seg button:hover { background: var(--cs-lilac-wash); }
    .cs-seg button[aria-pressed="true"] { background: var(--cs-lilac); color: var(--cs-purple-deep); }
    .cs-fchip {
      display: inline-flex; align-items: center; gap: 2px; height: 32px; padding: 0 4px 0 12px; border-radius: 8px;
      background: var(--cs-purple); color: #FFFFFF; font-size: 13px; font-weight: 500; white-space: nowrap;
    }
    .cs-fchip .k { font-weight: 400; opacity: 0.8; margin-right: 4px; }
    .cs-fchip button { width: 24px; height: 24px; border-radius: 50%; border: 0; background: transparent; color: inherit; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
    .cs-fchip button:hover { background: rgba(255, 255, 255, 0.2); }
    .cs-text-btn { height: 32px; padding: 0 12px; border-radius: 9999px; border: 0; background: transparent; color: var(--cs-purple); font-size: 13px; font-weight: 500; cursor: pointer; }
    .cs-text-btn:hover { background: var(--cs-lilac); }
    .cs-hint { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; font-size: 13px; line-height: 20px; color: var(--cs-ink-60); }

    /* KPI scorecards */
    .cs-kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-bottom: 14px; }
    .cs-kpi { position: relative; min-width: 0; padding: 16px 18px 14px; background: var(--cs-card); border: 1px solid var(--cs-line); border-radius: 20px; }
    .cs-kpi.is-alert::before { content: ''; position: absolute; top: -1px; left: 22px; right: 22px; height: 3px; border-radius: 0 0 3px 3px; background: var(--cs-orange); }
    .cs-kpi-label { display: flex; align-items: center; min-height: 22px; font-size: 14px; line-height: 20px; color: var(--cs-ink-60); }
    .cs-kpi app-kpi { display: block; margin-top: 2px; text-align: left; }
    .cs-kpi .da-kpi-wrap, .cs-kpi .kpi-body { display: block; width: 100%; height: auto; text-align: left; }
    .cs-kpi .kpi-label, .cs-kpi .kpi-icon { display: none; }
    .cs-kpi .kpi-value {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-start; gap: 0 10px; min-height: 46px;
      font-family: var(--cs-font); font-size: clamp(28px, 2.7vw, 38px); line-height: 46px; font-weight: 300;
      letter-spacing: -0.02em; color: var(--cs-ink); font-variant-numeric: tabular-nums; font-variation-settings: "ROND" 100;
    }
    .cs-kpi .kpi-value-text { flex: none; overflow: visible; text-overflow: clip; }
    .cs-kpi .kpi-change { font-family: var(--cs-font); font-size: 12px; line-height: 16px; font-weight: 500; letter-spacing: 0; padding: 2px 8px; }
    .cs-kpi .kpi-subtitle {
      display: block; margin-top: 4px; min-height: 16px; font-size: 12px; line-height: 16px; font-weight: 400;
      color: var(--cs-ink-60); opacity: 1; white-space: normal; overflow: visible; text-align: left;
    }

    /* Panels */
    .cs-row-a { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 14px; margin-bottom: 14px; }
    .cs-row-b { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 14px; }
    .cs-row-c { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
    .cs-panel { min-width: 0; display: flex; flex-direction: column; padding: 18px 20px 12px; background: var(--cs-card); border: 1px solid var(--cs-line); border-radius: 20px; }
    .cs-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
    .cs-panel-title { margin: 0; font-size: 17px; line-height: 24px; font-weight: 540; display: flex; align-items: center; }
    .cs-panel-sub { margin: 2px 0 0; font-size: 14px; line-height: 20px; color: var(--cs-ink-60); }
    .cs-keys { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 14px; margin-top: 4px; min-height: 20px; font-size: 13px; line-height: 20px; color: var(--cs-ink-60); }
    .cs-key { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
    .cs-key i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
    .cs-key i.cs-key-dash { width: 18px; height: 0; border-radius: 0; border-top: 2px dashed var(--cs-orange-ink); }
    .cs-sel {
      display: inline-flex; align-items: center; gap: 2px; height: 28px; padding: 0 2px 0 10px; border-radius: 8px; flex: none;
      background: var(--cs-lilac); color: var(--cs-purple-deep); font-size: 12px; font-weight: 500; white-space: nowrap; max-width: 220px;
    }
    .cs-sel span { overflow: hidden; text-overflow: ellipsis; }
    .cs-sel button { width: 24px; height: 24px; border-radius: 50%; border: 0; background: transparent; color: inherit; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; flex: none; }
    .cs-sel button:hover { background: rgba(77, 20, 140, 0.12); }
    .cs-panel .ag-root-wrapper { border: 0; }
    .cs-panel .ag-row { cursor: pointer; }
    .cs-mono { font-family: var(--cs-mono); font-variant-numeric: tabular-nums; }

    /* Field reports */
    .cs-cause { margin: 2px 0 12px; padding: 10px 14px; border-radius: 14px; background: var(--cs-orange-wash); border: 1px solid rgba(255, 102, 0, 0.22); font-size: 14px; line-height: 20px; }
    .cs-cause b { font-weight: 540; }
    .cs-cause small { display: block; font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-reports { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 8px; }
    .cs-report {
      display: block; width: 100%; padding: 12px 14px; text-align: left; cursor: pointer; color: var(--cs-ink);
      background: var(--cs-card); border: 1px solid var(--cs-line); border-radius: 16px; transition: border-color 0.12s, background 0.12s;
    }
    .cs-report:hover { border-color: var(--cs-purple-soft); background: var(--cs-lilac-wash); }
    .cs-report-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
    .cs-report-text { margin: 0; font-size: 14px; line-height: 20px; display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
    .cs-report-meta { margin-top: 6px; font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-empty { padding: 24px 8px; font-size: 14px; line-height: 20px; color: var(--cs-ink-60); text-align: center; }

    /* Verified mark */
    .cs-verified { position: relative; display: inline-flex; margin-left: 6px; padding: 1px; border-radius: 4px; color: var(--cs-positive); cursor: pointer; vertical-align: -3px; }
    .cs-verified:hover { background: rgba(0, 128, 82, 0.12); }
    .cs-verified-tip {
      position: absolute; z-index: 30; bottom: calc(100% + 8px); left: -12px; width: 264px; padding: 10px 16px;
      display: flex; flex-direction: column; gap: 2px; text-align: left; white-space: normal; pointer-events: none;
      background: var(--cs-card); color: var(--cs-ink); border-radius: 20px; font-size: 14px; line-height: 20px; font-weight: 400;
      box-shadow: inset 0 0 0 1px var(--cs-ink-60), 0 1px 4px rgba(0, 0, 0, 0.1);
      opacity: 0; visibility: hidden; transform: translateY(4px); transition: opacity 0.15s, transform 0.15s, visibility 0s 0.15s;
    }
    .cs-verified-tip-title { font-weight: 500; color: var(--cs-positive); }
    .cs-verified-tip-meta { margin-top: 4px; font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-verified:hover .cs-verified-tip, .cs-verified:focus-visible .cs-verified-tip { opacity: 1; visibility: visible; transform: none; transition-delay: 0s; }

    /* Footer */
    .cs-foot { margin-top: 18px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px; line-height: 16px; color: var(--cs-ink-60); }
    .cs-src { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 9999px; border: 1px solid var(--cs-line); background: var(--cs-card); white-space: nowrap; }
    .cs-src b { font-weight: 500; color: var(--cs-ink); }

    @media (max-width: 1180px) {
      .cs-kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .cs-row-b { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 960px) {
      .cs-row-a { grid-template-columns: minmax(0, 1fr); }
      .cs-reports { grid-template-columns: minmax(0, 1fr); }
      .cs-hint { display: none; }
    }
    @media (max-width: 700px) {
      .cs-root { padding: 14px 14px 24px; }
      .cs-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .cs-row-b { grid-template-columns: minmax(0, 1fr); }
      .cs-look { padding: 18px 16px; border-radius: 22px; }
      .cs-rank-row { grid-template-columns: minmax(0, 1fr) auto; }
      .cs-rank-bar { display: none; }
    }
  </style>
`;

/* ------------------------------------------------------------------ */
/* App                                                                 */
/* ------------------------------------------------------------------ */

export class CymbalShippingServicePerformance extends DataApp {
  static properties = {
    csPeriod: { type: String },
    csSel: { type: Object },
    csText: { type: String },
    csOpen: { type: Boolean },
    csActive: { type: Number },
    csAnswer: { type: Object },
    csLookups: { type: Object },
    csCtx: { type: Object },
    csReports: { type: Object },
    csHubColors: { type: Object },
  };

  constructor() {
    super();
    this.lookerModel = MODEL;
    this.explore = EXPLORE;
    this.csPeriod = 'this';
    this.csSel = {};
    this.csText = '';
    this.csOpen = false;
    this.csActive = 0;
    this.csAnswer = null;
    this.csLookups = { customers: [], hubs: [], services: [] };
    this.csCtx = null;
    this.csReports = { state: 'loading', items: [], cause: null };
    this.csHubColors = null;
    this._ctxSeq = 0;
    this._answerSeq = 0;
    this._matchList = [];
    this._index = this._buildIndex();
    this._gridOptions = {
      rowHeight: 40,
      headerHeight: 40,
      onRowClicked: (e) => {
        const tracking = e && e.data ? e.data['shipments.tracking_number'] : null;
        if (tracking) this._openPackage(String(tracking), true);
      },
    };
  }

  firstUpdated(changed) {
    if (super.firstUpdated) super.firstUpdated(changed);
    this._loadLookups();
    this._refreshContext();
  }

  /* ---------- filters ---------- */

  getEffectiveFilters(local = {}, { except = null, anyPeriod = false } = {}) {
    const filters = { ...(this.dashboardFilters || {}) };
    const period = PERIODS[this.csPeriod] || PERIODS.this;
    if (!anyPeriod && period.filter) filters['shipments.reporting_period'] = period.filter;
    const skip = Array.isArray(except) ? except : [except];
    for (const key of Object.keys(DIMS)) {
      if (skip.includes(key)) continue;
      const value = this.csSel[key];
      if (value == null || value === false || value === '') continue;
      if (DIMS[key].flag) filters[DIMS[key].field] = 'yes';
      else if (key === 'shipDay') filters[DIMS[key].field] = String(value).replace(/-/g, '/');
      else filters[DIMS[key].field] = lookerValue(value);
    }
    return { ...filters, ...local };
  }

  _setSel(patch, replace = false) {
    const next = replace ? {} : { ...this.csSel };
    for (const [key, value] of Object.entries(patch)) {
      if (value == null || value === false || value === '') delete next[key];
      else next[key] = value;
    }
    // A single ship day only makes sense across the whole six weeks.
    if (next.shipDay && this.csPeriod !== 'all') this.csPeriod = 'all';
    this.csSel = next;
    this._refreshContext();
  }

  _toggle(key, value) {
    this._setSel({ [key]: this.csSel[key] === value ? null : value });
  }

  _clearAll() {
    this.csSel = {};
    this._refreshContext();
  }

  _setPeriod(period) {
    if (period === this.csPeriod) return;
    this.csPeriod = period;
    if (this.csSel.shipDay) {
      const next = { ...this.csSel };
      delete next.shipDay;
      this.csSel = next;
    }
    this._refreshContext();
  }

  _onChart(key, e) {
    // One source of truth for selections: the chips on this page.
    e.preventDefault();
    e.stopPropagation();
    const raw = e.detail ? e.detail.value : null;
    if (raw == null || raw === '') return;
    const value = key === 'shipDay' ? isoDay(raw) : String(raw);
    if (value) this._toggle(key, value);
  }

  /* ---------- data that is not a chart ---------- */

  _run(query) {
    return this.runQuery({ model: MODEL, explore: EXPLORE, limit: '50', ...query });
  }

  async _loadLookups() {
    const [customers, hubs, services] = await Promise.allSettled([
      this._run({
        fields: ['customers.customer_name', 'customers.customer_tier', 'customers.industry_vertical', 'customers.account_director'],
        sorts: ['customers.customer_name asc'],
        limit: '200',
      }),
      this._run({
        fields: ['hubs.hub_name', 'hubs.hub_code', 'hubs.hub_type', 'hubs.region'],
        sorts: ['hubs.hub_name asc'],
        limit: '100',
      }),
      this._run({
        fields: ['services.service_name', 'services.service_family', 'services.commit_time_local', 'services.commit_days'],
        sorts: ['services.service_name asc'],
        limit: '100',
      }),
    ]);
    this.csLookups = {
      customers: rowsOf(customers)
        .map((r) => ({
          name: r['customers.customer_name'],
          tier: r['customers.customer_tier'],
          industry: r['customers.industry_vertical'],
          director: r['customers.account_director'],
        }))
        .filter((c) => c.name),
      hubs: rowsOf(hubs)
        .map((r) => ({
          name: r['hubs.hub_name'],
          code: r['hubs.hub_code'],
          type: r['hubs.hub_type'],
          region: r['hubs.region'],
        }))
        .filter((h) => h.name),
      services: rowsOf(services)
        .map((r) => ({
          name: r['services.service_name'],
          family: r['services.service_family'],
          clock: fmtClock(r['services.commit_time_local']),
          days: toNum(r['services.commit_days']),
        }))
        .filter((s) => s.name),
    };
    this._index = this._buildIndex();
  }

  async _refreshContext() {
    const seq = ++this._ctxSeq;
    const everyPeriod = this.getEffectiveFilters({}, { anyPeriod: true, except: 'aging' });
    const current = this.getEffectiveFilters();
    this.csCtx = null;
    this.csReports = { ...this.csReports, state: 'loading' };

    const [periods, hot, delays, recent, causes, hubs] = await Promise.allSettled([
      this._run({
        fields: ['shipments.reporting_period', 'shipments.on_time_delivery_rate', 'shipments.revenue_at_risk'],
        filters: everyPeriod,
        limit: '10',
      }),
      this._run({
        fields: REPORT_FIELDS,
        filters: { ...current, 'exception_evidence.is_temperature_excursion': 'yes' },
        sorts: ['exception_evidence.max_temperature_c desc'],
        limit: '12',
      }),
      this._run({
        fields: REPORT_FIELDS,
        filters: { ...current, 'exception_evidence.document_type': 'Hub Delay Notice' },
        sorts: ['live_package_tracking.hub_dwell_hours desc'],
        limit: '6',
      }),
      this._run({
        fields: REPORT_FIELDS,
        filters: { ...current, 'exception_evidence.document_type': '-NULL' },
        sorts: ['exception_evidence.captured_date desc'],
        limit: '8',
      }),
      this._run({
        fields: ['exception_evidence.root_cause', 'exception_evidence.document_count'],
        filters: { ...current, 'exception_evidence.root_cause': '-NULL' },
        sorts: ['exception_evidence.document_count desc'],
        limit: '3',
      }),
      this._run({
        fields: ['hubs.hub_name', 'shipments.on_time_delivery_rate'],
        filters: this.getEffectiveFilters({}, { except: ['hub', 'aging'] }),
        limit: '50',
      }),
    ]);
    if (seq !== this._ctxSeq) return;

    const hubColors = {};
    for (const r of rowsOf(hubs)) {
      const rate = toNum(r['shipments.on_time_delivery_rate']);
      if (r['hubs.hub_name'] && rate != null) hubColors[r['hubs.hub_name']] = rate < TARGET ? ORANGE : PURPLE;
    }
    this.csHubColors = Object.keys(hubColors).length ? hubColors : null;

    const byPeriod = {};
    for (const r of rowsOf(periods)) {
      byPeriod[r['shipments.reporting_period']] = {
        rate: toNum(r['shipments.on_time_delivery_rate']),
        risk: toNum(r['shipments.revenue_at_risk']),
      };
    }
    this.csCtx = { byPeriod };

    const items = [];
    const seen = new Set();
    const push = (r) => {
      const id = r['exception_evidence.evidence_id'];
      if (!id || seen.has(id) || items.length >= 3) return;
      seen.add(id);
      items.push(r);
    };
    const customersSeen = new Set();
    for (const r of rowsOf(hot)) {
      const name = r['customers.customer_name'];
      if (customersSeen.has(name) || customersSeen.size >= 2) continue;
      customersSeen.add(name);
      push(r);
    }
    for (const r of rowsOf(delays).slice(0, 1)) push(r);
    for (const r of rowsOf(recent)) push(r);

    const top = rowsOf(causes)[0];
    const failed = [hot, delays, recent].every((s) => s.status !== 'fulfilled');
    this.csReports = {
      state: failed ? 'error' : 'ready',
      items,
      cause: top && top['exception_evidence.root_cause']
        ? { text: top['exception_evidence.root_cause'], count: toNum(top['exception_evidence.document_count']) }
        : null,
    };
  }

  /* ---------- look it up ---------- */

  _buildIndex() {
    const L = this.csLookups || {};
    const customers = L.customers || [];
    const items = [];
    const add = (item) => {
      items.push({ ...item, hay: norm(`${item.label} ${item.keys || ''}`) });
    };
    const uniq = (list) => Array.from(new Set(list.filter(Boolean))).sort();

    for (const s of SHORTCUTS) add(s);
    for (const t of GLOSSARY) {
      add({ kind: 'term', icon: 'book', kindLabel: 'Definition', label: t.title, sub: 'What it means at Cymbal Shipping', keys: t.keys, term: t });
    }
    for (const c of customers) {
      add({ kind: 'customer', icon: 'business', kindLabel: 'Customer', label: c.name, sub: `${c.tier} account · ${c.industry}`, apply: { customer: c.name }, entity: c });
    }
    for (const h of L.hubs || []) {
      add({ kind: 'hub', icon: 'place', kindLabel: 'Hub', label: h.name, sub: `${h.type} · ${h.region} region`, keys: h.code, apply: { hub: h.name }, entity: h });
    }
    for (const s of L.services || []) {
      add({ kind: 'service', icon: 'truck', kindLabel: 'Service', label: s.name, sub: `${s.family} service`, apply: { service: s.name }, entity: s });
    }
    for (const d of uniq(customers.map((c) => c.director))) {
      const n = customers.filter((c) => c.director === d).length;
      add({ kind: 'director', icon: 'person', kindLabel: 'Account director', label: d, sub: `Looks after ${n} customer${n === 1 ? '' : 's'}`, apply: { director: d } });
    }
    for (const i of uniq(customers.map((c) => c.industry))) {
      add({ kind: 'industry', icon: 'filter', kindLabel: 'Industry', label: i, sub: 'Every customer in this industry', apply: { industry: i } });
    }
    for (const t of uniq(customers.map((c) => c.tier))) {
      add({ kind: 'tier', icon: 'filter', kindLabel: 'Account tier', label: `${t} accounts`, sub: 'Every customer in this account tier', apply: { tier: t } });
    }
    for (const f of FLAG_ENTRIES) add(f);
    for (const r of Object.keys(REASON_COLORS)) {
      add({
        kind: 'reason', icon: 'filter', kindLabel: 'Delay reason', label: r,
        sub: REASON_COLORS[r] === ORANGE ? 'Within our control' : 'Outside our control', apply: { reason: r },
      });
    }
    return items;
  }

  _matches(text) {
    const q = norm(text);
    if (!q) return [];
    const out = [];
    const digits = String(text).replace(/[\s-]/g, '');
    if (/^\d{4,12}$/.test(digits)) {
      const complete = digits.length === 12;
      out.push({
        kind: 'package', icon: 'package', kindLabel: 'Package', label: `Package ${fmtTracking(digits)}`,
        sub: complete ? 'Open the package record' : 'Enter all 12 digits to open the package record',
        tracking: digits, disabled: !complete,
      });
    }
    const tokens = q.split(' ').filter(Boolean);
    const scored = [];
    for (const item of this._index) {
      if (!tokens.every((t) => item.hay.includes(t))) continue;
      const label = norm(item.label);
      let score = KIND_RANK[item.kind] || 50;
      if (label.startsWith(q)) score -= 30;
      else if (label.split(' ').some((w) => w.startsWith(tokens[0]))) score -= 15;
      else if (label.includes(q)) score -= 8;
      scored.push([score, item]);
    }
    scored.sort((a, b) => a[0] - b[0] || a[1].label.localeCompare(b[1].label));
    return out.concat(scored.slice(0, 8 - out.length).map((s) => s[1]));
  }

  _onKey(e) {
    const list = this._matchList || [];
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.csOpen = true;
      this.csActive = list.length ? (this.csActive + 1) % list.length : 0;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.csActive = list.length ? (this.csActive - 1 + list.length) % list.length : 0;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = list[this.csActive] || list[0];
      if (item) this._pick(item);
      else if (this.csText.trim()) {
        this.csOpen = false;
        this.csAnswer = { kind: 'none', text: `Nothing matches "${this.csText.trim()}".` };
      }
    } else if (e.key === 'Escape') {
      this.csOpen = false;
    }
  }

  _pick(item) {
    if (!item || item.disabled) return;
    this.csOpen = false;
    this.csActive = 0;
    switch (item.kind) {
      case 'package':
        this.csText = fmtTracking(item.tracking);
        this._openPackage(item.tracking);
        return;
      case 'term':
        this.csText = item.label;
        this.csAnswer = { kind: 'term', term: item.term };
        return;
      case 'termRef': {
        const term = GLOSSARY.find((t) => t.id === item.termId);
        if (term) {
          this.csText = term.title;
          this.csAnswer = { kind: 'term', term };
        }
        return;
      }
      case 'question':
        this.csText = item.label;
        this._ask(item.ask);
        return;
      case 'preset':
        this.csText = item.label;
        this.csPeriod = 'this';
        this._setSel(item.sel, true);
        this._ask('customers', item.title);
        return;
      default:
        this.csText = item.label;
        this._setSel(item.apply);
        this.csAnswer = { kind: 'profile', item };
    }
  }

  async _ask(which, titleOverride) {
    const seq = ++this._answerSeq;
    const phrase = (PERIODS[this.csPeriod] || PERIODS.this).phrase;
    this.csAnswer = {
      kind: 'loading',
      text: which === 'hubs' ? 'Checking every hub against the on-time target' : 'Finding the customers with the most at stake',
    };
    try {
      if (which === 'hubs') {
        const rows = await this._run({
          fields: ['hubs.hub_name', 'shipments.on_time_delivery_rate', 'shipments.revenue_at_risk'],
          filters: this.getEffectiveFilters({}, { except: ['hub', 'aging'] }),
          sorts: ['shipments.on_time_delivery_rate asc'],
        });
        if (seq !== this._answerSeq) return;
        const scored = rows
          .map((r) => ({
            name: r['hubs.hub_name'],
            rate: toNum(r['shipments.on_time_delivery_rate']),
            risk: toNum(r['shipments.revenue_at_risk']),
          }))
          .filter((r) => r.name && r.rate != null);
        const below = scored.filter((r) => r.rate < TARGET);
        this.csAnswer = {
          kind: 'rank',
          verified: true,
          title: below.length
            ? `${below.length} of ${scored.length} hubs ${below.length === 1 ? 'is' : 'are'} below the 97.5% on-time target ${phrase}`
            : `Every hub is at or above the 97.5% on-time target ${phrase}`,
          text: 'Measured with the official on-time delivery rate: only delays within our control count against a hub.',
          hint: below.length ? 'Select a hub to filter the page.' : '',
          rows: below.map((r) => ({
            name: r.name,
            sub: `${fmtUsd(r.risk)} revenue at risk`,
            value: fmtPct(r.rate),
            valueSub: `${((TARGET - r.rate) * 100).toFixed(1)} points below target`,
            bar: r.rate,
            tone: 'bad',
            apply: { hub: r.name },
          })),
        };
      } else {
        const rows = await this._run({
          fields: [
            'customers.customer_name',
            'customers.customer_tier',
            'customers.account_director',
            'shipments.revenue_at_risk',
            'live_package_tracking.aging_packages',
            'exception_evidence.temperature_excursions',
          ],
          filters: this.getEffectiveFilters({}, { except: 'customer' }),
          sorts: ['shipments.revenue_at_risk desc'],
          limit: '5',
        });
        if (seq !== this._answerSeq) return;
        const scored = rows
          .map((r) => ({
            name: r['customers.customer_name'],
            tier: r['customers.customer_tier'],
            director: r['customers.account_director'],
            risk: toNum(r['shipments.revenue_at_risk']) || 0,
            held: toNum(r['live_package_tracking.aging_packages']) || 0,
            hot: toNum(r['exception_evidence.temperature_excursions']) || 0,
          }))
          .filter((r) => r.name && (r.risk > 0 || r.held > 0));
        const max = scored.reduce((m, r) => Math.max(m, r.risk), 0) || 1;
        this.csAnswer = {
          kind: 'rank',
          verified: true,
          title: scored.length
            ? titleOverride || `Customers with the most revenue at risk ${phrase}`
            : 'No revenue is at risk for this selection',
          text: scored.length
            ? 'Revenue at risk is the shipping charge we may have to refund under the Service Guarantee.'
            : '',
          hint: scored.length ? 'Select a customer to filter the page.' : '',
          rows: scored.map((r) => ({
            name: r.name,
            sub: `${r.tier} account · Account director ${r.director}`,
            value: fmtUsd(r.risk),
            valueSub: `${fmtInt(r.held)} held 6+ hours${r.hot > 0 ? ` · ${fmtInt(r.hot)} above 8°C` : ''}`,
            bar: r.risk / max,
            tone: 'plain',
            apply: { customer: r.name },
          })),
        };
      }
    } catch (err) {
      if (seq === this._answerSeq) this.csAnswer = { kind: 'error' };
    }
  }

  async _openPackage(tracking, scroll = false) {
    const digits = String(tracking || '').replace(/\D/g, '');
    const seq = ++this._answerSeq;
    this.csOpen = false;
    this.csAnswer = { kind: 'loading', text: `Opening package ${fmtTracking(digits)}` };
    if (scroll) {
      this.updateComplete.then(() => {
        const el = this.querySelector('.cs-answer');
        if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
    try {
      const rows = await this._run({
        fields: PACKAGE_FIELDS,
        filters: { 'shipments.tracking_number': digits },
        limit: '5',
      });
      if (seq !== this._answerSeq) return;
      this.csAnswer = rows && rows.length
        ? { kind: 'package', row: rows[0], docs: rows.filter((r) => r['exception_evidence.document_type']) }
        : { kind: 'none', text: `No package found with tracking number ${fmtTracking(digits)}.` };
    } catch (err) {
      if (seq === this._answerSeq) this.csAnswer = { kind: 'error' };
    }
  }

  /* ---------- render: chrome ---------- */

  _renderBar() {
    return html`
      <header class="cs-bar">
        <div class="cs-brand">
          <div class="cs-logo" aria-label="Cymbal Shipping"><span class="a">Cymbal</span><span class="b">Shipping</span></div>
          <span class="cs-bar-div" aria-hidden="true"></span>
          <span class="cs-bar-title">Service performance</span>
        </div>
        <span class="cs-asof"><span class="cs-asof-dot" aria-hidden="true"></span>Data as of Wed, Nov 11 · 8:00 AM ET</span>
      </header>`;
  }

  _renderLookup() {
    const typed = this.csText.trim().length > 0;
    const list = this.csOpen && typed ? this._matches(this.csText) : [];
    this._matchList = list;
    const showList = this.csOpen && typed;
    return html`
      <section class="cs-look" aria-label="Look it up">
        <h2 class="cs-look-h">Look it up</h2>
        <p class="cs-look-sub">Find a customer, hub, service or package, or check what a business term means.</p>
        <div class="cs-search">
          <div class="cs-search-box">
            ${icon('search', 22)}
            <input
              type="text"
              autocomplete="off"
              spellcheck="false"
              role="combobox"
              aria-label="Look it up"
              aria-controls="cs-suggest-list"
              aria-expanded=${showList ? 'true' : 'false'}
              placeholder="Try a customer, hub, service, tracking number or business term"
              .value=${this.csText}
              @input=${(e) => { this.csText = e.target.value; this.csOpen = true; this.csActive = 0; }}
              @focus=${(e) => { this.csOpen = true; if (e.target && e.target.select) e.target.select(); }}
              @blur=${() => { this.csOpen = false; }}
              @keydown=${(e) => this._onKey(e)} />
            ${typed ? html`
              <button type="button" class="cs-icon-btn" aria-label="Clear search"
                @mousedown=${(e) => e.preventDefault()}
                @click=${() => { this.csText = ''; this.csActive = 0; }}>${icon('close', 20)}</button>` : nothing}
          </div>
          ${showList ? html`
            <div class="cs-suggest" id="cs-suggest-list" role="listbox">
              ${list.length ? list.map((item, i) => html`
                <button type="button" role="option" class="cs-suggest-item ${i === this.csActive ? 'is-active' : ''}"
                  aria-selected=${i === this.csActive ? 'true' : 'false'}
                  ?disabled=${Boolean(item.disabled)}
                  @mousedown=${(e) => e.preventDefault()}
                  @click=${() => this._pick(item)}>
                  <span class="cs-suggest-ic">${icon(item.icon, 18)}</span>
                  <span class="cs-suggest-main">
                    <span class="cs-suggest-label">${item.label}</span>
                    ${item.sub ? html`<div class="cs-suggest-sub">${item.sub}</div>` : nothing}
                  </span>
                  <span class="cs-suggest-kind">${item.kindLabel}</span>
                </button>`) : html`
                <div class="cs-suggest-empty">Nothing matches yet. Try a customer or hub name, a service, a 12-digit tracking number, or a term such as "on-time".</div>`}
            </div>` : nothing}
        </div>
        <div class="cs-try">
          <span class="cs-try-label">Try</span>
          ${TRY_CHIPS.map((chip) => html`
            <button type="button" class="cs-chip" @click=${() => this._pick(chip)}>${icon(chip.icon, 16)}${chip.label}</button>`)}
        </div>
        ${this._renderAnswer()}
      </section>`;
  }

  _renderAnswer() {
    const a = this.csAnswer;
    if (!a) return nothing;
    const close = html`
      <button type="button" class="cs-icon-btn cs-answer-close" aria-label="Close" @click=${() => { this.csAnswer = null; }}>${icon('close', 20)}</button>`;
    let body;
    if (a.kind === 'loading') {
      body = html`<div class="cs-answer-title"><span class="cs-spinner" aria-hidden="true"></span>${a.text}</div>`;
    } else if (a.kind === 'error') {
      body = html`
        <div class="cs-answer-title">That look-up did not come back</div>
        <p class="cs-answer-text">Please try again in a moment.</p>`;
    } else if (a.kind === 'none') {
      body = html`
        <div class="cs-answer-title">${a.text}</div>
        <p class="cs-answer-text">Try a customer or hub name, a service, a 12-digit tracking number, or a business term such as on-time.</p>`;
    } else if (a.kind === 'term') {
      body = this._renderTerm(a.term);
    } else if (a.kind === 'profile') {
      body = this._renderProfile(a.item);
    } else if (a.kind === 'rank') {
      body = this._renderRank(a);
    } else if (a.kind === 'package') {
      body = this._renderPackage(a);
    } else {
      return nothing;
    }
    return html`<div class="cs-answer" role="status" aria-live="polite">${close}${body}</div>`;
  }

  _renderTerm(t) {
    return html`
      <div class="cs-eyebrow">Business definition</div>
      <div class="cs-answer-title">${t.title}${verifiedMark('This is the one agreed definition, used by this app, by Looker and by the Gemini agent.')}</div>
      <p class="cs-answer-text">${t.short}</p>
      ${t.bullets && t.bullets.length ? html`<ul class="cs-answer-list">${t.bullets.map((b) => html`<li>${b}</li>`)}</ul>` : nothing}
      <div class="cs-answer-foot"><span>Owner: ${t.owner}</span><span>From the Cymbal Shipping business glossary</span></div>`;
  }

  _renderProfile(item) {
    const e = item.entity || {};
    let title = item.label;
    const lines = [];
    if (item.kind === 'customer') {
      lines.push(`${e.tier} account in ${e.industry}.`);
      if (e.director) lines.push(`Account director: ${e.director}.`);
    } else if (item.kind === 'hub') {
      title = e.code ? `${item.label} (${e.code})` : item.label;
      lines.push(`${e.type} in the ${e.region} region.`);
    } else if (item.kind === 'service') {
      const dayText = { 1: 'the next day', 2: 'the second day', 3: 'the third day', 4: 'the fourth day' }[e.days] || '';
      lines.push(`${e.family} service${e.clock && dayText ? `, promised by ${e.clock} on ${dayText}` : ''}.`);
      lines.push(/express|international/i.test(e.family || '') ? 'Covered by the Service Guarantee.' : 'Not covered by the Service Guarantee.');
    } else if (item.sub) {
      lines.push(`${item.sub}.`);
    }
    return html`
      <div class="cs-eyebrow">${item.kindLabel}</div>
      <div class="cs-answer-title">${title}</div>
      <p class="cs-answer-text">${lines.join(' ')}</p>
      <div class="cs-answer-foot">
        <span>Everything below now shows only this ${item.kindLabel.toLowerCase()}.</span>
        <button type="button" class="cs-text-btn" @click=${() => { this._setSel(Object.fromEntries(Object.keys(item.apply).map((k) => [k, null]))); this.csAnswer = null; this.csText = ''; }}>Remove filter</button>
      </div>`;
  }

  _renderRank(a) {
    return html`
      <div class="cs-eyebrow">Answer</div>
      <div class="cs-answer-title">${a.title}${a.verified ? verifiedMark('Uses the agreed definitions for on-time delivery rate and revenue at risk.') : nothing}</div>
      ${a.text ? html`<p class="cs-answer-text">${a.text}</p>` : nothing}
      ${a.rows && a.rows.length ? html`
        <div class="cs-rank">
          ${a.rows.map((r) => html`
            <button type="button" class="cs-rank-row" @click=${() => this._setSel(r.apply)}>
              <span><span class="cs-rank-name">${r.name}</span><div class="cs-rank-sub">${r.sub}</div></span>
              <span class="cs-rank-bar ${r.tone === 'bad' ? 'is-bad' : ''}" aria-hidden="true"><span style="width: ${Math.max(2, Math.min(100, (r.bar || 0) * 100)).toFixed(1)}%"></span></span>
              <span class="cs-rank-val">${r.value}<small>${r.valueSub}</small></span>
            </button>`)}
        </div>` : nothing}
      ${a.hint ? html`<div class="cs-answer-foot"><span>${a.hint}</span></div>` : nothing}`;
  }

  _renderPackage(a) {
    const r = a.row;
    const outcome = String(r['shipments.service_outcome'] || '');
    const tone = /Within Our Control|At Risk/.test(outcome) ? 'bad' : /Late/.test(outcome) ? 'warn' : /On Time/.test(outcome) ? 'good' : 'info';
    const held = toNum(r['live_package_tracking.hub_dwell_hours']);
    const clock = fmtClock(r['services.commit_time_local']);
    const delivered = r['shipments.delivered_date'];
    const customer = r['customers.customer_name'];
    const doc = a.docs && a.docs[0];
    const temp = doc ? toNum(doc['exception_evidence.max_temperature_c']) : null;
    const minutes = doc ? toNum(doc['exception_evidence.minutes_out_of_range']) : null;
    const file = doc ? String(doc['exception_evidence.document_uri'] || '').split('/').pop() : '';
    const fact = (label, value, small, wide) => (value ? html`
      <div class="cs-fact ${wide ? 'is-wide' : ''}"><dt>${label}</dt><dd>${value}${small ? html`<small>${small}</small>` : nothing}</dd></div>` : nothing);
    return html`
      <div class="cs-eyebrow">Package</div>
      <div class="cs-answer-title">
        <span class="cs-mono">${fmtTracking(r['shipments.tracking_number'])}</span>
        <span class="cs-pill is-${tone}">${r['shipments.package_status']}${outcome ? ` · ${outcome.replace(' · ', ', ').toLowerCase()}` : ''}</span>
        ${isYes(r['shipments.is_cold_chain']) ? html`<span class="cs-pill is-info">${icon('thermo', 14)}Temperature-controlled</span>` : nothing}
        ${isYes(r['shipments.is_guarantee_refund_eligible']) ? html`<span class="cs-pill is-warn">Service Guarantee refund eligible</span>` : nothing}
      </div>
      <dl class="cs-facts">
        ${fact('Customer', customer, [r['customers.customer_tier'] ? `${r['customers.customer_tier']} account` : '', r['customers.account_director']].filter(Boolean).join(' · '))}
        ${fact('Service', r['services.service_name'])}
        ${fact('Hub', r['hubs.hub_name'], held != null ? `${held.toFixed(1)} hours at the hub` : '')}
        ${fact('Going to', [r['shipments.destination_metro'], r['shipments.destination_state']].filter(Boolean).join(', '))}
        ${fact('Shipped', fmtDay(r['shipments.ship_date'], true))}
        ${fact('Promised', `${fmtDay(r['shipments.committed_delivery_date'], true)}${clock ? ` by ${clock}` : ''}`)}
        ${delivered ? fact('Delivered', fmtDay(delivered, true)) : fact('Now expected', fmtDay(r['shipments.estimated_delivery_date'], true))}
        ${fact('Last scan', r['live_package_tracking.last_scan_type'])}
        ${fact('Recovery plan', r['live_package_tracking.recovery_plan'], '', true)}
      </dl>
      ${doc ? html`
        <div class="cs-note ${temp != null && temp > 8 ? '' : 'is-quiet'}">
          <span class="cs-pill ${temp != null && temp > 8 ? 'is-warn' : 'is-info'}">${icon('doc', 14)}${doc['exception_evidence.document_type']}</span>
          <p>${doc['exception_evidence.summary']}</p>
          <p class="cs-note-meta">
            ${doc['exception_evidence.root_cause'] ? html`Cause: ${doc['exception_evidence.root_cause']}. ` : nothing}
            ${temp != null ? html`Highest reading ${temp.toFixed(1)}°C${minutes != null ? `, ${fmtInt(minutes)} minutes above 8°C` : ''}. ` : nothing}
            ${doc['exception_evidence.customer_impact'] ? html`Customer impact: ${doc['exception_evidence.customer_impact']}. ` : nothing}
            ${file ? html`Field document: ${file}` : nothing}
          </p>
        </div>` : nothing}
      ${customer ? html`
        <div class="cs-answer-foot">
          <button type="button" class="cs-text-btn" @click=${() => this._setSel({ customer })}>Show everything for ${customer}</button>
        </div>` : nothing}`;
  }

  _renderControls() {
    const active = Object.keys(DIMS).filter((k) => this.csSel[k] != null && this.csSel[k] !== false && this.csSel[k] !== '');
    return html`
      <div class="cs-controls">
        <div class="cs-seg" role="group" aria-label="Time period">
          ${Object.keys(PERIODS).map((p) => html`
            <button type="button" aria-pressed=${this.csPeriod === p ? 'true' : 'false'} @click=${() => this._setPeriod(p)}>
              ${this.csPeriod === p ? icon('check', 16) : nothing}${PERIODS[p].label}
            </button>`)}
        </div>
        ${active.map((k) => html`
          <span class="cs-fchip">
            ${DIMS[k].flag ? nothing : html`<span class="k">${DIMS[k].label}</span>`}${selLabel(k, this.csSel[k])}
            <button type="button" aria-label="Remove ${DIMS[k].label} filter" @click=${() => this._setSel({ [k]: null })}>${icon('close', 16)}</button>
          </span>`)}
        ${active.length
          ? html`<button type="button" class="cs-text-btn" @click=${() => this._clearAll()}>Clear all</button>`
          : html`<span class="cs-hint">${icon('touch', 16)}Select any bar or point to filter the whole page</span>`}
      </div>`;
  }

  /* ---------- render: numbers ---------- */

  _deltas() {
    const period = PERIODS[this.csPeriod] || PERIODS.this;
    const by = (this.csCtx && this.csCtx.byPeriod) || {};
    const cur = period.filter ? by[period.filter] : null;
    const prev = period.compare ? by[period.compare] : null;
    const out = { rate: null, risk: null, below: Boolean(cur && cur.rate != null && cur.rate < TARGET) };
    if (cur && prev && cur.rate != null && prev.rate != null) {
      const pts = (cur.rate - prev.rate) * 100;
      if (Math.abs(pts) >= 0.05) {
        out.rate = { text: `${pts > 0 ? '+' : '−'}${Math.abs(pts).toFixed(1)} pts`, type: pts > 0 ? 'positive' : 'negative', sub: period.compareLabel };
      }
    }
    if (this.csPeriod === 'this' && !this.csSel.aging && cur && prev && cur.risk != null && prev.risk > 0) {
      const times = cur.risk / prev.risk;
      out.risk = times >= 1.15
        ? { text: `${times.toFixed(1)}×`, type: 'negative', sub: `vs ${fmtUsd(prev.risk)} all of last week` }
        : { text: '', type: 'neutral', sub: `All of last week: ${fmtUsd(prev.risk)}` };
    }
    return out;
  }

  _renderKpis(filters) {
    const period = PERIODS[this.csPeriod] || PERIODS.this;
    const d = this._deltas();
    return html`
      <section class="cs-kpis" aria-label="Key numbers">
        <div class="cs-kpi">
          <div class="cs-kpi-label">Packages shipped</div>
          <app-kpi bare looker-model="cymbal_shipping" explore="shipments"
            query-field="shipments.package_count" format="int"
            subtitle=${this.csSel.shipDay ? fmtDay(this.csSel.shipDay, true) : period.range}
            .filters=${filters}></app-kpi>
        </div>
        <div class="cs-kpi ${d.below ? 'is-alert' : ''}">
          <div class="cs-kpi-label">On-time delivery rate${verifiedMark('Official on-time delivery rate. Only delays within our control count against us. The target is 97.5%.')}</div>
          <app-kpi bare looker-model="cymbal_shipping" explore="shipments"
            query-field="shipments.on_time_delivery_rate" format="percent1"
            change=${d.rate ? d.rate.text : nothing}
            change-type=${d.rate ? d.rate.type : nothing}
            subtitle=${this.csSel.aging ? 'Whole selection · target 97.5%' : d.rate ? `${d.rate.sub} · target 97.5%` : 'Target 97.5%'}
            .filters=${this.getEffectiveFilters({}, { except: 'aging' })}></app-kpi>
        </div>
        <div class="cs-kpi">
          <div class="cs-kpi-label">Revenue at risk${verifiedMark('Shipping charges we may have to refund under the Service Guarantee, for delays within our control.')}</div>
          <app-kpi bare looker-model="cymbal_shipping" explore="shipments"
            query-field="shipments.revenue_at_risk" format="usd"
            change=${d.risk && d.risk.text ? d.risk.text : nothing}
            change-type=${d.risk && d.risk.text ? d.risk.type : nothing}
            subtitle=${d.risk ? d.risk.sub : 'Service Guarantee refunds'}
            .filters=${filters}></app-kpi>
        </div>
        <div class="cs-kpi">
          <div class="cs-kpi-label">Held 6+ hours at a hub</div>
          <app-kpi bare looker-model="cymbal_shipping" explore="shipments"
            query-field="live_package_tracking.aging_packages" format="int"
            subtitle="Right now, from live tracking"
            .filters=${filters}></app-kpi>
        </div>
        <div class="cs-kpi">
          <div class="cs-kpi-label">Temperature excursions</div>
          <app-kpi bare looker-model="cymbal_shipping" explore="shipments"
            query-field="exception_evidence.temperature_excursions" format="int"
            subtitle="Above 8°C, from field temperature logs"
            .filters=${filters}></app-kpi>
        </div>
      </section>`;
  }

  _panelHead(title, sub, selKey, verified, keys) {
    const sel = selKey ? this.csSel[selKey] : null;
    return html`
      <div class="cs-panel-head">
        <div>
          <h3 class="cs-panel-title">${title}${verified ? verifiedMark(verified) : nothing}</h3>
          ${sub ? html`<p class="cs-panel-sub">${sub}</p>` : nothing}
          ${keys ? html`<div class="cs-keys">${keys}</div>` : nothing}
        </div>
        ${sel ? html`
          <span class="cs-sel"><span>${selLabel(selKey, sel)}</span>
            <button type="button" aria-label="Remove ${DIMS[selKey].label} filter" @click=${() => this._setSel({ [selKey]: null })}>${icon('close', 16)}</button>
          </span>` : nothing}
      </div>`;
  }

  _renderCharts() {
    const period = PERIODS[this.csPeriod] || PERIODS.this;
    const scope = this.csSel.shipDay ? `shipped ${fmtDay(this.csSel.shipDay, true)}` : period.phrase;
    const allNote = this.csSel.aging ? ' Counts every package in this selection, not only those held.' : '';
    return html`
      <section class="cs-row-a">
        <div class="cs-panel">
          ${this._panelHead(
            'On-time delivery rate by ship day',
            this.csSel.aging
              ? 'Oct 1 to Nov 9. Counts every package in this selection, not only those held.'
              : 'Oct 1 to Nov 9. Every day stays on the chart, whichever period is selected.',
            'shipDay',
            'Official on-time delivery rate. Weather, customs, recipient and address delays are excused.',
            html`<span class="cs-key"><i class="cs-key-dash"></i>97.5% target</span>`)}
          <app-chart bare type="line" height="300px" looker-model="cymbal_shipping" explore="shipments"
            value-format="percent1"
            .options=${TREND_OPTIONS}
            .query=${{
              fields: ['shipments.ship_date', 'shipments.on_time_delivery_rate', 'shipments.raw_on_time_rate'],
              filters: this.getEffectiveFilters({}, { except: ['shipDay', 'aging'], anyPeriod: true }),
              sorts: ['shipments.ship_date asc'],
              limit: '100',
            }}
            @app-chart-click=${(e) => this._onChart('shipDay', e)}></app-chart>
        </div>
        <div class="cs-panel">
          ${this._panelHead(
            'On-time delivery rate by hub',
            `Packages ${scope}.${allNote}`,
            'hub',
            'Official on-time delivery rate, compared with the 97.5% company target.',
            html`<span class="cs-key"><i style="background:${ORANGE}"></i>Below target</span><span class="cs-key"><i class="cs-key-dash"></i>97.5% target</span>`)}
          <app-chart bare type="bar" height="300px" looker-model="cymbal_shipping" explore="shipments"
            value-format="percent1" color="var(--app-primary)"
            selected-value=${this.csSel.hub || nothing}
            .categoryColors=${this.csHubColors}
            .options=${HUB_OPTIONS}
            .query=${{
              fields: ['hubs.hub_name', 'shipments.on_time_delivery_rate'],
              filters: this.getEffectiveFilters({}, { except: ['hub', 'aging'] }),
              sorts: ['shipments.on_time_delivery_rate asc'],
              limit: '20',
            }}
            @app-chart-click=${(e) => this._onChart('hub', e)}></app-chart>
        </div>
      </section>

      <section class="cs-row-b">
        <div class="cs-panel">
          ${this._panelHead(
            'Revenue at risk by customer',
            `Top customers, packages ${scope}.`,
            'customer',
            'Shipping charges we may have to refund under the Service Guarantee.')}
          <app-chart bare type="bar" height="290px" looker-model="cymbal_shipping" explore="shipments"
            value-format="usd" color="var(--app-primary)"
            selected-value=${this.csSel.customer || nothing}
            .options=${MONEY_BAR_OPTIONS}
            .query=${{
              fields: ['customers.customer_name', 'shipments.revenue_at_risk'],
              filters: this.getEffectiveFilters({ 'shipments.revenue_at_risk': '>0' }, { except: 'customer' }),
              sorts: ['shipments.revenue_at_risk desc'],
              limit: '8',
            }}
            @app-chart-click=${(e) => this._onChart('customer', e)}></app-chart>
        </div>
        <div class="cs-panel">
          ${this._panelHead(
            'Revenue at risk by service',
            `Guaranteed services, packages ${scope}.`,
            'service',
            'Shipping charges we may have to refund under the Service Guarantee.')}
          <app-chart bare type="bar" height="290px" looker-model="cymbal_shipping" explore="shipments"
            value-format="usd" color="var(--app-primary)"
            selected-value=${this.csSel.service || nothing}
            .options=${MONEY_BAR_OPTIONS}
            .query=${{
              fields: ['services.service_name', 'shipments.revenue_at_risk'],
              filters: this.getEffectiveFilters({ 'shipments.revenue_at_risk': '>0' }, { except: 'service' }),
              sorts: ['shipments.revenue_at_risk desc'],
              limit: '8',
            }}
            @app-chart-click=${(e) => this._onChart('service', e)}></app-chart>
        </div>
        <div class="cs-panel">
          ${this._panelHead(
            'Delayed packages by reason',
            '',
            'reason',
            '',
            html`<span class="cs-key"><i style="background:${ORANGE}"></i>Within our control</span><span class="cs-key"><i style="background:${QUIET_BAR}"></i>Outside our control</span>`)}
          <app-chart bare type="bar" height="290px" looker-model="cymbal_shipping" explore="shipments"
            value-format="int"
            selected-value=${this.csSel.reason || nothing}
            .categoryColors=${REASON_COLORS}
            .options=${COUNT_BAR_OPTIONS}
            .query=${{
              fields: ['shipments.exception_reason', 'shipments.packages_with_exception'],
              filters: this.getEffectiveFilters({ 'shipments.exception_reason': '-NULL' }, { except: 'reason' }),
              sorts: ['shipments.packages_with_exception desc'],
              limit: '10',
            }}
            @app-chart-click=${(e) => this._onChart('reason', e)}></app-chart>
        </div>
      </section>`;
  }

  _renderDetail() {
    const reports = this.csReports || { state: 'loading', items: [] };
    return html`
      <section class="cs-row-c">
        <div class="cs-panel">
          ${this._panelHead(
            'Packages held 6+ hours right now',
            'Longest wait first, with the recovery plan for each. Select a row to open the package.')}
          <app-grid bare height="500px" looker-model="cymbal_shipping" explore="shipments"
            .columnDefs=${HELD_COLUMNS}
            .gridOptions=${this._gridOptions}
            .query=${{
              fields: [
                'shipments.tracking_number',
                'customers.customer_name',
                'services.service_name',
                'hubs.hub_name',
                'live_package_tracking.hub_dwell_hours',
                'shipments.is_cold_chain',
                'live_package_tracking.recovery_plan',
              ],
              filters: this.getEffectiveFilters({ 'live_package_tracking.is_aging': 'yes' }),
              sorts: ['live_package_tracking.hub_dwell_hours desc'],
              limit: '250',
            }}></app-grid>
        </div>
        <div class="cs-panel">
          ${this._panelHead(
            'What the field reports say',
            'Notes written by drivers and hub teams. Select one to open the package.')}
          ${reports.cause ? html`
            <div class="cs-cause">
              <small>Cause named most often</small>
              <b>${reports.cause.text}</b>${reports.cause.count != null ? html` · ${fmtInt(reports.cause.count)} reports` : nothing}
            </div>` : nothing}
          ${reports.items.length ? html`
            <div class="cs-reports">
              ${reports.items.map((r) => {
                const temp = toNum(r['exception_evidence.max_temperature_c']);
                const hot = temp != null && temp > 8;
                return html`
                  <button type="button" class="cs-report" @click=${() => this._openPackage(String(r['shipments.tracking_number'] || ''), true)}>
                    <div class="cs-report-top">
                      <span class="cs-pill ${hot ? 'is-warn' : 'is-info'}">${icon(hot ? 'thermo' : 'doc', 14)}${r['exception_evidence.document_type']}</span>
                      ${hot ? html`<span class="cs-pill is-bad">${temp.toFixed(1)}°C</span>` : nothing}
                    </div>
                    <p class="cs-report-text">${r['exception_evidence.summary']}</p>
                    <div class="cs-report-meta">${[r['customers.customer_name'], r['hubs.hub_name'], fmtDay(r['exception_evidence.captured_date'])].filter(Boolean).join(' · ')}</div>
                  </button>`;
              })}
            </div>` : html`
            <div class="cs-empty">${reports.state === 'loading' ? 'Reading the field reports' : reports.state === 'error' ? 'The field reports did not load. Please try again in a moment.' : 'No field reports for this selection.'}</div>`}
        </div>
      </section>`;
  }

  _renderFooter() {
    return html`
      <footer class="cs-foot" aria-label="Where these numbers come from">
        <span>Where these numbers come from</span>
        <span class="cs-src"><b>Shipment history</b> BigQuery</span>
        <span class="cs-src"><b>Package tracking</b> Spanner</span>
        <span class="cs-src"><b>Field reports</b> Documents in the lakehouse, sourced from Amazon S3</span>
        <span class="cs-src"><b>Definitions</b> Knowledge Catalog</span>
        <span class="cs-src"><b>Metrics</b> Looker</span>
      </footer>`;
  }

  render() {
    const filters = this.getEffectiveFilters();
    return html`
      ${STYLE}
      <div class="cs-root" hide-actions>
        ${this._renderBar()}
        ${this._renderLookup()}
        ${this._renderControls()}
        ${this._renderKpis(filters)}
        ${this._renderCharts()}
        ${this._renderDetail()}
        ${this._renderFooter()}
      </div>`;
  }
}

if (!customElements.get(elementName)) {
  customElements.define(elementName, CymbalShippingServicePerformance);
}

export default CymbalShippingServicePerformance;
