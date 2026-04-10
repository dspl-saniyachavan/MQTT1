"""
Compact dark-glass date/time widget — matches web app theme
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer, QDateTime


class ModernDateTimeWidget(QWidget):
    """Compact date/time widget styled to match the web app dark theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget#clockRoot {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 14px;
            }
        """)
        self.setObjectName("clockRoot")

        hl = QHBoxLayout(self)
        hl.setContentsMargins(14, 8, 14, 8)
        hl.setSpacing(10)

        # Date column
        date_col = QVBoxLayout()
        date_col.setSpacing(1)
        date_col.setContentsMargins(0, 0, 0, 0)

        self._day_lbl = QLabel()
        self._day_lbl.setStyleSheet(
            "color: #818cf8; font-size: 9px; font-weight: 700; "
            "letter-spacing: 2px; background: transparent;"
        )
        self._day_lbl.setAlignment(Qt.AlignCenter)

        self._date_lbl = QLabel()
        self._date_lbl.setStyleSheet(
            "color: #f1f5f9; font-size: 11px; font-weight: 600; background: transparent;"
        )
        self._date_lbl.setAlignment(Qt.AlignCenter)

        date_col.addWidget(self._day_lbl)
        date_col.addWidget(self._date_lbl)
        hl.addLayout(date_col)

        # Divider
        div = QFrame()
        div.setFixedSize(1, 32)
        div.setStyleSheet("background: rgba(100,116,139,0.5);")
        hl.addWidget(div)

        # Time row
        time_row = QHBoxLayout()
        time_row.setSpacing(3)
        time_row.setContentsMargins(0, 0, 0, 0)

        self._time_lbl = QLabel()
        self._time_lbl.setStyleSheet(
            "color: #f8fafc; font-size: 22px; font-weight: 700; "
            "font-family: 'Segoe UI', monospace; background: transparent;"
        )
        self._time_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        time_row.addWidget(self._time_lbl)

        # Period + seconds stacked
        ps_col = QVBoxLayout()
        ps_col.setSpacing(1)
        ps_col.setContentsMargins(0, 0, 0, 0)

        self._period_lbl = QLabel()
        self._period_lbl.setStyleSheet(
            "color: #818cf8; font-size: 9px; font-weight: 700; "
            "letter-spacing: 1px; background: transparent;"
        )
        self._period_lbl.setAlignment(Qt.AlignLeft)

        self._sec_lbl = QLabel()
        self._sec_lbl.setStyleSheet(
            "color: #94a3b8; font-size: 10px; font-weight: 600; background: transparent;"
        )
        self._sec_lbl.setAlignment(Qt.AlignLeft)

        ps_col.addWidget(self._period_lbl)
        ps_col.addWidget(self._sec_lbl)
        time_row.addLayout(ps_col)

        hl.addLayout(time_row)

    def _tick(self):
        now = QDateTime.currentDateTime()
        h24 = now.time().hour()
        m   = now.time().minute()
        s   = now.time().second()
        period = "AM" if h24 < 12 else "PM"
        h12 = h24 % 12 or 12

        self._day_lbl.setText(now.toString("ddd").upper())
        self._date_lbl.setText(now.toString("dd MMM").upper())
        self._time_lbl.setText(f"{h12:02d}:{m:02d}")
        self._period_lbl.setText(period)
        self._sec_lbl.setText(f"{s:02d}s")

    def closeEvent(self, event):
        self._timer.stop()
        event.accept()
