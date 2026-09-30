import re

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

KEYWORDS = (
    r"\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|JOIN|ON|AS|WITH|OVER|PARTITION BY|"
    r"CASE|WHEN|THEN|ELSE|END|LIMIT|WINDOW|USING|AND|OR|DESC|ASC|"
    r"ROWS UNBOUNDED PRECEDING)\b"
)
FUNCS = r"\b(COUNT|SUM|AVG|ROUND|MIN|MAX|NTILE|RANK|ROW_NUMBER)(?=\()"


class SqlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.kw_fmt = QTextCharFormat()
        self.kw_fmt.setForeground(QColor("#8FB4FF"))
        self.kw_fmt.setFontWeight(QFont.Weight.DemiBold)
        self.fn_fmt = QTextCharFormat()
        self.fn_fmt.setForeground(QColor("#F2C56B"))
        self.cm_fmt = QTextCharFormat()
        self.cm_fmt.setForeground(QColor("#7F92A6"))

    def highlightBlock(self, text: str):
        for m in re.finditer(KEYWORDS, text, re.IGNORECASE):
            self.setFormat(m.start(), m.end() - m.start(), self.kw_fmt)
        for m in re.finditer(FUNCS, text, re.IGNORECASE):
            self.setFormat(m.start(), m.end() - m.start(), self.fn_fmt)
        c = text.find("--")
        if c >= 0:
            self.setFormat(c, len(text) - c, self.cm_fmt)
