"""Synthetic demo portfolio. Everything here is generated (seeded RNG, labelled synthetic in the
UI). Activity history flows through the same analysers and rules as live data: notes go through
the sentiment analyser, cases through the scorecard, model and router."""
from __future__ import annotations

import math
import random
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select

from . import audit, clock
from .db import write_session
from .domain import ml, rules as rulebook, sentiment as senti
from .domain.geo import haversine_m, verify_visit
from .integrations import messaging
from .models import (
    Borrower, Branch, Case, CaseEvent, ContactAttempt, Dispute, ModelVersion, Note, Payment, PaymentLink, Promise,
    Region, User, Visit,
)
from .security import encrypt, hash_password, mask_name, mask_phone
from .services import allocate, rescore

DEMO_PASSWORD = "Demo@1234"

BRANCHES = [
    # region, name, city, state, pincode prefix, lat, lng, agents, cases, localities
    ("West", "Mumbai Central", "Mumbai", "Maharashtra", "400", 19.0330, 72.8500, 4, 140,
     ["Dadar West", "Parel", "Worli", "Sion", "Matunga", "Kurla West", "Chembur", "Ghatkopar East", "Bandra East", "Mahim"]),
    ("West", "Thane", "Thane", "Maharashtra", "4006", 19.2183, 72.9781, 2, 70,
     ["Naupada", "Vartak Nagar", "Kopri", "Wagle Estate", "Majiwada", "Kalwa"]),
    ("West", "Pune", "Pune", "Maharashtra", "411", 18.5204, 73.8567, 3, 90,
     ["Kothrud", "Hadapsar", "Yerawada", "Shivajinagar", "Kasba Peth", "Wakad", "Bibwewadi"]),
    ("West", "Nagpur", "Nagpur", "Maharashtra", "440", 21.1458, 79.0882, 2, 45,
     ["Sitabuldi", "Dharampeth", "Sadar", "Manish Nagar", "Itwari"]),
    ("West", "Nashik", "Nashik", "Maharashtra", "422", 19.9975, 73.7898, 2, 35,
     ["Panchavati", "College Road", "Cidco", "Satpur"]),
    ("West", "Ahmedabad", "Ahmedabad", "Gujarat", "380", 23.0225, 72.5714, 2, 45,
     ["Maninagar", "Navrangpura", "Naroda", "Vastrapur", "Bapunagar"]),
    ("North", "New Delhi", "New Delhi", "Delhi", "110", 28.6139, 77.2090, 3, 60,
     ["Lajpat Nagar", "Karol Bagh", "Rohini Sector 7", "Mayur Vihar", "Janakpuri", "Shahdara"]),
    ("North", "Lucknow", "Lucknow", "Uttar Pradesh", "226", 26.8467, 80.9462, 2, 35,
     ["Aminabad", "Gomti Nagar", "Alambagh", "Indira Nagar", "Chowk"]),
    ("North", "Jaipur", "Jaipur", "Rajasthan", "302", 26.9124, 75.7873, 2, 30,
     ["Malviya Nagar", "Mansarovar", "Vaishali Nagar", "Sanganer"]),
    ("South", "Bengaluru", "Bengaluru", "Karnataka", "560", 12.9716, 77.5946, 3, 55,
     ["Jayanagar", "Rajajinagar", "Whitefield", "BTM Layout", "Yeshwanthpur", "KR Puram"]),
    ("South", "Chennai", "Chennai", "Tamil Nadu", "600", 13.0827, 80.2707, 2, 35,
     ["T Nagar", "Tambaram", "Ambattur", "Velachery", "Perambur"]),
    ("South", "Hyderabad", "Hyderabad", "Telangana", "500", 17.3850, 78.4867, 2, 40,
     ["Ameerpet", "Kukatpally", "Dilsukhnagar", "Secunderabad", "Mehdipatnam"]),
    ("East", "Kolkata", "Kolkata", "West Bengal", "700", 22.5726, 88.3639, 2, 35,
     ["Salt Lake", "Behala", "Dum Dum", "Howrah Maidan", "Garia"]),
    ("East", "Patna", "Patna", "Bihar", "800", 25.5941, 85.1376, 2, 25,
     ["Kankarbagh", "Boring Road", "Rajendra Nagar", "Danapur"]),
]

FIRST_M = ["Rahul", "Amit", "Sanjay", "Vijay", "Suresh", "Imran", "Rohit", "Prakash", "Ganesh", "Arjun", "Nikhil", "Manoj",
           "Deepak", "Kiran", "Ravi", "Sachin", "Ajay", "Farhan", "Venkat", "Sourav", "Abhishek", "Mahesh", "Tushar", "Anil"]
FIRST_F = ["Priya", "Sneha", "Kavita", "Anita", "Pooja", "Meena", "Sunita", "Ayesha", "Lakshmi", "Neha", "Rupali", "Shreya",
           "Swati", "Divya", "Farida", "Geeta", "Madhuri", "Pallavi", "Rekha", "Nandini", "Bhavna", "Jyoti"]
SURNAMES = {
    "Maharashtra": ["Patil", "Deshmukh", "Joshi", "Kulkarni", "Pawar", "Jadhav", "Shinde", "Gaikwad", "More", "Chavan",
                    "Bhosale", "Kale", "Sawant", "Shaikh", "Khan", "Nair", "Mishra", "Salunkhe", "Wagh"],
    "Gujarat": ["Patel", "Shah", "Desai", "Mehta", "Parmar", "Chauhan", "Solanki", "Trivedi"],
    "Delhi": ["Sharma", "Verma", "Gupta", "Arora", "Malhotra", "Khanna", "Singh", "Kapoor", "Ansari"],
    "Uttar Pradesh": ["Yadav", "Mishra", "Pandey", "Tiwari", "Srivastava", "Shukla", "Qureshi", "Maurya"],
    "Rajasthan": ["Rathore", "Meena", "Sharma", "Agarwal", "Choudhary", "Jain"],
    "Karnataka": ["Gowda", "Rao", "Shetty", "Hegde", "Kumar", "Naik", "Iyengar"],
    "Tamil Nadu": ["Iyer", "Krishnan", "Murugan", "Subramanian", "Pillai", "Raman"],
    "Telangana": ["Reddy", "Naidu", "Rao", "Goud", "Varma", "Ali"],
    "West Bengal": ["Das", "Banerjee", "Mukherjee", "Ghosh", "Sen", "Chatterjee", "Roy"],
    "Bihar": ["Kumar", "Sinha", "Prasad", "Jha", "Thakur", "Mandal", "Paswan"],
}
LANG_MIX = {"Maharashtra": (("mr", .55), ("hi", .3), ("en", .15)), "Delhi": (("hi", .75), ("en", .25)),
            "Uttar Pradesh": (("hi", .85), ("en", .15)), "Rajasthan": (("hi", .85), ("en", .15)),
            "Bihar": (("hi", .9), ("en", .1)), "Gujarat": (("hi", .45), ("en", .55))}
LOANS = [("two_wheeler", .26), ("personal", .32), ("gold", .14), ("msme", .1), ("consumer_durable", .18)]
LOAN_SHAPE = {  # emi range, tenure months range
    "two_wheeler": ((2200, 4800), (18, 36)), "personal": ((3500, 16000), (12, 48)), "gold": ((1800, 7500), (6, 24)),
    "msme": ((11000, 42000), (24, 60)), "consumer_durable": ((1200, 3800), (6, 18)),
}
# reason-category mix by state (makes the sentiment map tell a story; synthetic)
CAT_BASE = {"will_pay": .36, "job_loss": .12, "medical": .1, "business_loss": .1, "family_event": .08, "dispute": .07,
            "willful_default": .07, "unreachable": .1}
CAT_TILT = {"Gujarat": {"business_loss": .14, "will_pay": .06}, "Bihar": {"job_loss": .16, "unreachable": .08, "will_pay": -.12},
            "Uttar Pradesh": {"job_loss": .08, "willful_default": .05}, "Maharashtra": {"will_pay": .12},
            "Karnataka": {"will_pay": .1}, "West Bengal": {"medical": .08, "family_event": .05},
            "Delhi": {"dispute": .08, "willful_default": .04}, "Telangana": {"business_loss": .06}}

NOTE_TEXT = {
    "en": {
        "will_pay": ["Salary is delayed this month, will pay full EMI by the 10th. Polite and cooperative.",
                     "Agreed to pay ₹{amt} tomorrow morning, sure about it.", "Will pay after salary credit on Friday, promise to pay."],
        "job_loss": ["Lost job in August, looking for work. Wants two months.", "Laid off from the factory, wife managing house expenses."],
        "medical": ["Father in hospital after surgery, savings used for treatment.", "Borrower sick with dengue, could not work for three weeks."],
        "business_loss": ["Shop closed by municipality for road work, sales down badly.", "Business loss after flooding, stock damaged."],
        "family_event": ["Daughter's wedding last month, expenses very high. Will restart after Diwali."],
        "dispute": ["Says already paid ₹{amt} in cash to previous agent, asks for receipt. Disputes amount.",
                    "Claims wrong amount, excess charges added after foreclosure request."],
        "willful_default": ["Refused to pay, shouted at agent and said do what you want.", "Said he will not pay, abusive on call."],
        "unreachable": ["House locked, neighbours say family shifted to village.", "Phone switched off, not at home on two visits."],
    },
    "hi": {
        "will_pay": [("सैलरी आते ही पूरी किस्त भर दूंगा, 10 तारीख तक ज़रूर।", "Will pay the full instalment as soon as salary comes, surely by the 10th."),
                     ("कल ₹{amt} दे दूंगा, पक्का।", "Will give ₹{amt} tomorrow, for sure.")],
        "job_loss": [("नौकरी चली गई है, नया काम ढूंढ रहे हैं। थोड़ा समय चाहिए।", "Lost the job, looking for new work. Needs some time.")],
        "medical": [("पिताजी अस्पताल में भर्ती हैं, इलाज में सारे पैसे लग गए।", "Father is admitted in hospital, all money went into treatment.")],
        "business_loss": [("दुकान बंद है, धंधा बहुत मंदा है, नुकसान हुआ।", "Shop is closed, business is very slow, suffered a loss.")],
        "family_event": [("बेटी की शादी थी, खर्चा बहुत हो गया।", "It was daughter's wedding, expenses were very high.")],
        "dispute": [("पहले ही भर दिया था, गलत राशि दिखा रहे हैं।", "Already paid earlier; you are showing the wrong amount.")],
        "willful_default": [("पैसा नहीं दूंगा, जो करना है करो।", "I will not pay, do whatever you want.")],
        "unreachable": [("घर बंद था, फोन बंद आ रहा है।", "House was locked, phone is switched off.")],
    },
    "mr": {
        "will_pay": [("पगार आल्यावर पूर्ण हप्ता भरेन, नक्की.", "Will pay the full instalment once salary comes, definitely."),
                     ("उद्या ₹{amt} भरतो.", "Will pay ₹{amt} tomorrow.")],
        "job_loss": [("नोकरी गेली आहे, काम शोधत आहे. थोडा वेळ द्या.", "Lost the job, searching for work. Give some time.")],
        "medical": [("आई रुग्णालयात आहे, उपचारासाठी पैसे लागले.", "Mother is in hospital, money went into treatment.")],
        "business_loss": [("व्यवसाय बंद आहे, खूप तोटा झाला.", "Business is shut, made a big loss.")],
        "family_event": [("मुलीचे लग्न झाले, खर्च खूप झाला.", "Daughter got married, expenses were heavy.")],
        "dispute": [("आधीच भरले आहे, चुकीची रक्कम दाखवत आहात.", "Already paid; you are showing the wrong amount.")],
        "willful_default": [("पैसे देणार नाही, जे करायचं ते करा.", "Will not give money, do whatever you want.")],
        "unreachable": [("घर बंद होते, फोन बंद आहे.", "House was locked, phone is off.")],
    },
}

PEOPLE = {  # staff names
    "admin": ("Aditi Rao", "admin@recoveriq.in"), "exec": ("Vikram Mehta", "exec@recoveriq.in"),
    "l1": {"West": ("Neha Kulkarni", "l1.west@recoveriq.in"), "North": ("Arvind Saxena", "l1.north@recoveriq.in"),
           "South": ("Lakshmi Narayanan", "l1.south@recoveriq.in"), "East": ("Debashis Roy", "l1.east@recoveriq.in")},
}
L2_NAMES = ["Suresh Nair", "Pradnya Kadam", "Omkar Joshi", "Rajesh Thakre", "Manisha Gite", "Hetal Parikh", "Karan Bedi",
            "Shalini Awasthi", "Mohit Rathore", "Prakash Hegde", "Revathi Sundar", "Srinivas Reddy", "Arpita Sen", "Nitin Sinha"]
AGENT_NAMES = ["Rahul Pawar", "Sameer Shaikh", "Pooja Jadhav", "Vinod Kamble", "Akash Gaikwad", "Snehal More", "Tejas Kulkarni",
               "Rupali Shinde", "Mayur Deshpande", "Kunal Thakur", "Ganesh Wankhede", "Payal Bhoyar", "Yogesh Ahire",
               "Sonal Nikam", "Jignesh Patel", "Dhara Shah", "Rakesh Yadav", "Mohd. Arif", "Simran Kaur", "Anurag Tiwari",
               "Shivani Mishra", "Devendra Singh", "Pooja Meena", "Harish Gowda", "Ramya Shetty", "Imtiaz Pasha",
               "Karthik Raman", "Divya Murugan", "Ravi Teja", "Sana Fatima", "Subhajit Das", "Moumita Ghosh",
               "Abhishek Jha", "Neelam Kumari"]


def _pick(rnd: random.Random, pairs):
    r, acc = rnd.random(), 0.0
    for v, w in pairs:
        acc += w
        if r <= acc:
            return v
    return pairs[-1][0]


def _local_dt(day_offset: int, hour: float, rnd: random.Random) -> datetime:
    """Naive UTC datetime for `day_offset` days ago at local `hour` (IST)."""
    base = clock.local_now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=day_offset)
    t = base + timedelta(hours=hour, minutes=rnd.randint(0, 59), seconds=rnd.randint(0, 59))
    return (t - t.utcoffset()).replace(tzinfo=None)


def ensure_seeded() -> None:
    with write_session() as db:
        if db.execute(select(func.count()).select_from(User)).scalar():
            return
        for kind in rulebook.DEFAULTS:
            rulebook.active(db, kind)
        seed(db)


def seed(db) -> None:
    rnd = random.Random(20261102)
    now = clock.utcnow()
    pw = hash_password(DEMO_PASSWORD)  # same demo password for every seeded user; hash once

    regions = {}
    for name in ("West", "North", "South", "East"):
        regions[name] = Region(name=name)
        db.add(regions[name])
    db.flush()

    admin = User(name=PEOPLE["admin"][0], email=PEOPLE["admin"][1], role="admin", password_hash=pw, phone="+919820000001")
    exe = User(name=PEOPLE["exec"][0], email=PEOPLE["exec"][1], role="exec", password_hash=pw, phone="+919820000002")
    db.add_all([admin, exe])
    l1 = {}
    for reg, (n, e) in PEOPLE["l1"].items():
        l1[reg] = User(name=n, email=e, role="l1", password_hash=pw, region_id=regions[reg].id, phone="+91982000001" + str(len(l1)))
        db.add(l1[reg])
    db.flush()

    branches, agents_by_branch, l2_by_branch = [], {}, {}
    agent_names = iter(AGENT_NAMES)
    for i, (reg, bname, city, state, prefix, lat, lng, n_agents, n_cases, locs) in enumerate(BRANCHES):
        br = Branch(region_id=regions[reg].id, name=bname, city=city, state=state, pincode_prefix=prefix, lat=lat, lng=lng)
        db.add(br)
        db.flush()
        branches.append((br, n_cases, locs))
        slug = city.lower().replace(" ", "")
        l2 = User(name=L2_NAMES[i], email=f"l2.{slug}@recoveriq.in", role="l2", password_hash=pw, branch_id=br.id,
                  region_id=br.region_id, manager_id=l1[reg].id, phone=f"+9198200001{i:02d}")
        db.add(l2)
        db.flush()
        l2_by_branch[br.id] = l2
        agents_by_branch[br.id] = []
        for k in range(n_agents):
            name = next(agent_names)
            email = "agent@recoveriq.in" if (i == 0 and k == 0) else f"{name.split()[0].lower().replace('.', '')}.{slug}@recoveriq.in"
            home = (19.0178, 72.8478) if (i == 0 and k == 0) else (lat + rnd.uniform(-0.05, 0.05), lng + rnd.uniform(-0.05, 0.05))
            a = User(name=name, email=email, role="agent", password_hash=pw, branch_id=br.id, region_id=br.region_id,
                     manager_id=l2.id, capacity=rnd.choice([24, 28, 30, 32]), home_lat=home[0], home_lng=home[1],
                     phone=f"+9199300{i:02d}{k:03d}")
            db.add(a)
            agents_by_branch[br.id].append(a)
    db.flush()

    # ---------------------------------------------------------------- model v1 (trained on synthetic data)
    res = ml.train(seed=7)
    mv = ModelVersion(version=1, name="selfcure-logreg-v1", status="active", params=res["params"], metrics=res["metrics"],
                      training_rows=res["training_rows"], real_outcome_rows=0, created_at=now - timedelta(days=21),
                      approved_by=admin.id, approved_at=now - timedelta(days=21))
    db.add(mv)
    db.flush()

    # ---------------------------------------------------------------- portfolio
    acc_no = 4100000
    cases: list[Case] = []
    for br, n_cases, locs in branches:
        for _ in range(n_cases):
            acc_no += rnd.randint(7, 61)
            female = rnd.random() < 0.38
            first = rnd.choice(FIRST_F if female else FIRST_M)
            last = rnd.choice(SURNAMES[br.state] if br.state in SURNAMES else SURNAMES["Maharashtra"])
            name = f"{first} {last}"
            lang = _pick(rnd, LANG_MIX.get(br.state, (("en", .7), ("hi", .3))))
            mobile = f"{rnd.choice('6789')}{rnd.randint(100000000, 999999999)}"
            loc = rnd.choice(locs)
            # spread borrowers around the branch (closer for big metros' demo agent)
            r_km = abs(rnd.gauss(0, 4.5 if br.city != "Mumbai" else 3.2))
            ang = rnd.uniform(0, 2 * math.pi)
            blat = br.lat + (r_km / 111) * math.cos(ang)
            blng = br.lng + (r_km / (111 * math.cos(math.radians(br.lat)))) * math.sin(ang)
            pincode = (br.pincode_prefix + f"{rnd.randint(1, 99 if len(br.pincode_prefix) == 3 else 15):0{6 - len(br.pincode_prefix)}d}")[:6]
            b = Borrower(name_enc=encrypt(name), phone_enc=encrypt("+91" + mobile),
                         email_enc=encrypt(f"{first.lower()}.{last.lower()}{rnd.randint(1, 99)}@example.in"),
                         address_enc=encrypt(f"{rnd.randint(1, 240)}, {rnd.choice(['Sai Krupa', 'Shanti Niwas', 'Om Residency', 'Green Park', 'Laxmi Sadan', 'Gokul Dham', 'Ashirwad'])}, {loc}, {br.city} {pincode}"),
                         name_masked=mask_name(name), phone_masked=mask_phone(mobile), pincode=pincode, city=br.city,
                         state=br.state, lat=round(blat, 6), lng=round(blng, 6), preferred_language=lang,
                         opt_out=["whatsapp"] if rnd.random() < 0.06 else [])
            db.add(b)
            db.flush()
            loan = _pick(rnd, LOANS)
            (emi_lo, emi_hi), (t_lo, t_hi) = LOAN_SHAPE[loan]
            emi = round(rnd.uniform(emi_lo, emi_hi) / 50) * 50
            tenure = rnd.randint(t_lo, t_hi)
            principal = round(emi * tenure * 0.86, -2)
            remaining = rnd.randint(max(2, tenure // 4), tenure)
            outstanding = round(emi * remaining * 0.9, -1)
            dpd = int(_pick(rnd, [(rnd.randint(3, 30), .45), (rnd.randint(31, 60), .25), (rnd.randint(61, 90), .17),
                                  (rnd.randint(91, 170), .13)]))
            missed = max(1, math.ceil(dpd / 30) + (1 if rnd.random() < 0.12 else 0))
            c = Case(account_no=f"SF{acc_no}", borrower_id=b.id, branch_id=br.id, loan_type=loan, principal=principal,
                     emi_amount=emi, outstanding=outstanding, amount_due=round(emi * missed, 2), dpd=dpd, missed_emis=missed,
                     dpd_bucket="", last_payment_date=(clock.local_today() - timedelta(days=dpd + rnd.randint(0, 25))),
                     status="NEW", created_at=now - timedelta(days=24), updated_at=now - timedelta(days=24),
                     unreachable_streak=rnd.choice([0, 0, 0, 0, 1, 2, 3, 4]) if dpd > 45 else 0)
            db.add(c)
            db.flush()
            db.add(CaseEvent(case_id=c.id, type="intake", title="Case created from core lending export (synthetic)",
                             data={"source": "seed"}, actor_name="Intake job", ts=c.created_at))
            rescore(db, c, quiet=True)
            db.add(CaseEvent(case_id=c.id, type="routing", title=f"Routed to {c.channel.title()} · risk {c.risk_score}",
                             data={"rule_version": 1}, actor_name="Rules engine", ts=c.created_at + timedelta(minutes=2)))
            cases.append(c)
    db.flush()
    audit.record(db, admin, "intake.upload", "intake_job", None,
                 {"file": "core_lending_export_oct.csv (synthetic)", "created": len(cases)}, ts=now - timedelta(days=24))
    allocate(db, [br.id for br, _, _ in branches], None)
    for ev in db.execute(select(CaseEvent).where(CaseEvent.type == "assignment")).scalars():
        ev.ts = now - timedelta(days=24) + timedelta(minutes=5)

    # ---------------------------------------------------------------- activity history (last ~21 days)
    audits: list[tuple] = []
    receipt_n = 0
    pay_rows = 0

    def ev(case, type_, title, ts, actor=None, data=None, actor_name=None):
        db.add(CaseEvent(case_id=case.id, type=type_, title=title, data=data or {}, actor_id=actor.id if actor else None,
                         actor_name=actor.name if actor else (actor_name or "System"), ts=ts))

    for c in cases:
        agent = db.get(User, c.assigned_agent_id) if c.assigned_agent_id else None
        lang = c.borrower.preferred_language
        state = c.borrower.state
        worked = agent is not None and rnd.random() < 0.72
        last_visit_t = None
        # field visits / calls
        if worked:
            for j in range(rnd.choice([1, 1, 2, 2, 3])):
                d = rnd.randint(1, 20)
                ts = _local_dt(d, rnd.uniform(9.2, 18.4), rnd)
                if c.channel == "FIELD" or (c.channel == "TELE" and rnd.random() < 0.2):
                    kind = _pick(rnd, [("verified", .8), ("flagged", .12), ("low", .08)])
                    off_m = rnd.uniform(15, 260) if kind == "verified" else rnd.uniform(420, 1800) if kind == "flagged" else rnd.uniform(20, 200)
                    ang = rnd.uniform(0, 2 * math.pi)
                    vlat = c.borrower.lat + (off_m / 111000) * math.cos(ang)
                    vlng = c.borrower.lng + (off_m / (111000 * math.cos(math.radians(c.borrower.lat)))) * math.sin(ang)
                    acc = rnd.uniform(6, 35) if kind != "low" else rnd.uniform(120, 400)
                    dist = haversine_m(vlat, vlng, c.borrower.lat, c.borrower.lng)
                    ver, why = verify_visit(dist, acc, None, vlat, vlng, ts.timestamp())
                    outcome = _pick(rnd, [("met_borrower", .45), ("promise_taken", .2), ("not_home", .18),
                                          ("door_locked", .07), ("refused", .05), ("payment_link_shared", .05)])
                    v = Visit(client_id=secrets.token_hex(16)[:8] + "-0000-4000-8000-" + secrets.token_hex(6),
                              case_id=c.id, agent_id=agent.id, lat=vlat, lng=vlng, accuracy_m=round(acc, 1),
                              distance_m=round(dist, 1), verification=ver, location_source="device", outcome=outcome,
                              remarks=None, device_ts=ts, server_ts=ts + timedelta(seconds=rnd.randint(1, 50)),
                              review_status="pending" if ver != "verified" and rnd.random() < 0.5 else (None if ver == "verified" else "approved"))
                    db.add(v)
                    db.flush()
                    ev(c, "visit", f"Field visit: {outcome.replace('_', ' ')} · {ver.replace('_', ' ')}", ts, agent,
                       {"visit_id": v.id, "verification": ver, "why": why, "distance_m": round(dist)})
                    audits.append((ts, agent, "visit.checkin", "visit", v.id, {"case": c.account_no, "verification": ver}))
                    last_visit_t = ts
                else:
                    st = _pick(rnd, [("connected", .55), ("no_answer", .45)])
                    db.add(ContactAttempt(client_id=None, case_id=c.id, channel="call", recipient=c.borrower.phone_masked,
                                          status=st, actor_id=agent.id, ts=ts))
                    ev(c, "call", f"Call: {st.replace('_', ' ')}", ts, agent)
                    audits.append((ts, agent, "contact.call", "case", c.id, {"case": c.account_no, "outcome": st}))
        # digital nudges
        if c.channel == "DIGITAL" or (worked and rnd.random() < 0.3):
            for _ in range(rnd.choice([1, 2, 2, 3])):
                d = rnd.randint(1, 18)
                ch = "whatsapp" if "whatsapp" not in (c.borrower.opt_out or []) and rnd.random() < .5 else rnd.choice(["sms", "email"])
                ts = _local_dt(d, rnd.uniform(9.5, 18.5), rnd)
                text = messaging.render("reminder", lang, name=mask_name("Customer X"), amount=c.amount_due,
                                        link="https://pay.recoveriq.in/p/•••", loan_type=c.loan_type)
                db.add(ContactAttempt(case_id=c.id, channel=ch, template="reminder", language=lang, recipient=c.borrower.phone_masked,
                                      body=text, status="delivered", actor_id=None, ts=ts))
                ev(c, "nudge", f"{ch.upper()} nudge delivered ({lang.upper()})", ts, actor_name="Nudge scheduler")
            if rnd.random() < 0.18:  # an attempt the policy engine stopped
                ts = _local_dt(rnd.randint(1, 15), rnd.uniform(19.2, 21.8), rnd)
                db.add(ContactAttempt(case_id=c.id, channel="sms", template="reminder", language=lang,
                                      recipient=c.borrower.phone_masked, status="blocked",
                                      block_reason=f"Quiet hours: contact allowed only 08:00–19:00 borrower local time "
                                                   f"(now {clock.to_local(ts):%H:%M}) · RBI fair-practice code", ts=ts))
                ev(c, "policy_block", "SMS nudge blocked by Contact Policy", ts, actor_name="Contact Policy Engine")
                audits.append((ts, None, "contact.blocked", "case", c.id, {"case": c.account_no, "reason": "quiet hours"}))
        # notes
        if (worked and rnd.random() < 0.62) or (not worked and rnd.random() < 0.08):
            tilt = CAT_TILT.get(state, {})
            weights = [(k, max(0.01, v + tilt.get(k, 0))) for k, v in CAT_BASE.items()]
            tot = sum(w for _, w in weights)
            cat = _pick(rnd, [(k, w / tot) for k, w in weights])
            nl = lang if lang in NOTE_TEXT else "en"
            choice = rnd.choice(NOTE_TEXT[nl][cat])
            amt = f"{round(c.emi_amount, -2):,.0f}"
            original, english = (choice, choice) if nl == "en" else choice
            original, english = original.replace("{amt}", amt), english.replace("{amt}", amt)
            res_s = senti.analyse(original, nl)
            ts = (last_visit_t + timedelta(minutes=rnd.randint(2, 15))) if last_visit_t else _local_dt(rnd.randint(1, 18), rnd.uniform(10, 18), rnd)
            n = Note(client_id=secrets.token_hex(4) + "-1111-4000-8000-" + secrets.token_hex(6), case_id=c.id,
                     agent_id=agent.id if agent else None, language=res_s["language"],
                     source="voice" if nl != "en" and rnd.random() < 0.6 else "typed", original_text=original,
                     english_text=english, sentiment=res_s["sentiment"], sentiment_score=res_s["score"],
                     reason_category=res_s["reason_category"], analyzer="lexicon", city=c.borrower.city, state=state,
                     captured_at=ts)
            db.add(n)
            c.last_sentiment, c.last_reason_category = n.sentiment, n.reason_category
            ev(c, "note", f"{n.source.title()} note · {n.sentiment} · {senti.CATEGORIES[n.reason_category]}", ts, agent,
               {"text": original[:200]})
        # promises
        if worked and rnd.random() < 0.34 and c.last_reason_category not in ("willful_default", "dispute"):
            created = _local_dt(rnd.randint(2, 12), rnd.uniform(10, 18), rnd)
            pdate = (clock.to_local(created) + timedelta(days=rnd.randint(2, 9))).date()
            if rnd.random() < 0.3:  # due very soon so the demo can fast-forward and watch them break
                pdate = clock.local_today() + timedelta(days=rnd.choice([0, 1, 2]))
            amount = round(min(c.amount_due, max(c.emi_amount, c.amount_due * rnd.choice([0.5, 1, 1]))), -1)
            p = Promise(client_id=secrets.token_hex(4) + "-2222-4000-8000-" + secrets.token_hex(6), case_id=c.id,
                        amount=amount, promised_date=pdate, status="open", channel="field", captured_by=agent.id,
                        created_at=created)
            db.add(p)
            ev(c, "ptp", f"Promise to pay ₹{amount:,.0f} by {pdate:%d %b %Y}", created, agent)
            audits.append((created, agent, "ptp.created", "promise", None, {"case": c.account_no, "amount": amount}))
            c.status = "PTP"
            outcome_r = rnd.random()
            due_passed = pdate + timedelta(days=1) < clock.local_today()
            if due_passed and outcome_r < 0.55:
                p.status = "kept"  # payment created below
                p.resolved_at = _local_dt(max(0, (clock.local_today() - pdate).days), rnd.uniform(10, 18), rnd)
                c.kept_ptp_count += 1
                c._seed_pay = (amount, p.resolved_at, True)
            elif due_passed:
                p.status, p.resolved_at = "broken", datetime.combine(pdate + timedelta(days=2), datetime.min.time()) + timedelta(hours=3)
                c.broken_ptp_count += 1
                ev(c, "ptp", f"Promise of ₹{amount:,.0f} for {pdate:%d %b} broken", p.resolved_at, actor_name="PTP scheduler")
                if c.broken_ptp_count >= 1 and rnd.random() < 0.45:
                    c.broken_ptp_count = 2
                    c.status = "ESCALATED"
                    c.escalated_to_id = l2_by_branch[c.branch_id].id
                    ev(c, "status", "Promise broken → Escalated", p.resolved_at + timedelta(minutes=1), actor_name="PTP scheduler",
                       data={"reason": "2 broken promises → escalated to branch manager"})
                else:
                    c.status = "FIELD"
                    c.channel = "FIELD"
        # spontaneous payments (digital self-cure or after field work)
        if not hasattr(c, "_seed_pay") and c.status not in ("ESCALATED",) and rnd.random() < (0.2 if c.channel == "DIGITAL" else 0.11):
            full = rnd.random() < 0.6
            amount = c.amount_due if full else round(c.amount_due * rnd.choice([0.3, 0.5]), -1)
            c._seed_pay = (max(amount, 500.0), _local_dt(rnd.randint(0, 20), rnd.uniform(9, 21), rnd), False)
        if hasattr(c, "_seed_pay"):
            amount, ts, from_ptp = c._seed_pay
            amount = round(min(amount, c.outstanding), 2)
            link = PaymentLink(case_id=c.id, gateway="sandbox", gateway_link_id=f"plink_seed{pay_rows:05d}",
                               token=secrets.token_urlsafe(16), amount=amount, amount_paid=amount,
                               gateway_url=f"/gateway/checkout/plink_seed{pay_rows:05d}", status="paid",
                               created_by=c.assigned_agent_id, created_at=ts - timedelta(hours=rnd.randint(1, 30)),
                               expires_at=ts + timedelta(days=6))
            db.add(link)
            db.flush()
            receipt_n += 1
            pay = Payment(case_id=c.id, link_id=link.id, gateway="sandbox", gateway_payment_id=f"pay_seed{pay_rows:06d}",
                          amount=amount, method=rnd.choice(["upi", "upi", "upi", "card", "netbanking"]), status="captured",
                          receipt_no=f"RIQ/{clock.local_today().year}/{receipt_n:06d}", source="webhook",
                          collected_by=c.assigned_agent_id, confirmed_at=ts)
            db.add(pay)
            pay_rows += 1
            c.collected_total += amount
            c.last_collected_at = ts
            c.amount_due = round(max(0.0, c.amount_due - amount), 2)
            c.outstanding = round(max(0.0, c.outstanding - amount), 2)
            ev(c, "payment", f"₹{amount:,.2f} confirmed by Gateway webhook", ts, actor_name="Payment gateway",
               data={"gateway_payment_id": pay.gateway_payment_id, "receipt_no": pay.receipt_no})
            audits.append((ts, None, "payment.confirmed", "payment", pay.id,
                           {"case": c.account_no, "amount": amount, "gateway_payment_id": pay.gateway_payment_id,
                            "receipt_no": pay.receipt_no, "source": "webhook"}))
            if c.amount_due <= 0.5:
                c.status, c.dpd, c.missed_emis = "PAID", 0, 0
                ev(c, "status", "Awaiting gateway → Paid (confirmed)", ts + timedelta(seconds=1), actor_name="payment-gateway")
            else:
                c.missed_emis = max(1, math.ceil(c.amount_due / c.emi_amount))
                if c.status == "PTP":
                    c.status = c.channel
            del c._seed_pay

    # disputes
    disp_cands = [c for c in cases if c.status in ("FIELD", "TELE") and c.last_reason_category == "dispute"][:7]
    for c in disp_cands:
        cat = rnd.choice(["already_paid", "wrong_amount", "wrong_amount", "service_issue"])
        ts = _local_dt(rnd.randint(1, 8), rnd.uniform(10, 17), rnd)
        d = Dispute(case_id=c.id, category=cat, description="Borrower states the overdue amount does not match their records.",
                    status="open", owner_queue="operations" if cat != "service_issue" else "customer-service",
                    raised_by=c.assigned_agent_id, created_at=ts)
        db.add(d)
        c.pre_payment_status, c.status = c.status, "DISPUTED"
        ev(c, "dispute", f"Dispute raised: {cat.replace('_', ' ')}", ts, db.get(User, c.assigned_agent_id))

    for ts, actor, action, entity, eid, payload in sorted(audits, key=lambda a: a[0]):
        audit.record(db, actor, action, entity, eid, payload, actor_label="seed-history" if actor is None else None, ts=ts)

    for c in cases:
        rescore(db, c, quiet=True, route=c.status in ("NEW", "SCORED", "DIGITAL", "TELE", "FIELD"))
        c.updated_at = now
    allocate(db, [br.id for br, _, _ in branches], None)
    audit.record(db, None, "seed.completed", "system", None,
                 {"cases": len(cases), "payments": pay_rows, "note": "Synthetic demo portfolio"}, actor_label="system")
