# RecoverIQ demo video — narration script

Voice: Microsoft neural voice *en-US-AndrewNeural* (male). Length 5:39. Recorded from the running app.

## 0:00  Intro

Every morning, a field agent at an Indian lender starts the day with a spreadsheet of three hundred overdue loans, and no idea which twenty really matter. Visits go unverified, promises get lost in notebooks, and payments are sometimes marked as paid before the money ever arrives. This is RecoverIQ, our solution for QUASAR five point oh, problem statement one, fintech. One case. One trail. Full visibility.

## 0:28  Manager dashboard

We sign in as the administrator, so we can see every screen. The dashboard shows the overdue book, the money collected, the collection rate, the cost to recover every hundred rupees, the digital self-cure rate, and promises kept. Every rupee counted here was confirmed by the payment gateway, never typed in by hand. Below, we see daily collections, the mix of field, tele-calling and digital cases, and how old the overdue book is.

## 0:56  Case intake

New overdue accounts arrive from the lender's core banking system as a CSV or Excel file. Let's upload a sample. Six accounts are created, and one bad row is rejected with a clear reason. Now we upload the exact same file again. Zero new cases. One loan account always means exactly one case, so nothing is ever duplicated.

## 1:18  Explainable risk score

The case queue ranks every account by priority. Let's open the top case. The risk score comes with its reasons. Every point is explained, like days past due, and missed instalments. Next to it, a machine learning model estimates the chance that this borrower pays on their own within thirty days, with its top drivers. On the right, a manager can send a nudge, create a payment link, reassign the agent, or override the channel. Every one of these actions is recorded.

## 1:48  Versioned routing rules

Routing is driven by versioned rules. Let's lower the field visit threshold from seventy to fifty five. When we publish, the whole book is re-scored instantly. Affected cases move to field visits and are assigned to agents, and every case remembers which rule version decided it.

## 2:07  Allocation

Allocation matches cases to agents by pincode, distance, each agent's recovery record in that bucket, and spare capacity. One click on rebalance evens out the workload across the team.

## 2:19  Field agent app (offline)

Now, the field agent's phone. Rahul sees today's worklist, ranked, with the reason each case is on top. Field areas often have no signal, so let's switch the network off. The app keeps working. Rahul checks in at the borrower's address, and the GPS position and time are captured. He adds a note in Marathi. The borrower lost his job, but will pay the instalment once his salary comes. Both actions wait safely on the phone. When the network comes back, they sync automatically, exactly once.

## 2:52  Live field map

Back at the branch, the check-in appears on the live field map. Visits within three hundred metres of the address are verified. Visits that are too far away, have poor GPS accuracy, or show impossible travel speed are flagged.

## 3:07  Collect payment

Now the most important rule. A case is marked paid only when the payment gateway confirms it. To collect, the agent shows a UPI QR code to the borrower.

## 3:17  Borrower pays

The borrower scans it and sees a secure page in their own language, with the agent's verified identity. They pay through the gateway checkout, which runs in test mode. The gateway sends a digitally signed webhook to RecoverIQ, and only then is the payment accepted, with an instant receipt.

## 3:35  Payment truth

On the manager's screen, the case is now paid and confirmed, and the receipt is attached to the same case record. What if the same webhook arrives twice? We replay it. The result is, duplicate ignored. Money is never posted twice. And a forged webhook with the wrong signature is rejected. If a webhook is ever lost, a reconciliation job asks the gateway and posts what's missing.

## 4:01  Compliance

Recovery agents may only contact borrowers between eight in the morning and seven in the evening. Let's move the demo clock to eight thirty at night, and try to send an SMS. It's blocked, and the attempt is still logged with the reason. The compliance report proves that nothing was ever delivered outside the window.

## 4:19  Audit trail

Every action goes into a tamper-evident audit trail, where each row carries the hash of the one before it. Now let's simulate an insider editing a payment directly in the database. Verification immediately points to the exact row that was changed. Restore it, and the chain is intact again.

## 4:39  Promises & escalations

Promises to pay are tracked automatically. Let's jump the clock three days ahead. Promises that weren't kept break on their own. The first break sends the case for a field visit, and the second escalates it to the branch manager.

## 4:53  Sentiment, leaderboard, learning loop

Notes in Hindi, Marathi and English become a sentiment map of India, so managers can see where hardship is building, state by state and city by city. The leaderboard ranks agents only on gateway-confirmed money and GPS-verified visits, with the proof behind every point. And the learning loop retrains the model on real outcomes, compares it in shadow mode, and goes live only after a manager approves it.

## 5:19  Close

RecoverIQ covers all eighteen essential requirements, backed by automated tests and a full browser test. It runs with a single command, works offline in the field, and keeps every rupee and every contact provable. One case. One trail. Full visibility. Thank you.
