"""
LoginWidget - login form for phpVMS client
"""
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QLineEdit, QPushButton, QMessageBox
)


class LoginWidget(QWidget):
    """Login form widget"""

    login_requested = Signal(str, str)  # base_url, api_key

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Title
        title = QLabel("phpVMS API Client")
        title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Login form
        form_group = QGroupBox("Login")
        form_layout = QFormLayout()

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://your-phpvms.com")
        # Load cached settings
        settings = QSettings()
        cached_base_url = settings.value("api/base_url", "")
        if cached_base_url:
            self.base_url_input.setText(str(cached_base_url))
        form_layout.addRow("Base URL:", self.base_url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Your API key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        cached_api_key = settings.value("api/api_key", "")
        if cached_api_key:
            self.api_key_input.setText(str(cached_api_key))
        form_layout.addRow("API Key:", self.api_key_input)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.on_login_clicked)
        form_layout.addRow("", self.login_button)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Instructions
        instructions = QLabel(
            "Enter your phpVMS base URL and API key to authenticate.\n"
            "The API key can be found in your phpVMS user profile."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(instructions)

        layout.addStretch()
        self.setLayout(layout)

    def on_login_clicked(self):
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "Error", "Enter base URL")
            return

        if not api_key:
            QMessageBox.warning(self, "Error", "Enter API key")
            return

        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url

        settings = QSettings()
        settings.setValue("api/base_url", base_url)
        settings.setValue("api/api_key", api_key)

        self.login_requested.emit(base_url, api_key)

    def set_login_enabled(self, enabled: bool):
        self.login_button.setEnabled(enabled)
        self.base_url_input.setEnabled(enabled)
        self.api_key_input.setEnabled(enabled)
