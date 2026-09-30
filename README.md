'''
A PyQt6 desktop app for Voltnet Broadband, a fictional ISP: which customers
will leave, and why. No browser, no server — a normal double-clickable
Python app. Same SQLite + logistic-regression backend as the web version,
300 synthetic customers generated in `data_gen.py`.
'''
## Run
    pip install -r requirements.txt
    python gui.py          # first run builds the database + model automatically

Rebuild the data and model from scratch at any point: `python pipeline.py`

## Layout
    data_gen.py       300-row synthetic customers (hidden churn rules + noise, seeded)
    sql/schema.sql    tables, index, v_customer_risk view
    pipeline.py       generate -> SQLite -> train -> score -> write predictions back to SQL
    model.py          logistic regression + random forest check, per-customer "why"
    queries.py        the 7 SQL queries shown on the SQL insights page
    db.py             tiny SQLite helper (rows / one)
    widgets.py         custom Qt widgets: gauge, driver bars, risk meter, stat boxes
    sql_highlight.py  SQL syntax highlighter for the insights viewer
    gui.py            the PyQt6 application (sidebar nav + 5 pages)

## Pages
    Overview      watchlist of the riskiest active customers + churn breakdowns
    Customers     filter/sort/search the full customer list, export to CSV
    (double-click any customer row to open their detail view)
    What-if       score a hypothetical customer and see what drives the number
    SQL insights  the 7 queries, live, with syntax-highlighted SQL and results
    Model         ROC-AUC/precision/recall, confusion matrix, LR vs RF comparison

