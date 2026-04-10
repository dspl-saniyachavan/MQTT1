"""
Telemetry widget for real-time data display
"""

import random
from collections import deque
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QGridLayout, QScrollArea)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPainter, QColor
from src.ui.simple_line_chart import SimpleLineChart
from telemetry_config import TELEMETRY_INTERVAL_SECONDS
from collections import defaultdict

_alert_log: list = []  # [{param_name, value, alert_min, alert_max, timestamp, resolved_at}]

def format_time_utc(dt):
    """Format datetime to HH:MM:SS local time format"""
    return dt.strftime('%H:%M:%S')

class MiniChart(QWidget):
    """Mini bar chart widget"""
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.values = deque([random.randint(30, 90) for _ in range(14)], maxlen=14)
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
    
    def update_value(self, value):
        """Add new value and update chart"""
        self.values.append(int(value))
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        bar_width = width / len(self.values)
        
        for i, value in enumerate(self.values):
            bar_height = (value / 100) * height
            x = i * bar_width
            y = height - bar_height
            
            painter.fillRect(int(x + 1), int(y), int(bar_width - 2), int(bar_height), self.color)


class TelemetryWidget(QWidget):
    """Widget for displaying real-time telemetry data"""
    
    def __init__(self, telemetry_service=None, auth_service=None):
        super().__init__()
        self.telemetry_service = telemetry_service
        self.auth_service = auth_service
        self.parameter_widgets = {}
        self.line_charts = {}
        self.charts_created = False
        self.is_paused = False
        self._max_chart_points = 50
        self.setup_ui()
        
        if self.telemetry_service:
            self.telemetry_service.parameters_updated.connect(self.update_all_parameters)
            self.telemetry_service.parameter_changed.connect(self.update_single_parameter)
            self.telemetry_service.connection_status_changed.connect(self.on_connection_status_changed)
            self.telemetry_service.refresh_parameters()
    
    def setup_ui(self):
        """Setup telemetry UI"""
        self.setStyleSheet("background-color: #0f172a;")
        layout = QVBoxLayout(self)
        
        # Responsive spacing and margins
        screen_width = self.screen().availableGeometry().width()
        spacing = 12 if screen_width < 1200 else 24
        margin = 30 if screen_width < 1200 else 80
        
        layout.setSpacing(spacing)
        layout.setContentsMargins(margin, 30, margin, 30)
        
        user_name = "User"
        if self.auth_service:
            current_user = self.auth_service.get_current_user()
            if current_user:
                user_name = current_user.get('name', 'User')
        
        self.welcome_label = QLabel(f"Welcome back, {user_name}!")
        self.welcome_label.setStyleSheet("""
            font-size: 48px; 
            font-weight: 700; 
            color: white; 
            letter-spacing: -0.5px;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        
        subtitle_label = QLabel("Monitor your telemetry streams in real-time")
        subtitle_label.setStyleSheet("""
            font-size: 20px; 
            color: #94a3b8; 
            font-weight: 400;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        
        layout.addWidget(self.welcome_label)
        layout.addWidget(subtitle_label)
        layout.addSpacing(16)
        
        section_label = QLabel("LIVE DATA STREAM")
        section_label.setStyleSheet("""
            font-size: 13px; 
            font-weight: 700; 
            color: #64748b; 
            letter-spacing: 2.5px;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        layout.addWidget(section_label)
        layout.addSpacing(8)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background: #1e293b; width: 8px; border-radius: 4px; }
            QScrollBar::handle:vertical { background: #475569; border-radius: 4px; }
        """)
        
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(24)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(16)
        self.create_parameter_cards()
        scroll_layout.addLayout(self.grid_layout)
        
        scroll_layout.addSpacing(32)
        trends_label = QLabel("HISTORICAL TRENDS")
        trends_label.setStyleSheet("""
            font-size: 13px; 
            font-weight: 700; 
            color: #64748b; 
            letter-spacing: 2.5px;
            background: transparent;
        """)
        scroll_layout.addWidget(trends_label)
        scroll_layout.addSpacing(16)
        
        self.charts_layout = QVBoxLayout()
        self.charts_layout.setSpacing(24)
        self.create_line_charts()
        scroll_layout.addLayout(self.charts_layout)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)
    
    def create_parameter_cards(self):
        """Create parameter display cards"""
        if self.telemetry_service:
            parameters = list(self.telemetry_service.get_parameters().values())
            print(f"Creating parameter cards for {len(parameters)} parameters")
        else:
            parameters = []
        
        if not parameters:
            placeholder = QLabel("No parameters configured. Add parameters to see telemetry data.")
            placeholder.setStyleSheet("""
                QLabel {
                    color: #64748b;
                    font-size: 16px;
                    padding: 40px;
                    text-align: center;
                    background: transparent;
                }
            """)
            placeholder.setAlignment(Qt.AlignCenter)
            self.grid_layout.addWidget(placeholder, 0, 0, 1, 3)
            return
        
        for i, param in enumerate(parameters):
            card = self.create_parameter_card(param)
            self.grid_layout.addWidget(card, i // 3, i % 3)
    
    def create_parameter_card(self, param):
        """Create individual parameter card"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 16px;
                border: none;
            }
        """)
        card.setMinimumSize(300, 180)
        card.setSizePolicy(
            card.sizePolicy().horizontalPolicy(),
            __import__('PySide6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Expanding
        )
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(24, 24, 24, 20)
        
        header_layout = QHBoxLayout()
        
        value_label = QLabel(f"{param['value']:.1f}")
        value_label.setStyleSheet("""
            font-size: 56px; 
            font-weight: 700; 
            color: #0f172a; 
            letter-spacing: -1.5px;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        
        trend_label = QLabel("")
        trend_label.setStyleSheet("""
            font-size: 32px;
            color: #64748b;
            background: transparent;
        """)
        
        header_layout.addWidget(value_label)
        header_layout.addWidget(trend_label, alignment=Qt.AlignTop)
        header_layout.addStretch()
        
        name_label = QLabel(f"{param['name']} ({param['unit']})")
        name_label.setStyleSheet("""
            font-size: 15px; 
            color: #64748b; 
            font-weight: 500;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        
        timestamp_label = QLabel(format_time_utc(datetime.now()))
        timestamp_label.setStyleSheet("""
            font-size: 12px; 
            color: #94a3b8; 
            font-weight: 400;
            font-family: 'Inter', 'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif;
            background: transparent;
        """)
        
        chart = MiniChart(param['color'])
        chart.setFixedHeight(60)

        # Alert badge — shown when value is out of range
        alert_badge = QLabel("")
        alert_badge.setWordWrap(True)
        alert_badge.setVisible(False)

        # Range info label shown below badge
        range_label = QLabel("")
        range_label.setWordWrap(True)
        range_label.setStyleSheet("font-size: 11px; background: transparent;")
        range_label.setVisible(False)

        layout.addLayout(header_layout)
        layout.addWidget(name_label)
        layout.addWidget(alert_badge)
        layout.addWidget(range_label)
        layout.addWidget(timestamp_label)
        layout.addWidget(chart)

        self.parameter_widgets[param['id']] = {
            'value_label': value_label,
            'trend_label': trend_label,
            'name_label': name_label,
            'timestamp_label': timestamp_label,
            'chart': chart,
            'alert_badge': alert_badge,
            'range_label': range_label,
            'card_frame': card,
            'min': param.get('min', 0),
            'max': param.get('max', 100),
            'alert_min': param.get('alert_min'),
            'alert_max': param.get('alert_max'),
            'warn_min': param.get('warn_min'),
            'warn_max': param.get('warn_max'),
            'prev_value': param['value'],
            'in_alert': False,
        }
        
        return card
    
    def create_line_charts(self):
        """Create line charts once"""
        if self.charts_created:
            return
        
        if self.telemetry_service:
            parameters = list(self.telemetry_service.get_parameters().values())
            print(f" Creating line charts for {len(parameters)} parameters")
        else:
            parameters = []
        
        if not parameters:
            return
        
        for param in parameters:
            chart = SimpleLineChart(
                param['id'],
                param['name'],
                param['unit'],
                param['color']
            )
            self.charts_layout.addWidget(chart)
            self.line_charts[param['id']] = chart
        
        self.charts_created = True
    
    @Slot()
    def update_all_parameters(self):
        """Update all parameters — skip if paused."""
        if not self.telemetry_service or self.is_paused:
            return

        parameters = self.telemetry_service.get_parameters()
        timestamp  = datetime.now()

        # Rebuild cards only when the parameter set changes
        current_param_ids = set(self.parameter_widgets.keys())
        new_param_ids     = set(parameters.keys())

        if new_param_ids != current_param_ids:
            while self.grid_layout.count():
                w = self.grid_layout.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self.parameter_widgets.clear()
            self.create_parameter_cards()

            while self.charts_layout.count():
                w = self.charts_layout.takeAt(0).widget()
                if w:
                    w.deleteLater()
            self.line_charts.clear()
            self.charts_created = False
            self.create_line_charts()

        for param_id, param in parameters.items():
            if param_id not in self.parameter_widgets:
                continue
            value  = param['value']
            widget = self.parameter_widgets[param_id]
            prev   = widget.get('prev_value', value)

            # Sync alert/warn thresholds
            widget['alert_min'] = param.get('alert_min')
            widget['alert_max'] = param.get('alert_max')
            widget['warn_min']  = param.get('warn_min')
            widget['warn_max']  = param.get('warn_max')

            # Only update labels when value actually changed (reduces repaints)
            if value != prev:
                widget['value_label'].setText(f"{value:.1f}")
                widget['timestamp_label'].setText(format_time_utc(timestamp))

                trend_symbol, trend_color = self._trend(value, prev)
                widget['trend_label'].setText(trend_symbol)
                if trend_symbol:
                    widget['trend_label'].setStyleSheet(
                        f"font-size: 32px; color: {trend_color}; background: transparent;"
                    )

                lo, hi = widget['min'], widget['max']
                widget['chart'].update_value(((value - lo) / max(hi - lo, 1)) * 100)

            self._apply_alert_style(
                widget, value,
                is_critical=(
                    (widget['alert_min'] is not None and value < widget['alert_min']) or
                    (widget['alert_max'] is not None and value > widget['alert_max'])
                ),
                is_warning=False,  # computed inside _apply_alert_style via warn thresholds
                alert_min=widget['alert_min'], alert_max=widget['alert_max'],
                warn_min=widget['warn_min'],   warn_max=widget['warn_max'],
                param_name=param.get('name', str(param_id))
            )
            widget['prev_value'] = value

            if param_id in self.line_charts:
                self.line_charts[param_id].add_value(value, timestamp)
    
    @staticmethod
    def _trend(value: float, prev: float):
        if value > prev + 0.1:
            return '▲', '#059669'
        if value < prev - 0.1:
            return '▼', '#dc2626'
        return '', '#64748b'

    @Slot(str, float)
    def update_single_parameter(self, param_id, value):
        """Update single parameter."""
        if self.is_paused:
            return
        timestamp = datetime.now()
        if param_id in self.parameter_widgets:
            widget = self.parameter_widgets[param_id]
            prev   = widget.get('prev_value', value)
            widget['value_label'].setText(f"{value:.1f}")
            widget['timestamp_label'].setText(format_time_utc(timestamp))
            trend_symbol, trend_color = self._trend(value, prev)
            widget['trend_label'].setText(trend_symbol)
            if trend_symbol:
                widget['trend_label'].setStyleSheet(
                    f"font-size: 32px; color: {trend_color}; background: transparent;"
                )
            self._apply_alert_style(
                widget, value,
                is_critical=(
                    (widget.get('alert_min') is not None and value < widget['alert_min']) or
                    (widget.get('alert_max') is not None and value > widget['alert_max'])
                ),
                is_warning=False,
                alert_min=widget.get('alert_min'), alert_max=widget.get('alert_max'),
                warn_min=widget.get('warn_min'),   warn_max=widget.get('warn_max'),
                param_name=str(param_id)
            )
            lo, hi = widget['min'], widget['max']
            widget['chart'].update_value(((value - lo) / max(hi - lo, 1)) * 100)
            widget['prev_value'] = value
        if param_id in self.line_charts:
            self.line_charts[param_id].add_value(value, timestamp)
    
    def _apply_alert_style(self, widget, value, is_critical, is_warning,
                            alert_min, alert_max, warn_min, warn_max, param_name):
        """Apply alert styles - only colour value label and badge, card stays white."""
        if not is_critical:
            is_warning = (
                (warn_min is not None and value < warn_min) or
                (warn_max is not None and value > warn_max)
            )
        out_of_range = is_critical or is_warning
        was_in_alert = widget.get('in_alert', False)

        # Value label colour only
        if is_critical:
            value_color = '#dc2626'
        elif is_warning:
            value_color = '#d97706'
        else:
            value_color = '#0f172a'
        widget['value_label'].setStyleSheet(
            f"font-size: 56px; font-weight: 700; color: {value_color}; "
            "letter-spacing: -1.5px; font-family: 'Inter', 'Segoe UI', sans-serif; background: transparent;"
        )

        # Name label subtle colour
        if 'name_label' in widget:
            name_color = '#dc2626' if is_critical else '#d97706' if is_warning else '#64748b'
            widget['name_label'].setStyleSheet(
                f"font-size: 15px; color: {name_color}; font-weight: 500; "
                "font-family: 'Inter', 'Segoe UI', sans-serif; background: transparent;"
            )

        # Alert badge
        badge = widget.get('alert_badge')
        if badge:
            if is_critical:
                badge.setText("\u26a0 CRITICAL")
                badge.setStyleSheet("""
                    QLabel {
                        color: #ffffff;
                        background-color: #dc2626;
                        font-size: 10px; font-weight: 700;
                        padding: 2px 8px; border-radius: 8px;
                    }
                """)
                badge.setVisible(True)
            elif is_warning:
                badge.setText("\u26a1 WARNING")
                badge.setStyleSheet("""
                    QLabel {
                        color: #ffffff;
                        background-color: #d97706;
                        font-size: 10px; font-weight: 700;
                        padding: 2px 8px; border-radius: 8px;
                    }
                """)
                badge.setVisible(True)
            else:
                badge.setVisible(False)

        # Range info label
        range_lbl = widget.get('range_label')
        if range_lbl:
            if out_of_range:
                rmin = alert_min if is_critical else warn_min
                rmax = alert_max if is_critical else warn_max
                color = '#dc2626' if is_critical else '#d97706'
                range_lbl.setText(
                    f"Range: {rmin if rmin is not None else chr(8212)} \u2013 "
                    f"{rmax if rmax is not None else chr(8212)} | Current: {value:.2f}"
                )
                range_lbl.setStyleSheet(f"font-size: 11px; color: {color}; background: transparent;")
                range_lbl.setVisible(True)
            else:
                range_lbl.setVisible(False)

        # Card frame — white background always, only border changes
        card_frame = widget.get('card_frame')
        if card_frame:
            if is_critical:
                card_frame.setStyleSheet(
                    "QFrame { background: white; border-radius: 16px;"
                    " border: 2px solid #dc2626; }"
                )
            elif is_warning:
                card_frame.setStyleSheet(
                    "QFrame { background: white; border-radius: 16px;"
                    " border: 2px solid #d97706; }"
                )
            else:
                card_frame.setStyleSheet(
                    "QFrame { background: white; border-radius: 16px; border: none; }"
                )

        # Alert log transitions
        if out_of_range and not was_in_alert:
            _alert_log.append({
                'param_name': param_name,
                'value': value,
                'alert_min': alert_min,
                'alert_max': alert_max,
                'timestamp': datetime.now().isoformat(),
                'resolved_at': None,
            })
        elif not out_of_range and was_in_alert:
            for entry in reversed(_alert_log):
                if entry['param_name'] == param_name and entry['resolved_at'] is None:
                    entry['resolved_at'] = datetime.now().isoformat()
                    break

    def on_connection_status_changed(self, is_connected):
        """MQTT status changed — desktop keeps generating regardless, never pause UI."""
        if is_connected:
            print("[UI] MQTT connected")
        else:
            print("[UI] MQTT disconnected — desktop continues generating and buffering")
        # Never set is_paused — desktop must keep updating charts even when offline
    
    def refresh_parameters(self):
        """Refresh parameters and update UI"""
        if not self.telemetry_service:
            return
        self.telemetry_service.refresh_parameters()
        # Sync all alert/warn ranges into existing widgets
        for param_id, param in self.telemetry_service.get_parameters().items():
            if param_id in self.parameter_widgets:
                w = self.parameter_widgets[param_id]
                w['alert_min'] = param.get('alert_min')
                w['alert_max'] = param.get('alert_max')
                w['warn_min']  = param.get('warn_min')
                w['warn_max']  = param.get('warn_max')
        self.update_all_parameters()

    def refresh_parameters_silent(self):
        """Refresh parameters without triggering UI rebuild (no flash)"""
        if not self.telemetry_service:
            return
        self.telemetry_service.refresh_parameters()

    def update_user_name(self, name: str):
        """Update the welcome label with a new user name"""
        if hasattr(self, 'welcome_label'):
            self.welcome_label.setText(f"Welcome back, {name}!")

    def apply_max_chart_points(self, max_points: int):
        """Resize all line charts when MAX_CHART_DATA_POINTS config changes."""
        if max_points == self._max_chart_points:
            return
        self._max_chart_points = max_points
        for chart in self.line_charts.values():
            chart.set_max_points(max_points)
        print(f"[WIDGET] All charts resized to {max_points} points")
