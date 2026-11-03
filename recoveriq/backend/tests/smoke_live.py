"""Live smoke test against a running server: every page's API for every role, no 5xx allowed.
    python backend/tests/smoke_live.py http://localhost:8010"""
import sys
import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/") + "/api/v1"
ROLES = ["admin@recoveriq.in", "exec@recoveriq.in", "l1.west@recoveriq.in", "l2.mumbai@recoveriq.in", "agent@recoveriq.in"]
GETS = ["/meta", "/auth/me", "/cases?limit=5", "/dashboards/summary?days=30", "/dashboards/field?hours=168",
        "/dashboards/sentiment?level=state", "/dashboards/sentiment?level=city&state=Maharashtra",
        "/dashboards/sentiment?level=borrower&state=Maharashtra", "/leaderboard?days=30", "/compliance/report?days=30",
        "/allocation/workload", "/promises?status=open", "/promises?status=broken", "/promises?status=kept", "/escalations",
        "/disputes?status=open", "/payments?limit=10", "/payments/webhooks", "/notifications?limit=10", "/rules", "/models",
        "/audit?limit=10", "/audit/verify", "/audit/demo/state", "/intake/jobs", "/users", "/agent/worklist", "/agent/visits",
        "/visits/review", "/intake/sample.csv"]
bad = 0
for email in ROLES:
    c = httpx.Client(timeout=30)
    tok = c.post(BASE + "/auth/login", json={"email": email, "password": "Demo@1234"}).json()["access_token"]
    h = {"Authorization": "Bearer " + tok}
    codes = {}
    for g in GETS:
        r = c.get(BASE + g, headers=h)
        codes[g] = r.status_code
        if r.status_code >= 500:
            bad += 1
            print("5xx", email, g, r.text[:200])
    first = c.get(BASE + "/cases?limit=1", headers=h).json()["items"] if codes["/cases?limit=5"] == 200 else []
    if first:
        r = c.get(BASE + f"/cases/{first[0]['id']}", headers=h)
        codes["case_detail"] = r.status_code
        bad += r.status_code >= 500
    ok = sum(1 for v in codes.values() if v < 400)
    denied = [k for k, v in codes.items() if v in (401, 403)]
    print(f"{email:28s} ok={ok:2d} denied(by role)={len(denied):2d} other={[ (k,v) for k,v in codes.items() if v>=400 and v not in (401,403)]}")
print("5xx errors:", bad)
sys.exit(1 if bad else 0)
