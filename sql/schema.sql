DROP VIEW  IF EXISTS v_customer_risk;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    tenure_months       INTEGER NOT NULL,
    contract            TEXT NOT NULL,
    internet_service    TEXT NOT NULL,
    tech_support        TEXT NOT NULL,
    payment_method      TEXT NOT NULL,
    monthly_charges     REAL NOT NULL,
    total_charges       REAL NOT NULL,
    support_tickets_90d INTEGER NOT NULL,
    late_payments_6m    INTEGER NOT NULL,
    days_since_login    INTEGER NOT NULL,
    churned             INTEGER NOT NULL CHECK (churned IN (0, 1))
);

CREATE TABLE predictions (
    customer_id  TEXT PRIMARY KEY REFERENCES customers(customer_id),
    churn_prob   REAL NOT NULL,
    risk_band    TEXT NOT NULL,
    top_reasons  TEXT NOT NULL,   -- JSON: top 3 drivers pushing risk up
    all_contribs TEXT NOT NULL,   -- JSON: every driver, signed impact
    action       TEXT NOT NULL
);

CREATE INDEX idx_pred_prob ON predictions(churn_prob DESC);

CREATE VIEW v_customer_risk AS
SELECT c.*, p.churn_prob, p.risk_band, p.top_reasons, p.all_contribs, p.action
FROM customers c
JOIN predictions p USING (customer_id);
