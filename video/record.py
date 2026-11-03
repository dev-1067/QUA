"""Records each scene of the demo video from the running app, timing every action to the
voice-over cues in work/timing.json. Usage: python record.py [base_url] [scene ...]"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
WORK = HERE / "work"
REC = WORK / "rec"
REC.mkdir(parents=True, exist_ok=True)
BASE = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].startswith("http") else "http://localhost:8010").rstrip("/")
ONLY = [a for a in sys.argv[1:] if not a.startswith("http")]
TIMING = json.loads((WORK / "timing.json").read_text(encoding="utf-8"))
STATE_FILE = WORK / "state.json"
STATE = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
VIEW = {"width": 1536, "height": 864}

CURSOR = """
(() => {
  const add = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 9-6.5 1.6L16 20l-2.6 1.3-3.5-7.3L4 18z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'-40px', top:'-40px', zIndex:2147483647, pointerEvents:'none',
      transition:'transform .08s', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left = e.clientX - 4 + 'px'; c.style.top = e.clientY - 2 + 'px'; }, true);
    addEventListener('mousedown', e => {
      c.style.transform = 'scale(.85)';
      const r = document.createElement('div');
      Object.assign(r.style, {position:'fixed', left:e.clientX-18+'px', top:e.clientY-18+'px', width:'36px', height:'36px',
        borderRadius:'50%', border:'3px solid rgba(45,212,191,.9)', zIndex:2147483646, pointerEvents:'none',
        transition:'transform .45s ease-out, opacity .45s ease-out'});
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 500);
    }, true);
    addEventListener('mouseup', () => { c.style.transform = ''; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add();
})();
"""


def api(path, body=None, token=None, method=None):
    req = urllib.request.Request(BASE + "/api/v1" + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
                                 method=method or ("POST" if body is not None else "GET"))
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if raw[:1] in (b"{", b"[") else raw


def session(email):
    return api("/auth/login", {"email": email, "password": "Demo@1234"})


class Scene:
    def __init__(self, browser, name, who):
        self.name, self.t = name, TIMING[name]
        self.ctx = browser.new_context(viewport=VIEW, record_video_dir=str(REC / name), record_video_size={"width": 1920, "height": 1080},
                                       color_scheme="light", geolocation={"latitude": 19.0178, "longitude": 72.8478}, permissions=["geolocation"])
        init = CURSOR + "try{localStorage.setItem('riq-theme','light')}catch(e){}"
        if who in ("admin", "agent"):
            s = session("admin@recoveriq.in" if who == "admin" else "agent@recoveriq.in")
            self.token = s["access_token"]
            init += f";try{{if(!sessionStorage.getItem('__seeded')){{localStorage.setItem('riq-session', {json.dumps(json.dumps(s))});sessionStorage.setItem('__seeded','1')}}}}catch(e){{}}"
        self.ctx.add_init_script(init)
        self.page = self.ctx.new_page()
        self.t_ctx = time.time()
        self.start = None
        self.mx, self.my = VIEW["width"] / 2, VIEW["height"] / 2

    def begin(self):
        self.page.wait_for_timeout(300)
        self.page.mouse.move(self.mx, self.my)
        self.start = time.time()

    def at(self, cue):
        target = self.start + self.t["cues"][cue]
        while time.time() < target:
            self.page.wait_for_timeout(min(100, max(10, (target - time.time()) * 1000)))

    def move(self, loc, dx=0.5, dy=0.5, steps=22):
        loc.scroll_into_view_if_needed()
        b = loc.bounding_box()
        x, y = b["x"] + b["width"] * dx, b["y"] + b["height"] * dy
        self.page.mouse.move(x, y, steps=steps)
        self.mx, self.my = x, y

    def click(self, loc, pause=150, dx=0.5, dy=0.5):
        self.move(loc, dx, dy)
        self.page.wait_for_timeout(pause)
        self.page.mouse.down()
        self.page.mouse.up()

    def scroll(self, dy, steps=12):
        for _ in range(steps):
            self.page.mouse.wheel(0, dy / steps)
            self.page.wait_for_timeout(35)

    def finish(self, tail=0.8):
        end = self.start + self.t["duration"] + tail
        while time.time() < end:
            self.page.wait_for_timeout(100)
        length = time.time() - self.start
        offset = self.start - self.t_ctx
        video = self.page.video
        self.ctx.close()
        src = Path(video.path())
        dst = REC / f"{self.name}.webm"
        if dst.exists():
            dst.unlink()
        src.rename(dst)
        STATE.setdefault("segments", {})[self.name] = {"offset": round(offset, 2), "length": round(length, 2)}
        STATE_FILE.write_text(json.dumps(STATE, indent=2))
        print(f"  recorded {self.name}: offset {offset:.2f}s length {length:.1f}s")


def wait_text(page, text, timeout=20000):
    page.get_by_text(text).first.wait_for(timeout=timeout)


# ------------------------------------------------------------------ scenes

def s01_dashboard(b):
    s = Scene(b, "s01_dashboard", "public")
    s.page.goto(BASE + "/login")
    wait_text(s.page, "Demo accounts")
    s.begin()
    s.page.wait_for_timeout(900)
    s.click(s.page.get_by_role("button", name=re.compile("Administrator")))
    s.at("kpis")
    for label in ["Overdue book", "Collected", "Collection rate", "Cost per ₹100", "Digital self-cure", "Promises kept"]:
        s.move(s.page.get_by_text(label, exact=True).first, steps=14)
        s.page.wait_for_timeout(1300)
    s.at("charts")
    s.page.mouse.move(VIEW["width"] / 2, 600, steps=10)
    s.scroll(420)
    s.finish()


def s02_intake(b):
    s = Scene(b, "s02_intake", "admin")
    csv = WORK / "recoveriq_sample_intake.csv"
    csv.write_bytes(api("/intake/sample.csv", token=s.token))
    s.page.goto(BASE + "/app/intake")
    wait_text(s.page, "Drop a CSV")
    s.begin()
    s.move(s.page.get_by_text("Sample CSV").first)
    s.at("upload1")
    s.move(s.page.get_by_text("Drop a CSV").first)
    s.page.locator("input[type=file]").set_input_files(str(csv))
    wait_text(s.page, "Rejected rows")
    s.page.wait_for_timeout(600)
    s.move(s.page.get_by_text("Rejected rows").first, steps=16)
    s.at("upload2")
    s.move(s.page.get_by_text("Drop a CSV").first)
    s.page.locator("input[type=file]").set_input_files(str(csv))
    wait_text(s.page, "No duplicates created")
    s.move(s.page.get_by_text("No duplicates created").first, steps=16)
    s.finish()


def s03_case(b):
    s = Scene(b, "s03_case", "admin")
    s.page.goto(BASE + "/app/cases")
    s.page.locator("table tbody tr").first.wait_for()
    s.page.wait_for_timeout(500)
    s.begin()
    s.move(s.page.locator("table tbody tr").nth(2), steps=18)
    s.at("open")
    s.click(s.page.locator("table tbody tr").first)
    wait_text(s.page, "Why this priority")
    STATE["top_case"] = s.page.url.rsplit("/", 1)[-1]
    s.at("reasons")
    s.move(s.page.get_by_text("Why this priority").first, 0.3, 4)
    s.page.wait_for_timeout(1500)
    s.move(s.page.get_by_text("Queue priority").first, 0.3, 0.5, steps=30)
    s.at("model")
    s.move(s.page.get_by_text("Self-cure model").first, 0.5, 4)
    s.at("actions")
    s.move(s.page.get_by_text("Digital nudge").first)
    s.page.wait_for_timeout(1800)
    s.move(s.page.get_by_text("Collect payment").first)
    s.page.wait_for_timeout(1800)
    s.move(s.page.get_by_role("button", name=re.compile("Reassign agent")))
    s.page.wait_for_timeout(1300)
    s.move(s.page.get_by_role("button", name=re.compile("Override channel")))
    s.finish()


def s04_rules(b):
    s = Scene(b, "s04_rules", "admin")
    s.page.goto(BASE + "/app/rules")
    wait_text(s.page, "Channel decision")
    s.page.wait_for_timeout(500)
    s.begin()
    slider = s.page.locator("input[type=range]").nth(1)
    s.move(s.page.get_by_text("Risk score bands").first)
    s.at("slide")
    s.move(slider, 0.7, 0.5)
    cur = int(slider.input_value())
    for v in range(cur, 54, -1):
        slider.fill(str(v))
        box = slider.bounding_box()
        s.page.mouse.move(box["x"] + box["width"] * v / 100, box["y"] + box["height"] / 2)
        s.page.wait_for_timeout(90)
    s.at("publish")
    note = s.page.get_by_placeholder(re.compile("Why are you changing")).first
    s.click(note)
    note.type("Send more high-risk accounts to field visits", delay=18)
    s.click(s.page.get_by_role("button", name=re.compile("Publish v")).first)
    wait_text(s.page, "is live")
    s.move(s.page.get_by_text("is live").first)
    s.finish()


def s05_allocation(b):
    s = Scene(b, "s05_allocation", "admin")
    s.page.goto(BASE + "/app/allocation")
    wait_text(s.page, "Workload by agent")
    s.page.wait_for_timeout(500)
    s.begin()
    s.move(s.page.get_by_text("Workload by agent").first, 0.2, 3)
    s.at("rebalance")
    s.click(s.page.get_by_role("button", name=re.compile("Rebalance")))
    s.finish()


def pick_agent_case(token):
    wl = api("/agent/worklist", token=token)["items"]
    for c in wl[1:]:
        if c["status"] in ("FIELD", "TELE") and c["amount_due"] > 2000 and not c["ptp"]:
            return c
    return wl[1]


def s06_agent(b):
    s = Scene(b, "s06_agent", "agent")
    case = pick_agent_case(s.token)
    STATE["agent_case"] = case["id"]
    STATE["agent_case_name"] = case["borrower_name"]
    s.page.goto(BASE + "/agent")
    wait_text(s.page, "Today's worklist")
    s.page.wait_for_timeout(1500)
    s.begin()
    cards = s.page.locator("li.card")
    for i in range(3):
        s.move(cards.nth(i), 0.35, 0.3, steps=16)
        s.page.wait_for_timeout(900)
    s.at("offline")
    s.click(s.page.get_by_role("button", name="Menu"))
    s.page.wait_for_timeout(500)
    s.click(s.page.locator("label:has-text('Simulate no network') input"))
    s.page.wait_for_timeout(700)
    s.click(s.page.get_by_text("Today's worklist"), dx=0.08)
    s.page.wait_for_timeout(500)
    s.click(s.page.locator("li.card", has_text=case["borrower_name"]).first)
    wait_text(s.page, "Why this is on top")
    s.at("checkin")
    s.click(s.page.get_by_text("Check in", exact=True))
    s.page.wait_for_timeout(500)
    s.click(s.page.get_by_role("button", name="Demo location", exact=True))
    s.page.wait_for_timeout(500)
    s.click(s.page.get_by_role("button", name="Save check-in"))
    s.at("note")
    s.click(s.page.get_by_text("Voice note", exact=True))
    s.page.wait_for_timeout(400)
    box = s.page.locator("textarea").first
    s.click(box)
    box.type("नोकरी गेली आहे, पगार आल्यावर हप्ता भरेन.", delay=35)
    s.page.wait_for_timeout(300)
    s.click(s.page.get_by_role("button", name="Save note"))
    s.page.wait_for_timeout(1200)
    s.move(s.page.get_by_text(re.compile("waiting to sync")).first)
    s.at("online")
    s.click(s.page.get_by_role("button", name="Back"))
    s.page.wait_for_timeout(500)
    s.click(s.page.get_by_role("button", name="Menu"))
    s.page.wait_for_timeout(500)
    s.click(s.page.locator("label:has-text('Simulate no network') input"))
    s.page.wait_for_timeout(400)
    s.click(s.page.get_by_text("Today's worklist"), dx=0.08)
    s.page.get_by_text(re.compile("Synced \\d+ action")).first.wait_for(timeout=15000)
    s.finish()


def s07_fieldmap(b):
    s = Scene(b, "s07_fieldmap", "admin")
    s.page.goto(BASE + "/app/field")
    wait_text(s.page, "Check-ins")
    s.page.wait_for_timeout(2500)
    s.begin()
    first = s.page.locator("ul li").filter(has_text="GPS verified").first
    s.move(first)
    s.at("list")
    s.click(first)
    s.page.wait_for_timeout(2500)
    s.move(s.page.get_by_text(re.compile(r"^Verified")).first)
    s.page.wait_for_timeout(1500)
    sel = s.page.locator("select").first
    s.move(sel)
    sel.select_option("flagged")
    s.page.wait_for_timeout(1200)
    s.move(s.page.get_by_text(re.compile(r"^Flagged")).first)
    s.finish()


def s08_qr(b):
    s = Scene(b, "s08_qr", "agent")
    s.page.goto(BASE + f"/agent/case/{STATE['agent_case']}")
    wait_text(s.page, "Why this is on top")
    s.page.wait_for_timeout(800)
    s.begin()
    s.move(s.page.get_by_text("Overdue", exact=True).first)
    s.at("qr")
    s.click(s.page.get_by_text("Collect", exact=True))
    s.page.wait_for_timeout(500)
    s.click(s.page.get_by_role("button", name=re.compile("Show UPI QR")))
    s.page.get_by_text("Scan to pay").wait_for()
    STATE["pay_path"] = s.page.locator("a[title='Open borrower page']").get_attribute("href")
    s.move(s.page.locator("img[alt='Payment QR code']"))
    s.finish()


def s09_borrower(b):
    s = Scene(b, "s09_borrower", "public")
    s.page.goto(BASE + STATE["pay_path"])
    s.page.get_by_role("button", name="EN").wait_for()
    s.page.wait_for_timeout(1000)
    s.begin()
    s.move(s.page.locator("main").first, 0.5, 0.15, steps=18)
    s.page.wait_for_timeout(2000)
    s.move(s.page.get_by_text(re.compile("ID AG-")).first)
    s.at("english")
    s.click(s.page.get_by_role("button", name="EN"))
    s.page.wait_for_timeout(700)
    s.click(s.page.get_by_role("button", name=re.compile("Pay securely")))
    s.page.get_by_text("Sandbox Pay").first.wait_for()
    s.page.wait_for_timeout(1000)
    s.click(s.page.get_by_role("button", name=re.compile("^Pay ₹")))
    s.page.get_by_text("Payment received").wait_for(timeout=25000)
    s.page.wait_for_timeout(500)
    s.move(s.page.get_by_text(re.compile("RIQ/")).first)
    s.finish()


def s10_paid(b):
    s = Scene(b, "s10_paid", "admin")
    s.page.goto(BASE + f"/app/cases/{STATE['agent_case']}")
    wait_text(s.page, "Paid · confirmed")
    s.page.wait_for_timeout(500)
    s.begin()
    s.move(s.page.get_by_text("Paid · confirmed").first)
    s.page.wait_for_timeout(1500)
    s.click(s.page.get_by_role("button", name=re.compile("^Payments")).first)
    s.page.wait_for_timeout(600)
    s.move(s.page.get_by_text("signed webhook").first)
    s.at("webhooks")
    s.page.goto(BASE + "/app/payments")
    wait_text(s.page, "Replay a webhook")
    s.at("replay")
    s.click(s.page.get_by_role("button", name="Replay latest"))
    wait_text(s.page, "duplicate_ignored")
    s.move(s.page.get_by_text("duplicate_ignored").first)
    s.at("forge")
    s.click(s.page.get_by_role("button", name="Send forged event"))
    wait_text(s.page, "HTTP 401")
    s.move(s.page.get_by_text("HTTP 401").first)
    s.finish()


def s11_compliance(b):
    s = Scene(b, "s11_compliance", "admin")
    cases = api("/cases?status=DIGITAL&limit=5", token=s.token)["items"]
    s.page.goto(BASE + f"/app/cases/{cases[0]['id']}")
    wait_text(s.page, "Digital nudge")
    s.page.wait_for_timeout(500)
    s.begin()
    s.move(s.page.get_by_text("Digital nudge").first)
    s.at("clock")
    s.click(s.page.locator("header button").filter(has_text=re.compile(r"\d{2}:\d{2}")).first)
    s.page.wait_for_timeout(600)
    s.click(s.page.get_by_role("button", name="8:30 PM"))
    s.page.wait_for_timeout(700)
    s.click(s.page.get_by_text("Digital nudge").first)
    s.at("send")
    s.click(s.page.get_by_role("button", name=re.compile("^Send .* in")))
    wait_text(s.page, "BLOCKED")
    s.move(s.page.get_by_text("BLOCKED").first)
    s.at("report")
    s.page.goto(BASE + "/app/compliance")
    wait_text(s.page, "Contact attempts by hour")
    s.page.wait_for_timeout(800)
    s.move(s.page.get_by_text("Delivered outside window").first)
    s.page.wait_for_timeout(1500)
    s.move(s.page.get_by_text("Contact attempts by hour").first, 0.5, 6)
    s.finish()


def s12_audit(b):
    s = Scene(b, "s12_audit", "admin")
    s.page.goto(BASE + "/app/audit")
    wait_text(s.page, "Chain intact")
    s.page.wait_for_timeout(500)
    s.begin()
    s.move(s.page.get_by_text("Chain intact").first)
    s.page.wait_for_timeout(2500)
    s.move(s.page.locator("table tbody tr").first, 0.85, 0.5)
    s.at("tamper")
    s.click(s.page.get_by_role("button", name="Simulate insider tampering"))
    wait_text(s.page, "Tampering detected")
    s.move(s.page.get_by_text("Tampering detected").first)
    s.at("restore")
    s.click(s.page.get_by_role("button", name="Restore row"))
    wait_text(s.page, "Chain intact")
    s.finish()


def s13_promises(b):
    s = Scene(b, "s13_promises", "admin")
    s.page.goto(BASE + "/app/promises")
    s.page.locator("table tbody tr").first.wait_for()
    s.begin()
    s.move(s.page.locator("table tbody tr").first, 0.45, 0.5)
    s.at("jump")
    s.click(s.page.locator("header button").filter(has_text=re.compile(r"\d{2}:\d{2}")).first)
    s.page.wait_for_timeout(600)
    s.click(s.page.get_by_role("button", name="+3 days"))
    s.page.wait_for_timeout(1200)
    s.click(s.page.get_by_role("button", name="Broken", exact=True))
    s.at("escalations")
    s.click(s.page.get_by_role("button", name=re.compile("^Escalations")))
    s.page.wait_for_timeout(800)
    s.move(s.page.locator("table tbody tr").first, 0.3, 0.5)
    s.finish()


def s14_insight(b):
    s = Scene(b, "s14_insight", "admin")
    s.page.goto(BASE + "/app/sentiment")
    wait_text(s.page, "Borrower sentiment")
    s.page.wait_for_timeout(2500)
    s.begin()
    s.move(s.page.locator(".leaflet-container").first, 0.45, 0.6)
    s.at("state")
    s.click(s.page.get_by_text("Maharashtra", exact=True).first)
    s.page.wait_for_timeout(1200)
    s.move(s.page.get_by_text("Cities").first, 0.5, 3)
    s.at("leader")
    s.page.goto(BASE + "/app/leaderboard")
    wait_text(s.page, "points")
    s.page.wait_for_timeout(600)
    s.click(s.page.locator("main ul li").first)
    s.page.wait_for_timeout(1500)
    s.move(s.page.get_by_text("Gateway-confirmed payments").first)
    s.at("models")
    s.page.goto(BASE + "/app/models")
    wait_text(s.page, "Retrain now")
    s.page.wait_for_timeout(500)
    s.click(s.page.get_by_role("button", name=re.compile("Retrain now")))
    s.page.get_by_text(re.compile("Shadow comparison")).first.wait_for(timeout=20000)
    s.page.wait_for_timeout(500)
    s.move(s.page.get_by_role("button", name=re.compile("Approve")).first)
    s.finish()


ORDER = [s01_dashboard, s02_intake, s03_case, s04_rules, s05_allocation, s06_agent, s07_fieldmap, s08_qr,
         s09_borrower, s10_paid, s11_compliance, s12_audit, s13_promises, s14_insight]

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        admin = session("admin@recoveriq.in")["access_token"]
        api("/clock", {"mode": "reset"}, token=admin)
        try:
            for fn in ORDER:
                if ONLY and fn.__name__ not in ONLY:
                    continue
                print("scene", fn.__name__)
                try:
                    fn(browser)
                except Exception:
                    for ctx in browser.contexts:
                        for pg in ctx.pages:
                            pg.screenshot(path=str(WORK / f"_fail_{fn.__name__}.png"))
                            print("  url:", pg.url)
                    raise
        finally:
            api("/clock", {"mode": "reset"}, token=session("admin@recoveriq.in")["access_token"])
            STATE_FILE.write_text(json.dumps(STATE, indent=2))
            browser.close()
