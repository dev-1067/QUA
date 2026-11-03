"""Narration for the RecoverIQ demo video. `{name}` marks a cue: the recorder performs that step
at the moment the voice reaches the word right after the marker."""

VOICE = "en-US-AndrewNeural"
RATE = "+0%"

SCENES = [
    ("s00_intro", "card",
     "Every morning, a field agent at an Indian lender starts the day with a spreadsheet of three hundred overdue loans, "
     "and no idea which twenty really matter. Visits go unverified, promises get lost in notebooks, and payments are "
     "sometimes marked as paid before the money ever arrives. {title}This is RecoverIQ, our solution for QUASAR five point "
     "oh, problem statement one, fintech. One case. One trail. Full visibility."),

    ("s01_dashboard", "admin",
     "We sign in as the administrator, so we can see every screen. {kpis}The dashboard shows the overdue book, the money "
     "collected, the collection rate, the cost to recover every hundred rupees, the digital self-cure rate, and promises "
     "kept. Every rupee counted here was confirmed by the payment gateway, never typed in by hand. {charts}Below, we see "
     "daily collections, the mix of field, tele-calling and digital cases, and how old the overdue book is."),

    ("s02_intake", "admin",
     "New overdue accounts arrive from the lender's core banking system as a CSV or Excel file. {upload1}Let's upload a "
     "sample. Six accounts are created, and one bad row is rejected with a clear reason. {upload2}Now we upload the exact "
     "same file again. Zero new cases. One loan account always means exactly one case, so nothing is ever duplicated."),

    ("s03_case", "admin",
     "The case queue ranks every account by priority. {open}Let's open the top case. {reasons}The risk score comes with "
     "its reasons. Every point is explained, like days past due, and missed instalments. {model}Next to it, a machine "
     "learning model estimates the chance that this borrower pays on their own within thirty days, with its top drivers. "
     "{actions}On the right, a manager can send a nudge, create a payment link, reassign the agent, or override the "
     "channel. Every one of these actions is recorded."),

    ("s04_rules", "admin",
     "Routing is driven by versioned rules. {slide}Let's lower the field visit threshold from seventy to fifty five. "
     "{publish}When we publish, the whole book is re-scored instantly. Affected cases move to field visits and are "
     "assigned to agents, and every case remembers which rule version decided it."),

    ("s05_allocation", "admin",
     "Allocation matches cases to agents by pincode, distance, each agent's recovery record in that bucket, and spare "
     "capacity. {rebalance}One click on rebalance evens out the workload across the team."),

    ("s06_agent", "agent",
     "Now, the field agent's phone. Rahul sees today's worklist, ranked, with the reason each case is on top. "
     "{offline}Field areas often have no signal, so let's switch the network off. The app keeps working. {checkin}Rahul "
     "checks in at the borrower's address, and the GPS position and time are captured. {note}He adds a note in Marathi. "
     "The borrower lost his job, but will pay the instalment once his salary comes. {online}Both actions wait safely on "
     "the phone. When the network comes back, they sync automatically, exactly once."),

    ("s07_fieldmap", "admin",
     "Back at the branch, the check-in appears on the live field map. {list}Visits within three hundred metres of the "
     "address are verified. Visits that are too far away, have poor GPS accuracy, or show impossible travel speed are "
     "flagged."),

    ("s08_qr", "agent",
     "Now the most important rule. A case is marked paid only when the payment gateway confirms it. {qr}To collect, "
     "the agent shows a UPI QR code to the borrower."),

    ("s09_borrower", "public",
     "The borrower scans it and sees a secure page in their own language, with the agent's verified identity. "
     "{english}{pay}They pay through the gateway checkout, which runs in test mode. {confirm}The gateway sends a "
     "digitally signed webhook to RecoverIQ, and only then is the payment accepted, with an instant receipt."),

    ("s10_paid", "admin",
     "On the manager's screen, the case is now paid and confirmed, and the receipt is attached to the same case record. "
     "{webhooks}What if the same webhook arrives twice? {replay}We replay it. The result is, duplicate ignored. Money is "
     "never posted twice. {forge}And a forged webhook with the wrong signature is rejected. If a webhook is ever lost, a "
     "reconciliation job asks the gateway and posts what's missing."),

    ("s11_compliance", "admin",
     "Recovery agents may only contact borrowers between eight in the morning and seven in the evening. {clock}Let's "
     "move the demo clock to eight thirty at night, {send}and try to send an SMS. It's blocked, and the attempt is still "
     "logged with the reason. {report}The compliance report proves that nothing was ever delivered outside the window."),

    ("s12_audit", "admin",
     "Every action goes into a tamper-evident audit trail, where each row carries the hash of the one before it. "
     "{tamper}Now let's simulate an insider editing a payment directly in the database. Verification immediately points "
     "to the exact row that was changed. {restore}Restore it, and the chain is intact again."),

    ("s13_promises", "admin",
     "Promises to pay are tracked automatically. {jump}Let's jump the clock three days ahead. Promises that weren't kept "
     "break on their own. {escalations}The first break sends the case for a field visit, and the second escalates it to "
     "the branch manager."),

    ("s14_insight", "admin",
     "Notes in Hindi, Marathi and English become a sentiment map of India, {state}so managers can see where hardship is "
     "building, state by state and city by city. {leader}The leaderboard ranks agents only on gateway-confirmed money and "
     "GPS-verified visits, with the proof behind every point. {models}And the learning loop retrains the model on real "
     "outcomes, compares it in shadow mode, and goes live only after a manager approves it."),

    ("s15_outro", "card",
     "RecoverIQ covers all eighteen essential requirements, backed by automated tests and a full browser test. It runs "
     "with a single command, works offline in the field, and keeps every rupee and every contact provable. "
     "{tag}One case. One trail. Full visibility. Thank you."),
]
