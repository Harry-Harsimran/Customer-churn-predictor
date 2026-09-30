
import csv
import json
import sys

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import db
import model as M
from pipeline import run as run_pipeline
from queries import QUERIES
from sql_highlight import SqlHighlighter
from widgets import (
    BAND_COLOR, BLUE, GONE, HIGH, INK, LINE, LOW, MEDIUM_FILL, PANEL, SLATE,
    Card, DriverBar, RiskGauge, RiskMeter, RiskMixBar, SectionHeader, StatBox,
    Swatch, TagLabel, bar_row, band_of, make_stat_strip, rate_bar,
)

APP_QSS = f"""
QMainWindow, QWidget {{ background: #F1F4F7; font-family: "Segoe UI", Arial, sans-serif; font-size: 13px; color: {INK}; }}
QScrollArea {{ border: none; background: transparent; }}
QLabel {{ background: transparent; }}
QPushButton {{ background: {BLUE}; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background: #1F45A0; }}
QPushButton#ghost {{ background: transparent; color: {BLUE}; border: 1px solid {BLUE}; }}
QPushButton#ghost:hover {{ background: #E3EAF8; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: white; border: 1px solid #BCC7D2; border-radius: 6px; padding: 6px 8px; min-height: 18px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QTableWidget {{ background: white; border: 1px solid {LINE}; border-radius: 8px; gridline-color: #E9EEF2; }}
QTableWidget::item {{ padding: 6px; border-bottom: 1px solid #E9EEF2; }}
QHeaderView::section {{ background: #F8FAFB; color: {SLATE}; border: none; border-bottom: 1px solid {LINE};
    padding: 8px 10px; font-weight: 600; font-size: 12px; }}
QListWidget {{ background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 4px; }}
QListWidget::item {{ padding: 10px 12px; border-radius: 6px; margin: 1px; }}
QListWidget::item:selected {{ background: #E3EAF8; color: {BLUE}; }}
QPlainTextEdit {{ background: #0F1B29; color: #DCE6F0; border-radius: 8px; padding: 14px;
    font-family: Consolas, "Courier New", monospace; font-size: 12px; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: #C3CCD5; border-radius: 5px; min-height: 24px; }}
"""

CHOICES = {
    "contract": ["Month-to-month", "One year", "Two year"],
    "internet_service": ["Fiber", "Cable", "DSL"],
    "tech_support": ["No", "Yes"],
    "payment_method": ["Credit card (auto)", "Bank transfer (auto)", "Electronic check", "Mailed check"],
}
DEFAULTS = {
    "tenure_months": 6, "monthly_charges": 79.0, "support_tickets_90d": 3, "late_payments_6m": 1,
    "days_since_login": 20, "contract": "Month-to-month", "internet_service": "Fiber",
    "tech_support": "No", "payment_method": "Electronic check",
}
SORTS = {"Highest risk": "churn_prob DESC", "Shortest tenure": "tenure_months ASC",
         "Biggest bill": "monthly_charges DESC", "Name": "name ASC"}


def h1(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {INK};")
    return lbl


def lede(text):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"font-size: 14px; color: {SLATE};")
    lbl.setMaximumWidth(720)
    return lbl


def scroll(inner: QWidget) -> QScrollArea:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setWidget(inner)
    return sc


def page_root() -> tuple[QScrollArea, QVBoxLayout]:
    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(36, 28, 36, 28)
    lay.setSpacing(18)
    return scroll(inner), lay


class CustomerDialog(QDialog):
    """Detail view for one customer: gauge, profile, and driver breakdown."""

    def __init__(self, cid: str, parent=None):
        super().__init__(parent)
        c = db.one("SELECT * FROM v_customer_risk WHERE customer_id = ?", (cid,))
        self.setWindowTitle(f"{c['name']} — Churn Radar")
        self.resize(1020, 640)
        self.setMinimumWidth(960)
        contribs = json.loads(c["all_contribs"])
        top = max(abs(x["impact"]) for x in contribs) or 1
        peers = db.one("SELECT COUNT(*) AS n, ROUND(100.0*AVG(churned),0) AS rate FROM customers WHERE contract=?",
                       (c["contract"],))

        root = QVBoxLayout(self)
        root.addWidget(h1(c["name"]))
        if c["churned"]:
            root.addWidget(lede("This customer has already left. The scores below show what the "
                                "model saw before they went."))
        else:
            root.addWidget(lede(f"{c['contract']} on {c['internet_service']}, paying "
                                f"${c['monthly_charges']:.2f} a month for {c['tenure_months']} months."))

        cols = QHBoxLayout()
        cols.setSpacing(28)
        root.addLayout(cols, 1)

        left = QVBoxLayout()
        gauge_row = QHBoxLayout()
        gauge_row.addWidget(RiskGauge(c["churn_prob"], c["risk_band"]))
        tag_col = QVBoxLayout()
        tag_col.addWidget(TagLabel(f"{c['risk_band']} risk", c["risk_band"]), alignment=Qt.AlignmentFlag.AlignLeft)
        if not c["churned"]:
            loss = QLabel(f"Expected monthly loss: <b>${c['monthly_charges'] * c['churn_prob']:.0f}</b>")
            loss.setStyleSheet(f"color: {SLATE}; font-size: 12px; margin-top: 4px;")
            tag_col.addWidget(loss)
        tag_col.addStretch(1)
        gauge_row.addLayout(tag_col)
        gauge_row.addStretch(1)
        left.addLayout(gauge_row)

        if not c["churned"]:
            action = QFrame()
            action.setStyleSheet("background: #FFF6DF; border-left: 4px solid #F2B43C; border-radius: 0 6px 6px 0;")
            al = QVBoxLayout(action)
            t = QLabel("Suggested next step")
            t.setStyleSheet("color: #7A5A0B; font-weight: 700; font-size: 12px;")
            p = QLabel(c["action"])
            p.setWordWrap(True)
            al.addWidget(t)
            al.addWidget(p)
            left.addWidget(action)

        facts_lbl = QLabel("Profile")
        facts_lbl.setStyleSheet(f"color: {SLATE}; font-weight: 700; font-size: 12px; margin-top: 6px;")
        left.addWidget(facts_lbl)
        facts = QGridLayout()
        facts.setHorizontalSpacing(14)
        facts.setVerticalSpacing(4)
        rows_ = [("Contract", c["contract"]), ("Internet", c["internet_service"]),
                 ("Tech support", c["tech_support"]), ("Payment", c["payment_method"]),
                 ("Lifetime billed", f"${c['total_charges']:.0f}"),
                 ("Last login", f"{c['days_since_login']} days ago"),
                 ("Late payments (6m)", c["late_payments_6m"]), ("Tickets (90d)", c["support_tickets_90d"])]
        for i, (k, v) in enumerate(rows_):
            kk = QLabel(k); kk.setStyleSheet(f"color: {SLATE};")
            vv = QLabel(str(v)); vv.setStyleSheet("font-weight: 600;")
            facts.addWidget(kk, i, 0)
            facts.addWidget(vv, i, 1)
        left.addLayout(facts)
        peer_lbl = QLabel(f"Customers on {c['contract']} contracts: {int(peers['rate'])}% "
                          f"have left ({peers['n']} total).")
        peer_lbl.setWordWrap(True)
        peer_lbl.setStyleSheet(f"color: {SLATE}; font-size: 12px; margin-top: 6px;")
        left.addWidget(peer_lbl)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(SectionHeader("Why the model says this"))
        why = QLabel("Each bar is how far this customer sits from the average customer on that "
                     "factor, in terms of leaving risk.")
        why.setWordWrap(True)
        why.setStyleSheet(f"font-size: 13px; color: {SLATE};")
        right.addWidget(why)
        for d in sorted(contribs, key=lambda x: -x["impact"]):
            if abs(d["impact"]) < 0.05:
                continue
            right.addWidget(DriverBar(d["label"], d["value"], d["impact"], top))
        legend = QHBoxLayout()
        legend.addWidget(Swatch(LOW, "keeps them"))
        legend.addWidget(Swatch(HIGH, "pushes them out"))
        legend.addStretch(1)
        right.addLayout(legend)
        right.addStretch(1)

        cols.addLayout(left, 5)
        cols.addLayout(right, 6)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)


class Sidebar(QFrame):
    def __init__(self, on_nav, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setStyleSheet(f"background: {INK};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 24, 20, 20)
        lay.setSpacing(4)

        brand = QLabel("\u25CE  Churn Radar")
        brand.setStyleSheet("color: white; font-size: 17px; font-weight: 700;")
        lay.addWidget(brand)
        lay.addSpacing(24)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        names = ["Overview", "Customers", "What-if", "SQL insights", "Model"]
        for i, name in enumerate(names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(self._btn_qss())
            btn.clicked.connect(lambda _, idx=i: on_nav(idx))
            self.group.addButton(btn, i)
            lay.addWidget(btn)
        self.group.button(0).setChecked(True)

        lay.addStretch(1)
        foot = QLabel("Voltnet Broadband\n300 synthetic customers")
        foot.setStyleSheet("color: #8798AA; font-size: 11px;")
        lay.addWidget(foot)

    @staticmethod
    def _btn_qss():
        return (
            "QPushButton { background: transparent; color: #C9D3DE; text-align: left; "
            "padding: 9px 12px; border-radius: 6px; font-weight: 500; border: none; }"
            "QPushButton:hover { background: rgba(255,255,255,0.07); }"
            "QPushButton:checked { background: rgba(255,255,255,0.12); color: white; "
            "border-left: 3px solid #F2B43C; }"
        )

    def set_index(self, idx):
        b = self.group.button(idx)
        if b:
            b.setChecked(True)


class OverviewPage(QScrollArea):
    def __init__(self, on_open_customer, on_goto_customers):
        sc, lay = page_root()
        super().__init__()
        self.setWidgetResizable(True)
        self.setWidget(sc.widget())

        kpi = db.one("""SELECT COUNT(*) AS total, SUM(churned=0) AS active, SUM(churned) AS churned,
                              ROUND(100.0*AVG(churned),1) AS churn_rate FROM customers""")
        risk = db.one("""SELECT SUM(risk_band='High') AS high,
                                ROUND(SUM(CASE WHEN risk_band='High' THEN monthly_charges END),0) AS high_rev,
                                ROUND(SUM(monthly_charges*churn_prob),0) AS rev_risk,
                                ROUND(SUM(monthly_charges),0) AS mrr
                        FROM v_customer_risk WHERE churned=0""")
        by_contract = db.rows("""SELECT contract, ROUND(100.0*AVG(churned),1) AS rate FROM customers
                                 GROUP BY contract ORDER BY rate DESC""")
        by_tenure = db.rows("""SELECT CASE WHEN tenure_months<6 THEN 'Under 6 mo' WHEN tenure_months<12
                                     THEN '6-11 mo' WHEN tenure_months<24 THEN '1-2 yrs' ELSE '2+ yrs' END bucket,
                                     MIN(tenure_months) o, ROUND(100.0*AVG(churned),1) rate
                              FROM customers GROUP BY bucket ORDER BY o""")
        mix = {r["risk_band"]: r["n"] for r in db.rows(
            "SELECT risk_band, COUNT(*) n FROM v_customer_risk WHERE churned=0 GROUP BY risk_band")}
        watch = db.rows("""SELECT customer_id, name, contract, monthly_charges, churn_prob, risk_band, top_reasons
                           FROM v_customer_risk WHERE churned=0 ORDER BY churn_prob DESC LIMIT 8""")
        for w in watch:
            w["reasons"] = json.loads(w["top_reasons"])

        top_name = watch[0]["name"] if watch else "—"
        lay.addWidget(h1(f"{risk['high'] or 0} active customers are likely to leave. Start with {top_name}."))
        lay.addWidget(lede(
            f"Together the high-risk group is worth about ${risk['high_rev'] or 0:,.0f} a month. "
            f"Across all active customers, the model expects to lose ${risk['rev_risk']:,.0f} "
            f"of ${risk['mrr']:,.0f} in monthly revenue."))
        lay.addWidget(make_stat_strip([
            (str(kpi["active"]), "active customers"),
            (str(kpi["churned"]), f"already left ({kpi['churn_rate']}%)"),
            (str(risk["high"] or 0), "high risk now"),
            (f"${risk['rev_risk']:,.0f}", "monthly revenue at risk"),
        ]))

        cols = QHBoxLayout()
        cols.setSpacing(28)
        lay.addLayout(cols, 1)

        left = QVBoxLayout()
        head = SectionHeader("Watchlist", "See all customers →")
        if head.action:
            head.action.linkActivated.connect(lambda _: on_goto_customers())
        left.addWidget(head)
        table = QTableWidget(len(watch), 3)
        table.setHorizontalHeaderLabels(["Customer", "Chance of leaving", "Main reasons"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 170)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for r, w in enumerate(watch):
            who = QTableWidgetItem(f"{w['name']}\n{w['contract']}, ${w['monthly_charges']:.0f}/mo")
            who.setData(Qt.ItemDataRole.UserRole, w["customer_id"])
            table.setItem(r, 0, who)
            cell = QWidget()
            hl = QHBoxLayout(cell)
            hl.setContentsMargins(6, 4, 6, 4)
            hl.addWidget(RiskMeter(w["churn_prob"], w["risk_band"]))
            pl = QLabel(f"{w['churn_prob']*100:.0f}%")
            pl.setStyleSheet("font-weight: 700; margin-left: 6px;")
            hl.addWidget(pl)
            hl.addStretch(1)
            table.setCellWidget(r, 1, cell)
            reasons = "  ·  ".join(f"{x['label']}: {x['value']}" for x in w["reasons"])
            table.setItem(r, 2, QTableWidgetItem(reasons))
            table.setRowHeight(r, 46)
        table.cellDoubleClicked.connect(
            lambda row, _c: on_open_customer(table.item(row, 0).data(Qt.ItemDataRole.UserRole)))
        table.setMinimumHeight(340)
        left.addWidget(table, 1)

        right = QVBoxLayout()
        right.addWidget(SectionHeader("Where churn happens"))
        c3 = QLabel("By contract"); c3.setStyleSheet(f"color:{SLATE}; font-weight:700; font-size:12px; margin-top:8px;")
        right.addWidget(c3)
        for r in by_contract:
            right.addWidget(bar_row(r["contract"], r["rate"], f"{r['rate']}%"))
        t3 = QLabel("By tenure"); t3.setStyleSheet(f"color:{SLATE}; font-weight:700; font-size:12px; margin-top:12px;")
        right.addWidget(t3)
        for r in by_tenure:
            right.addWidget(bar_row(r["bucket"], r["rate"], f"{r['rate']}%"))
        m3 = QLabel("Risk mix of active customers")
        m3.setStyleSheet(f"color:{SLATE}; font-weight:700; font-size:12px; margin-top:12px;")
        right.addWidget(m3)
        right.addWidget(RiskMixBar(mix.get("Low", 0), mix.get("Medium", 0), mix.get("High", 0)))
        legend = QHBoxLayout()
        legend.addWidget(Swatch(LOW, f"Low {mix.get('Low', 0)}"))
        legend.addWidget(Swatch(MEDIUM_FILL, f"Medium {mix.get('Medium', 0)}"))
        legend.addWidget(Swatch(HIGH, f"High {mix.get('High', 0)}"))
        legend.addStretch(1)
        right.addLayout(legend)
        right.addStretch(1)

        cols.addLayout(left, 6)
        cols.addLayout(right, 4)


class CustomersPage(QScrollArea):
    def __init__(self, on_open_customer):
        super().__init__()
        self.setWidgetResizable(True)
        self.on_open_customer = on_open_customer
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(14)
        self.setWidget(inner)

        lay.addWidget(h1("Customers"))
        self.count_lbl = lede("")
        lay.addWidget(self.count_lbl)

        filt = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Name or ID"); self.search.setFixedWidth(160)
        self.status = QComboBox(); self.status.addItems(["Active", "Already left", "All"])
        self.band = QComboBox(); self.band.addItems(["Any", "High", "Medium", "Low"])
        self.contract = QComboBox(); self.contract.addItems(["Any", "Month-to-month", "One year", "Two year"])
        self.sort = QComboBox(); self.sort.addItems(list(SORTS.keys()))
        apply_btn = QPushButton("Apply")
        export_btn = QPushButton("Export CSV"); export_btn.setObjectName("ghost")
        for lbl, w in [("Search", self.search), ("Status", self.status), ("Risk", self.band),
                       ("Contract", self.contract), ("Sort by", self.sort)]:
            col = QVBoxLayout()
            l = QLabel(lbl); l.setStyleSheet(f"color:{SLATE}; font-size:11px; font-weight:700;")
            col.addWidget(l); col.addWidget(w)
            filt.addLayout(col)
        filt.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        filt.addWidget(export_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        filt.addStretch(1)
        lay.addLayout(filt)
        apply_btn.clicked.connect(self.reload)
        export_btn.clicked.connect(self.export_csv)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Customer", "Contract", "Tenure", "Bill", "Chance of leaving", "Main reasons"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hh = self.table.horizontalHeader()
        for i in (1, 2, 3, 4):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(
            lambda row, _c: self.on_open_customer(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)))
        lay.addWidget(self.table, 1)
        self.reload()

    def _filter_sql(self):
        where, params = ["1=1"], []
        s = self.status.currentText()
        if s == "Active":
            where.append("churned=0")
        elif s == "Already left":
            where.append("churned=1")
        if self.band.currentText() != "Any":
            where.append("risk_band=?"); params.append(self.band.currentText())
        if self.contract.currentText() != "Any":
            where.append("contract=?"); params.append(self.contract.currentText())
        q = self.search.text().strip()
        if q:
            where.append("(name LIKE ? OR customer_id LIKE ?)"); params += [f"%{q}%"] * 2
        return " AND ".join(where), params

    def _rows(self):
        where, params = self._filter_sql()
        order = SORTS[self.sort.currentText()]
        rows = db.rows(f"""SELECT customer_id, name, contract, tenure_months, monthly_charges, churned,
                                  churn_prob, risk_band, top_reasons FROM v_customer_risk
                           WHERE {where} ORDER BY {order}""", params)
        for r in rows:
            r["reasons"] = json.loads(r["top_reasons"])
        return rows

    def reload(self):
        rows = self._rows()
        self.count_lbl.setText(f"{len(rows)} shown. Sorted by {self.sort.currentText().lower()}.")
        self.table.setRowCount(len(rows))
        for r, c in enumerate(rows):
            who = QTableWidgetItem(f"{c['name']}\n{c['customer_id']}")
            who.setData(Qt.ItemDataRole.UserRole, c["customer_id"])
            self.table.setItem(r, 0, who)
            self.table.setItem(r, 1, QTableWidgetItem(c["contract"]))
            self.table.setItem(r, 2, QTableWidgetItem(f"{c['tenure_months']} mo"))
            self.table.setItem(r, 3, QTableWidgetItem(f"${c['monthly_charges']:.0f}"))
            if c["churned"]:
                cell = QWidget(); hl = QHBoxLayout(cell); hl.setContentsMargins(6, 4, 6, 4)
                hl.addWidget(TagLabel("Left", "Gone")); hl.addStretch(1)
                self.table.setCellWidget(r, 4, cell)
                self.table.setItem(r, 5, QTableWidgetItem(""))
            else:
                cell = QWidget(); hl = QHBoxLayout(cell); hl.setContentsMargins(6, 4, 6, 4)
                hl.addWidget(RiskMeter(c["churn_prob"], c["risk_band"]))
                pl = QLabel(f"{c['churn_prob']*100:.0f}%"); pl.setStyleSheet("font-weight:700; margin-left:6px;")
                hl.addWidget(pl); hl.addStretch(1)
                self.table.setCellWidget(r, 4, cell)
                reasons = "  ·  ".join(f"{x['label']}: {x['value']}" for x in c["reasons"][:2])
                self.table.setItem(r, 5, QTableWidgetItem(reasons))
            self.table.setRowHeight(r, 46)

    def export_csv(self):
        where, params = self._filter_sql()
        rows = db.rows(f"""SELECT customer_id, name, contract, tenure_months, monthly_charges,
                                  ROUND(churn_prob,3) AS churn_prob, risk_band, action
                           FROM v_customer_risk WHERE {where} ORDER BY churn_prob DESC""", params)
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "churn_watchlist.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["customer_id"])
            w.writeheader(); w.writerows(rows)
        QMessageBox.information(self, "Exported", f"Saved {len(rows)} rows to\n{path}")


class SimulatorPage(QScrollArea):
    def __init__(self, art):
        super().__init__()
        self.art = art
        self.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(18)
        self.setWidget(inner)

        lay.addWidget(h1("What-if simulator"))
        lay.addWidget(lede("Describe a customer, or change one detail, and see how the risk moves."))

        cols = QHBoxLayout()
        cols.setSpacing(28)
        lay.addLayout(cols, 1)

        form_card = Card()
        form_lay = QVBoxLayout(form_card)
        form_lay.setContentsMargins(20, 20, 20, 20)
        form = QFormLayout()
        form.setSpacing(10)
        self.contract = QComboBox(); self.contract.addItems(CHOICES["contract"])
        self.tenure = QSpinBox(); self.tenure.setRange(0, 120)
        self.bill = QDoubleSpinBox(); self.bill.setRange(0, 300); self.bill.setPrefix("$"); self.bill.setDecimals(2)
        self.internet = QComboBox(); self.internet.addItems(CHOICES["internet_service"])
        self.tech = QComboBox(); self.tech.addItems(CHOICES["tech_support"])
        self.payment = QComboBox(); self.payment.addItems(CHOICES["payment_method"])
        self.late = QSpinBox(); self.late.setRange(0, 365)
        self.tickets = QSpinBox(); self.tickets.setRange(0, 365)
        self.login = QSpinBox(); self.login.setRange(0, 365)
        for k, v in DEFAULTS.items():
            getattr(self, {"contract": "contract", "tenure_months": "tenure", "monthly_charges": "bill",
                           "internet_service": "internet", "tech_support": "tech", "payment_method": "payment",
                           "late_payments_6m": "late", "support_tickets_90d": "tickets",
                           "days_since_login": "login"}[k])
        self.contract.setCurrentText(DEFAULTS["contract"]); self.tenure.setValue(DEFAULTS["tenure_months"])
        self.bill.setValue(DEFAULTS["monthly_charges"]); self.internet.setCurrentText(DEFAULTS["internet_service"])
        self.tech.setCurrentText(DEFAULTS["tech_support"]); self.payment.setCurrentText(DEFAULTS["payment_method"])
        self.late.setValue(DEFAULTS["late_payments_6m"]); self.tickets.setValue(DEFAULTS["support_tickets_90d"])
        self.login.setValue(DEFAULTS["days_since_login"])
        form.addRow("Contract", self.contract)
        form.addRow("Tenure (months)", self.tenure)
        form.addRow("Monthly bill", self.bill)
        form.addRow("Internet", self.internet)
        form.addRow("Tech support", self.tech)
        form.addRow("Payment method", self.payment)
        form.addRow("Late payments (6m)", self.late)
        form.addRow("Support tickets (90d)", self.tickets)
        form.addRow("Days since last login", self.login)
        form_lay.addLayout(form)
        score_btn = QPushButton("Score this customer")
        score_btn.clicked.connect(self.score)
        form_lay.addWidget(score_btn)
        cols.addWidget(form_card, 5)

        self.result_box = QVBoxLayout()
        self.result_widget = QWidget()
        self.result_widget.setLayout(self.result_box)
        self.placeholder = QLabel(
            "Nothing scored yet. The form starts with a risky profile: month-to-month, fiber, "
            "three tickets, no tech support. Press Score this customer, then try switching the "
            "contract to Two year.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(f"color:{SLATE}; background:white; border:1px dashed {LINE}; "
                                       "border-radius:8px; padding:20px;")
        self.result_box.addWidget(self.placeholder)
        self.result_box.addStretch(1)
        cols.addWidget(self.result_widget, 5)

    def _clear_result(self):
        while self.result_box.count():
            item = self.result_box.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def score(self):
        vals = {
            "contract": self.contract.currentText(), "tenure_months": self.tenure.value(),
            "monthly_charges": self.bill.value(), "internet_service": self.internet.currentText(),
            "tech_support": self.tech.currentText(), "payment_method": self.payment.currentText(),
            "late_payments_6m": self.late.value(), "support_tickets_90d": self.tickets.value(),
            "days_since_login": self.login.value(),
        }
        r = M.explain(self.art, pd.DataFrame([vals]))[0]
        top = max(abs(x["impact"]) for x in r["contribs"]) or 1
        self._clear_result()
        row = QHBoxLayout()
        row.addWidget(RiskGauge(r["prob"], r["band"]))
        row.addWidget(TagLabel(f"{r['band']} risk", r["band"]), alignment=Qt.AlignmentFlag.AlignTop)
        row.addStretch(1)
        self.result_box.addLayout(row)
        action = QFrame()
        action.setStyleSheet("background:#FFF6DF; border-left:4px solid #F2B43C; border-radius:0 6px 6px 0;")
        al = QVBoxLayout(action)
        t = QLabel("Suggested next step"); t.setStyleSheet("color:#7A5A0B; font-weight:700; font-size:12px;")
        p = QLabel(r["action"]); p.setWordWrap(True)
        al.addWidget(t); al.addWidget(p)
        self.result_box.addWidget(action)
        self.result_box.addWidget(SectionHeader("What is driving it"))
        for d in sorted(r["contribs"], key=lambda x: -x["impact"]):
            if abs(d["impact"]) < 0.05:
                continue
            self.result_box.addWidget(DriverBar(d["label"], d["value"], d["impact"], top))
        self.result_box.addStretch(1)


class InsightsPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(14)
        lay.addWidget(h1("SQL insights"))
        lay.addWidget(lede("Seven queries run live on the SQLite database. The last three read from "
                           "v_customer_risk, the view that joins customers to the model's predictions."))

        cols = QHBoxLayout()
        cols.setSpacing(20)
        lay.addLayout(cols, 1)

        self.list = QListWidget()
        self.list.setFixedWidth(270)
        self.list.setWordWrap(True)
        for q in QUERIES:
            self.list.addItem(QListWidgetItem(q["title"]))
        cols.addWidget(self.list)

        right = QVBoxLayout()
        self.why = lede("")
        right.addWidget(self.why)
        self.sql_view = QPlainTextEdit()
        self.sql_view.setReadOnly(True)
        self.sql_view.setFixedHeight(190)
        self.highlighter = SqlHighlighter(self.sql_view.document())
        right.addWidget(self.sql_view)
        self.result_table = QTableWidget()
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.verticalHeader().setVisible(False)
        right.addWidget(self.result_table, 1)
        cols.addLayout(right, 1)

        self.list.currentRowChanged.connect(self.show_query)
        self.list.setCurrentRow(0)

    def show_query(self, idx):
        if idx < 0:
            return
        q = QUERIES[idx]
        self.why.setText(q["why"])
        self.sql_view.setPlainText(q["sql"])
        data = db.rows(q["sql"])
        cols = list(data[0].keys()) if data else []
        self.result_table.setColumnCount(len(cols))
        self.result_table.setHorizontalHeaderLabels(cols)
        self.result_table.setRowCount(len(data))
        for r, row in enumerate(data):
            for c, key in enumerate(cols):
                self.result_table.setItem(r, c, QTableWidgetItem(str(row[key])))
        self.result_table.resizeColumnsToContents()


class ModelPage(QScrollArea):
    def __init__(self, art):
        super().__init__()
        self.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(18)
        self.setWidget(inner)
        m = art["metrics"]

        lay.addWidget(h1("How good is the model?"))
        lay.addWidget(lede(f"Logistic regression trained on {m['n_train']} customers and tested on "
                           f"{m['n_test']} it had not seen. A customer counts as \"will leave\" at "
                           f"{int(m['threshold']*100)}% or higher."))
        lay.addWidget(make_stat_strip([
            (f"{m['roc_auc']:.2f}", "ROC-AUC on the test set"),
            (f"{m['precision']*100:.0f}%", "of flagged customers really leave"),
            (f"{m['recall']*100:.0f}%", "of leavers get flagged"),
            (f"{m['f1']:.2f}", "F1 score"),
        ]))

        cols = QHBoxLayout()
        cols.setSpacing(28)
        lay.addLayout(cols, 1)

        left = QVBoxLayout()
        left.addWidget(SectionHeader("What drives churn overall"))
        left.addWidget(lede("Average size of each factor's push on a customer's risk, in log-odds."))
        top = max(g["importance"] for g in art["global"])
        for g in art["global"]:
            left.addWidget(bar_row(g["label"], g["importance"] / top * 100, f"{g['importance']:.2f}", label_w=150))
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(SectionHeader("Test-set results"))
        conf = QGridLayout()
        conf.setSpacing(3)
        headers = ["", "Predicted stays", "Predicted leaves"]
        for c, htext in enumerate(headers):
            l = QLabel(htext); l.setStyleSheet(f"color:{SLATE}; font-size:11px; font-weight:700;")
            conf.addWidget(l, 0, c)
        rows_ = [("Actually stayed", m["confusion"]["tn"], m["confusion"]["fp"]),
                 ("Actually left", m["confusion"]["fn"], m["confusion"]["tp"])]
        for r, (label, a, b) in enumerate(rows_, start=1):
            l = QLabel(label); l.setStyleSheet(f"color:{SLATE}; font-size:11px; font-weight:700;")
            conf.addWidget(l, r, 0)
            ok_is_first = (r == 1)
            a_cell = self._conf_cell(a, ok_is_first)
            b_cell = self._conf_cell(b, not ok_is_first)
            conf.addWidget(a_cell, r, 1)
            conf.addWidget(b_cell, r, 2)
        right.addLayout(conf)
        right.addWidget(QLabel(""))
        h3 = QLabel("Logistic regression vs random forest")
        h3.setStyleSheet(f"color:{SLATE}; font-weight:700; font-size:12px; margin-top:14px;")
        right.addWidget(h3)
        right.addWidget(lede("5-fold cross-validated ROC-AUC on all 300 rows."))
        right.addWidget(bar_row("Logistic regression", m["cv_auc_lr"] * 100, f"{m['cv_auc_lr']:.2f}"))
        right.addWidget(bar_row("Random forest", m["cv_auc_rf"] * 100, f"{m['cv_auc_rf']:.2f}"))
        note = QLabel("With only 300 rows the simple model wins or ties, and it can explain every "
                      "score. That is why Churn Radar uses it.")
        note.setWordWrap(True)
        note.setStyleSheet(f"border-left:3px solid {BLUE}; padding-left:12px; color:{SLATE}; margin-top:16px;")
        right.addWidget(note)
        right.addStretch(1)

        cols.addLayout(left, 5)
        cols.addLayout(right, 5)

    @staticmethod
    def _conf_cell(value, ok):
        lbl = QLabel(str(value))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bg, fg = ("#D9EEEA", "#1D6A60") if ok else ("#F8DEDC", "#A5302A")
        lbl.setStyleSheet(f"background:{bg}; color:{fg}; font-size:22px; font-weight:700; "
                          "padding:16px; border-radius:6px;")
        return lbl


class MainWindow(QMainWindow):
    def __init__(self, art):
        super().__init__()
        self.setWindowTitle("Churn Radar — Voltnet Broadband")
        self.resize(1280, 860)
        self.art = art

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = Sidebar(self.goto)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.customers_page = CustomersPage(self.open_customer)
        self.overview_page = OverviewPage(self.open_customer, lambda: self.goto(1))
        self.stack.addWidget(self.overview_page)     # 0
        self.stack.addWidget(self.customers_page)    # 1
        self.stack.addWidget(SimulatorPage(art))      # 2
        self.stack.addWidget(InsightsPage())          # 3
        self.stack.addWidget(ModelPage(art))          # 4

    def goto(self, idx):
        self.stack.setCurrentIndex(idx)
        self.sidebar.set_index(idx)
        if idx == 1:
            self.customers_page.reload()

    def open_customer(self, cid):
        CustomerDialog(cid, self).exec()


def main():
    if not (db.DB_PATH.exists() and M.ARTIFACT_PATH.exists()):
        run_pipeline()
    art = M.load()

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow(art)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
