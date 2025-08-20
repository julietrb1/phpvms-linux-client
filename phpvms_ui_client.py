"""
phpVMS PySide UI Client

A simple PySide6 GUI application that demonstrates authentication and PIREP listing
using the phpVMS API client.

Features:
- Login with API key authentication
- Display user information
- List previous PIREPs

Requirements:
- PySide6
- requests
- phpvms_api_client.py (in the same directory)
"""

import sys
import traceback
from typing import Optional, List, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QStatusBar, QGroupBox, QFormLayout, QTextEdit,
    QHeaderView, QProgressBar, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QIcon

from vms_types import Pirep

# Import our phpVMS API client
try:
    from phpvms_api_client import create_client, PhpVmsApiException, PirepState
except ImportError as e:
    print(f"Error importing phpVMS API client: {e}")
    print("Make sure phpvms_api_client.py is in the same directory")
    sys.exit(1)


class ApiWorker(QThread):
    """Worker thread for API calls to prevent UI freezing"""

    # Signals
    login_result = Signal(bool, str, dict)  # success, message, user_data
    pireps_result = Signal(bool, str, list)  # success, message, pireps_data

    def __init__(self):
        super().__init__()
        self.client = None
        self.operation = None
        self.base_url = None
        self.api_key = None

    def set_login_operation(self, base_url: str, api_key: str):
        """Set up login operation"""
        self.operation = "login"
        self.base_url = base_url
        self.api_key = api_key

    def set_pireps_operation(self, client):
        """Set up PIREPs fetch operation"""
        self.operation = "pireps"
        self.client = client

    def run(self):
        """Execute the operation in the background thread"""
        try:
            if self.operation == "login":
                self._do_login()
            elif self.operation == "pireps":
                self._do_fetch_pireps()
        except Exception as e:
            if self.operation == "login":
                self.login_result.emit(False, f"Unexpected error: {str(e)}", {})
            elif self.operation == "pireps":
                self.pireps_result.emit(False, f"Unexpected error: {str(e)}", [])

    def _do_login(self):
        """Perform login operation"""
        try:
            # Create client
            client = create_client(self.base_url, api_key=self.api_key)

            # Test authentication by getting current user
            response = client.get_current_user()
            user_data = response.get('data', {})

            if user_data:
                self.login_result.emit(True, "Login successful!", user_data)
            else:
                self.login_result.emit(False, "No user data received", {})

        except PhpVmsApiException as e:
            self.login_result.emit(False, f"API Error: {e.message}", {})
        except Exception as e:
            self.login_result.emit(False, f"Connection error: {str(e)}", {})

    def _do_fetch_pireps(self):
        """Fetch PIREPs operation"""
        try:
            response = self.client.get_user_pireps()
            pireps_data = response.get('data', [])
            self.pireps_result.emit(True, f"Found {len(pireps_data)} PIREPs", pireps_data)

        except PhpVmsApiException as e:
            self.pireps_result.emit(False, f"API Error: {e.message}", [])
        except Exception as e:
            self.pireps_result.emit(False, f"Error fetching PIREPs: {str(e)}", [])


class LoginWidget(QWidget):
    """Login form widget"""

    login_requested = Signal(str, str)  # base_url, api_key

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Set up the login UI"""
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
        """Handle login button click"""
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "Error", "Please enter a base URL")
            return

        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter an API key")
            return

        # Ensure URL has proper format
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'https://' + base_url

        self.login_requested.emit(base_url, api_key)

    def set_login_enabled(self, enabled: bool):
        """Enable/disable login controls"""
        self.login_button.setEnabled(enabled)
        self.base_url_input.setEnabled(enabled)
        self.api_key_input.setEnabled(enabled)


class UserInfoWidget(QWidget):
    """Widget to display user information"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Set up the user info UI"""
        layout = QVBoxLayout()

        # User info group
        self.user_group = QGroupBox("User Information")
        user_layout = QFormLayout()

        self.name_label = QLabel("-")
        self.pilot_id_label = QLabel("-")
        self.airline_label = QLabel("-")
        self.rank_label = QLabel("-")
        self.flights_label = QLabel("-")
        self.flight_time_label = QLabel("-")
        self.current_airport_label = QLabel("-")

        user_layout.addRow("Name:", self.name_label)
        user_layout.addRow("Pilot ID:", self.pilot_id_label)
        user_layout.addRow("Airline ID:", self.airline_label)
        user_layout.addRow("Rank ID:", self.rank_label)
        user_layout.addRow("Total Flights:", self.flights_label)
        user_layout.addRow("Flight Time:", self.flight_time_label)
        user_layout.addRow("Current Airport:", self.current_airport_label)

        self.user_group.setLayout(user_layout)
        layout.addWidget(self.user_group)

        self.setLayout(layout)

    def update_user_info(self, user_data: Dict[str, Any]):
        """Update the user information display"""
        self.name_label.setText(user_data.get('name', 'Unknown'))
        self.pilot_id_label.setText(str(user_data.get('pilot_id', 'Unknown')))
        self.airline_label.setText(str(user_data.get('airline_id', 'Unknown')))
        self.rank_label.setText(str(user_data.get('rank_id', 'Unknown')))
        self.flights_label.setText(str(user_data.get('flights', 0)))

        # Convert flight time from minutes to hours:minutes
        flight_time_minutes = user_data.get('flight_time', 0)
        hours = flight_time_minutes // 60
        minutes = flight_time_minutes % 60
        self.flight_time_label.setText(f"{hours}h {minutes}m")

        self.current_airport_label.setText(user_data.get('curr_airport_id', 'Unknown'))


class PirepsWidget(QWidget):
    """Widget to display PIREPs table"""

    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Set up the PIREPs UI"""
        layout = QVBoxLayout()

        # Header with refresh button
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Previous PIREPs"))
        header_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.refresh_button)

        layout.addLayout(header_layout)

        # PIREPs table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Flight", "Route", "Aircraft", "State", "Date", "Flight Time", "Distance"
        ])

        # Configure table
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

        self.setLayout(layout)

    def update_pireps(self, pireps_data: List[Pirep]):
        """Update the PIREPs table"""
        self.table.setRowCount(len(pireps_data))

        for row, pirep in enumerate(pireps_data):
            # Flight number
            flight_number = pirep.get('flight_number', 'N/A')
            self.table.setItem(row, 1, QTableWidgetItem(flight_number))

            # Route
            dep = pirep.get('dpt_airport_id', '')
            arr = pirep.get('arr_airport_id', '')
            route = f"{dep} → {arr}" if dep and arr else "N/A"
            self.table.setItem(row, 2, QTableWidgetItem(route))

            aircraft_name = pirep.get('aircraft', {}).get('name', '')
            self.table.setItem(row, 3, QTableWidgetItem(str(aircraft_name) if aircraft_name else 'N/A'))

            # State
            state_value = pirep.get('state', 0)
            try:
                state_name = PirepState(state_value).name
            except ValueError:
                state_name = f"Unknown ({state_value})"
            self.table.setItem(row, 4, QTableWidgetItem(state_name))

            # Date
            created_at = pirep.get('created_at', '')
            if created_at:
                try:
                    # Parse ISO date and format it nicely
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    date_str = created_at
            else:
                date_str = 'N/A'
            self.table.setItem(row, 5, QTableWidgetItem(date_str))

            # Flight time
            flight_time = pirep.get('flight_time', 0)
            if flight_time:
                hours = flight_time // 60
                minutes = flight_time % 60
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = 'N/A'
            self.table.setItem(row, 6, QTableWidgetItem(time_str))

            # Distance
            distance = pirep.get('distance', 0)
            # Coerce to float safely (API may return a numeric string)
            distance_value: Optional[float]
            try:
                if distance is None or distance == 0:
                    distance_value = None
                elif isinstance(distance, (int, float)):
                    distance_value = float(distance)
                elif isinstance(distance, str) and distance.strip() != "":
                    distance_value = float(distance)
                else:
                    distance_value = None
            except Exception:
                distance_value = None
            distance_str = f"{distance_value:.0f} nm" if distance_value is not None else 'N/A'
            self.table.setItem(row, 7, QTableWidgetItem(distance_str))

    def set_refresh_enabled(self, enabled: bool):
        """Enable/disable refresh button"""
        self.refresh_button.setEnabled(enabled)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.client = None
        self.user_data = None
        self.worker = ApiWorker()
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Set up the main UI"""
        self.setWindowTitle("phpVMS API Client")
        self.setMinimumSize(800, 600)

        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Create widgets
        self.login_widget = LoginWidget()
        self.user_info_widget = UserInfoWidget()
        self.pireps_widget = PirepsWidget()

        # Create splitter for main content
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel (user info)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.user_info_widget)
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)

        # Right panel (PIREPs)
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.pireps_widget)
        self.splitter.setSizes([300, 500])

        # Initially show login widget
        layout.addWidget(self.login_widget)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Please login to continue")

        # Logout button (initially hidden)
        self.logout_button = QPushButton("Logout")
        self.logout_button.setVisible(False)
        self.logout_button.clicked.connect(self.logout)

    def setup_connections(self):
        """Set up signal connections"""
        # Login widget
        self.login_widget.login_requested.connect(self.on_login_requested)

        # PIREPs widget
        self.pireps_widget.refresh_requested.connect(self.refresh_pireps)

        # Worker signals
        self.worker.login_result.connect(self.on_login_result)
        self.worker.pireps_result.connect(self.on_pireps_result)

    def on_login_requested(self, base_url: str, api_key: str):
        """Handle login request"""
        self.status_bar.showMessage("Logging in...")
        self.show_progress(True)
        self.login_widget.set_login_enabled(False)

        # Start login in worker thread
        self.worker.set_login_operation(base_url, api_key)
        self.worker.start()

    def on_login_result(self, success: bool, message: str, user_data: Dict[str, Any]):
        """Handle login result"""
        self.show_progress(False)
        self.login_widget.set_login_enabled(True)

        if success:
            # Store client and user data
            self.client = create_client(self.worker.base_url, api_key=self.worker.api_key)
            self.user_data = user_data

            # Update UI
            self.user_info_widget.update_user_info(user_data)
            self.show_main_interface()
            self.status_bar.showMessage(f"Logged in as {user_data.get('name', 'Unknown')}")

            # Automatically fetch PIREPs
            self.refresh_pireps()
        else:
            QMessageBox.critical(self, "Login Failed", message)
            self.status_bar.showMessage("Login failed")

    def show_main_interface(self):
        """Switch to main interface after successful login"""
        # Hide login widget
        self.login_widget.setVisible(False)

        # Show main content
        self.centralWidget().layout().addWidget(self.splitter)

        # Add logout button to status bar
        self.logout_button.setVisible(True)
        self.status_bar.addPermanentWidget(self.logout_button)

    def refresh_pireps(self):
        """Refresh PIREPs data"""
        if not self.client:
            return

        self.status_bar.showMessage("Loading PIREPs...")
        self.show_progress(True)
        self.pireps_widget.set_refresh_enabled(False)

        # Start PIREPs fetch in worker thread
        self.worker.set_pireps_operation(self.client)
        self.worker.start()

    def on_pireps_result(self, success: bool, message: str, pireps_data: List[Pirep]):
        """Handle PIREPs result"""
        self.show_progress(False)
        self.pireps_widget.set_refresh_enabled(True)

        if success:
            self.pireps_widget.update_pireps(pireps_data)
            self.status_bar.showMessage(message)
        else:
            QMessageBox.warning(self, "Error", f"Failed to load PIREPs: {message}")
            self.status_bar.showMessage("Failed to load PIREPs")

    def logout(self):
        """Handle logout"""
        # Clear data
        self.client = None
        self.user_data = None

        # Hide main interface
        self.splitter.setVisible(False)
        self.logout_button.setVisible(False)

        # Show login widget
        self.login_widget.setVisible(True)

        # Clear status
        self.status_bar.showMessage("Ready - Please login to continue")

    def show_progress(self, show: bool):
        """Show/hide progress bar"""
        if show:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        else:
            self.progress_bar.setVisible(False)


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("phpVMS API Client")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("phpVMS")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
