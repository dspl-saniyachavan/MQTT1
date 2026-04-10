from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class CustomMessageBox(QDialog):
    """Custom styled message box"""

    def __init__(self, title: str, message: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                border-radius: 15px;
            }
            QLabel {
                color: white;
                font-size: 18px;
            }
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)

        layout = QVBoxLayout(self)
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(30, 30, 30, 30)
        # layout.setSpacing(20)
        layout.addLayout(center_layout)

        # Message label
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # OK button
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)  # Close dialog on click
        layout.addWidget(self.ok_button, alignment=Qt.AlignCenter)


from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt

class CustomMessageBox1(QDialog):
    """Custom message box with Yes and No buttons"""

    def __init__(self, title: str, message: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                border-radius: 15px;
            }
            QLabel {
                color: white;
                font-size: 18px;
            }
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
            QPushButton#noButton {
                background-color: #dc2626;
            }
            QPushButton#noButton:hover {
                background-color: #b91c1c;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Message label
        self.label = QLabel(message)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        # Yes button
        self.yes_button = QPushButton("Yes")
        self.yes_button.clicked.connect(self.accept)  # Dialog returns Accepted
        btn_layout.addWidget(self.yes_button)

        # No button
        self.no_button = QPushButton("No")
        self.no_button.setObjectName("noButton")
        self.no_button.clicked.connect(self.reject)  # Dialog returns Rejected
        btn_layout.addWidget(self.no_button)

        layout.addLayout(btn_layout)