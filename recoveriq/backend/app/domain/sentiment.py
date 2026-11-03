"""Borrower-note sentiment and reason category.

Default analyser: a multilingual keyword lexicon (English, Hindi, Marathi in Devanagari, and
romanised Hinglish/Marathi). It always works offline. When ANTHROPIC_API_KEY is configured the
LLM analyser (integrations/llm.py) is tried first and also returns an English translation."""
from __future__ import annotations

import re

CATEGORIES = {
    "job_loss": "Job loss",
    "medical": "Medical emergency",
    "business_loss": "Business loss",
    "family_event": "Family event",
    "dispute": "Disputes the dues",
    "willful_default": "Unwilling to pay",
    "will_pay": "Intends to pay",
    "unreachable": "Could not reach",
    "other": "Other",
}

# category -> keywords (lower-case; Devanagari kept as-is). Order of CATEGORY_ORDER breaks ties.
KEYWORDS: dict[str, list[str]] = {
    "job_loss": [
        "lost job", "lost my job", "laid off", "layoff", "unemployed", "no job", "job gone", "salary stopped",
        "naukri chali", "naukri gayi", "naukri nahi", "job chali", "job gaya", "kaam chhut", "kaam nahi",
        "नौकरी चली", "नौकरी छूट", "नौकरी नहीं", "बेरोजगार", "काम छूट", "छंटनी",
        "नोकरी गेली", "नोकरी सुटली", "नोकरी नाही", "बेरोजगार", "काम गेले",
    ],
    "medical": [
        "hospital", "surgery", "operation", "illness", "sick", "medical", "doctor", "treatment", "accident",
        "bimar", "beemar", "aspatal", "ilaaj", "dawai",
        "अस्पताल", "बीमार", "इलाज", "ऑपरेशन", "दवाई", "दुर्घटना",
        "रुग्णालय", "दवाखाना", "आजारी", "उपचार", "शस्त्रक्रिया", "अपघात",
    ],
    "business_loss": [
        "business loss", "shop closed", "sales down", "no customers", "loss in business", "crop failed", "crop loss",
        "dhanda band", "dhandha band", "dukan band", "business band", "nuksan", "nuksaan", "fasal",
        "धंधा बंद", "दुकान बंद", "नुकसान", "घाटा", "फसल खराब",
        "व्यवसाय बंद", "दुकान बंद", "तोटा", "पीक गेले", "नुकसान",
    ],
    "family_event": [
        "wedding", "marriage", "death in family", "passed away", "funeral", "daughter's wedding", "festival expenses",
        "shaadi", "shadi", "maut", "dehant", "lagna",
        "शादी", "विवाह", "निधन", "मृत्यु", "देहांत",
        "लग्न", "निधन", "मृत्यू",
    ],
    "dispute": [
        "wrong amount", "already paid", "not my loan", "fraud", "excess charges", "never took", "dispute", "incorrect",
        "galat amount", "pehle hi bhar", "pehle hi de", "mera loan nahi", "dhokha",
        "गलत राशि", "गलत रकम", "पहले ही भर", "पहले ही दे", "मेरा लोन नहीं", "धोखा",
        "चुकीची रक्कम", "आधीच भरले", "आधीच भरलं", "माझे कर्ज नाही", "फसवणूक",
    ],
    "willful_default": [
        "won't pay", "will not pay", "refuse", "refused", "not paying", "do what you want", "can't make me",
        "nahi dunga", "nahin dunga", "nahi bharunga", "paisa nahi dunga", "jo karna hai karo", "nahi denar",
        "नहीं दूंगा", "नहीं दूँगा", "नहीं भरूंगा", "जो करना है करो", "पैसा नहीं दूंगा",
        "देणार नाही", "भरणार नाही", "जे करायचं ते करा",
    ],
    "will_pay": [
        "will pay", "i will pay", "pay by", "pay next", "pay on", "pay tomorrow", "pay after salary", "arrange money",
        "promise to pay", "part payment", "paying today", "will clear",
        "bhar dunga", "bhar denge", "de dunga", "de denge", "kar dunga", "payment karunga", "salary aate hi",
        "bharen", "bharto", "deen", "bharun takto",
        "भर दूंगा", "भर दूँगा", "दे दूंगा", "दे दूँगा", "भर देंगे", "दे देंगे", "चुका दूंगा", "सैलरी आते ही",
        "भरेन", "भरतो", "देईन", "भरून टाकतो", "पगार आल्यावर", "भरू",
    ],
    "unreachable": [
        "not reachable", "switched off", "no answer", "door locked", "house locked", "shifted", "not at home",
        "phone band", "ghar band", "mila nahi",
        "फोन बंद", "घर बंद", "नहीं मिले", "नहीं मिला",
        "फोन बंद", "घर बंद", "भेटले नाहीत", "सापडले नाहीत",
    ],
}

CATEGORY_ORDER = ["willful_default", "dispute", "medical", "job_loss", "business_loss", "family_event",
                  "unreachable", "will_pay"]

POSITIVE = ["will pay", "promise", "cooperative", "polite", "agreed", "happy", "arrange", "today", "tomorrow",
            "sure", "definitely", "thank", "pakka", "zaroor", "jarur", "haan", "theek",
            "ज़रूर", "जरूर", "पक्का", "हाँ", "ठीक", "धन्यवाद", "निश्चित", "नक्की", "हो", "बरं"]
NEGATIVE = ["angry", "abuse", "abusive", "threat", "refuse", "won't", "never", "rude", "shouted", "harass",
            "gussa", "gaali", "nahi", "nahin", "pareshan",
            "गुस्सा", "गाली", "नहीं", "परेशान", "कभी नहीं", "राग", "शिवी", "नाही", "त्रास"]

CATEGORY_TONE = {"will_pay": 0.55, "willful_default": -0.85, "dispute": -0.45, "job_loss": -0.35,
                 "medical": -0.3, "business_loss": -0.35, "family_event": -0.15, "unreachable": -0.3}

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MARATHI_HINTS = ["आहे", "नाही", "भरेन", "देईन", "पगार", "आल्यावर", "माझे", "नोकरी", "लग्न", "रुग्णालय", "आजारी",
                 "तोटा", "करायचं", "भरतो", "आधीच", "भेटले"]


def detect_language(text: str, hint: str | None = None) -> str:
    if hint in ("hi", "mr", "en"):
        return hint
    if DEVANAGARI.search(text):
        return "mr" if any(h in text for h in MARATHI_HINTS) else "hi"
    return "en"


def _hits(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w in text)


def analyse(text: str, language_hint: str | None = None) -> dict:
    t = (text or "").lower()
    language = detect_language(text or "", language_hint)
    scores = {cat: _hits(t, kws) for cat, kws in KEYWORDS.items()}
    category = "other"
    best = 0
    for cat in CATEGORY_ORDER:
        if scores[cat] > best:
            best, category = scores[cat], cat
    # "will pay after salary" style notes carry hardship + intent; intent wins when explicit
    if scores["will_pay"] and category in ("job_loss", "medical", "business_loss", "family_event") \
            and scores["will_pay"] >= scores[category]:
        category = "will_pay"

    pos = _hits(t, POSITIVE)
    neg = _hits(t, NEGATIVE)
    score = CATEGORY_TONE.get(category, 0.0) + 0.15 * pos - 0.15 * neg
    if category == "will_pay":
        score = max(score, 0.3)
    if category == "willful_default":
        score = min(score, -0.6)
    score = max(-1.0, min(1.0, round(score, 2)))
    sentiment = "positive" if score >= 0.2 else "negative" if score <= -0.2 else "neutral"
    return {"language": language, "sentiment": sentiment, "score": score, "reason_category": category,
            "english_text": text if language == "en" else gist(text, category), "analyzer": "lexicon"}


# Offline English gist for Hindi / Marathi / Hinglish notes: phrase glossary matched in order of
# appearance. It is a gist, not a full translation, and is shown with a "≈" prefix in the UI.
GLOSSARY: list[tuple[str, str]] = [
    # job & income
    ("नौकरी चली", "lost the job"), ("नौकरी छूट", "lost the job"), ("नोकरी गेली", "lost the job"), ("नोकरी सुटली", "lost the job"),
    ("naukri chali", "lost the job"), ("naukri gayi", "lost the job"), ("बेरोजगार", "unemployed"), ("काम शोधत", "looking for work"),
    ("काम ढूंढ", "looking for work"), ("नया काम", "new work"), ("सैलरी आते ही", "as soon as salary comes"), ("salary aate hi", "as soon as salary comes"),
    ("पगार आल्यावर", "once salary comes"), ("पगार", "salary"), ("सैलरी", "salary"), ("salary", "salary"),
    # health & family
    ("अस्पताल", "hospital"), ("रुग्णालय", "hospital"), ("दवाखाना", "clinic"), ("बीमार", "ill"), ("आजारी", "ill"), ("इलाज", "treatment"),
    ("उपचार", "treatment"), ("ऑपरेशन", "operation"), ("पिताजी", "father"), ("वडील", "father"), ("आई", "mother"), ("माँ", "mother"),
    ("शादी", "wedding"), ("लग्न", "wedding"), ("बेटी", "daughter"), ("मुलीचे", "daughter's"), ("निधन", "death in the family"),
    # business
    ("धंधा बंद", "business shut"), ("dhanda band", "business shut"), ("दुकान बंद", "shop closed"), ("व्यवसाय बंद", "business shut"),
    ("नुकसान", "loss"), ("तोटा", "loss"), ("घाटा", "loss"), ("मंदा", "slow sales"), ("फसल", "crop"), ("पीक", "crop"),
    # disputes & refusals
    ("पहले ही भर", "already paid"), ("आधीच भरले", "already paid"), ("गलत राशि", "wrong amount"), ("चुकीची रक्कम", "wrong amount"),
    ("मेरा लोन नहीं", "not my loan"), ("माझे कर्ज नाही", "not my loan"), ("धोखा", "fraud"), ("फसवणूक", "fraud"),
    ("नहीं दूंगा", "will not pay"), ("नहीं दूँगा", "will not pay"), ("देणार नाही", "will not pay"), ("भरणार नाही", "will not pay"),
    ("nahi dunga", "will not pay"), ("जो करना है करो", "do whatever you want"), ("जे करायचं ते करा", "do whatever you want"),
    # intent to pay
    ("भर दूंगा", "will pay"), ("भर दूँगा", "will pay"), ("दे दूंगा", "will pay"), ("दे दूँगा", "will pay"), ("भर देंगे", "will pay"),
    ("bhar dunga", "will pay"), ("de dunga", "will pay"), ("भरेन", "will pay"), ("भरतो", "will pay"), ("देईन", "will pay"), ("भरू", "will pay"),
    ("किस्त", "instalment"), ("हप्ता", "instalment"), ("पूरी", "full"), ("पूर्ण", "full"), ("कल", "tomorrow"), ("उद्या", "tomorrow"),
    ("अगले महीने", "next month"), ("पुढच्या महिन्यात", "next month"), ("ज़रूर", "surely"), ("जरूर", "surely"), ("पक्का", "for sure"),
    ("नक्की", "definitely"), ("थोड़ा समय", "needs some time"), ("थोडा वेळ", "needs some time"),
    # contactability
    ("घर बंद", "house locked"), ("फोन बंद", "phone switched off"), ("phone band", "phone switched off"), ("नहीं मिले", "not found"),
    ("भेटले नाहीत", "not found"), ("गाँव", "village"), ("गावी", "to the village"),
]

CATEGORY_GIST = {
    "will_pay": "intends to pay", "job_loss": "job loss", "medical": "medical emergency", "business_loss": "business loss",
    "family_event": "family event expenses", "dispute": "disputes the dues", "willful_default": "unwilling to pay",
    "unreachable": "could not be reached", "other": "general update",
}


def gist(text: str, category: str) -> str:
    low = (text or "").lower()
    hits: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for phrase, en in sorted(GLOSSARY, key=lambda p: -len(p[0])):  # longest phrase wins on overlap
        start = low.find(phrase.lower())
        if start < 0:
            continue
        end = start + len(phrase)
        if any(s < end and start < e for s, e in taken):
            continue
        taken.append((start, end))
        hits.append((start, en))
    words: list[str] = []
    for _, en in sorted(hits):
        if en not in words:
            words.append(en)
    amount = re.search(r"₹\s?[\d,]+", text or "")
    if amount:
        words.append(amount.group(0).replace(" ", ""))
    core = "; ".join(words) if words else CATEGORY_GIST.get(category, "general update")
    return f"≈ {core[0].upper()}{core[1:]} ({CATEGORY_GIST.get(category, category)})"
