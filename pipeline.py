import json
import sqlite3

import db
import model as M
from data_gen import generate


def run():
    df = generate()
    db.DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db.DB_PATH)
    conn.executescript((db.BASE / "sql" / "schema.sql").read_text())
    df.to_sql("customers", conn, if_exists="append", index=False)

    art = M.train(df)
    scored = M.explain(art, df)
    conn.executemany(
        "INSERT INTO predictions VALUES (?,?,?,?,?,?)",
        [(cid, s["prob"], s["band"], json.dumps(s["reasons"]), json.dumps(s["contribs"]), s["action"])
         for cid, s in zip(df["customer_id"], scored)],
    )
    conn.commit()
    conn.close()

    out = df[["customer_id", "name", "churned"]].copy()
    out["churn_prob"] = [round(s["prob"], 4) for s in scored]
    out["top_reasons"] = ["; ".join(f'{r["label"]}: {r["value"]}' for r in s["reasons"]) for s in scored]
    out.to_csv(db.BASE / "data" / "scored_customers.csv", index=False)
    print(f"Loaded {len(df)} customers | churn rate {df.churned.mean():.1%} | "
          f"test ROC-AUC {art['metrics']['roc_auc']:.3f}")


if __name__ == "__main__":
    run()
