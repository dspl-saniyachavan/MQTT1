"""
History Page — multi-parameter table with time range filter, stats, chart, pagination
"""

import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSizePolicy, QGridLayout, QDateTimeEdit,
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QColor, QPainter, QPen, QFont

_COLORS = [
    "#6439ff", "#54d7ff", "#f472b6", "#a78bfa",
    "#fb923c", "#34d399", "#ef4444", "#8b5cf6",
]

PRESETS = {
    "Last 15 min":  15,
    "Last 30 min":  30,
    "Last 1 hour":  60,
    "Last 6 hours": 360,
    "Last 24 hours": 1440,
    "Last 7 days":  10080,
    "Last 30 days": 43200,
}

PAGE_SIZES = [10, 25, 50, 100]


# ── Combined multi-parameter line chart ───────────────────────────────────────
class MultiLineChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series: dict = {}
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_series(self, series: dict):
        self.series = series
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor("#1e293b"))

        active = {pid: s for pid, s in self.series.items() if len(s["points"]) >= 2}
        if not active:
            painter.setPen(QColor("#64748b"))
            f = QFont(); f.setPointSize(11); painter.setFont(f)
            painter.drawText(w // 2 - 80, h // 2, "No data to display")
            return

        pl, pr, pt, pb = 60, 20, 30, 50
        cw, ch = w - pl - pr, h - pt - pb

        all_vals = [v for s in active.values() for _, v in s["points"]]
        all_ts   = [t for s in active.values() for t, _ in s["points"]]
        lo, hi   = min(all_vals), max(all_vals)
        t0, t1   = min(all_ts),   max(all_ts)
        vrange   = (hi - lo) or 1
        trange   = (t1 - t0) or 1

        def tx(t): return pl + (t - t0) / trange * cw
        def ty(v): return pt + ch - (v - lo) / vrange * ch

        painter.setPen(QPen(QColor("#334155"), 1))
        for i in range(5):
            y = pt + ch * i / 4
            painter.drawLine(pl, int(y), w - pr, int(y))
            val = hi - vrange * i / 4
            painter.setPen(QColor("#64748b"))
            f = QFont(); f.setPointSize(8); painter.setFont(f)
            painter.drawText(2, int(y) + 4, f"{val:.1f}")
            painter.setPen(QPen(QColor("#334155"), 1))

        for sid, s in active.items():
            pts = s["points"]
            color = QColor(s["color"])
            painter.setPen(QPen(color, 2))
            for i in range(len(pts) - 1):
                x1, y1 = tx(pts[i][0]),   ty(pts[i][1])
                x2, y2 = tx(pts[i+1][0]), ty(pts[i+1][1])
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            lx, ly = tx(pts[-1][0]), ty(pts[-1][1])
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(lx) - 4, int(ly) - 4, 8, 8)

        lx = pl
        f = QFont(); f.setPointSize(9); painter.setFont(f)
        for sid, s in active.items():
            painter.setBrush(QColor(s["color"]))
            painter.setPen(Qt.NoPen)
            painter.drawRect(lx, h - pb + 14, 12, 12)
            painter.setPen(QColor("#cbd5e1"))
            painter.drawText(lx + 16, h - pb + 25, f"{s['name']} ({s['unit']})")
            lx += 150


# ── History Page ──────────────────────────────────────────────────────────────
class HistoryPage(QWidget):
    def __init__(self, db, auth_service, back_signal=None):
        super().__init__()
        self.db = db
        self.auth_service = auth_service
        self._back_signal = back_signal
        self._param_colors: dict = {}
        self._current_page = 1
        self._items_per_page = 10
        self._all_rows: list = []   # list of (timestamp, {pid: value})
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        hdr = QFrame()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet("QFrame{background:#1e293b;border-bottom:1px solid #334155;}")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)

        title = QLabel("Parameter History")
        f = QFont(); f.setPointSize(15); f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color:white;background:transparent;")
        hl.addWidget(title)
        hl.addStretch()

        # Preset selector
        hl.addWidget(QLabel("Range:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(PRESETS.keys()))
        self._preset_combo.setCurrentText("Last 24 hours")
        self._preset_combo.setStyleSheet(
            "QComboBox{background:#334155;color:white;border:1px solid #475569;"
            "border-radius:4px;padding:4px 10px;min-width:120px;}"
            "QComboBox QAbstractItemView{background:#1e293b;color:white;}"
        )
        self._preset_combo.currentIndexChanged.connect(self._load)
        hl.addWidget(self._preset_combo)

        # Rows per page
        hl.addWidget(QLabel("  Rows:"))
        self._page_size_combo = QComboBox()
        self._page_size_combo.addItems([str(s) for s in PAGE_SIZES])
        self._page_size_combo.setCurrentText("10")
        self._page_size_combo.setStyleSheet(
            "QComboBox{background:#334155;color:white;border:1px solid #475569;"
            "border-radius:4px;padding:4px 8px;min-width:60px;}"
            "QComboBox QAbstractItemView{background:#1e293b;color:white;}"
        )
        self._page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        hl.addWidget(self._page_size_combo)

        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setStyleSheet(
            "QPushButton{background:#3b82f6;color:white;border:none;border-radius:6px;"
            "padding:8px 16px;font-weight:600;}"
            "QPushButton:hover{background:#2563eb;}"
        )
        refresh_btn.clicked.connect(self._load)
        hl.addWidget(refresh_btn)

        root.addWidget(hdr)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{background:#0f172a;border:none;}"
            "QScrollBar:vertical{background:#1e293b;width:8px;}"
            "QScrollBar::handle:vertical{background:#475569;border-radius:4px;}"
        )
        content = QWidget()
        content.setStyleSheet("background:#0f172a;")
        self._cl = QVBoxLayout(content)
        self._cl.setContentsMargins(24, 24, 24, 24)
        self._cl.setSpacing(24)

        # Stats section
        stats_lbl = QLabel("PARAMETER STATISTICS")
        stats_lbl.setStyleSheet(
            "color:#64748b;font-size:11px;font-weight:700;"
            "letter-spacing:2px;background:transparent;"
        )
        self._cl.addWidget(stats_lbl)

        self._stats_frame = QFrame()
        self._stats_frame.setStyleSheet(
            "QFrame{background:#1e293b;border-radius:12px;border:1px solid #334155;}"
        )
        self._stats_grid = QGridLayout(self._stats_frame)
        self._stats_grid.setContentsMargins(16, 16, 16, 16)
        self._stats_grid.setHorizontalSpacing(16)
        self._stats_grid.setVerticalSpacing(16)
        self._cl.addWidget(self._stats_frame)

        # Chart section
        chart_lbl = QLabel("MULTI-PARAMETER TREND")
        chart_lbl.setStyleSheet(
            "color:#64748b;font-size:11px;font-weight:700;"
            "letter-spacing:2px;background:transparent;"
        )
        self._cl.addWidget(chart_lbl)

        self._chart = MultiLineChart()
        self._chart.setStyleSheet("border-radius:12px;")
        self._cl.addWidget(self._chart)

        # Table section
        tbl_lbl = QLabel("HISTORY TABLE")
        tbl_lbl.setStyleSheet(
            "color:#64748b;font-size:11px;font-weight:700;"
            "letter-spacing:2px;background:transparent;"
        )
        self._cl.addWidget(tbl_lbl)

        self._table = QTableWidget()
        self._table.setStyleSheet("""
            QTableWidget{
                background:#1e293b;color:#e2e8f0;
                border:1px solid #334155;border-radius:8px;
                gridline-color:#334155;font-size:13px;
            }
            QHeaderView::section{
                background:#0f172a;color:#94a3b8;border:none;
                padding:10px 8px;font-weight:700;font-size:12px;
            }
            QTableWidget::item{padding:8px;}
            QTableWidget::item:selected{background:#3b82f6;color:white;}
            QTableWidget::item:alternate{background:#162032;}
        """)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(300)
        self._cl.addWidget(self._table)

        # Pagination controls
        self._pagination_frame = QFrame()
        self._pagination_frame.setStyleSheet("QFrame{background:transparent;}")
        pg_layout = QHBoxLayout(self._pagination_frame)
        pg_layout.setContentsMargins(0, 0, 0, 0)

        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.setStyleSheet(
            "QPushButton{background:#334155;color:white;border:none;border-radius:6px;"
            "padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#475569;}"
            "QPushButton:disabled{background:#1e293b;color:#475569;}"
        )
        self._prev_btn.clicked.connect(self._prev_page)

        self._page_label = QLabel("Page 1 / 1")
        self._page_label.setStyleSheet("color:#94a3b8;font-size:12px;background:transparent;")
        self._page_label.setAlignment(Qt.AlignCenter)

        self._next_btn = QPushButton("Next →")
        self._next_btn.setStyleSheet(
            "QPushButton{background:#334155;color:white;border:none;border-radius:6px;"
            "padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#475569;}"
            "QPushButton:disabled{background:#1e293b;color:#475569;}"
        )
        self._next_btn.clicked.connect(self._next_page)

        self._row_count_label = QLabel("")
        self._row_count_label.setStyleSheet("color:#64748b;font-size:11px;background:transparent;")

        pg_layout.addWidget(self._prev_btn)
        pg_layout.addWidget(self._page_label)
        pg_layout.addWidget(self._next_btn)
        pg_layout.addStretch()
        pg_layout.addWidget(self._row_count_label)
        self._cl.addWidget(self._pagination_frame)

        scroll.setWidget(content)
        root.addWidget(scroll)

    # ── Load ──────────────────────────────────────────────────────────────────
    def _load(self):
        preset_name = self._preset_combo.currentText()
        minutes = PRESETS.get(preset_name, 1440)
        # Fetch enough rows to cover the time range
        limit = max(2000, minutes * 2)
        rows = self.db.get_parameter_stream_data(limit=limit)
        if not rows:
            self._all_rows = []
            self._render_page()
            return

        # Filter by time range
        cutoff = datetime.now() - timedelta(minutes=minutes)
        filtered = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["timestamp"]))
                if ts >= cutoff:
                    filtered.append(r)
            except Exception:
                filtered.append(r)

        for r in filtered:
            pid = r["parameter_id"]
            if pid not in self._param_colors:
                self._param_colors[pid] = _COLORS[len(self._param_colors) % len(_COLORS)]

        self._current_page = 1
        self._build_stats(filtered)
        self._build_chart(filtered)
        self._build_all_rows(filtered)
        self._render_page()

    def _build_all_rows(self, rows):
        """Build unified timestamp-keyed rows for pagination."""
        ts_map: dict = defaultdict(dict)
        for r in rows:
            ts_map[r["timestamp"]][r["parameter_id"]] = r["value"]
        self._all_rows = sorted(ts_map.items(), key=lambda x: x[0], reverse=True)

    # ── Stats ─────────────────────────────────────────────────────────────────
    def _build_stats(self, rows):
        while self._stats_grid.count():
            item = self._stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        by_param: dict = defaultdict(list)
        meta: dict = {}
        for r in rows:
            pid = r["parameter_id"]
            by_param[pid].append(r["value"])
            meta[pid] = {"name": r["parameter_name"], "unit": r["unit"]}

        COLS = 3
        for i, (pid, vals) in enumerate(by_param.items()):
            color = self._param_colors.get(pid, "#6439ff")
            mean_v   = statistics.mean(vals)
            median_v = statistics.median(vals)
            sd_v     = statistics.stdev(vals) if len(vals) > 1 else 0.0
            min_v    = min(vals)
            max_v    = max(vals)
            unit     = meta[pid]["unit"]

            card = QFrame()
            card.setMinimumWidth(180)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.setStyleSheet(
                f"QFrame{{background:#0f172a;border-radius:8px;"
                f"border-left:3px solid {color};}}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)

            name_lbl = QLabel(f"{meta[pid]['name']}  ({len(vals)} records)")
            name_lbl.setStyleSheet(
                f"color:{color};font-weight:700;font-size:13px;background:transparent;"
            )
            cl.addWidget(name_lbl)

            for label, value in [
                ("Min",    min_v),
                ("Max",    max_v),
                ("Mean",   mean_v),
                ("Median", median_v),
                ("Std Dev", sd_v),
            ]:
                rw = QHBoxLayout()
                lbl = QLabel(f"{label}:")
                lbl.setFixedWidth(55)
                lbl.setStyleSheet("color:#94a3b8;font-size:12px;background:transparent;")
                val_lbl = QLabel(f"{value:.2f} {unit}")
                val_lbl.setStyleSheet(
                    "color:#e2e8f0;font-size:12px;font-weight:600;background:transparent;"
                )
                rw.addWidget(lbl)
                rw.addWidget(val_lbl)
                rw.addStretch()
                cl.addLayout(rw)

            grid_row, grid_col = divmod(i, COLS)
            self._stats_grid.addWidget(card, grid_row, grid_col)

    # ── Chart ─────────────────────────────────────────────────────────────────
    def _build_chart(self, rows):
        by_param: dict = defaultdict(list)
        meta: dict = {}
        for r in rows:
            pid = r["parameter_id"]
            try:
                ts = datetime.fromisoformat(str(r["timestamp"])).timestamp()
            except Exception:
                ts = 0.0
            by_param[pid].append((ts, r["value"]))
            meta[pid] = {"name": r["parameter_name"], "unit": r["unit"]}

        series = {}
        for pid, pts in by_param.items():
            pts.sort(key=lambda x: x[0])
            series[pid] = {
                "name":   meta[pid]["name"],
                "unit":   meta[pid]["unit"],
                "color":  self._param_colors.get(pid, "#6439ff"),
                "points": pts,
            }
        self._chart.set_series(series)

    # ── Pagination ────────────────────────────────────────────────────────────
    def _on_page_size_changed(self):
        self._items_per_page = int(self._page_size_combo.currentText())
        self._current_page = 1
        self._render_page()

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_page()

    def _next_page(self):
        total_pages = self._total_pages()
        if self._current_page < total_pages:
            self._current_page += 1
            self._render_page()

    def _total_pages(self):
        if not self._all_rows:
            return 1
        import math
        return max(1, math.ceil(len(self._all_rows) / self._items_per_page))

    def _render_page(self):
        total_pages = self._total_pages()
        start = (self._current_page - 1) * self._items_per_page
        page_rows = self._all_rows[start: start + self._items_per_page]

        self._page_label.setText(f"Page {self._current_page} / {total_pages}")
        self._row_count_label.setText(f"{len(self._all_rows)} total rows")
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(self._current_page < total_pages)

        # Collect param ids from current page
        param_ids_in_page: set = set()
        for _, pid_map in page_rows:
            param_ids_in_page.update(pid_map.keys())

        # Build column headers
        # Gather param meta from all rows
        param_meta: dict = {}
        for r_ts, pid_map in self._all_rows:
            for pid in pid_map:
                if pid not in param_meta:
                    # find name/unit from db rows — use stored data
                    pass
        # Re-fetch meta from db for column headers
        param_ids = sorted(param_ids_in_page)
        col_headers = ["Timestamp"] + [str(pid) for pid in param_ids]

        # Try to get names from chart series
        series = self._chart.series
        col_headers = ["Timestamp"] + [
            f"{series[pid]['name']} ({series[pid]['unit']})" if pid in series else str(pid)
            for pid in param_ids
        ]

        self._table.setColumnCount(len(col_headers))
        self._table.setHorizontalHeaderLabels(col_headers)
        self._table.setRowCount(len(page_rows))

        for row_idx, (ts, pid_map) in enumerate(page_rows):
            ts_item = QTableWidgetItem(str(ts))
            ts_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row_idx, 0, ts_item)

            for col_idx, pid in enumerate(param_ids, start=1):
                val = pid_map.get(pid)
                text = f"{val:.2f}" if val is not None else "—"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if val is not None:
                    item.setForeground(QColor(self._param_colors.get(pid, "#e2e8f0")))
                self._table.setItem(row_idx, col_idx, item)

        self._table.resizeColumnsToContents()
