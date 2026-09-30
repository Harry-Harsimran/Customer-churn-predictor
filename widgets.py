from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget,
)

INK = "#12202F"
SLATE = "#566677"
LINE = "#D8DFE6"
PANEL = "#FFFFFF"
BLUE = "#2A55C0"
LOW = "#2C8C80"
MEDIUM = "#B98515"
MEDIUM_FILL = "#E2A82E"
HIGH = "#D6453D"
GONE = "#6B7A89"

BAND_COLOR = {"Low": LOW, "Medium": MEDIUM_FILL, "High": HIGH}
BAND_TEXT = {"Low": LOW, "Medium": MEDIUM, "High": HIGH}


def band_of(p: float) -> str:
    return "High" if p >= 0.6 else "Medium" if p >= 0.3 else "Low"


class Card(QFrame):
    """A white panel with a rounded border, used to group a section."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet(
            f"#Card {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px; }}"
        )


class SectionHeader(QWidget):
    def __init__(self, title: str, action_text: str | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 8)
        h = QLabel(title)
        h.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {INK};")
        lay.addWidget(h)
        lay.addStretch(1)
        self.action = None
        if action_text:
            self.action = QLabel(f'<a href="#" style="color:{BLUE}; text-decoration:none;">{action_text}</a>')
            self.action.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            lay.addWidget(self.action)


class StatBox(QFrame):
    """One number + caption, used in the KPI strips."""

    def __init__(self, value: str, caption: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Stat")
        self.setStyleSheet(f"#Stat {{ border-left: 1px solid {LINE}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(2)
        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {INK}; border: none;")
        cap = QLabel(caption)
        cap.setStyleSheet(f"font-size: 12px; color: {SLATE}; border: none;")
        lay.addWidget(self.value_lbl)
        lay.addWidget(cap)


def make_stat_strip(items: list[tuple[str, str]]) -> QWidget:
    box = QFrame()
    box.setStyleSheet(f"QFrame {{ border-top: 1px solid {LINE}; border-bottom: 1px solid {LINE}; }}")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    for i, (val, cap) in enumerate(items):
        s = StatBox(val, cap)
        if i == 0:
            s.setStyleSheet("border-left: none;")
        lay.addWidget(s, 1)
    return box


def rate_bar(pct: float, color: str = BLUE) -> QProgressBar:
    """A plain horizontal percentage bar (0-100), no text, colored chunk."""
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(int(max(0.0, min(100.0, pct)) * 10))
    bar.setTextVisible(False)
    bar.setFixedHeight(10)
    bar.setStyleSheet(
        f"QProgressBar {{ background: #E3E9EE; border: none; border-radius: 5px; }}"
        f"QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}"
    )
    return bar


def bar_row(label: str, pct: float, trailing: str, color: str = BLUE, label_w: int = 130) -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 3, 0, 3)
    lay.setSpacing(10)
    lb = QLabel(label)
    lb.setFixedWidth(label_w)
    lb.setWordWrap(True)
    lb.setStyleSheet(f"color: {INK}; font-size: 13px;")
    lay.addWidget(lb)
    lay.addWidget(rate_bar(pct, color), 1)
    tr = QLabel(trailing)
    tr.setFixedWidth(46)
    tr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    tr.setStyleSheet(f"color: {SLATE}; font-size: 12px;")
    lay.addWidget(tr)
    return row


class TagLabel(QLabel):
    """Small colored pill, e.g. risk band or 'Left'."""

    def __init__(self, text: str, band: str, parent=None):
        super().__init__(text, parent)
        color = {"Low": LOW, "Medium": "#B98515", "High": HIGH, "Gone": GONE}.get(band, GONE)
        self.setStyleSheet(
            f"background: {color}; color: white; font-size: 11px; font-weight: 700;"
            f"padding: 2px 10px; border-radius: 9px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(20)


class RiskMeter(QWidget):
    """Compact bar for table cells: filled proportion to churn probability."""

    def __init__(self, prob: float, band: str, parent=None):
        super().__init__(parent)
        self.prob = prob
        self.color = QColor(BAND_COLOR.get(band, GONE))
        self.setFixedSize(90, 10)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 1, self.width(), 8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#E3E9EE"))
        p.drawRoundedRect(track, 4, 4)
        fill_w = max(6.0, self.width() * self.prob)
        p.setBrush(self.color)
        p.drawRoundedRect(QRectF(0, 1, fill_w, 8), 4, 4)


class RiskGauge(QWidget):
    """Half-donut gauge showing a churn probability, mirrors the web version."""

    def __init__(self, prob: float, band: str, parent=None):
        super().__init__(parent)
        self.prob = prob
        self.color = QColor(BAND_COLOR.get(band, GONE))
        self.setFixedSize(220, 132)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(14, 10, w - 28, (w - 28))
        pen_w = 15
        track = QPen(QColor("#DCE3E9"), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(track)
        p.drawArc(rect, 0 * 16, 180 * 16)
        fill = QPen(self.color, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(fill)
        span = int(180 * self.prob)
        p.drawArc(rect, 0 * 16, span * 16)
        p.setPen(QColor(INK))
        f = QFont()
        f.setPointSize(22)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, h - 62, w, 34), Qt.AlignmentFlag.AlignCenter, f"{round(self.prob * 100)}%")
        f2 = QFont()
        f2.setPointSize(9)
        p.setFont(f2)
        p.setPen(QColor(SLATE))
        p.drawText(QRectF(0, h - 28, w, 20), Qt.AlignmentFlag.AlignCenter, "chance of leaving")


class DriverBar(QWidget):
    """One row of a customer's driver breakdown: label, value, bidirectional bar."""

    def __init__(self, label: str, value: str, impact: float, top: float, parent=None):
        super().__init__(parent)
        self.impact, self.top = impact, max(top, 0.001)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(10)
        lb = QLabel(label)
        lb.setFixedWidth(172)
        lb.setWordWrap(True)
        lb.setStyleSheet(f"font-size: 13px; color: {INK}; font-weight: 600;")
        val = QLabel(value)
        val.setFixedWidth(140)
        val.setWordWrap(True)
        val.setStyleSheet(f"font-size: 13px; color: {SLATE};")
        self.bar = _DriverBarPaint(impact, self.top)
        lay.addWidget(lb)
        lay.addWidget(val)
        lay.addWidget(self.bar, 1)


class _DriverBarPaint(QWidget):
    def __init__(self, impact, top, parent=None):
        super().__init__(parent)
        self.impact, self.top = impact, top
        self.setMinimumHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid = w / 2
        p.setPen(QPen(QColor("#B4C0CC"), 2))
        p.drawLine(int(mid), 1, int(mid), h - 1)
        frac = min(abs(self.impact) / self.top, 1.0) * (w / 2 - 6)
        color = QColor(HIGH) if self.impact > 0 else QColor(LOW)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        if self.impact > 0:
            p.drawRoundedRect(QRectF(mid, 2, frac, h - 4), 3, 3)
        else:
            p.drawRoundedRect(QRectF(mid - frac, 2, frac, h - 4), 3, 3)


class RiskMixBar(QWidget):
    """3-segment stacked bar: Low / Medium / High counts among active customers."""

    def __init__(self, low: int, medium: int, high: int, parent=None):
        super().__init__(parent)
        self.counts = [low, medium, high]
        self.colors = [QColor(LOW), QColor(MEDIUM_FILL), QColor(HIGH)]
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        total = max(sum(self.counts), 1)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 7, 7)
        p.setClipPath(path)
        x = 0.0
        for count, color in zip(self.counts, self.colors):
            seg_w = w * count / total
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRect(QRectF(x, 0, seg_w + 1, h))
            x += seg_w


class Swatch(QWidget):
    """Small colored square + label, for legends."""

    def __init__(self, color: str, text: str, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        sq = QLabel()
        sq.setFixedSize(10, 10)
        sq.setStyleSheet(f"background: {color}; border-radius: 2px;")
        lay.addWidget(sq)
        t = QLabel(text)
        t.setStyleSheet(f"color: {SLATE}; font-size: 12px;")
        lay.addWidget(t)
