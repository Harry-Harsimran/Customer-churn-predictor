
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ARTIFACT_PATH = Path(__file__).parent / "models" / "churn_model.joblib"
THRESHOLD = 0.40

NUM = ["tenure_months", "monthly_charges", "support_tickets_90d", "late_payments_6m", "days_since_login"]
CAT = ["contract", "internet_service", "tech_support", "payment_method"]
FEATURES = NUM + CAT

LABELS = {
    "tenure_months": "Tenure", "monthly_charges": "Monthly bill",
    "support_tickets_90d": "Support tickets (90d)", "late_payments_6m": "Late payments (6m)",
    "days_since_login": "Last login", "contract": "Contract", "internet_service": "Internet",
    "tech_support": "Tech support", "payment_method": "Payment method",
}

ACTIONS = {
    "contract": "Offer a 12-month plan with a loyalty discount.",
    "tenure_months": "Book a check-in call and add a new-customer perk.",
    "monthly_charges": "Review the plan and offer a right-sized cheaper tier.",
    "support_tickets_90d": "Escalate to a senior agent for a proactive callback.",
    "late_payments_6m": "Move them to autopay and waive the next late fee.",
    "days_since_login": "Send a re-engagement nudge with a usage tip.",
    "internet_service": "Run a line-quality check and offer a free speed test visit.",
    "tech_support": "Add a free 3-month tech support trial.",
    "payment_method": "Invite them to switch to auto-debit with a bill credit.",
}


def band(p: float) -> str:
    return "High" if p >= 0.6 else "Medium" if p >= 0.3 else "Low"


def fmt(feature, v):
    if feature == "tenure_months":
        return f"{int(v)} mo"
    if feature == "monthly_charges":
        return f"${float(v):.2f}"
    if feature == "days_since_login":
        return "today" if int(v) == 0 else f"{int(v)} days ago"
    if feature in NUM:
        return str(int(v))
    return str(v)


def _pre():
    return ColumnTransformer([
        ("num", StandardScaler(), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT),
    ])


def _lr():
    return Pipeline([("pre", _pre()), ("clf", LogisticRegression(max_iter=2000, C=0.5))])


def _rf():
    return Pipeline([("pre", _pre()),
                     ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=4, random_state=42))])


def _group_of(name: str) -> str:
    kind, rest = name.split("__", 1)
    if kind == "num":
        return rest
    return next(c for c in CAT if rest.startswith(c + "_"))


def train(df: pd.DataFrame) -> dict:
    X, y = df[FEATURES], df["churned"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    lr = _lr().fit(Xtr, ytr)
    prob = lr.predict_proba(Xte)[:, 1]
    pred = (prob >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()

    cv = StratifiedKFold(5, shuffle=True, random_state=42)
    metrics = {
        "threshold": THRESHOLD, "n_train": len(Xtr), "n_test": len(Xte),
        "roc_auc": float(roc_auc_score(yte, prob)),
        "precision": float(precision_score(yte, pred, zero_division=0)),
        "recall": float(recall_score(yte, pred)),
        "f1": float(f1_score(yte, pred)),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "cv_auc_lr": float(cross_val_score(_lr(), X, y, cv=cv, scoring="roc_auc").mean()),
        "cv_auc_rf": float(cross_val_score(_rf(), X, y, cv=cv, scoring="roc_auc").mean()),
    }

    final = _lr().fit(X, y)                       # refit on everything for scoring
    pre = final.named_steps["pre"]
    Xt = pre.transform(X)
    art = {
        "pipe": final,
        "mu": Xt.mean(axis=0),
        "groups": [_group_of(n) for n in pre.get_feature_names_out()],
        "metrics": metrics,
    }
    art["global"] = _global_importance(art, df)
    ARTIFACT_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(art, ARTIFACT_PATH)
    return art


def load() -> dict:
    return joblib.load(ARTIFACT_PATH)


def _grouped_contribs(art, df):
    pipe = art["pipe"]
    Xt = pipe.named_steps["pre"].transform(df[FEATURES])
    raw = (Xt - art["mu"]) * pipe.named_steps["clf"].coef_[0]
    grouped = np.zeros((len(df), len(FEATURES)))
    for j, g in enumerate(art["groups"]):
        grouped[:, FEATURES.index(g)] += raw[:, j]
    return grouped


def _global_importance(art, df):
    g = np.abs(_grouped_contribs(art, df)).mean(axis=0)
    items = [{"label": LABELS[f], "importance": float(v)} for f, v in zip(FEATURES, g)]
    return sorted(items, key=lambda d: -d["importance"])


def explain(art, df: pd.DataFrame) -> list[dict]:
    """Per row: churn probability, all drivers (signed), top reasons, suggested action."""
    prob = art["pipe"].predict_proba(df[FEATURES])[:, 1]
    grouped = _grouped_contribs(art, df)
    out = []
    for i, (_, row) in enumerate(df[FEATURES].iterrows()):
        items = [{"feature": f, "label": LABELS[f], "value": fmt(f, row[f]),
                  "impact": round(float(grouped[i, k]), 3)} for k, f in enumerate(FEATURES)]
        items.sort(key=lambda d: -d["impact"])
        reasons = [c for c in items if c["impact"] > 0.15][:3]
        action = ACTIONS[reasons[0]["feature"]] if reasons else "No action needed. Keep the relationship warm."
        out.append({"prob": float(prob[i]), "band": band(float(prob[i])),
                    "contribs": items, "reasons": reasons, "action": action})
    return out
