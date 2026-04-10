import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow
from src.core.database import DatabaseManager
from src.core.config import Config
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PrecisionPulse Desktop")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("DSPL") 
    app.setStyle('Fusion') 
    #  db initialization
    db_manager = DatabaseManager()
    db_manager.initialize_database() 
    # Create, show main window
    window = MainWindow()
    window.show()
    return app.exec()
if __name__ == "__main__":
    sys.exit(main())