
QUERIES = [
    {
        "title": "Churn rate by contract type",
        "why": "Plain GROUP BY. Month-to-month customers are the ones who leave.",
        "sql": """SELECT contract,
       COUNT(*)                          AS customers,
       SUM(churned)                      AS churned,
       ROUND(100.0 * AVG(churned), 1)    AS churn_pct
FROM customers
GROUP BY contract
ORDER BY churn_pct DESC;""",
    },
    {
        "title": "Churn by tenure bucket",
        "why": "CASE turns a raw number into buckets you can compare.",
        "sql": """SELECT CASE
         WHEN tenure_months < 6  THEN '1. under 6 mo'
         WHEN tenure_months < 12 THEN '2. 6-11 mo'
         WHEN tenure_months < 24 THEN '3. 1-2 yrs'
         ELSE                         '4. 2+ yrs'
       END                               AS tenure_bucket,
       COUNT(*)                          AS customers,
       ROUND(100.0 * AVG(churned), 1)    AS churn_pct
FROM customers
GROUP BY tenure_bucket
ORDER BY tenure_bucket;""",
    },
    {
        "title": "Churn by price quartile",
        "why": "NTILE(4) is a window function. It ranks customers into equal-sized price bands without hand-picked cutoffs.",
        "sql": """WITH priced AS (
    SELECT churned, monthly_charges,
           NTILE(4) OVER (ORDER BY monthly_charges) AS price_quartile
    FROM customers
)
SELECT price_quartile,
       MIN(monthly_charges)              AS from_price,
       MAX(monthly_charges)              AS to_price,
       ROUND(100.0 * AVG(churned), 1)    AS churn_pct
FROM priced
GROUP BY price_quartile;""",
    },
    {
        "title": "Support pain and churn",
        "why": "Do repeat tickets predict leaving? Grouped by ticket count, capped at 3+.",
        "sql": """SELECT MIN(support_tickets_90d, 3)  AS tickets_90d_capped,
       COUNT(*)                          AS customers,
       ROUND(100.0 * AVG(churned), 1)    AS churn_pct
FROM customers
GROUP BY MIN(support_tickets_90d, 3)
ORDER BY 1;""",
    },
    {
        "title": "Revenue at risk by contract",
        "why": "Expected monthly loss = bill x churn probability, for customers still active. Joins the model output back to SQL.",
        "sql": """SELECT contract,
       COUNT(*)                                         AS active_customers,
       ROUND(SUM(monthly_charges), 0)                   AS monthly_revenue,
       ROUND(SUM(monthly_charges * churn_prob), 0)      AS expected_loss,
       ROUND(100.0 * SUM(monthly_charges * churn_prob)
             / SUM(monthly_charges), 1)                 AS loss_pct
FROM v_customer_risk
WHERE churned = 0
GROUP BY contract
ORDER BY expected_loss DESC;""",
    },
    {
        "title": "Riskiest customers inside each contract",
        "why": "RANK() OVER (PARTITION BY ...) gives a top-3 per group in one query.",
        "sql": """SELECT contract, customer_id, name,
       ROUND(churn_prob, 2) AS churn_prob, risk_rank
FROM (
    SELECT *,
           RANK() OVER (PARTITION BY contract
                        ORDER BY churn_prob DESC) AS risk_rank
    FROM v_customer_risk
    WHERE churned = 0
)
WHERE risk_rank <= 3
ORDER BY contract, risk_rank;""",
    },
    {
        "title": "How much revenue does a save-list protect?",
        "why": "Running total over the riskiest customers. Shows where a retention team should stop calling.",
        "sql": """SELECT ROW_NUMBER() OVER w                    AS nth_customer,
       name,
       ROUND(churn_prob, 2)                     AS churn_prob,
       ROUND(SUM(monthly_charges * churn_prob)
             OVER (w ROWS UNBOUNDED PRECEDING), 0) AS cumulative_expected_loss
FROM v_customer_risk
WHERE churned = 0
WINDOW w AS (ORDER BY churn_prob DESC)
LIMIT 10;""",
    },
]
