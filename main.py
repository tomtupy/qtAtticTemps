import sys
from PyQt6.QtWidgets import QApplication
from attic_temps import AtticTempsWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AtticTempsWindow()
    window.show()
    sys.exit(app.exec())
