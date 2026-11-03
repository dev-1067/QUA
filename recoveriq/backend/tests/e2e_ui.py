"""Browser end-to-end test: signs in, opens every screen, presses the main buttons, fails on any
console/page error, and saves screenshots to docs/screenshots.

    python backend/tests/e2e_ui.py http://localhost:8010
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
errors: list[str] = []
steps: list[str] = []


def watch(page, label):
    page.on("console", lambda m: m.type == "error" and "ServiceWorker" not in m.text and "ERR_INTERNET_DISCONNECTED" not in m.text and errors.append(f"[{label}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{label}] pageerror: {e}"))


def shot(page, name, full=False):
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)


def step(msg):
    steps.append(msg)
    print("  ok", msg.encode("ascii", "replace").decode())


def login(page, role_text):
    page.goto(BASE + "/login")
    page.evaluate("localStorage.clear()")
    page.goto(BASE + "/login")
    page.get_by_role("button", name=re.compile(role_text)).click()


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="light")
    page = ctx.new_page()
    watch(page, "manager")

    page.goto(BASE + "/login")
    shot(page, "01_login")
    login(page, "Administrator")
    expect(page.get_by_text("Overdue book")).to_be_visible(timeout=20000)
    shot(page, "02_dashboard")
    step("admin login → dashboard KPIs render")

    page.goto(BASE + "/app/cases")
    expect(page.locator("table tbody tr").first).to_be_visible()
    page.get_by_placeholder(re.compile("Search account")).fill("Pune")
    page.wait_for_timeout(700)
    shot(page, "03_case_queue")
    page.get_by_placeholder(re.compile("Search account")).fill("")
    page.wait_for_timeout(500)
    step("case queue search + filters")

    page.goto(BASE + "/app/cases?status=FIELD")
    expect(page.locator("table tbody tr").first).to_be_visible()
    page.wait_for_timeout(600)
    page.locator("table tbody tr").nth(2).click()
    expect(page.get_by_text("Why this priority")).to_be_visible()
    shot(page, "04_case_detail")
    page.get_by_role("button", name=re.compile("Create link")).click()
    expect(page.get_by_text("Scan to pay")).to_be_visible()
    shot(page, "05_payment_link")
    step("case detail + payment link QR")
    for tab in ["Visits", "Payments", "Notes", "Contacts", "Timeline"]:
        page.get_by_role("button", name=re.compile(f"^{tab}")).first.click()
        page.wait_for_timeout(250)
    step("case tabs switch")
    page.get_by_role("button", name=re.compile("Reveal contact details")).click()
    page.get_by_placeholder(re.compile("Borrower called")).fill("Borrower asked to update phone number")
    page.get_by_role("button", name="Reveal", exact=True).click()
    page.wait_for_timeout(600)
    step("PII reveal with reason")
    page.get_by_role("button", name=re.compile("Reassign agent")).click()
    page.get_by_placeholder(re.compile("Borrower speaks")).fill("Closer agent for a Marathi speaker")
    page.get_by_role("button", name="Reassign", exact=True).click()
    page.wait_for_timeout(600)
    step("reassign with reason")

    # demo clock → quiet hours → nudge blocked; then 11:00 → nudge delivered
    page.locator("header").get_by_role("button").filter(has_text=re.compile(r"\d{2}:\d{2}")).click()
    page.get_by_role("button", name="11:00 AM").click()
    page.wait_for_timeout(800)
    page.keyboard.press("Escape")
    page.reload()
    page.get_by_role("button", name=re.compile("Send .* in")).click()
    expect(page.get_by_text(re.compile("delivered to the outbox|BLOCKED"))).to_be_visible()
    shot(page, "06_nudge")
    step("clock 11:00 → nudge sent through contact policy")

    pages = [("intake", "Drop a CSV"), ("allocation", "Workload by agent"), ("field", "Check-ins"),
             ("promises", "Promises & escalations"), ("disputes", "Disputes"), ("payments", "Replay a webhook"),
             ("notifications", "Message outbox"), ("sentiment", "Borrower sentiment"), ("leaderboard", "Leaderboard"),
             ("rules", "Channel decision"), ("models", "Learning loop"), ("audit", "Audit trail"), ("compliance", "Contact attempts by hour")]
    for i, (slug, text) in enumerate(pages, start=7):
        page.goto(f"{BASE}/app/{slug}")
        expect(page.get_by_text(text).first).to_be_visible(timeout=15000)
        if slug in ("field", "sentiment"):
            page.wait_for_timeout(2500)
        shot(page, f"{i:02d}_{slug}")
        step(f"/{slug} renders")

    page.goto(BASE + "/app/allocation")
    page.get_by_role("button", name=re.compile("Rebalance")).click()
    expect(page.get_by_text(re.compile("Moved \\d+ case"))).to_be_visible()
    step("allocation rebalance")
    page.goto(BASE + "/app/payments")
    page.get_by_role("button", name="Send forged event").click()
    expect(page.get_by_text(re.compile("HTTP 401"))).to_be_visible()
    step("forged webhook rejected (401)")
    page.get_by_role("button", name="Run now").click()
    page.wait_for_timeout(800)
    step("reconciliation run")
    page.goto(BASE + "/app/audit")
    expect(page.get_by_text("Chain intact")).to_be_visible(timeout=15000)
    page.get_by_role("button", name="Simulate insider tampering").click()
    expect(page.get_by_text(re.compile("Tampering detected at row"))).to_be_visible()
    shot(page, "20_audit_tampered")
    page.get_by_role("button", name="Restore row").click()
    expect(page.get_by_text("Chain intact")).to_be_visible()
    step("audit chain: intact → tamper detected → restored")
    page.goto(BASE + "/app/models")
    page.get_by_role("button", name=re.compile("Retrain now")).click()
    expect(page.get_by_text(re.compile("Shadow comparison"))).to_be_visible(timeout=20000)
    step("model retrain → shadow comparison")
    page.goto(BASE + "/app/rules")
    page.get_by_role("button", name="Test").click()
    expect(page.get_by_text(re.compile("Matches \\d+ of"))).to_be_visible()
    step("default-rule tester")
    page.goto(BASE + "/app/sentiment")
    page.wait_for_timeout(1500)
    page.get_by_text("Maharashtra").first.click()
    expect(page.get_by_text("Cities")).to_be_visible()
    shot(page, "21_sentiment_state")
    step("sentiment drill-down to a state")

    # dark theme screenshot
    page.goto(BASE + "/app")
    page.get_by_role("button", name="Dark").click()
    shot(page, "22_dashboard_dark")
    page.get_by_role("button", name="Light").click()
    step("theme switch")

    # reset clock
    page.evaluate("""async () => { const s = JSON.parse(localStorage.getItem('riq-session'));
      await fetch('/api/v1/clock', {method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer '+s.access_token}, body: JSON.stringify({mode:'reset'})}) }""")

    # ---------------- agent (phone)
    m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True,
                            color_scheme="light", geolocation={"latitude": 19.0178, "longitude": 72.8478}, permissions=["geolocation"])
    ap = m.new_page()
    watch(ap, "agent")
    login(ap, "Field agent")
    try:
        expect(ap.get_by_text("Today's worklist")).to_be_visible(timeout=20000)
    except Exception:
        ap.screenshot(path=str(OUT / "_debug_agent.png"))
        print("agent url:", ap.url)
        raise
    ap.wait_for_timeout(1200)
    shot(ap, "30_agent_worklist")
    step("agent worklist")
    ap.locator("li.card").nth(1).click()
    expect(ap.get_by_text("Why this is on top")).to_be_visible()
    shot(ap, "31_agent_case")
    ap.get_by_text("Promise", exact=True).click()
    ap.locator("input[type=number]").fill("2500")
    ap.get_by_role("button", name="Save promise").click()
    expect(ap.get_by_text("Promise recorded")).to_be_visible()
    step("agent records a promise (online)")
    m.set_offline(True)
    ap.evaluate("window.dispatchEvent(new Event('offline'))")
    ap.get_by_text("Check in", exact=True).click()
    ap.get_by_role("button", name="Demo location", exact=True).first.click()
    ap.get_by_role("button", name="Save check-in").click()
    expect(ap.get_by_text(re.compile("waiting to sync"))).to_be_visible()
    shot(ap, "32_agent_offline")
    step("agent check-in while OFFLINE → queued")
    m.set_offline(False)
    ap.evaluate("window.dispatchEvent(new Event('online'))")
    expect(ap.get_by_text(re.compile("Synced \\d+ action"))).to_be_visible(timeout=15000)
    step("back online → outbox synced")
    ap.get_by_text("Collect", exact=True).click()
    ap.get_by_role("button", name=re.compile("Show UPI QR")).click()
    expect(ap.get_by_text("Scan to pay")).to_be_visible()
    shot(ap, "33_agent_collect")
    pay_path = ap.locator("a[title='Open borrower page']").get_attribute("href")
    step("agent shows UPI QR")

    # ---------------- borrower pays on their phone
    bp = m.new_page()
    watch(bp, "borrower")
    bp.goto(BASE + pay_path)
    try:
        expect(bp.get_by_role("button", name=re.compile("Pay securely|सुरक्षित"))).to_be_visible(timeout=10000)
    except Exception:
        bp.screenshot(path=str(OUT / "_debug_pay.png"))
        print("pay url:", bp.url, bp.inner_text("body")[:600])
        raise
    bp.get_by_role("button", name="EN").click()
    shot(bp, "34_pay_page")
    bp.get_by_role("button", name=re.compile("Pay securely")).click()
    expect(bp.get_by_text("Sandbox Pay").first).to_be_visible(timeout=15000)
    shot(bp, "35_gateway_checkout")
    bp.get_by_role("button", name=re.compile("^Pay ₹")).click()
    expect(bp.get_by_text("Payment received")).to_be_visible(timeout=20000)
    bp.wait_for_timeout(600)
    shot(bp, "36_paid_receipt")
    step("borrower pays → webhook → PAID + receipt")

    browser.close()

print(f"\n{len(steps)} steps passed")
if errors:
    print(f"{len(errors)} browser errors:")
    for e in errors:
        print("  ", e.encode("ascii", "replace").decode()[:300])
    sys.exit(1)
print("No console or page errors.")
