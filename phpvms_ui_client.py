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

import json
import re
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QStatusBar, QGroupBox, QFormLayout, QTextEdit,
    QHeaderView, QProgressBar, QSplitter, QTabWidget, QComboBox
)

from udp_bridge import UdpBridge
from vms_types import Pirep

# Import our phpVMS API client
try:
    from phpvms_api_client import create_client, PhpVmsApiException, PirepState, PirepWorkflowManager
except ImportError as e:
    print(f"Error importing phpVMS API client: {e}")
    print("Make sure phpvms_api_client.py is in the same directory")
    sys.exit(1)


class ApiWorker(QThread):
    """Worker thread for API calls to prevent UI freezing"""

    # Signals
    login_result = Signal(bool, str, dict)  # success, message, user_data
    pireps_result = Signal(bool, str, list, dict)  # success, message, pireps_data, meta
    airports_result = Signal(bool, str, list, dict)  # success, message, airports_list, meta
    preload_result = Signal(bool, str, dict)  # success, message, {airlines:[], fleet:[]}

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

    def set_pireps_operation(self, client, page: int = 1, limit: int = 50):
        """Set up PIREPs fetch operation"""
        self.operation = "pireps"
        self.client = client
        self._pireps_page = page
        self._pireps_limit = limit

    def set_airports_operation(self, client, page: int = 1, limit: int = 50):
        """Set up airports fetch operation"""
        self.operation = "airports"
        self.client = client
        self._airports_page = page
        self._airports_limit = limit


    def set_preload_operation(self, client):
        """Set up preload (airlines and fleet) operation"""
        self.operation = "preload"
        self.client = client

    def run(self):
        """Execute the operation in the background thread"""
        try:
            if self.operation == "login":
                self._do_login()
            elif self.operation == "pireps":
                self._do_fetch_pireps()
            elif self.operation == "airports":
                self._do_fetch_airports()
            elif self.operation == "preload":
                self._do_preload()
        except Exception as e:
            if self.operation == "login":
                self.login_result.emit(False, f"Unexpected error: {str(e)}", {})
            elif self.operation == "pireps":
                self.pireps_result.emit(False, f"Unexpected error: {str(e)}", [], {})
            elif self.operation == "airports":
                self.airports_result.emit(False, f"Unexpected error: {str(e)}", [], {})
            elif self.operation == "preload":
                self.preload_result.emit(False, f"Unexpected error: {str(e)}", {})

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
            response = self.client.get_user_pireps(page=getattr(self, '_pireps_page', 1), limit=getattr(self, '_pireps_limit', 50))
            pireps_data = response.get('data', [])
            meta = response.get('meta', {}) if isinstance(response, dict) else {}
            self.pireps_result.emit(True, f"Loaded {len(pireps_data)} PIREPs", pireps_data, meta)

        except PhpVmsApiException as e:
            self.pireps_result.emit(False, f"API Error: {e.message}", [], {})
        except Exception as e:
            self.pireps_result.emit(False, f"Error fetching PIREPs: {str(e)}", [], {})

    def _do_fetch_airports(self):
        try:
            response = self.client.get_airports(page=getattr(self, '_airports_page', 1), limit=getattr(self, '_airports_limit', 50))
            airports_data = response.get('data', [])
            meta = response.get('meta', {}) if isinstance(response, dict) else {}
            self.airports_result.emit(True, f"Loaded {len(airports_data)} airports", airports_data, meta)
        except PhpVmsApiException as e:
            self.airports_result.emit(False, f"API Error: {e.message}", [], {})
        except Exception as e:
            self.airports_result.emit(False, f"Error fetching airports: {str(e)}", [], {})


    def _do_preload(self):
        try:
            airlines_resp = self.client.get_airlines()
            fleet_resp = self.client.get_fleet()
            result = {
                'airlines': airlines_resp.get('data', []) if isinstance(airlines_resp, dict) else [],
                'fleet': fleet_resp.get('data', []) if isinstance(fleet_resp, dict) else [],
            }
            self.preload_result.emit(True, "Preload complete", result)
        except PhpVmsApiException as e:
            self.preload_result.emit(False, f"API Error: {e.message}", {})
        except Exception as e:
            self.preload_result.emit(False, f"Error during preload: {str(e)}", {})


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

        # Cache credentials (API key is sensitive; store unencrypted per requirements)
        settings = QSettings()
        settings.setValue("api/base_url", base_url)
        settings.setValue("api/api_key", api_key)

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
        self.rank_label = QLabel("-")
        self.flights_label = QLabel("-")
        self.flight_time_label = QLabel("-")
        self.current_airport_label = QLabel("-")

        user_layout.addRow("Name:", self.name_label)
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
        self.rank_label.setText(str(user_data.get('rank', {}).get('name', 'Unknown')))
        self.flights_label.setText(str(user_data.get('flights', 0)))

        # Convert flight time from minutes to hours:minutes
        flight_time_minutes = user_data.get('flight_time', 0)
        hours = flight_time_minutes // 60
        minutes = flight_time_minutes % 60
        self.flight_time_label.setText(f"{hours}h {minutes}m")

        self.current_airport_label.setText(user_data.get('curr_airport', 'Unknown'))


class AirportsWidget(QWidget):
    """Widget to display Airports list"""

    refresh_requested = Signal()
    page_change_requested = Signal(int)
    page_size_change_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Controls row
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.refresh_button)
        controls.addStretch()
        layout.addLayout(controls)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ICAO", "IATA", "Name", "City", "Country", "Latitude", "Longitude", "Elevation"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Pagination/footer controls
        footer = QHBoxLayout()
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.page_label = QLabel("Page 1/1")
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Go to page")
        self.page_input.setFixedWidth(90)
        self.page_input.setValidator(QIntValidator(1, 1000000, self))
        self.page_go_btn = QPushButton("Go")
        self.page_size_combo = QComboBox()
        for n in [10, 25, 50, 100]:
            self.page_size_combo.addItem(str(n), userData=n)
        self.page_size_combo.setCurrentText("25")
        self.prev_btn.clicked.connect(lambda: self.page_change_requested.emit(max(1, getattr(self, '_current_page', 1) - 1)))
        self.next_btn.clicked.connect(lambda: self.page_change_requested.emit(getattr(self, '_current_page', 1) + 1))
        self.page_size_combo.currentIndexChanged.connect(lambda: self.page_size_change_requested.emit(int(self.page_size_combo.currentText())))
        def _emit_go():
            try:
                txt = self.page_input.text().strip()
                if txt:
                    self.page_change_requested.emit(max(1, int(txt)))
            except Exception:
                pass
        self.page_go_btn.clicked.connect(_emit_go)
        self.page_input.returnPressed.connect(_emit_go)
        footer.addStretch()
        footer.addWidget(self.prev_btn)
        footer.addWidget(self.next_btn)
        footer.addWidget(self.page_label)
        footer.addWidget(self.page_input)
        footer.addWidget(self.page_go_btn)
        footer.addWidget(QLabel("Per page:"))
        footer.addWidget(self.page_size_combo)
        layout.addLayout(footer)

        self.setLayout(layout)

    def update_pagination(self, current_page: int, last_page: int, total: int):
        self._current_page = max(1, current_page)
        self._last_page = max(1, last_page)
        self._total = max(0, total)
        self.page_label.setText(f"Page {self._current_page}/{self._last_page} ({self._total})")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._last_page)
        try:
            self.page_input.setText(str(self._current_page))
        except Exception:
            pass


    def update_airports(self, airports: List[Dict[str, Any]]):
        self.table.setRowCount(len(airports))
        for row, ap in enumerate(airports):
            def g(key, default=""):
                return ap.get(key, default)
            icao = g('icao') or g('id') or g('icao_code') or g('icao_id')
            self.table.setItem(row, 0, QTableWidgetItem(str(icao or '')))
            self.table.setItem(row, 1, QTableWidgetItem(str(g('iata') or '')))
            self.table.setItem(row, 2, QTableWidgetItem(str(g('name') or '')))
            self.table.setItem(row, 3, QTableWidgetItem(str(g('city') or g('location') or '')))
            self.table.setItem(row, 4, QTableWidgetItem(str(g('country') or g('country_name') or '')))
            # lat/lon/elevation can be in various keys
            lat = ap.get('lat') or ap.get('latitude') or ap.get('ground_lat')
            lon = ap.get('lon') or ap.get('longitude') or ap.get('ground_lon')
            elev = ap.get('elevation') or ap.get('altitude')
            self.table.setItem(row, 5, QTableWidgetItem(str(lat or '')))
            self.table.setItem(row, 6, QTableWidgetItem(str(lon or '')))
            self.table.setItem(row, 7, QTableWidgetItem(str(elev or '')))

    def set_refresh_enabled(self, enabled: bool):
        self.refresh_button.setEnabled(enabled)


class CurrentFlightWidget(QWidget):
    """Widget for entering current flight information"""

    def __init__(self):
        super().__init__()
        # Action buttons wired by MainWindow
        self.prefile_button = QPushButton("Prefile")
        self.file_button = QPushButton("File PIREP")
        self.cancel_button = QPushButton("Cancel PIREP")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        form = QFormLayout()

        # SimBrief import controls
        simbrief_row = QHBoxLayout()
        self.simbrief_id_input = QLineEdit()
        self.simbrief_id_input.setPlaceholderText("SimBrief ID (numeric)")
        self.simbrief_id_input.setValidator(QIntValidator(0, 99999999, self))
        # Load cached SimBrief user id
        try:
            sb_id = QSettings().value("simbrief/userid", "")
            if sb_id:
                self.simbrief_id_input.setText(str(sb_id))
        except Exception:
            pass
        self.import_simbrief_button = QPushButton("Import SimBrief")
        simbrief_row.addWidget(self.simbrief_id_input)
        simbrief_row.addWidget(self.import_simbrief_button)
        simbrief_row.addStretch()
        form.addRow("SimBrief:", simbrief_row)

        self.airline_combo = QComboBox()
        form.addRow("Airline:", self.airline_combo)

        self.flight_number_input = QLineEdit()
        self.flight_number_input.setText("1")
        form.addRow("Flight Number:", self.flight_number_input)

        self.leg_input = QLineEdit()
        form.addRow("Leg:", self.leg_input)

        self.code_input = QLineEdit()
        form.addRow("Code:", self.code_input)

        self.flight_type_combo = QComboBox()
        # Populate with provided constants
        flight_types = [
            ("J", "Scheduled Pax"), ("F", "Scheduled Cargo"), ("C", "Charter Pax Only"),
            ("A", "Additional Cargo"), ("E", "VIP"), ("G", "Additional Pax"),
            ("H", "Charter Cargo/Mail"), ("I", "Ambulance"), ("K", "Training"),
            ("M", "Mail Service"), ("O", "Charter Special"), ("P", "Positioning"),
            ("T", "Technical Test"), ("W", "Military"), ("X", "Technical Stop"),
            ("S", "Shuttle"), ("B", "Additional Shuttle"), ("Q", "Cargo In Cabin"),
            ("R", "Addtl Cargo In Cabin"), ("L", "Charter Cargo In Cabin"),
            ("D", "General Aviation"), ("N", "Air Taxi"), ("Y", "Company Specific"), ("Z", "Other")
        ]
        for code, label in flight_types:
            self.flight_type_combo.addItem(f"{code} - {label}", userData=code)
        form.addRow("Flight Type:", self.flight_type_combo)

        self.aircraft_combo = QComboBox()
        self.aircraft_combo.setMinimumWidth(200)
        form.addRow("Aircraft:", self.aircraft_combo)

        self.dep_input = QLineEdit()
        form.addRow("Departure Airport:", self.dep_input)

        self.arr_input = QLineEdit()
        form.addRow("Arrival Airport:", self.arr_input)

        self.route_text = QTextEdit()
        self.route_text.setPlaceholderText("Enter route (free text)")
        form.addRow("Flight Route:", self.route_text)

        # New integer fields
        self.level_input = QLineEdit()
        self.level_input.setPlaceholderText("e.g., 350 (flight level)")
        self.level_input.setValidator(QIntValidator(0, 9999, self))
        form.addRow("Level:", self.level_input)

        self.planned_distance_input = QLineEdit()
        self.planned_distance_input.setPlaceholderText("nm (e.g., 425)")
        self.planned_distance_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Planned Distance:", self.planned_distance_input)

        self.planned_time_input = QLineEdit()
        self.planned_time_input.setPlaceholderText("minutes (e.g., 95)")
        self.planned_time_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Planned Flight Time:", self.planned_time_input)

        layout.addLayout(form)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.prefile_button)
        btn_row.addWidget(self.file_button)
        btn_row.addWidget(self.cancel_button)
        layout.addLayout(btn_row)

        layout.addStretch()
        self.setLayout(layout)

    def set_airlines(self, airlines: List[Dict[str, Any]]):
        self.airline_combo.clear()
        for a in airlines:
            name = a.get('name') or a.get('icao') or str(a.get('id'))
            self.airline_combo.addItem(str(name), userData=a)

    def set_fleet(self, fleet: List[Dict[str, Any]]):
        self.aircraft_combo.clear()
        
        def _normalize_ac_name(s: Any) -> str:
            try:
                s = str(s)
                if '|' in s:
                    left, sep, right = s.partition('|')
                    left = left.strip()
                    # Remove extraneous spaces between trailing letters and digits (e.g., "PHX 12" -> "PHX12")
                    left = re.sub(r'([A-Za-z])\s+(\d)', r'\1\2', left)
                    return f"{left} | {right.strip()}"
                # Fallback: apply to whole string
                return re.sub(r'([A-Za-z])\s+(\d)', r'\1\2', s)
            except Exception:
                return str(s)
        
        names = []
        for ac in fleet:
            raw = ac.get('name') or ac.get('registration') or ac.get('id')
            disp = _normalize_ac_name(raw)
            names.append((disp, ac))
        names.sort(key=lambda x: x[0])
        self.aircraft_combo.clear()
        for disp, ac in names:
            self.aircraft_combo.addItem(str(disp), userData=ac)


class PirepsWidget(QWidget):
    """Widget to display PIREPs table"""

    refresh_requested = Signal()
    page_change_requested = Signal(int)  # new page number
    page_size_change_requested = Signal(int)  # new page size (limit)
    cancel_selected_requested = Signal(str)  # emits selected PIREP id

    def __init__(self):
        super().__init__()
        self._current_page = 1
        self._last_page = 1
        self._total = 0
        self._limit = 25
        self._row_pirep_ids: List[str] = []
        self.setup_ui()

    def setup_ui(self):
        """Set up the PIREPs UI"""
        layout = QVBoxLayout()

        # Header with refresh + pagination controls
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Previous PIREPs"))
        header_layout.addStretch()

        # Pagination controls
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.page_label = QLabel("Page 1/1")
        self.page_size_combo = QComboBox()
        for n in [10, 25, 50, 100]:
            self.page_size_combo.addItem(str(n), userData=n)
        self.page_size_combo.setCurrentText(str(self._limit))
        self.prev_btn.clicked.connect(lambda: self.page_change_requested.emit(max(1, self._current_page - 1)))
        self.next_btn.clicked.connect(lambda: self.page_change_requested.emit(self._current_page + 1))
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)

        header_layout.addWidget(self.prev_btn)
        header_layout.addWidget(self.next_btn)
        header_layout.addWidget(self.page_label)
        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Go to page")
        self.page_input.setFixedWidth(90)
        self.page_input.setValidator(QIntValidator(1, 1000000, self))
        self.page_go_btn = QPushButton("Go")
        def _emit_go_pireps():
            try:
                txt = self.page_input.text().strip()
                if txt:
                    self.page_change_requested.emit(max(1, int(txt)))
            except Exception:
                pass
        self.page_go_btn.clicked.connect(_emit_go_pireps)
        self.page_input.returnPressed.connect(_emit_go_pireps)
        header_layout.addWidget(self.page_input)
        header_layout.addWidget(self.page_go_btn)
        header_layout.addWidget(QLabel("Per page:"))
        header_layout.addWidget(self.page_size_combo)

        # Note: Refresh and Cancel Selected buttons moved to left User Information pane for better space usage
        layout.addLayout(header_layout)

        # PIREPs table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Route", "State", "Date", "Duration", "Dist. (nm)"
        ])

        # Configure table
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

        self.setLayout(layout)

    def _on_cancel_selected_clicked(self):
        # Determine selected row and map to PIREP id
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No selection", "Please select a PIREP row to cancel.")
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self._row_pirep_ids):
            QMessageBox.warning(self, "Invalid selection", "Could not determine selected PIREP.")
            return
        pid = self._row_pirep_ids[row] if row < len(self._row_pirep_ids) else ""
        if not isinstance(pid, str) or not pid.strip():
            QMessageBox.warning(self, "Invalid PIREP", "Selected PIREP has no valid ID.")
            return
        self.cancel_selected_requested.emit(pid)

    def _on_page_size_changed(self):
        limit = int(self.page_size_combo.currentText())
        self._limit = limit
        self.page_size_change_requested.emit(limit)

    def update_pagination(self, current_page: int, last_page: int, total: int):
        self._current_page = max(1, current_page)
        self._last_page = max(1, last_page)
        self._total = max(0, total)
        self.page_label.setText(f"Page {self._current_page}/{self._last_page} ({self._total})")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < self._last_page)
        try:
            self.page_input.setText(str(self._current_page))
        except Exception:
            pass

    def update_pireps(self, pireps_data: List[Pirep]):
        """Update the PIREPs table"""
        self.table.setRowCount(len(pireps_data))
        self._row_pirep_ids = []

        for row, pirep in enumerate(pireps_data):
            try:
                pid = pirep.get('id')
            except Exception:
                pid = "-"
            self._row_pirep_ids.append(pid)

            # Route
            dep = pirep.get('dpt_airport_id', '')
            arr = pirep.get('arr_airport_id', '')
            route = f"{dep} → {arr}" if dep and arr else "N/A"
            self.table.setItem(row, 0, QTableWidgetItem(route))

            # State
            state_value = pirep.get('state', 0)
            try:
                state_name = PirepState(state_value).name
            except ValueError:
                state_name = f"Unknown ({state_value})"
            self.table.setItem(row, 1, QTableWidgetItem(state_name))

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
            self.table.setItem(row, 2, QTableWidgetItem(date_str))

            # Flight time
            flight_time = pirep.get('flight_time', 0)
            if flight_time:
                hours = flight_time // 60
                minutes = flight_time % 60
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = 'N/A'
            self.table.setItem(row, 3, QTableWidgetItem(time_str))

            # Distance
            distance = pirep.get('distance', {}).get('nmi', -1)
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
            distance_str = f"{distance_value:.0f}" if distance_value is not None else 'N/A'
            self.table.setItem(row, 4, QTableWidgetItem(distance_str))

    def set_refresh_enabled(self, enabled: bool):
        """Enable/disable refresh button (no-op if button is not present in this widget)."""
        try:
            if hasattr(self, 'refresh_button') and self.refresh_button is not None:
                self.refresh_button.setEnabled(enabled)
        except Exception:
            pass

    def get_selected_pirep_id(self) -> Optional[str]:
        """Return the PIREP ID (string) for the currently selected row, or None if not valid."""
        try:
            row = self.table.currentRow()
            if row is None or row < 0:
                return None
            if row >= len(self._row_pirep_ids):
                return None
            pid = self._row_pirep_ids[row]
            if isinstance(pid, str) and pid.strip():
                return pid
            return None
        except Exception:
            return None


class BridgeStatusWidget(QWidget):
    """Detailed status view for the UDP bridge."""
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self._last_log_len = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Top row with metrics
        row = QHBoxLayout()
        self.running_label = QLabel("Bridge: -")
        self.addr_label = QLabel("Addr: -")
        self.pkts_label = QLabel("Packets: 0 ok / 0 err")
        self.last_label = QLabel("Last: -")
        row.addWidget(self.running_label)
        row.addSpacing(12)
        row.addWidget(self.addr_label)
        row.addSpacing(12)
        row.addWidget(self.pkts_label)
        row.addSpacing(12)
        row.addWidget(self.last_label)
        row.addStretch()

        layout.addLayout(row)

        # Controls
        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Port (default 47777)")
        self.port_input.setFixedWidth(140)
        ctrl.addWidget(QLabel("UDP Port:"))
        ctrl.addWidget(self.port_input)
        ctrl.addSpacing(8)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Bridge log will appear here...")
        layout.addWidget(self.log_view)

        self.setLayout(layout)

        # Wire signals
        self.start_btn.clicked.connect(self.start_requested.emit)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

    def update_from_snapshot(self, snap: Dict[str, Any]):
        running = snap.get("running", False)
        host = snap.get("host", "127.0.0.1")
        port = snap.get("port", 47777)
        ok = snap.get("packets_ok", 0)
        err = snap.get("packets_err", 0)
        last_ts = snap.get("last_packet_time")
        last_time = "-"
        if isinstance(last_ts, (int, float)) and last_ts > 0:
            from datetime import datetime
            last_time = datetime.fromtimestamp(last_ts).strftime("%H:%M:%S")
        self.running_label.setText(f"Bridge: {'running' if running else 'stopped'}")
        self.addr_label.setText(f"Addr: {host}:{port}")
        self.pkts_label.setText(f"Packets: {ok} ok / {err} err")
        self.last_label.setText(f"Last: {last_time} | PIREP {snap.get('last_pirep_id') or '-'} {snap.get('last_status') or '-'}")

        logs = snap.get("log") or []
        # Only append new lines
        if isinstance(logs, list):
            if len(logs) != self._last_log_len:
                # show last ~300 lines to keep UI fast
                view_lines = logs[-300:]
                self.log_view.setPlainText("\n".join(view_lines))
                self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
                self._last_log_len = len(logs)

    def set_controls_state(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)


class MainWindow(QMainWindow):
    """Main application window"""

    @staticmethod
    def _parse_simbrief_ete_to_minutes(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            # If numeric, assume minutes if reasonable; if big, assume seconds
            if isinstance(value, (int, float)):
                v = int(value)
                if v > 0 and v < 60*24*24:
                    return v
                # If too big, guess it's seconds
                return int(round(v / 60))
            if not isinstance(value, str):
                return None
            s = value.strip()
            if not s:
                return None
            # ISO8601 like PT1H30M or PT90M
            if s.upper().startswith('PT'):
                hours = 0
                minutes = 0
                import re
                h = re.search(r"(\d+)H", s.upper())
                m = re.search(r"(\d+)M", s.upper())
                if h:
                    hours = int(h.group(1))
                if m:
                    minutes = int(m.group(1))
                return hours*60 + minutes
            # HH:MM[:SS]
            if ':' in s:
                parts = s.split(':')
                if len(parts) >= 2:
                    hh = int(parts[0]) if parts[0] else 0
                    mm = int(parts[1]) if parts[1] else 0
                    return hh*60 + mm
            # "0130" -> 1h30m style
            if s.isdigit() and len(s) in (3,4):
                hh = int(s[:-2])
                mm = int(s[-2:])
                return hh*60 + mm
            # Fallback: try int directly
            return int(s)
        except Exception:
            return None
    """Main application window"""

    def __init__(self):
        super().__init__()
        self._active_pirep_id = None
        self.client = None
        self.user_data = None
        # Active workers list to keep references until finished
        self._workers: List[ApiWorker] = []
        # Track in-flight operations for proper progress bar behavior
        self._inflight_ops = 0
        # Store last login credentials for client recreation
        self._base_url: Optional[str] = None
        self._api_key: Optional[str] = None
        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Set up the main UI"""
        self.setWindowTitle("phpVMS API Client")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Create widgets
        self.login_widget = LoginWidget()
        self.user_info_widget = UserInfoWidget()
        self.pireps_widget = PirepsWidget()
        self.airports_widget = AirportsWidget()
        self.current_flight_widget = CurrentFlightWidget()

        # Flights & info (existing) content inside a splitter
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel (user info)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.user_info_widget)

        # Actions under User Information: Refresh and Cancel Selected (moved from PIREPs header)
        actions_row = QHBoxLayout()
        self.pireps_refresh_btn = QPushButton("Refresh")
        self.pireps_cancel_btn = QPushButton("Cancel Selected")
        self.pireps_cancel_btn.setEnabled(False)
        actions_row.addWidget(self.pireps_refresh_btn)
        actions_row.addWidget(self.pireps_cancel_btn)
        actions_row.addStretch()
        left_layout.addLayout(actions_row)

        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)

        # Right panel (PIREPs)
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.pireps_widget)
        self.splitter.setSizes([300, 500])

        # Tab widget (created but added after login)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.current_flight_widget, "Current flight")
        self.tabs.addTab(self.airports_widget, "Airports")
        flights_info_container = QWidget()
        fic_layout = QVBoxLayout()
        fic_layout.setContentsMargins(0, 0, 0, 0)
        fic_layout.addWidget(self.splitter)
        flights_info_container.setLayout(fic_layout)
        self.tabs.addTab(flights_info_container, "PIREPs")
        # Bridge status tab (added now, but visible after login along with others)
        self.bridge_status_widget = BridgeStatusWidget()
        self.tabs.addTab(self.bridge_status_widget, "Status")
        self.tabs.setVisible(False)

        # Initially show login widget
        layout.addWidget(self.login_widget)
        layout.addWidget(self.tabs)

        # Initialize page size combos from saved settings
        try:
            self.pireps_widget.page_size_combo.setCurrentText(str(self._pireps_limit))
            self.airports_widget.page_size_combo.setCurrentText(str(self._airports_limit))
        except Exception:
            pass

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Please login to continue")

        # Bridge summary label (right side, before Logout)
        self.bridge_summary_label = QLabel("")
        self.bridge_summary_label.setVisible(False)

        # Logout button (initially hidden)
        self.logout_button = QPushButton("Logout")
        self.logout_button.setVisible(False)
        self.logout_button.clicked.connect(self.logout)
        
        # Internal caches and pagination state
        self._airport_icaos_cache = set()
        self._airports_list = []
        # Pagination defaults
        settings = QSettings()
        self._pireps_limit = int(settings.value("ui/pireps_limit", 25))
        self._pireps_page = 1
        self._airports_limit = int(settings.value("ui/airports_limit", 25))
        self._airports_page = 1

        # UDP Bridge runtime members
        self._udp_bridge: Optional[UdpBridge] = None
        self._bridge_timer: Optional[QTimer] = None

        # Active PIREP context
        self._active_pirep_id: Optional[str] = None
        self._workflow: Optional[PirepWorkflowManager] = None

    def setup_connections(self):
        """Set up signal connections"""
        # Login widget
        self.login_widget.login_requested.connect(self.on_login_requested)

        # PIREPs widget
        self.pireps_widget.refresh_requested.connect(self.refresh_pireps)
        self.pireps_widget.page_change_requested.connect(self._on_pireps_page_change)
        self.pireps_widget.page_size_change_requested.connect(self._on_pireps_page_size_change)
        self.pireps_widget.cancel_selected_requested.connect(self.on_cancel_selected_clicked)

        # Airports widget
        self.airports_widget.refresh_requested.connect(self.refresh_airports)
        self.airports_widget.page_change_requested.connect(self._on_airports_page_change)
        self.airports_widget.page_size_change_requested.connect(self._on_airports_page_size_change)

        # Worker signals are connected per-operation when spawning workers

        # Current flight actions
        self.current_flight_widget.prefile_button.clicked.connect(self.on_prefile_clicked)
        self.current_flight_widget.file_button.clicked.connect(self.on_file_clicked)
        self.current_flight_widget.cancel_button.clicked.connect(self.on_cancel_clicked)
        self.current_flight_widget.import_simbrief_button.clicked.connect(self.on_import_simbrief_clicked)

        # Left panel actions for PIREPs
        self.pireps_refresh_btn.clicked.connect(self.refresh_pireps)
        self.pireps_cancel_btn.clicked.connect(self.on_cancel_selected_left)
        # Enable/disable cancel based on selection presence
        try:
            self.pireps_widget.table.itemSelectionChanged.connect(self._on_pireps_selection_changed)
        except Exception:
            pass

    def _on_pireps_page_change(self, new_page: int):
        if new_page < 1:
            return
        self._pireps_page = new_page
        self.refresh_pireps()

    def _on_pireps_page_size_change(self, new_limit: int):
        if new_limit <= 0:
            return
        self._pireps_limit = new_limit
        QSettings().setValue("ui/pireps_limit", new_limit)
        self._pireps_page = 1
        self.refresh_pireps()

    def _on_airports_page_change(self, new_page: int):
        if new_page < 1:
            return
        self._airports_page = new_page
        self.refresh_airports()

    def _on_airports_page_size_change(self, new_limit: int):
        if new_limit <= 0:
            return
        self._airports_limit = new_limit
        QSettings().setValue("ui/airports_limit", new_limit)
        self._airports_page = 1
        self.refresh_airports()

    def _create_worker(self) -> ApiWorker:
        """Create a new worker for an operation and wire signals."""
        worker = ApiWorker()
        # Connect signals
        worker.login_result.connect(self.on_login_result)
        worker.pireps_result.connect(self.on_pireps_result)
        worker.airports_result.connect(self.on_airports_result)
        worker.preload_result.connect(self.on_preload_result)
        # Track and clean up
        worker.finished.connect(self._on_worker_finished)
        self._workers.append(worker)
        return worker

    def _on_worker_finished(self):
        # Remove finished worker from list
        sender = self.sender()
        try:
            self._workers.remove(sender)  # type: ignore
        except ValueError:
            pass
        # Decrement in-flight ops and hide progress if none left
        if self._inflight_ops > 0:
            self._inflight_ops -= 1
        if self._inflight_ops <= 0:
            self._inflight_ops = 0
            self.progress_bar.setVisible(False)

    def on_login_requested(self, base_url: str, api_key: str):
        """Handle login request"""
        self.status_bar.showMessage("Logging in...")
        self.show_progress(True)
        self.login_widget.set_login_enabled(False)

        # Store for later client creation
        self._base_url = base_url
        self._api_key = api_key
        # Start login in a new worker thread
        worker = self._create_worker()
        worker.set_login_operation(base_url, api_key)
        worker.start()

    def on_login_result(self, success: bool, message: str, user_data: Dict[str, Any]):
        """Handle login result"""
        self.show_progress(False)
        self.login_widget.set_login_enabled(True)

        if success:
            # Store client and user data
            if self._base_url and self._api_key:
                self.client = create_client(self._base_url, api_key=self._api_key)
            else:
                # Fallback: try to reconstruct from user settings (shouldn't happen normally)
                settings = QSettings()
                base_url = str(settings.value("api/base_url", ""))
                api_key = str(settings.value("api/api_key", ""))
                if base_url and api_key:
                    if not base_url.startswith(("http://", "https://")):
                        base_url = "https://" + base_url
                    self.client = create_client(base_url, api_key=api_key)
            self.user_data = user_data
            # Initialize workflow manager
            try:
                self._workflow = PirepWorkflowManager(self.client)
            except Exception:
                self._workflow = None

            # Save user_data to cache to avoid future login network calls
            try:
                settings = QSettings()
                settings.setValue("api/user_data", json.dumps(user_data))
                settings.setValue("api/user_cached_at", datetime.utcnow().isoformat() + "Z")
            except Exception:
                pass

            # Update UI
            self.user_info_widget.update_user_info(user_data)
            self.show_main_interface()
            self.status_bar.showMessage(f"Logged in as {user_data.get('name', 'Unknown')}")

            # Preload data for tabs
            self.preload_reference_data()
            # Load airports list
            self.refresh_airports()
            # Automatically fetch PIREPs
            self.refresh_pireps()
        else:
            QMessageBox.critical(self, "Login Failed", message)
            self.status_bar.showMessage("Login failed")

    def show_main_interface(self):
        """Switch to main interface after successful login"""
        # Hide login widget
        self.login_widget.setVisible(False)

        # Show main content (tabs)
        self.tabs.setVisible(True)

        # Add bridge summary and logout button to status bar (summary left of logout)
        if self.bridge_summary_label not in self.status_bar.children():
            self.status_bar.addPermanentWidget(self.bridge_summary_label, 1)
        self.bridge_summary_label.setVisible(True)
        self.logout_button.setVisible(True)
        self.status_bar.addPermanentWidget(self.logout_button)

        # Wire bridge tab controls
        self.bridge_status_widget.start_requested.connect(self._on_bridge_start)
        self.bridge_status_widget.stop_requested.connect(self._on_bridge_stop)

        # Start UDP bridge automatically with default port
        self._start_udp_bridge()

    def refresh_pireps(self):
        """Refresh PIREPs data"""
        if not self.client:
            return

        self.status_bar.showMessage("Loading PIREPs...")
        self.show_progress(True)
        try:
            self.pireps_refresh_btn.setEnabled(False)
        except Exception:
            pass

        # Start PIREPs fetch in its own worker thread
        worker = self._create_worker()
        worker.set_pireps_operation(self.client, page=getattr(self, '_pireps_page', 1), limit=getattr(self, '_pireps_limit', 25))
        worker.start()

    def refresh_airports(self):
        if not self.client:
            return
        self.status_bar.showMessage("Loading airports...")
        self.show_progress(True)
        self.airports_widget.set_refresh_enabled(False)
        worker = self._create_worker()
        worker.set_airports_operation(self.client, page=getattr(self, '_airports_page', 1), limit=getattr(self, '_airports_limit', 25))
        worker.start()


    def on_airports_result(self, success: bool, message: str, airports_data: List[Dict[str, Any]], meta: Dict[str, Any]):
        self.show_progress(False)
        self.airports_widget.set_refresh_enabled(True)
        if success:
            self._airports_list = airports_data
            # Update cache set
            self._airport_icaos_cache = set()
            for ap in airports_data:
                icao = ap.get('icao') or ap.get('id') or ap.get('icao_code') or ap.get('icao_id')
                if isinstance(icao, str):
                    self._airport_icaos_cache.add(icao.upper())
            self.airports_widget.update_airports(airports_data)
            # Update pagination controls based on meta
            current = int(meta.get('current_page') or meta.get('current') or 1)
            last = int(meta.get('last_page') or meta.get('last') or (current if len(airports_data) < self._airports_limit else current + 1))
            total = int(meta.get('total', len(airports_data))) if isinstance(meta, dict) else len(airports_data)
            self._airports_page = max(1, current)
            self.airports_widget.update_pagination(current, last, total)
            per_page = int(meta.get('per_page', self._airports_limit)) if isinstance(meta, dict) else self._airports_limit
            self._airports_limit = per_page
            try:
                self.airports_widget.page_size_combo.setCurrentText(str(per_page))
            except Exception:
                pass
            self.status_bar.showMessage(message)
        else:
            QMessageBox.warning(self, "Error", f"Failed to load airports: {message}")
            self.status_bar.showMessage("Failed to load airports")


    def preload_reference_data(self):
        if not self.client:
            return
        self.status_bar.showMessage("Loading reference data...")
        self.show_progress(True)
        worker = self._create_worker()
        worker.set_preload_operation(self.client)
        worker.start()

    def on_preload_result(self, success: bool, message: str, data: Dict[str, Any]):
        self.show_progress(False)
        if success:
            airlines = data.get('airlines', [])
            fleet = data.get('fleet', [])
            self.current_flight_widget.set_airlines(airlines)
            # Populate aircraft list from the first fleet only (user selects aircraft)
            aircraft_list: List[Dict[str, Any]] = []
            if isinstance(fleet, list) and len(fleet) > 0:
                first_fleet = fleet[0]
                # Some APIs may return 'aircraft' or 'aircrafts'
                if isinstance(first_fleet, dict):
                    aircraft_list = first_fleet.get('aircraft') or first_fleet.get('aircrafts') or []
                    if not isinstance(aircraft_list, list):
                        aircraft_list = []
            self.current_flight_widget.set_fleet(aircraft_list)
            self.status_bar.showMessage(message)
        else:
            QMessageBox.warning(self, "Error", f"Failed to preload data: {message}")
            self.status_bar.showMessage("Failed to preload data")

    def on_pireps_result(self, success: bool, message: str, pireps_data: List[Pirep], meta: Dict[str, Any]):
        """Handle PIREPs result"""
        self.show_progress(False)
        try:
            self.pireps_refresh_btn.setEnabled(True)
        except Exception:
            pass
        # After load, disable cancel until a valid selection is made
        try:
            self.pireps_cancel_btn.setEnabled(False)
        except Exception:
            pass

        if success:
            self.pireps_widget.update_pireps(pireps_data)
            # Update pagination controls based on meta
            current = int(meta.get('current_page') or meta.get('current') or 1)
            last = int(meta.get('last_page') or meta.get('last') or (current if len(pireps_data) < self._pireps_limit else current + 1))
            total = int(meta.get('total', len(pireps_data))) if isinstance(meta, dict) else len(pireps_data)
            self._pireps_page = max(1, current)
            self.pireps_widget.update_pagination(current, last, total)
            # Update page size combo to reflect per_page if provided
            per_page = int(meta.get('per_page', self._pireps_limit)) if isinstance(meta, dict) else self._pireps_limit
            self._pireps_limit = per_page
            try:
                self.pireps_widget.page_size_combo.setCurrentText(str(per_page))
            except Exception:
                pass
            self.status_bar.showMessage(message)
        else:
            QMessageBox.warning(self, "Error", f"Failed to load PIREPs: {message}")
            self.status_bar.showMessage("Failed to load PIREPs")

    def on_import_simbrief_clicked(self):
        """Fetch SimBrief OFP JSON and populate current flight fields."""
        try:
            sb_id = self.current_flight_widget.simbrief_id_input.text().strip()
            if not sb_id:
                QMessageBox.information(self, "SimBrief", "Please enter your SimBrief ID.")
                return
            # Persist the SimBrief ID
            try:
                QSettings().setValue("simbrief/userid", sb_id)
            except Exception:
                pass
            # Build URL
            url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={sb_id}&json=1"
            self.status_bar.showMessage("Importing SimBrief...")
            self.show_progress(True)
            # Disable import button
            try:
                self.current_flight_widget.import_simbrief_button.setEnabled(False)
            except Exception:
                pass
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.show_progress(False)
            try:
                self.current_flight_widget.import_simbrief_button.setEnabled(True)
            except Exception:
                pass
            QMessageBox.warning(self, "SimBrief Import Failed", str(e))
            self.status_bar.showMessage("SimBrief import failed")
            return
        finally:
            pass

        # Parse and populate fields
        try:
            origin = ((data or {}).get("origin") or {})
            dest = ((data or {}).get("destination") or {})
            general = ((data or {}).get("general") or {})
            times = ((data or {}).get("times") or {})

            dep_icao = origin.get("icao_code") or origin.get("icao") or origin.get("iata_code") or ""
            arr_icao = dest.get("icao_code") or dest.get("icao") or dest.get("iata_code") or ""
            if dep_icao:
                self.current_flight_widget.dep_input.setText(str(dep_icao).upper())
            if arr_icao:
                self.current_flight_widget.arr_input.setText(str(arr_icao).upper())

            route = general.get("route") or general.get("route_text") or ""
            if route:
                self.current_flight_widget.route_text.setPlainText(str(route))

            init_alt = general.get("initial_altitude")
            if init_alt is not None:
                self.current_flight_widget.level_input.setText(str(init_alt))

            rdist = general.get("route_distance")
            try:
                if rdist is not None and str(rdist).strip() != "":
                    self.current_flight_widget.planned_distance_input.setText(str(int(float(rdist))))
            except Exception:
                pass

            ete_val = int(times.get("est_time_enroute")) / 60
            minutes = self._parse_simbrief_ete_to_minutes(ete_val)
            if minutes is not None:
                self.current_flight_widget.planned_time_input.setText(str(int(minutes)))

            self.status_bar.showMessage("SimBrief OFP imported")
        finally:
            self.show_progress(False)
            try:
                self.current_flight_widget.import_simbrief_button.setEnabled(True)
            except Exception:
                pass

    def on_prefile_clicked(self):
        if not self.client:
            QMessageBox.information(self, "Not logged in", "Please login first.")
            return
        if not self._workflow:
            try:
                self._workflow = PirepWorkflowManager(self.client)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Workflow init failed: {e}")
                return
        try:
            airline = self.current_flight_widget.airline_combo.currentData()
            aircraft = self.current_flight_widget.aircraft_combo.currentData()
            flight_number = self.current_flight_widget.flight_number_input.text().strip() or None
            dpt = self.current_flight_widget.dep_input.text().strip().upper()
            arr = self.current_flight_widget.arr_input.text().strip().upper()
            route = self.current_flight_widget.route_text.toPlainText().strip() or None
            level_text = self.current_flight_widget.level_input.text().strip()
            planned_distance_text = self.current_flight_widget.planned_distance_input.text().strip()
            planned_time_text = self.current_flight_widget.planned_time_input.text().strip()
            level = int(level_text) if level_text != "" else None
            planned_distance = int(planned_distance_text) if planned_distance_text != "" else None
            planned_flight_time = int(planned_time_text) if planned_time_text != "" else None
            flight_data: Dict[str, Any] = {
                "airline_id": int(airline.get('id')) if isinstance(airline, dict) and airline.get('id') else None,
                "aircraft_id": int(aircraft.get('id')) if isinstance(aircraft, dict) and aircraft.get('id') else None,
                "flight_number": int(flight_number),
                "dpt_airport_id": dpt,
                "arr_airport_id": arr,
                "route": route,
                "level": level,
                "planned_distance": planned_distance,
                "planned_flight_time": planned_flight_time,
                "source": 1,
                "source_name": "XPlane12",
            }
            # Remove None values
            flight_data = {k: v for k, v in flight_data.items() if v is not None}
            if not flight_data.get('airline_id') or not flight_data.get('aircraft_id') or not dpt or not arr:
                QMessageBox.warning(self, "Missing fields", "Please select airline, aircraft, and enter both departure and arrival.")
                return
            self.show_progress(True)
            pirep = self._workflow.start_flight(flight_data)
        except Exception as e:
            self.show_progress(False)
            QMessageBox.warning(self, "Prefile failed", str(e))
            return
        finally:
            pass
        self.show_progress(False)
        try:
            pid = str(pirep.get('id'))
            self._active_pirep_id = pid
            # also reflect in user_data for persistence, if desired
            try:
                if isinstance(self.user_data, dict):
                    self.user_data['last_pirep_id'] = pid
            except Exception:
                pass
            self.status_bar.showMessage(f"Prefiled PIREP #{pid} (IN_PROGRESS)")
        except Exception:
            self.status_bar.showMessage("Prefiled PIREP (id unknown)")

    def on_cancel_clicked(self):
        if not self.client or not self._workflow:
            return
        if not self._active_pirep_id:
            QMessageBox.information(self, "No active PIREP", "There is no active PIREP to cancel.")
            return
        pid = self._active_pirep_id
        confirm = QMessageBox.question(self, "Cancel PIREP", f"Cancel PIREP {pid}?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self.show_progress(True)
        try:
            self._workflow.cancel_flight(pid)
        except Exception as e:
            QMessageBox.warning(self, "Cancel failed", str(e))
        finally:
            self.show_progress(False)
        self._active_pirep_id = None
        self.status_bar.showMessage(f"Cancelled PIREP #{pid}")

    def on_file_clicked(self):
        if not self.client or not self._workflow:
            return
        if not self._active_pirep_id:
            QMessageBox.information(self, "No active PIREP", "There is no active PIREP to file.")
            return
        pid = self._active_pirep_id
        # Minimal final data; phpVMS may accept partial; user can edit later in web UI if needed
        final_data: Dict[str, Any] = {
            "notes": "Filed from Python client",
            "route": self.current_flight_widget.route_text.toPlainText().strip() or None,
        }
        # Include planned fields if still available
        try:
            level_text = self.current_flight_widget.level_input.text().strip()
            planned_distance_text = self.current_flight_widget.planned_distance_input.text().strip()
            planned_time_text = self.current_flight_widget.planned_time_input.text().strip()
            if level_text != "":
                final_data["level"] = int(level_text)
            if planned_distance_text != "":
                final_data["planned_distance"] = int(planned_distance_text)
            if planned_time_text != "":
                final_data["planned_flight_time"] = int(planned_time_text)
        except Exception:
            pass
        final_data = {k: v for k, v in final_data.items() if v is not None}
        self.show_progress(True)
        try:
            self._workflow.complete_flight(pid, final_data)
        except Exception as e:
            self.show_progress(False)
            QMessageBox.warning(self, "File failed", str(e))
            return
        self.show_progress(False)
        self.status_bar.showMessage(f"Filed PIREP #{pid} (PENDING)")
        # After filing, consider no longer active
        self._active_pirep_id = None

    def on_cancel_selected_clicked(self, pid: str):
        """Cancel the selected PIREP from the Flights tab, respecting state rules."""
        if not self.client:
            QMessageBox.information(self, "Not logged in", "Please login first.")
            return
        if not self._workflow:
            try:
                self._workflow = PirepWorkflowManager(self.client)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Workflow init failed: {e}")
                return
        confirm = QMessageBox.question(self, "Cancel PIREP", f"Cancel PIREP {pid}?", QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self.show_progress(True)
        try:
            self._workflow.cancel_flight(pid)
        except Exception as e:
            QMessageBox.warning(self, "Cancel failed", str(e))
        finally:
            self.show_progress(False)
        self.status_bar.showMessage(f"Cancelled PIREP {pid}")
        # Refresh PIREPs list to reflect state change
        self.refresh_pireps()

    def on_cancel_selected_left(self):
        """Triggered by the left-pane 'Cancel Selected' button; acts on selected PIREP in the table."""
        pid = self.pireps_widget.get_selected_pirep_id()
        if not pid:
            QMessageBox.information(self, "No selection", "Select a PIREP to cancel.")
            return
        self.on_cancel_selected_clicked(pid)

    def _on_pireps_selection_changed(self):
        """Enable/disable the Cancel Selected button based on selection validity."""
        try:
            has_valid = bool(self.pireps_widget.get_selected_pirep_id())
            self.pireps_cancel_btn.setEnabled(has_valid)
        except Exception:
            try:
                self.pireps_cancel_btn.setEnabled(False)
            except Exception:
                pass

    def logout(self):
        """Handle logout"""
        # Stop bridge and timer
        self._stop_udp_bridge()

        # Clear data
        self.client = None
        self.user_data = None
        self._workflow = None
        self._active_pirep_id = None

        # Hide main interface
        self.tabs.setVisible(False)
        self.logout_button.setVisible(False)
        self.bridge_summary_label.setVisible(False)

        # Show login widget
        self.login_widget.setVisible(True)

        # Clear status
        self.status_bar.showMessage("Ready - Please login to continue")

    def _on_bridge_start(self):
        # If user entered a port, restart on that port
        self._start_udp_bridge()

    def _on_bridge_stop(self):
        self._stop_udp_bridge()

    def _start_udp_bridge(self):
        if not self.client:
            return
        # Read desired host/port
        host = getattr(self.bridge_status_widget, 'host_input', None).text().strip() if hasattr(self.bridge_status_widget, 'host_input') else "0.0.0.0"
        if not host:
            host = "0.0.0.0"
        port = 47777
        try:
            text = self.bridge_status_widget.port_input.text().strip()
            if text:
                port = int(text)
        except Exception:
            port = 47777
        # If already running on same host/port, just ensure timer exists
        if self._udp_bridge and self._udp_bridge.is_running() and getattr(self._udp_bridge, 'port', None) == port and getattr(self._udp_bridge, 'host', None) == host:
            self._ensure_bridge_timer()
            return
        # Stop existing
        if self._udp_bridge:
            try:
                self._udp_bridge.stop()
            except Exception:
                pass
        # Create/start new with active PIREP provider
        pid_provider = (lambda: self._active_pirep_id)
        try:
            self._udp_bridge = UdpBridge(self.client, pirep_id_provider=pid_provider, host=host, port=port)
        except TypeError:
            self._udp_bridge = UdpBridge(self.client, port=port)
            try:
                if hasattr(self._udp_bridge, '_pirep_id_provider'):
                    setattr(self._udp_bridge, '_pirep_id_provider', pid_provider)
                if hasattr(self._udp_bridge, 'host'):
                    setattr(self._udp_bridge, 'host', host)
            except Exception:
                pass
        self._udp_bridge.start()
        self._ensure_bridge_timer()

    def _stop_udp_bridge(self):
        if self._bridge_timer:
            self._bridge_timer.stop()
            self._bridge_timer = None
        if self._udp_bridge:
            try:
                self._udp_bridge.stop()
            except Exception:
                pass
        self.bridge_status_widget.set_controls_state(False)
        self.bridge_summary_label.setText("")

    def _ensure_bridge_timer(self):
        if not self._bridge_timer:
            self._bridge_timer = QTimer(self)
            self._bridge_timer.setInterval(1000)
            self._bridge_timer.timeout.connect(self._update_bridge_status_ui)
        if not self._bridge_timer.isActive():
            self._bridge_timer.start()
        # Immediate update
        self._update_bridge_status_ui()

    def _update_bridge_status_ui(self):
        if not self._udp_bridge:
            return
        snap = self._udp_bridge.status_snapshot()
        # Update status bar summary
        self.bridge_summary_label.setText(self._udp_bridge.status_summary())
        self.bridge_status_widget.update_from_snapshot(snap)
        self.bridge_status_widget.set_controls_state(snap.get("running", False))

    def show_progress(self, show: bool):
        """Refcounted progress indicator across concurrent operations."""
        if show:
            self._inflight_ops += 1
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        else:
            if self._inflight_ops > 0:
                self._inflight_ops -= 1
            if self._inflight_ops <= 0:
                self._inflight_ops = 0
                self.progress_bar.setVisible(False)

    def try_auto_login(self, base_url: str, api_key: str):
        """Attempt to skip a network login by using cached user data.
        If cached user data is available, set up the client and UI directly.
        Otherwise, fallback to the normal login flow (which makes a network call).
        """
        # Normalize base_url
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url
        self._base_url = base_url
        self._api_key = api_key

        # Load cached user_data
        settings = QSettings()
        cached_user_json = settings.value("api/user_data", "")
        user_data = None
        if isinstance(cached_user_json, str) and cached_user_json.strip():
            try:
                user_data = json.loads(cached_user_json)
            except Exception:
                user_data = None

        if user_data:
            # Use cached user data; avoid calling get_current_user
            self.client = create_client(base_url, api_key=api_key)
            self.user_data = user_data
            self.user_info_widget.update_user_info(user_data)
            self.show_main_interface()
            self.status_bar.showMessage(f"Logged in (cached) as {user_data.get('name', 'Unknown')}")

            # Proceed to load other data
            self.preload_reference_data()
            self.refresh_airports()
            self.refresh_pireps()
        else:
            # No cached user; fallback to network login
            self.on_login_requested(base_url, api_key)


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

    # Attempt auto-login if cached credentials exist
    settings = QSettings()
    cached_base_url = settings.value("api/base_url", "")
    cached_api_key = settings.value("api/api_key", "")
    if cached_base_url and cached_api_key:
        base_url = str(cached_base_url)
        api_key = str(cached_api_key)
        # Try to use cached user data to avoid a login network call
        window.try_auto_login(base_url, api_key)

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
