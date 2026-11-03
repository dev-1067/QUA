# 7-minute demo script

Before you start: `python run.py --reset`, sign in as **Branch manager** in one window and **Field agent** in a second window (phone-size, or a real phone on the same Wi-Fi). Clock button in the top bar → **11:00 AM**.

| Time | Do | Say |
|---|---|---|
| 0:00 | Dashboard | "This is a Mumbai branch manager's morning. Every rupee in *Collected* was confirmed by the payment gateway." |
| 0:30 | Admin → **Case intake** → Sample CSV → upload twice | "Second upload: 0 created, 6 unchanged. One case per account, always." |
| 1:00 | **Case queue** → top case | "Risk 75: +35 for 125 days past due, +20 for missed EMIs… every point is a reason. The model adds a self-cure probability with its drivers." |
| 1:45 | Admin → **Rules** → Channel: field from 70 → 55 → Publish | "Rules are versioned. Cases re-route immediately and remember which version decided them." |
| 2:15 | **Allocation** → Rebalance | "Fit = proximity, recovery record in that DPD bucket, spare capacity." |
| 2:45 | Agent window → menu → *Simulate no network* → open a case → Check in (Demo location) → Voice note in Marathi → back online | "The phone had no signal; the actions waited in the outbox and synced exactly once." Then show the check-in on **Live field map**. |
| 3:45 | Agent → Collect → QR. Judge scans and pays | "The case says *Awaiting gateway* until the signed webhook lands… now it's Paid, with a receipt." |
| 4:45 | **Payments** → Replay webhook, then Forged webhook | "Replay: duplicate ignored. Forgery: 401. Money is posted once, and only by the gateway." |
| 5:15 | Clock → **8:30 PM** → case → Send SMS | "Blocked: quiet hours, RBI fair practice. The attempt is still logged." Then **Compliance**. |
| 5:45 | Admin → **Audit trail** → Simulate insider tampering | "Someone edited one payment directly in the database. The chain breaks exactly there." Restore. |
| 6:15 | Clock → **+3 days** → **Promises & escalations** | "Promises that weren't paid broke on their own; second breaks went to the branch manager." |
| 6:40 | **Sentiment map** → Maharashtra; **Leaderboard** → tap an agent | "Hardship by state and city, from notes in three languages. Rankings only count verified work." |
| 7:00 | Clock → Reset | "One case. One trail. Full visibility." |
