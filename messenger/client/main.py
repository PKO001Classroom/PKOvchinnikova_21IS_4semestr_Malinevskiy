import sys
import requests
from PyQt5.QtWidgets import QApplication, QMessageBox
#from ui.login_dialog import LoginDialog  # Убрали client.
#from ui.main_window import MainWindow    # Убрали client.
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow

class MessengerClient:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.auth_token = None
        self.current_user = None
        
    def run(self):
        # Show login dialog
        login_dialog = LoginDialog()
        if login_dialog.exec_():
            self.auth_token = login_dialog.auth_token
            self.current_user = login_dialog.current_user
            
            # Show main window
            main_window = MainWindow(self.auth_token, self.current_user)
            main_window.show()
            
            return self.app.exec_()
        return 0

if __name__ == "__main__":
    client = MessengerClient()
    sys.exit(client.run())