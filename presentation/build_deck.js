// Builds RecoverIQ_QUASAR5_Deck.pptx — run: node build_deck.js
const pptxgen = require("pptxgenjs");
const path = require("path");
const { applyTheme } = require(path.join(process.env.PPTX_SKILL, "scripts", "apply_theme.js"));

const THEME = {
  name: "RecoverIQ Pine",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "18201D", lt1: "FFFFFF", dk2: "10201B", lt2: "F3F5F4",
    accent1: "0F766E", accent2: "2DD4BF", accent3: "C2410C", accent4: "4F46E5", accent5: "B45309", accent6: "15803D",
    hlink: "0F766E", folHlink: "4F46E5",
  },
};
const HEX = { pine: "10201B", ink: "18201D", muted: "5F6B66", line: "E2E6E4", soft: "F3F5F4", teal: "0F766E", mint: "2DD4BF",
  field: "C2410C", tele: "4F46E5", amber: "B45309", green: "15803D", red: "BE2121", white: "FFFFFF", mintSoft: "E0F2EE" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.title = "RecoverIQ — QUASAR 5.0 PS-01 Fintech";
pres.author = "RecoverIQ team";
pres.company = "QUASAR 5.0";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;
const IMG = (f) => path.join(__dirname, "img", f);

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "DARK", background: { color: HEX.pine },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.2, w: 11, h: 1.9, fontSize: 48, bold: true, color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: M, y: 4.25, w: 9, h: 1.2, fontSize: 18, color: "A9C3BA", valign: "top", align: "left", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.white },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.68, w: W - 2 * M, h: 0.72, fontSize: 30, bold: true, color: C.text1, valign: "top", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.36, w: 8, h: 0.3, fontSize: 11, bold: true, color: C.accent1, charSpacing: 2, align: "left", margin: 0 }, text: "" } },
    { text: { text: "RecoverIQ  ·  QUASAR 5.0  ·  PS-01 Fintech", options: { x: M, y: H - 0.42, w: 6, h: 0.3, fontSize: 10, color: "8A9590", margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: "8A9590", align: "right" },
});

let n = 0;
const sec = (t) => pres.addSection({ title: t });
let curSec = "";
function content(kicker, title, notes) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: curSec });
  s.addText(kicker.toUpperCase(), { placeholder: "kicker" });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function card(s, x, y, w, h, opts = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: opts.fill || HEX.soft },
    line: { color: opts.line || opts.fill || HEX.soft, width: 0.75 }, objectName: opts.name || "card" });
}
function dot(s, x, y, label, color = HEX.teal, d = 0.42) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color } });
  s.addText(String(label), { x, y, w: d, h: d, fontSize: 13, bold: true, color: HEX.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
function txt(s, text, o) { s.addText(text, { margin: 0, isTextBox: true, valign: "top", color: HEX.ink, fontSize: 14, ...o }); }
function shot(s, file, x, y, w, ratio, name) {
  const h = w / ratio;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: 0.06,
    fill: { color: HEX.white }, line: { color: HEX.line, width: 1 }, shadow: { type: "outer", color: "000000", opacity: 0.18, blur: 8, offset: 3, angle: 90 } });
  s.addImage({ path: IMG(file), x, y, w, h, altText: name || file, objectName: name || file });
  return h;
}
function phone(s, file, x, y, h, name) {
  const w = h * (1170 / 2532);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.07, y: y - 0.07, w: w + 0.14, h: h + 0.14, rectRadius: 0.22,
    fill: { color: "0B1411" }, line: { color: "0B1411" }, shadow: { type: "outer", color: "000000", opacity: 0.25, blur: 10, offset: 4, angle: 90 } });
  s.addImage({ path: IMG(file), x, y, w, h, altText: name || file, objectName: name || file, rounding: false });
  return w;
}
const R = 2880 / 1800;

// ================================================================== 1 title
sec("Opening"); curSec = "Opening";
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: curSec });
  s.addText("One case. One trail. Full visibility.", { placeholder: "title" });
  s.addText("RecoverIQ — an explainable, offline-first, compliance-by-design debt collections platform for banks and NBFCs", { placeholder: "body" });
  txt(s, [{ text: "Recover", options: { color: HEX.white } }, { text: "IQ", options: { color: HEX.mint } }], { x: M, y: 0.6, w: 4, h: 0.5, fontSize: 24, bold: true });
  txt(s, "QUASAR 5.0  ·  PS-01 FINTECH  ·  AI-POWERED DEBT COLLECTIONS", { x: M, y: 1.55, w: 9, h: 0.35, fontSize: 12, bold: true, color: HEX.mint, charSpacing: 3 });
  const stats = [["18 / 18", "essential requirements built"], ["0", "payments marked paid without the gateway"], ["34", "automated browser checks passing"]];
  stats.forEach(([k, v], i) => {
    const x = M + i * 3.2;
    txt(s, k, { x, y: 5.75, w: 3, h: 0.55, fontSize: 28, bold: true, color: HEX.white });
    txt(s, v, { x, y: 6.3, w: 2.9, h: 0.6, fontSize: 13, color: "A9C3BA" });
  });
  s.addNotes("Open with the line: an NBFC agent starts the day with an Excel sheet of 300 overdue accounts and no idea which 20 matter. RecoverIQ fixes that. The three numbers are facts about the working prototype, not projections.");
}

// ================================================================== 2 team
{
  const s = content("Team", "The team behind RecoverIQ",
    "Replace the four member cards with your names, colleges and photos before submitting. Keep one skill per person that maps to a part of the product.");
  const roles = [["Backend & Data", "FastAPI, state machine, payments & webhooks, audit chain, offline sync"],
    ["Frontend & Mobile", "Manager console, agent PWA, maps, borrower pay page"],
    ["AI & Integrations", "Scorecard + self-cure model, multilingual sentiment, contact policy"],
    ["Product & Pitch", "Demo story, compliance content, testing, decks and video"]];
  roles.forEach(([r, d], i) => {
    const x = M + i * 3.07, y = 1.6, w = 2.85, h = 4.9;
    card(s, x, y, w, h, { name: `member-${i + 1}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.35, y: y + 0.4, w: 1.2, h: 1.2, fill: { color: HEX.mintSoft }, line: { color: HEX.mintSoft } });
    txt(s, "Photo", { x: x + 0.35, y: y + 0.8, w: 1.2, h: 0.4, fontSize: 11, color: HEX.teal, align: "center" });
    txt(s, "Member name", { x: x + 0.35, y: y + 1.85, w: w - 0.6, h: 0.4, fontSize: 18, bold: true });
    txt(s, "College · Year", { x: x + 0.35, y: y + 2.25, w: w - 0.6, h: 0.3, fontSize: 12, color: HEX.muted });
    txt(s, r, { x: x + 0.35, y: y + 2.8, w: w - 0.6, h: 0.35, fontSize: 14, bold: true, color: HEX.teal });
    txt(s, d, { x: x + 0.35, y: y + 3.2, w: w - 0.6, h: 1.4, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 3 problem
sec("Problem"); curSec = "Problem";
{
  const s = content("The problem", "Collections still run on spreadsheets, phone calls and trust",
    "Walk through one branch's morning. Lists come as Excel, split by hand. Every account gets the same treatment. Managers can't see visits. Promises live in notebooks. Payments get posted by hand. Compliance can't be proven. The RBI number frames why lenders care right now.");
  card(s, M, 1.55, 4.1, 5.15, { fill: HEX.pine });
  txt(s, "~40%", { x: M + 0.4, y: 1.95, w: 3.4, h: 1.1, fontSize: 60, bold: true, color: HEX.mint });
  txt(s, "of fresh NPAs in FY24 came from retail non-home loans, much of it through NBFC and fintech digital lending.", { x: M + 0.4, y: 3.15, w: 3.3, h: 1.6, fontSize: 15, color: HEX.white });
  txt(s, "Source: RBI Financial Stability Report, June 2024 (as summarised in the plan's sources)", { x: M + 0.4, y: 5.85, w: 3.3, h: 0.6, fontSize: 10, color: "8FB3A8" });
  const pains = [
    ["Every account treated alike", "A ₹4,000 account 5 days late gets the same visit as a ₹4 lakh account 85 days late."],
    ["No field visibility", "Managers can't see who visited whom, or whether the visit happened at all."],
    ["Promises go missing", "\"I'll pay on the 10th\" lives in a notebook. Broken promises go unnoticed for weeks."],
    ["Payments posted by hand", "Double-posting, and cases marked paid when the money never arrived."],
    ["Compliance hard to prove", "RBI expects contact only 8 AM–7 PM and fair conduct, with no reliable log to show it."],
  ];
  pains.forEach(([h, d], i) => {
    const y = 1.6 + i * 1.03;
    dot(s, 5.15, y + 0.05, i + 1, HEX.field);
    txt(s, h, { x: 5.8, y, w: 6.9, h: 0.35, fontSize: 16, bold: true });
    txt(s, d, { x: 5.8, y: y + 0.38, w: 6.9, h: 0.55, fontSize: 13, color: HEX.muted });
  });
}

// ================================================================== 4 root cause
{
  const s = content("Root cause", "Fragmented tools mean there is no single case record",
    "Contrast the two columns. The root cause is not lazy agents; it's that there is no single shared record of the case, so nothing can be prioritised, verified or audited.");
  const cols = [
    { t: "Today", c: HEX.field, items: ["Excel lists split by whoever is free", "Phone and WhatsApp updates at day's end", "Payment status typed in by staff", "No record of contact times", "Same treatment for every borrower"] },
    { t: "With RecoverIQ", c: HEX.teal, items: ["One case per account, ranked by explainable priority", "GPS-stamped visits that sync even from offline phones", "PAID only on a signed gateway webhook", "Contact Policy Engine blocks 8 PM calls and logs why", "Field visit, call or digital nudge chosen per case"] },
  ];
  cols.forEach((col, i) => {
    const x = M + i * 6.2, w = 5.9;
    card(s, x, 1.55, w, 5.15, { fill: i ? HEX.mintSoft : "FBEFE8" });
    txt(s, col.t, { x: x + 0.4, y: 1.85, w: w - 0.8, h: 0.5, fontSize: 22, bold: true, color: col.c });
    col.items.forEach((it, j) => {
      const y = 2.6 + j * 0.8;
      s.addShape(pres.shapes.OVAL, { x: x + 0.42, y: y + 0.08, w: 0.16, h: 0.16, fill: { color: col.c }, line: { color: col.c } });
      txt(s, it, { x: x + 0.8, y, w: w - 1.2, h: 0.65, fontSize: 15 });
    });
  });
}

// ================================================================== 5 beneficiaries
{
  const s = content("Beneficiaries", "Everyone in the collection chain gets something concrete",
    "Borrowers are a beneficiary, not an afterthought: respectful contact in their language, a self-pay page, and receipts. Regulators get provable compliance.");
  const b = [
    ["Lenders", "Banks, NBFCs, MFIs: faster recovery, lower cost to collect, provable compliance"],
    ["Field agents", "A ranked worklist that works offline and credit only for verified work"],
    ["Managers", "Live field map, allocation, escalations, one consistent record"],
    ["Borrowers", "Contact only in fair hours, in Hindi, Marathi or English; self-pay link, instant receipt"],
    ["Regulators & auditors", "Tamper-evident trail of every contact, reveal and payment"],
  ];
  b.forEach(([h, d], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 4.1, y = 1.6 + row * 2.6, w = 3.85, hh = 2.35;
    card(s, x, y, w, hh);
    dot(s, x + 0.35, y + 0.35, i + 1);
    txt(s, h, { x: x + 0.35, y: y + 0.95, w: w - 0.7, h: 0.4, fontSize: 18, bold: true });
    txt(s, d, { x: x + 0.35, y: y + 1.38, w: w - 0.7, h: 0.9, fontSize: 13, color: HEX.muted });
  });
  card(s, M + 2 * 4.1, 1.6 + 2.6, 3.85, 2.35, { fill: HEX.pine });
  txt(s, "Built for Bharat-scale field operations: patchy networks, many languages, strict fair-practice rules.", { x: M + 2 * 4.1 + 0.35, y: 4.55, w: 3.15, h: 1.7, fontSize: 15, color: HEX.white });
}

// ================================================================== 6 lifecycle
sec("Solution"); curSec = "Solution";
{
  const s = content("Our solution", "The lifecycle of one case, end to end",
    "This is the whole product in one picture. Each box is a working screen in the demo. The bottom band is the point: every step lands in the same case record and the audit chain.");
  const steps = [
    ["Intake", "CSV / Excel, one case per account, row-level errors"],
    ["Score", "0–100 risk with reasons + self-cure %"],
    ["Route", "Field · Tele · Digital by versioned rules"],
    ["Work", "Allocation, offline agent app, nudges"],
    ["Pay", "Link / UPI QR → gateway → signed webhook"],
    ["Learn", "Outcomes retrain the model; manager approves"],
  ];
  const bw = 1.82, gap = 0.2;
  steps.forEach(([h, d], i) => {
    const x = M + i * (bw + gap), y = 1.75;
    card(s, x, y, bw, 2.9, { fill: i === 4 ? HEX.pine : HEX.soft });
    dot(s, x + 0.25, y + 0.25, i + 1, i === 4 ? HEX.mint : HEX.teal);
    txt(s, h, { x: x + 0.25, y: y + 0.85, w: bw - 0.4, h: 0.45, fontSize: 19, bold: true, color: i === 4 ? HEX.white : HEX.ink });
    txt(s, d, { x: x + 0.25, y: y + 1.35, w: bw - 0.4, h: 1.4, fontSize: 12.5, color: i === 4 ? "BFD6CE" : HEX.muted });
    if (i < steps.length - 1) s.addShape(pres.shapes.CHEVRON, { x: x + bw + 0.04, y: y + 1.3, w: 0.12, h: 0.26, fill: { color: "B9C4BF" }, line: { color: "B9C4BF" } });
  });
  card(s, M, 5.0, W - 2 * M, 1.6, { fill: HEX.mintSoft });
  txt(s, "Every step writes to one shared case record and a hash-chained audit trail", { x: M + 0.4, y: 5.25, w: 11, h: 0.4, fontSize: 17, bold: true, color: HEX.teal });
  txt(s, "Same case open on three screens updates together over WebSocket · status changes only through the backend state machine · PAID and CLOSED only from the payment service", { x: M + 0.4, y: 5.7, w: 11.3, h: 0.7, fontSize: 13.5, color: HEX.ink });
}

// ================================================================== 7 innovation
{
  const s = content("What's new", "Seven ideas that make RecoverIQ different",
    "Pick two or three to say out loud depending on time; the slide carries the rest.");
  const items = [
    ["Explainable dual-layer scoring", "Rule scorecard shows every point; a logistic self-cure model adds exact per-feature attributions."],
    ["Payment truth from the gateway", "HMAC-verified webhooks, unique payment IDs, reconciliation for lost webhooks."],
    ["Offline-first agent app", "IndexedDB outbox with client UUIDs, idempotent sync, conflicts ruled out by design."],
    ["Compliance as code", "Every SMS, WhatsApp, email and call passes the 8 AM–7 PM window, caps and opt-outs."],
    ["Tamper-evident audit", "SHA-256 hash chain; the database refuses UPDATE and DELETE on the log."],
    ["Multilingual sentiment map", "Hindi, Marathi, English notes → mood and reason → state, city, borrower."],
    ["Human-approved learning loop", "Retrain → shadow comparison → manager approves → rollback any time."],
  ];
  items.forEach(([h, d], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.15, y = 1.55 + row * 1.32;
    dot(s, x, y + 0.05, i + 1);
    txt(s, h, { x: x + 0.62, y, w: 5.3, h: 0.38, fontSize: 16, bold: true });
    txt(s, d, { x: x + 0.62, y: y + 0.4, w: 5.3, h: 0.8, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 8 product: dashboard
sec("Product tour"); curSec = "Product tour";
{
  const s = content("Product tour · Manager console", "Portfolio health at a glance, live",
    "Collected money on this dashboard is only gateway-confirmed money. Cost per ₹100 uses configurable visit and message costs. The live activity feed streams check-ins and payments over WebSocket.");
  shot(s, "02_dashboard.jpg", M, 1.5, 8.3, R, "Manager dashboard");
  const pts = [["Six KPIs", "Overdue book, collected, collection rate, cost per ₹100, digital self-cure, promises kept"],
    ["Ageing & channel mix", "DPD buckets SMA-0 → NPA and Field / Tele / Digital split"],
    ["Live activity", "Check-ins, payments and broken promises arrive in real time"],
    ["Scoped by role", "Branch, region or all-India; PII masked for managers"]];
  pts.forEach(([h, d], i) => {
    const y = 1.55 + i * 1.3;
    txt(s, h, { x: 9.35, y, w: 3.4, h: 0.35, fontSize: 15, bold: true, color: HEX.teal });
    txt(s, d, { x: 9.35, y: y + 0.38, w: 3.4, h: 0.85, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 9 case detail
{
  const s = content("Product tour · Explainable priority", "Every score comes with its reasons",
    "Point at the reasons: +35 for DPD, +20 for missed EMIs. The model card shows exact attributions because for a linear model SHAP equals coefficient times deviation. On the right: nudges are policy-checked before they are sent.");
  shot(s, "04_case_detail.jpg", M, 1.5, 8.3, R, "Case detail");
  const pts = [["Scorecard reasons", "Each point added or removed is shown, with the rule version used"],
    ["Self-cure model", "Probability of paying in 30 days with its top three drivers"],
    ["One timeline", "Intake, routing, visits, notes, nudges, payments: one record"],
    ["Actions with reasons", "Reassign, override channel, reveal PII: all audited"]];
  pts.forEach(([h, d], i) => {
    const y = 1.55 + i * 1.3;
    txt(s, h, { x: 9.35, y, w: 3.4, h: 0.35, fontSize: 15, bold: true, color: HEX.teal });
    txt(s, d, { x: 9.35, y: y + 0.38, w: 3.4, h: 0.85, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 10 agent app
{
  const s = content("Product tour · Field agent app", "A worklist that keeps working with no network",
    "Demo: toggle 'Simulate no network', check in and take a Marathi note, then reconnect. The outbox syncs and the server reports duplicates as already applied, so nothing is posted twice. Payments are never written offline.");
  const ph = 4.85;
  let x = M;
  [["30_agent_worklist.jpg", "Ranked worklist"], ["32_agent_offline.jpg", "Offline: actions queued"], ["33_agent_collect.jpg", "UPI QR to collect"]].forEach(([f, cap]) => {
    const w = phone(s, f, x, 1.5, ph, cap);
    txt(s, cap, { x: x - 0.07, y: 6.5, w: w + 0.14, h: 0.3, fontSize: 11, color: HEX.muted, align: "center" });
    x += w + 0.35;
  });
  const pts = [["GPS + time on every check-in", "Within 300 m = verified; far, low-accuracy or impossible travel speed = flagged"],
    ["Outbox with client UUIDs", "Visits, notes, promises sync later; the server applies each exactly once"],
    ["Voice notes", "Record and transcribe in Hindi, Marathi or English; edit before saving"],
    ["Installable PWA", "Add to home screen on any Android or iPhone"]];
  pts.forEach(([h, d], i) => {
    const y = 1.55 + i * 1.3;
    txt(s, h, { x: 8.6, y, w: 4.15, h: 0.35, fontSize: 15, bold: true, color: HEX.teal });
    txt(s, d, { x: 8.6, y: y + 0.38, w: 4.15, h: 0.85, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 11 payment truth
{
  const s = content("Product tour · Payment truth", "A case turns PAID only when the gateway says so",
    "Live moment for judges: scan the QR, pay in test mode, watch the case flip to Paid on the manager screen only after the signed webhook lands. Then press 'Replay webhook' (duplicate ignored) and 'Forged webhook' (401 rejected).");
  const ph = 4.3;
  let x = M;
  [["34_pay_page.jpg", "1 · Borrower pay page"], ["35_gateway_checkout.jpg", "2 · Gateway checkout"], ["36_paid_receipt.jpg", "3 · Confirmed + receipt"]].forEach(([f, cap]) => {
    const w = phone(s, f, x, 1.5, ph, cap);
    txt(s, cap, { x: x - 0.1, y: 5.95, w: w + 0.2, h: 0.3, fontSize: 11, color: HEX.muted, align: "center" });
    x += w + 0.32;
  });
  card(s, 7.55, 1.5, 5.2, 5.1, { fill: HEX.pine });
  txt(s, "Proven in the demo", { x: 7.9, y: 1.8, w: 4.6, h: 0.4, fontSize: 18, bold: true, color: HEX.mint });
  const proofs = [["Signed webhook", "HMAC-SHA256 verified before anything is posted"],
    ["Replay → duplicate_ignored", "Unique gateway payment ID: no double posting"],
    ["Forged event → 401", "Wrong signature is rejected and logged"],
    ["Lost webhook → reconciliation", "Job asks the gateway and posts what's missing"],
    ["Instant receipt", "PDF receipt for the borrower and the branch"]];
  proofs.forEach(([h, d], i) => {
    const y = 2.4 + i * 0.82;
    txt(s, h, { x: 7.9, y, w: 4.6, h: 0.33, fontSize: 14, bold: true, color: HEX.white });
    txt(s, d, { x: 7.9, y: y + 0.33, w: 4.6, h: 0.4, fontSize: 12, color: "A9C3BA" });
  });
}

// ================================================================== 12 compliance
{
  const s = content("Product tour · Compliance by design", "Fair-practice rules enforced in code, and provable",
    "Show the compliance chart: zero deliveries outside the window, and the blocked attempts that prove the engine works. Then the audit page: press 'Simulate insider tampering' — verification points at the exact row. Restore and it's intact again.");
  shot(s, "19_compliance.jpg", M, 1.5, 6.0, R, "Compliance report");
  shot(s, "20_audit_tampered.jpg", 6.75, 1.5, 6.0, R, "Audit chain with tampering detected");
  txt(s, "Contact attempts by hour: nothing delivered outside 8 AM–7 PM; blocked attempts logged with the reason.", { x: M, y: 5.45, w: 6.0, h: 0.9, fontSize: 13, color: HEX.muted });
  txt(s, "Audit trail: an edit made directly in the database breaks the hash chain at that exact row.", { x: 6.75, y: 5.45, w: 6.0, h: 0.9, fontSize: 13, color: HEX.muted });
}

// ================================================================== 13 sentiment
{
  const s = content("Product tour · Borrower sentiment", "Hardship mapped from what borrowers actually say",
    "Notes in Devanagari Hindi and Marathi and romanised Hinglish are analysed offline by a multilingual lexicon; with an API key, Claude adds a translation. Click a state to see cities and borrowers.");
  shot(s, "21_sentiment_state.jpg", M, 1.5, 8.3, R, "Sentiment map");
  const pts = [["Three languages", "Hindi, Marathi, English and Hinglish, typed or spoken"],
    ["Mood + reason", "Job loss, medical, business loss, dispute, unwilling, intends to pay"],
    ["State → city → borrower", "India map with drill-down and recent notes"],
    ["Feeds the score", "An 'unwilling to pay' note adds risk points, visibly"]];
  pts.forEach(([h, d], i) => {
    const y = 1.55 + i * 1.3;
    txt(s, h, { x: 9.35, y, w: 3.4, h: 0.35, fontSize: 15, bold: true, color: HEX.teal });
    txt(s, d, { x: 9.35, y: y + 0.38, w: 3.4, h: 0.85, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 14 requirement coverage
sec("Engineering"); curSec = "Engineering";
{
  const s = content("Requirement coverage", "18 of 18 essential requirements, each with a live proof",
    "This table is the answer to 'did you cover the problem statement?' Each row has a demo action that proves it.");
  const rows = [
    ["1 Case intake", "Re-upload same CSV → 0 new cases"], ["2 Risk scoring", "Reasons panel on every case"],
    ["3 Channel decision", "Change threshold → cases re-route"], ["4 Allocation", "Rebalance evens workload bars"],
    ["5 Agent app", "Ranked worklist on a phone"], ["6 Visit tracking", "GPS check-in → verified / flagged"],
    ["7 Digital nudges", "8:30 PM nudge blocked + logged"], ["8 Payment collection", "UPI QR, pay link, PDF receipt"],
    ["9 Payment confirmation", "Replay webhook → no double post"], ["10 PTP & escalation", "+3 days → promise breaks → escalates"],
    ["11 Dashboards", "Live KPIs, ageing, field map"], ["12 Offline", "No network → check-in → sync"],
    ["13 Permissions", "Exec sees 98XXXXX321; reveal needs reason"], ["14 Audit & compliance", "Verify chain; tamper → detected"],
    ["15 Default rule", "Edit expression → reclassify"], ["16 Sentiment view", "India map, state → city → borrower"],
    ["17 Note capture", "Hindi / Marathi voice → text"], ["18 Single case record", "Same case updates on 3 screens"],
  ];
  const head = (t) => ({ text: t, options: { bold: true, color: HEX.white, fill: { color: HEX.pine }, fontSize: 12 } });
  const half = (arr) => [[head("Requirement"), head("Proof in the demo")], ...arr.map(([a, b], i) => [
    { text: a, options: { bold: true, fontSize: 12, fill: { color: i % 2 ? HEX.white : HEX.soft } } },
    { text: b, options: { fontSize: 12, color: HEX.muted, fill: { color: i % 2 ? HEX.white : HEX.soft } } }])];
  s.addTable(half(rows.slice(0, 9)), { x: M, y: 1.45, w: 5.95, colW: [2.35, 3.6], rowH: 0.47, border: { type: "solid", color: HEX.line, pt: 0.5 }, margin: [3, 6, 3, 6] });
  s.addTable(half(rows.slice(9)), { x: 6.78, y: 1.45, w: 5.95, colW: [2.35, 3.6], rowH: 0.47, border: { type: "solid", color: HEX.line, pt: 0.5 }, margin: [3, 6, 3, 6] });
}

// ================================================================== 15 architecture
{
  const s = content("Architecture", "Stateless API, one source of truth, payment truth from the gateway",
    "Today the whole stack runs from one command on a laptop (SQLite, in-process scheduler) so the demo never depends on venue Wi-Fi. The same code targets Postgres and separate workers for the pilot.");
  const box = (x, y, w, h, title, sub, dark) => {
    card(s, x, y, w, h, { fill: dark ? HEX.pine : HEX.soft, line: dark ? HEX.pine : HEX.line });
    txt(s, title, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.35, fontSize: 14, bold: true, color: dark ? HEX.white : HEX.ink });
    txt(s, sub, { x: x + 0.2, y: y + 0.52, w: w - 0.4, h: h - 0.6, fontSize: 11.5, color: dark ? "A9C3BA" : HEX.muted });
  };
  // clients
  txt(s, "CLIENTS", { x: M, y: 1.45, w: 3, h: 0.3, fontSize: 11, bold: true, color: HEX.teal, charSpacing: 2 });
  box(M, 1.8, 3.1, 1.2, "Agent PWA", "IndexedDB outbox · GPS · mic · offline");
  box(M, 3.15, 3.1, 1.2, "Manager console", "React · charts · Leaflet maps");
  box(M, 4.5, 3.1, 1.2, "Borrower pay page", "Signed link · EN / हिं / मरा");
  // core
  txt(s, "CORE (FASTAPI)", { x: 4.35, y: 1.45, w: 4, h: 0.3, fontSize: 11, bold: true, color: HEX.teal, charSpacing: 2 });
  box(4.35, 1.8, 4.3, 1.2, "REST API + RBAC scope", "JWT · Argon2id · lockout · PII masking", true);
  box(4.35, 3.15, 4.3, 1.2, "Domain services", "State machine · scorecard · ML · allocation · contact policy", true);
  box(4.35, 4.5, 4.3, 1.2, "Webhook receiver + WebSocket hub", "HMAC verify · idempotent posting · live events", true);
  // data / external
  txt(s, "DATA & EXTERNAL", { x: 9.4, y: 1.45, w: 3.4, h: 0.3, fontSize: 11, bold: true, color: HEX.teal, charSpacing: 2 });
  box(9.4, 1.8, 3.33, 1.2, "SQL database", "Cases · events · append-only hash-chained audit");
  box(9.4, 3.15, 3.33, 1.2, "Payment gateway", "Razorpay test mode or built-in sandbox");
  box(9.4, 4.5, 3.33, 1.2, "AI services", "Self-cure model · lexicon + optional Claude");
  [[3.7, 2.4], [3.7, 3.75], [3.7, 5.1], [8.65, 2.4], [8.65, 3.75], [8.65, 5.1]].forEach(([x, y]) =>
    s.addShape(pres.shapes.LINE, { x, y, w: 0.65, h: 0, line: { color: "9AA8A2", width: 1.25, endArrowType: "triangle" } }));
  card(s, M, 6.0, W - 2 * M, 0.75, { fill: HEX.mintSoft });
  txt(s, "Background jobs: promise-break scheduler (every minute) · gateway reconciliation (every 10 minutes) · nightly retrain → shadow → approve", { x: M + 0.3, y: 6.2, w: 11.5, h: 0.4, fontSize: 13, color: HEX.ink });
}

// ================================================================== 16 data model
{
  const s = content("Data model", "Three constraints carry most of the correctness",
    "Mention optimistic versioning on cases and the encrypted PII columns. The three constraints on the left are what judges can test live.");
  const k = [["UNIQUE(account_no)", "One case per loan account. Re-uploading a file updates, never duplicates."],
    ["UNIQUE(gateway_payment_id)", "A replayed or duplicate webhook can't post money twice."],
    ["UNIQUE(client_id)", "Offline actions carry device-made UUIDs, so a resent outbox applies once."]];
  k.forEach(([h, d], i) => {
    const y = 1.6 + i * 1.65;
    card(s, M, y, 5.8, 1.45);
    txt(s, h, { x: M + 0.35, y: y + 0.25, w: 5.1, h: 0.4, fontSize: 17, bold: true, color: HEX.teal, fontFace: "Consolas" });
    txt(s, d, { x: M + 0.35, y: y + 0.7, w: 5.1, h: 0.65, fontSize: 13, color: HEX.muted });
  });
  const tables = ["cases", "borrowers (encrypted PII)", "case_events", "assignments", "visits", "contact_attempts", "promises", "payment_links", "payments", "webhook_events", "notes", "disputes", "rule_versions", "model_versions", "audit_log (hash-chained)", "users · branches · regions"];
  card(s, 6.75, 1.6, 5.98, 4.75, { fill: HEX.pine });
  txt(s, "16 tables", { x: 7.1, y: 1.85, w: 5, h: 0.45, fontSize: 18, bold: true, color: HEX.mint });
  tables.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    txt(s, t, { x: 7.1 + col * 2.8, y: 2.45 + row * 0.47, w: 2.75, h: 0.4, fontSize: 12.5, color: HEX.white, fontFace: "Consolas" });
  });
}

// ================================================================== 17 tech & quality
{
  const s = content("Tech stack & engineering quality", "Chosen so the demo works on stage, every time",
    "Numbers on the right are from the test suites in the repository: pytest for domain and API rules, Playwright for the browser walk-through, and a live smoke test that calls every endpoint as all five roles.");
  const stack = [["Frontend", "React 18 · TypeScript · Vite · Tailwind · Recharts · Leaflet · Dexie (IndexedDB) · PWA"],
    ["Backend", "Python · FastAPI · SQLAlchemy 2 · Pydantic v2 · WebSocket"],
    ["Data", "SQLite (WAL) for the laptop demo; Postgres-ready via DATABASE_URL"],
    ["AI / ML", "scikit-learn logistic model, exact attributions · multilingual lexicon · optional Claude"],
    ["Security", "JWT + refresh · Argon2id · AES-GCM PII · HMAC webhooks · RBAC scopes"],
    ["Payments", "Razorpay Payment Links (test) or built-in sandbox gateway"]];
  stack.forEach(([h, d], i) => {
    const y = 1.55 + i * 0.86;
    txt(s, h, { x: M, y, w: 1.7, h: 0.35, fontSize: 14, bold: true, color: HEX.teal });
    txt(s, d, { x: M + 1.8, y, w: 5.3, h: 0.75, fontSize: 13 });
  });
  const stats = [["27", "unit, API & integration tests passing"], ["34", "browser steps passing, 0 console errors"], ["5 roles × 31", "endpoints smoke-tested, 0 server errors"], ["740", "synthetic accounts across 14 branches"]];
  stats.forEach(([k2, v], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 8.05 + col * 2.4, y = 1.6 + row * 2.45;
    card(s, x, y, 2.25, 2.2, { fill: row ? HEX.mintSoft : HEX.pine });
    txt(s, k2, { x: x + 0.25, y: y + 0.3, w: 1.9, h: 0.8, fontSize: k2.length > 4 ? 24 : 36, bold: true, color: row ? HEX.teal : HEX.mint });
    txt(s, v, { x: x + 0.25, y: y + 1.2, w: 1.85, h: 0.85, fontSize: 12, color: row ? HEX.ink : HEX.white });
  });
}

// ================================================================== 18 impact & business
sec("Impact"); curSec = "Impact";
{
  const s = content("Expected impact", "Targets for a one-branch pilot, not claims",
    "Say clearly that these are pilot targets to be measured, and that all prototype data is synthetic. The business model is per active delinquent case per month, or per agent seat.");
  const t = [["20–30%", "of low-risk accounts self-cure digitally, no visit needed"], ["↓ cost", "to collect: visits go to the accounts where they matter"],
    ["0", "contacts outside 8 AM–7 PM, with the log to prove it"], ["Same day", "visibility of every visit, promise and payment"]];
  t.forEach(([k2, v], i) => {
    const x = M + i * 3.07;
    card(s, x, 1.55, 2.85, 2.5);
    txt(s, k2, { x: x + 0.3, y: 1.85, w: 2.3, h: 0.8, fontSize: 32, bold: true, color: HEX.teal });
    txt(s, v, { x: x + 0.3, y: 2.75, w: 2.3, h: 1.1, fontSize: 13, color: HEX.muted });
  });
  card(s, M, 4.35, W - 2 * M, 2.3, { fill: HEX.pine });
  txt(s, "Business model", { x: M + 0.4, y: 4.6, w: 4, h: 0.4, fontSize: 18, bold: true, color: HEX.mint });
  const bm = [["Customers", "NBFCs, small finance banks, MFIs, co-op banks, fintech lenders, agencies"],
    ["Pricing", "Per active delinquent case per month, or per agent seat; enterprise VPC tier"],
    ["Go-to-market", "Pilot one branch → measure cost per recovery & self-cure → expand by region"]];
  bm.forEach(([h, d], i) => {
    const x = M + 0.4 + i * 4.0;
    txt(s, h, { x, y: 5.15, w: 3.7, h: 0.35, fontSize: 14, bold: true, color: HEX.white });
    txt(s, d, { x, y: 5.5, w: 3.7, h: 0.95, fontSize: 12.5, color: "A9C3BA" });
  });
}

// ================================================================== 19 scale & roadmap
{
  const s = content("Scalability & roadmap", "From one branch to multi-region, and on to the finale",
    "The scale path is standard: stateless API, worker pools, partitioning, read replicas. The finale plan is to capture judge feedback in the first session and show a 'You said → We built' slide.");
  const st = [["Pilot", "1 branch · 20 agents · ~5k cases", "1 API · managed Postgres"], ["Region", "10 branches · 300 agents · ~100k cases", "API autoscale · worker pools · read replica"],
    ["Multi-region", "5k agents · ~5M cases", "Partition by tenant + region · OLAP for dashboards"]];
  st.forEach(([h, a, b], i) => {
    const x = M + i * 4.1;
    card(s, x, 1.55, 3.85, 2.25, { fill: i === 2 ? HEX.pine : HEX.soft });
    txt(s, h, { x: x + 0.3, y: 1.8, w: 3.3, h: 0.4, fontSize: 19, bold: true, color: i === 2 ? HEX.mint : HEX.teal });
    txt(s, a, { x: x + 0.3, y: 2.3, w: 3.3, h: 0.5, fontSize: 13.5, bold: true, color: i === 2 ? HEX.white : HEX.ink });
    txt(s, b, { x: x + 0.3, y: 2.85, w: 3.3, h: 0.8, fontSize: 12.5, color: i === 2 ? "A9C3BA" : HEX.muted });
  });
  const road = [["Done", "Working prototype: all 18 requirements, tests, demo data"], ["Round 0 · Dec", "This deck + 90-second demo video"],
    ["Round 1 · Jan", "5-minute engineering pitch + live link"], ["Finale · 23–24 Jan", "Judge feedback → build → 'You said, we built'"],
    ["Next", "Voice-bot reminders · route optimiser · Account Aggregator affordability"]];
  s.addShape(pres.shapes.LINE, { x: M + 0.2, y: 4.62, w: W - 2 * M - 0.4, h: 0, line: { color: "B9C4BF", width: 1.5 } });
  road.forEach(([h, d], i) => {
    const x = M + i * 2.46;
    s.addShape(pres.shapes.OVAL, { x: x + 0.1, y: 4.47, w: 0.3, h: 0.3, fill: { color: i === 0 ? HEX.green : HEX.teal }, line: { color: HEX.white, width: 2 } });
    txt(s, h, { x, y: 4.95, w: 2.3, h: 0.35, fontSize: 14, bold: true, color: i === 0 ? HEX.green : HEX.ink });
    txt(s, d, { x, y: 5.33, w: 2.25, h: 1.2, fontSize: 12, color: HEX.muted });
  });
}

// ================================================================== 20 demo script
{
  const s = content("Live demo", "Seven minutes, eight moments judges can verify",
    "Rehearse with the demo clock: set it to 8:30 PM for the blocked nudge, then +3 days for broken promises. Reset to real time at the end.");
  const d = [["Intake", "Upload sample CSV twice: 0 duplicates"], ["Score & route", "Open a case: reasons; move a threshold: cases re-route"],
    ["Allocate", "Rebalance: workload bars even out"], ["Agent phone", "Offline check-in + Marathi note → reconnect → synced"],
    ["Payment truth", "Judge scans QR, pays → PAID after webhook; replay → ignored"], ["Compliance", "8:30 PM nudge blocked; tamper → chain breaks"],
    ["Visibility", "Dashboard, sentiment map, leaderboard with proofs"], ["Close", "One case. One trail. Full visibility."]];
  d.forEach(([h, t2], i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.15, y = 1.55 + row * 1.25;
    card(s, x, y, 5.95, 1.08);
    dot(s, x + 0.25, y + 0.3, i + 1);
    txt(s, h, { x: x + 0.85, y: y + 0.18, w: 4.9, h: 0.35, fontSize: 15, bold: true });
    txt(s, t2, { x: x + 0.85, y: y + 0.55, w: 4.9, h: 0.45, fontSize: 12.5, color: HEX.muted });
  });
}

// ================================================================== 21 closing
sec("Close"); curSec = "Close";
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: curSec });
  s.addText("One case. One trail. Full visibility.", { placeholder: "title" });
  s.addText("Thank you. We'd love to hear what would make this deployable at your bank tomorrow.", { placeholder: "body" });
  txt(s, [{ text: "Recover", options: { color: HEX.white } }, { text: "IQ", options: { color: HEX.mint } }], { x: M, y: 0.6, w: 4, h: 0.5, fontSize: 24, bold: true });
  txt(s, "Run it:  python run.py   →   http://localhost:8000   ·   demo password Demo@1234", { x: M, y: 6.25, w: 11, h: 0.4, fontSize: 14, color: "8FB3A8", fontFace: "Consolas" });
  s.addNotes("Close by inviting feedback: in the finale we will build what the judges ask for in the first session.");
}

(async () => {
  const out = path.join(__dirname, "RecoverIQ_QUASAR5_Deck.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
