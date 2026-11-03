"""Layer 2: probability that an account self-cures within 30 days.

Logistic regression on standardised features. For a linear model the SHAP value of feature i
is exactly coef_i * (x_i - mean_i) (interventional SHAP with independent features), so the
reasons shown are exact attributions, not an approximation.

Training data for the prototype is SYNTHETIC (generated below from documented assumptions)
plus any real outcomes already in the database. It is labelled as such everywhere in the UI.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

LOAN_TYPES = ["personal", "two_wheeler", "gold", "msme", "consumer_durable"]
FEATURES = ["dpd_months", "missed_emis", "log_outstanding", "burden_ratio", "broken_ptps",
            "unreachable", "sentiment", "paid_recently"] + [f"lt_{t}" for t in LOAN_TYPES[1:]]

LABELS = {
    "dpd_months": "Days past due",
    "missed_emis": "Missed EMIs",
    "log_outstanding": "Outstanding size",
    "burden_ratio": "Overdue vs EMI burden",
    "broken_ptps": "Broken promises",
    "unreachable": "Unreachable streak",
    "sentiment": "Borrower sentiment",
    "paid_recently": "Recent part-payment",
    "lt_two_wheeler": "Loan type: two-wheeler",
    "lt_gold": "Loan type: gold",
    "lt_msme": "Loan type: MSME",
    "lt_consumer_durable": "Loan type: consumer durable",
}

SENT_VALUE = {"positive": 0.7, "neutral": 0.0, "negative": -0.7, None: 0.0}


def featurise(dpd, missed, outstanding, amount_due, emi, broken, unreachable, sentiment, paid_recently, loan_type):
    row = [
        dpd / 30.0,
        float(missed),
        math.log10(max(outstanding, 1000)),
        min((amount_due or 0) / max(emi or 1, 1), 12) / 3.0,
        float(broken),
        1.0 if unreachable >= 3 else 0.0,
        sentiment,
        1.0 if paid_recently else 0.0,
    ]
    row += [1.0 if loan_type == t else 0.0 for t in LOAN_TYPES[1:]]
    return row


def case_features(case, paid_recently: bool) -> list[float]:
    return featurise(case.dpd or 0, case.missed_emis or 0, case.outstanding or 0, case.amount_due or 0,
                     case.emi_amount or 1, case.broken_ptp_count or 0, case.unreachable_streak or 0,
                     SENT_VALUE.get(case.last_sentiment, 0.0), paid_recently, case.loan_type)


def synthetic_dataset(n: int = 6000, seed: int = 7):
    """Documented generating assumptions: self-cure falls with DPD, missed EMIs, size, broken
    promises and unreachability; rises with positive sentiment, recent part-payments and
    secured (gold) loans. Noise keeps the relationship imperfect."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        dpd = int(rng.choice([rng.integers(1, 31), rng.integers(31, 61), rng.integers(61, 91), rng.integers(91, 181)],
                             p=[0.45, 0.25, 0.18, 0.12]))
        missed = max(0, min(8, int(round(dpd / 30 + rng.normal(0, 0.6)))))
        lt = rng.choice(LOAN_TYPES, p=[0.35, 0.25, 0.15, 0.1, 0.15])
        outstanding = float(np.exp(rng.normal(11.6, 0.8)))
        emi = max(1500.0, outstanding / rng.uniform(12, 48))
        amount_due = emi * max(missed, 1)
        broken = int(rng.poisson(0.25 + dpd / 120))
        unreach = int(rng.poisson(0.6 + dpd / 70))
        sent = float(rng.choice([0.7, 0.0, -0.7], p=[0.35, 0.4, 0.25]))
        paid = bool(rng.random() < max(0.05, 0.45 - dpd / 300))
        x = featurise(dpd, missed, outstanding, amount_due, emi, broken, unreach, sent, paid, lt)
        logit = (1.6 - 0.85 * x[0] - 0.25 * x[1] - 0.55 * (x[2] - 5) - 0.3 * x[3] - 0.55 * x[4]
                 - 1.0 * x[5] + 1.2 * x[6] + 0.9 * x[7]
                 + {"gold": 0.6, "msme": -0.35, "two_wheeler": 0.1, "consumer_durable": 0.2}.get(lt, 0.0)
                 + rng.normal(0, 0.6))
        X.append(x)
        y.append(int(rng.random() < 1 / (1 + math.exp(-logit))))
    return np.array(X), np.array(y)


def train(extra_X: list[list[float]] | None = None, extra_y: list[int] | None = None, seed: int = 7) -> dict:
    X, y = synthetic_dataset(seed=seed)
    weights = np.ones(len(y))
    real_rows = 0
    if extra_X:
        real_rows = len(extra_X)
        X = np.vstack([X, np.array(extra_X)])
        y = np.concatenate([y, np.array(extra_y)])
        weights = np.concatenate([weights, np.full(real_rows, 3.0)])  # real outcomes count more

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    cut = int(len(y) * 0.8)
    tr, te = idx[:cut], idx[cut:]
    mean = X[tr].mean(axis=0)
    scale = X[tr].std(axis=0)
    scale[scale == 0] = 1.0
    Z = (X - mean) / scale
    clf = LogisticRegression(max_iter=500, C=1.0)
    clf.fit(Z[tr], y[tr], sample_weight=weights[tr])
    p = clf.predict_proba(Z[te])[:, 1]
    auc = float(roc_auc_score(y[te], p))
    k = max(1, int(len(te) * 0.2))
    top = np.argsort(-p)[:k]
    prec_at_k = float(y[te][top].mean())
    return {
        "params": {"features": FEATURES, "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
                   "mean": mean.tolist(), "scale": scale.tolist()},
        "metrics": {"auc": round(auc, 4), "precision_at_20pct": round(prec_at_k, 4),
                    "base_rate": round(float(y.mean()), 4), "holdout_rows": int(len(te))},
        "training_rows": int(len(y)),
        "real_outcome_rows": real_rows,
    }


def predict(params: dict, x: list[float]) -> tuple[float, list[dict]]:
    coef = np.array(params["coef"])
    mean = np.array(params["mean"])
    scale = np.array(params["scale"])
    z = (np.array(x) - mean) / scale
    contrib = coef * z
    logit = params["intercept"] + contrib.sum()
    p = 1 / (1 + math.exp(-logit))
    order = np.argsort(-np.abs(contrib))
    reasons = []
    for i in order[:3]:
        c = float(contrib[i])
        if abs(c) < 0.02:
            continue
        name = params["features"][i]
        reasons.append({
            "feature": name,
            "label": LABELS.get(name, name),
            "impact": round(c, 3),
            "direction": "raises" if c > 0 else "lowers",
        })
    return round(p, 4), reasons
