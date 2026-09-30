
import numpy as np
import pandas as pd

FIRST = ["Aarav", "Maya", "Liam", "Sofia", "Noah", "Zara", "Kabir", "Elena", "Ethan", "Ira",
         "Mateo", "Nina", "Omar", "Leah", "Arjun", "Chloe", "Dev", "Hana", "Jonas", "Priya",
         "Tariq", "Ruth", "Kian", "Meera", "Lucas", "Anika", "Felix", "Sana", "Owen", "Tara"]
LAST = ["Sharma", "Okafor", "Nguyen", "Rossi", "Bakshi", "Petrov", "Silva", "Khan", "Meyer", "Ito",
        "Dhillon", "Costa", "Larsen", "Mehta", "Ali", "Fischer", "Gill", "Novak", "Reyes", "Bose"]

CONTRACTS = ["Month-to-month", "One year", "Two year"]
INTERNET = ["Fiber", "Cable", "DSL"]
PAYMENT = ["Credit card (auto)", "Bank transfer (auto)", "Electronic check", "Mailed check"]


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


def generate(n: int = 300, seed: int = 11, target_rate: float = 0.27) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    contract = rng.choice(CONTRACTS, n, p=[0.55, 0.25, 0.20])
    tenure = np.where(contract == "Month-to-month", rng.integers(1, 37, n),
             np.where(contract == "One year", rng.integers(4, 49, n), rng.integers(12, 73, n)))
    internet = rng.choice(INTERNET, n, p=[0.45, 0.25, 0.30])
    tech = np.where(rng.random(n) < 0.38, "Yes", "No")
    pay = rng.choice(PAYMENT, n, p=[0.28, 0.24, 0.32, 0.16])

    base = pd.Series(internet).map({"Fiber": 74, "Cable": 58, "DSL": 44}).to_numpy()
    monthly = np.clip(base + rng.normal(0, 7, n) + np.where(tech == "Yes", 8, 0), 25, 130).round(2)

    late = np.clip(rng.poisson(np.where(pay == "Electronic check", 1.4, 0.5)), 0, 6)
    tickets = np.clip(rng.poisson(np.where(internet == "Fiber", 1.5, 0.9)), 0, 7)
    login = np.clip(rng.exponential(11, n).round().astype(int), 0, 90)

    z = (0.9 * (contract == "Month-to-month") - 1.1 * (contract == "Two year")
         - 0.04 * tenure + 0.02 * (monthly - 60)
         - 0.9 * (tech == "Yes") + 0.5 * (internet == "Fiber")
         + 0.6 * (pay == "Electronic check")
         + 0.35 * tickets + 0.30 * late + 0.03 * login
         + rng.normal(0, 0.6, n))

    lo, hi = -10.0, 10.0                      # solve intercept so overall churn ~ target_rate
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if _sigmoid(z + mid).mean() > target_rate else (mid, hi)
    churned = (rng.random(n) < _sigmoid(z + mid)).astype(int)

    names, seen = [], set()
    while len(names) < n:
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if nm not in seen:
            seen.add(nm)
            names.append(nm)

    return pd.DataFrame({
        "customer_id": [f"VN-{1001 + i}" for i in range(n)],
        "name": names,
        "tenure_months": tenure,
        "contract": contract,
        "internet_service": internet,
        "tech_support": tech,
        "payment_method": pay,
        "monthly_charges": monthly,
        "total_charges": (tenure * monthly * rng.uniform(0.95, 1.05, n)).round(2),
        "support_tickets_90d": tickets,
        "late_payments_6m": late,
        "days_since_login": login,
        "churned": churned,
    })


if __name__ == "__main__":
    d = generate()
    print(d.head(), "\nchurn rate:", d.churned.mean().round(3))
