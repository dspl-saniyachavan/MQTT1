"""
Simplified Line Chart Widget - matches web UI functionality
"""

from collections import deque
from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush


class SimpleLineChart(QWidget):
    """Simple line chart that matches web UI behavior"""
    
    def __init__(self, param_id, param_name, param_unit, color, parent=None):
        super().__init__(parent)
        self.param_id = param_id
        self.param_name = param_name
        self.param_unit = param_unit
        self.color = QColor(color)
        self._max_points = 50
        self.values = deque(maxlen=self._max_points)
        self.timestamps = deque(maxlen=self._max_points)
        self.points = []
        self.hovered_point = None
        self.setMinimumHeight(350)
        self.setStyleSheet("background-color: white; border-radius: 16px;")
        self.setMouseTracking(True)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(50)

    def set_max_points(self, max_points: int):
        """Resize the data deques to a new max — called when MAX_CHART_DATA_POINTS changes."""
        if max_points == self._max_points:
            return
        self._max_points = max_points
        old_values = list(self.values)
        old_ts = list(self.timestamps)
        self.values = deque(old_values[-max_points:], maxlen=max_points)
        self.timestamps = deque(old_ts[-max_points:], maxlen=max_points)
        print(f"[CHART] {self.param_name}: resized to {max_points} points")
    def add_value(self, value, timestamp=None):
        """Add value to chart"""
        if value is not None:
            self.values.append(float(value))
            self.timestamps.append(timestamp or datetime.now())
            print(f"[CHART] {self.param_name}: Added value {value}, total points: {len(self.values)}")
    def paintEvent(self, event):
        """Paint the chart"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  
        w = self.width()
        h = self.height()
        painter.fillRect(self.rect(), QColor("white"))
        if len(self.values) < 2:
            painter.setPen(QColor("#64748b"))
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(w // 2 - 100, h // 2, "Collecting data...")
            return
        pad_left = 70
        pad_right = 40
        pad_top = 80
        pad_bottom = 50
        chart_w = w - pad_left - pad_right
        chart_h = h - pad_top - pad_bottom        
        min_val = min(self.values)
        max_val = max(self.values)
        val_range = max_val - min_val if max_val != min_val else 1
        painter.setPen(QColor("#1e293b"))
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pad_left, 35, self.param_name)
        painter.setPen(QColor("#64748b"))
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        current = self.values[-1]
        painter.setPen(self.color)
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        text = f"{current:.1f} {self.param_unit}"
        painter.drawText(w - pad_right - 200, 40, text)        
        painter.setPen(QColor("#64748b"))
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(w - pad_right - 200, 60, "Current Value")
        
        # Draw grid lines
        painter.setPen(QPen(QColor("#e5e7eb"), 1))
        for i in range(5):
            y = pad_top + (chart_h * i / 4)
            painter.drawLine(pad_left, int(y), w - pad_right, int(y))
            
            # Y-axis labels
            val = max_val - (val_range * i / 4)
            painter.setPen(QColor("#9ca3af"))
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(10, int(y + 5), f"{val:.1f}")
            painter.setPen(QPen(QColor("#e5e7eb"), 1))
        
        # Draw X-axis labels
        painter.setPen(QColor("#9ca3af"))
        for i, t in enumerate([0, 10, 20, 30, 40, 50, 60]):
            x = pad_left + (chart_w * i / 6)
            painter.drawText(int(x - 15), h - 20, f"{t}s")
        
        # Calculate points
        self.points = []
        for i, value in enumerate(self.values):
            x = pad_left + (chart_w * i / max(len(self.values) - 1, 1))
            y = pad_top + chart_h - ((value - min_val) / val_range * chart_h)
            self.points.append((x, y, value, i))
        
        # Draw line
        painter.setPen(QPen(self.color, 3))
        for i in range(len(self.points) - 1):
            x1, y1, _, _ = self.points[i]
            x2, y2, _, _ = self.points[i + 1]
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        
        # Draw points
        painter.setBrush(self.color)
        painter.setPen(Qt.NoPen)
        for x, y, _, _ in self.points:
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
        
        # Draw hover tooltip
        if self.hovered_point is not None:
            x, y, value, idx = self.hovered_point
            ts = list(self.timestamps)[idx]
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%H:%M:%S")
            else:
                ts_str = str(ts)
            
            line1 = f"{self.param_name}: {value:.2f}"
            line2 = ts_str
            
            # Draw tooltip box
            painter.setPen(QPen(self.color, 2))
            painter.setBrush(QBrush(QColor("white")))
            
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            
            metrics = painter.fontMetrics()
            width1 = metrics.horizontalAdvance(line1)
            width2 = metrics.horizontalAdvance(line2)
            text_width = max(width1, width2)
            text_height = metrics.height() * 2 + 12
            
            tooltip_x = int(x) - text_width // 2 - 12
            tooltip_y = int(y) - text_height - 15
            
            # Adjust tooltip position if it goes off-screen
            if tooltip_y < 10:
                tooltip_y = int(y) + 15
            if tooltip_x < 10:
                tooltip_x = 10
            if tooltip_x + text_width + 24 > w:
                tooltip_x = w - text_width - 24
            
            painter.drawRect(tooltip_x, tooltip_y, text_width + 24, text_height)
            painter.setPen(QColor("#1e293b"))
            painter.drawText(tooltip_x + 12, tooltip_y + 18, line1)
            painter.drawText(tooltip_x + 12, tooltip_y + 18 + metrics.height(), line2)
    
    def mouseMoveEvent(self, event):
        """Track mouse hover over points"""
        pos = event.pos()
        self.hovered_point = None
        
        for point in self.points:
            x, y, value, idx = point
            dist = ((pos.x() - x) ** 2 + (pos.y() - y) ** 2) ** 0.5
            if dist < 10:
                self.hovered_point = point
                break
        
        self.update()
    
    def leaveEvent(self, event):
        """Clear hover when mouse leaves"""
        self.hovered_point = None
        self.update()
