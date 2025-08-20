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
import json
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QStatusBar, QGroupBox, QFormLayout, QTextEdit,
    QHeaderView, QProgressBar, QSplitter, QTabWidget, QComboBox
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
    pireps_result = Signal(bool, str, list, dict)  # success, message, pireps_data, meta
    airports_result = Signal(bool, str, list, dict)  # success, message, airports_list, meta
    lookup_airport_result = Signal(bool, str, dict)  # success, message, airport_data
    preload_result = Signal(bool, str, dict)  # success, message, {airlines:[], fleet:[]}

    def __init__(self):
        super().__init__()
        self.client = None
        self.operation = None
        self.base_url = None
        self.api_key = None
        self.lookup_icao = None

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

    def set_lookup_airport_operation(self, client, icao: str):
        """Set up airport lookup operation"""
        self.operation = "lookup_airport"
        self.client = client
        self.lookup_icao = icao

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
            elif self.operation == "lookup_airport":
                self._do_lookup_airport()
            elif self.operation == "preload":
                self._do_preload()
        except Exception as e:
            if self.operation == "login":
                self.login_result.emit(False, f"Unexpected error: {str(e)}", {})
            elif self.operation == "pireps":
                self.pireps_result.emit(False, f"Unexpected error: {str(e)}", [], {})
            elif self.operation == "airports":
                self.airports_result.emit(False, f"Unexpected error: {str(e)}", [], {})
            elif self.operation == "lookup_airport":
                self.lookup_airport_result.emit(False, f"Unexpected error: {str(e)}", {})
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

    def _do_lookup_airport(self):
        try:
            response = self.client.lookup_airport(self.lookup_icao)
            airport_data = response.get('data', {}) if isinstance(response, dict) else response
            self.lookup_airport_result.emit(True, f"Lookup complete for {self.lookup_icao}", airport_data or {})
        except PhpVmsApiException as e:
            self.lookup_airport_result.emit(False, f"API Error: {e.message}", {})
        except Exception as e:
            self.lookup_airport_result.emit(False, f"Error looking up airport: {str(e)}", {})

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
    """Widget to display Airports and perform lookup"""

    refresh_requested = Signal()
    lookup_requested = Signal(str)  # ICAO
    page_change_requested = Signal(int)
    page_size_change_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Controls row
        controls = QHBoxLayout()
        controls.addWidget(QLabel("ICAO:"))
        self.lookup_input = QLineEdit()
        self.lookup_input.setPlaceholderText("e.g., KJFK")
        self.lookup_input.setMaxLength(6)
        # Make it about 20% shorter than its default suggested width
        try:
            w = self.lookup_input.sizeHint().width()
            self.lookup_input.setFixedWidth(int(w * 0.8))
        except Exception:
            pass
        controls.addWidget(self.lookup_input)

        # Inline info label to display last lookup details
        self.lookup_info_label = QLabel("")
        self.lookup_info_label.setStyleSheet("color: #555;")
        self.lookup_info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        controls.addWidget(self.lookup_info_label)

        self.lookup_btn = QPushButton("Lookup")
        self.lookup_btn.clicked.connect(self._on_lookup_clicked)
        controls.addWidget(self.lookup_btn)
        controls.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.refresh_button)
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
        self.page_size_combo = QComboBox()
        for n in [10, 25, 50, 100]:
            self.page_size_combo.addItem(str(n), userData=n)
        self.page_size_combo.setCurrentText("25")
        self.prev_btn.clicked.connect(lambda: self.page_change_requested.emit(max(1, getattr(self, '_current_page', 1) - 1)))
        self.next_btn.clicked.connect(lambda: self.page_change_requested.emit(getattr(self, '_current_page', 1) + 1))
        self.page_size_combo.currentIndexChanged.connect(lambda: self.page_size_change_requested.emit(int(self.page_size_combo.currentText())))
        footer.addStretch()
        footer.addWidget(self.prev_btn)
        footer.addWidget(self.next_btn)
        footer.addWidget(self.page_label)
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

    def _on_lookup_clicked(self):
        icao = self.lookup_input.text().strip().upper()
        if not icao:
            QMessageBox.warning(self, "Lookup", "Please enter an ICAO code")
            return
        self.lookup_requested.emit(icao)

    def set_lookup_info(self, airport: Optional[Dict[str, Any]]):
        """Display brief info about the looked-up airport next to the input."""
        if not airport:
            self.lookup_info_label.setText("")
            self.lookup_info_label.setToolTip("")
            return
        icao = airport.get('icao') or airport.get('id') or ''
        name = airport.get('name') or ''
        city = airport.get('city') or airport.get('location') or ''
        country = airport.get('country') or airport.get('country_name') or ''
        iata = airport.get('iata') or ''
        brief = f"{icao} {f'({iata})' if iata else ''} - {name}".strip()
        self.lookup_info_label.setText(brief)
        # Tooltip with more details
        lat = airport.get('lat') or airport.get('latitude') or airport.get('ground_lat') or ''
        lon = airport.get('lon') or airport.get('longitude') or airport.get('ground_lon') or ''
        elev = airport.get('elevation') or airport.get('altitude') or ''
        tooltip = f"Name: {name}\nCity: {city}\nCountry: {country}\nLat: {lat}  Lon: {lon}\nElevation: {elev}"
        self.lookup_info_label.setToolTip(tooltip)

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
        self.lookup_btn.setEnabled(enabled)


class CurrentFlightWidget(QWidget):
    """Widget for entering current flight information"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        form = QFormLayout()

        self.airline_combo = QComboBox()
        form.addRow("Airline:", self.airline_combo)

        self.flight_number_input = QLineEdit()
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

        layout.addLayout(form)
        layout.addStretch()
        self.setLayout(layout)

    def set_airlines(self, airlines: List[Dict[str, Any]]):
        self.airline_combo.clear()
        for a in airlines:
            name = a.get('name') or a.get('icao') or str(a.get('id'))
            self.airline_combo.addItem(str(name), userData=a)

    def set_fleet(self, fleet: List[Dict[str, Any]]):
        self.aircraft_combo.clear()
        for ac in fleet:
            name = ac.get('name') or ac.get('registration') or str(ac.get('id'))
            self.aircraft_combo.addItem(str(name), userData=ac)


class PirepsWidget(QWidget):
    """Widget to display PIREPs table"""

    refresh_requested = Signal()
    page_change_requested = Signal(int)  # new page number
    page_size_change_requested = Signal(int)  # new page size (limit)

    def __init__(self):
        super().__init__()
        self._current_page = 1
        self._last_page = 1
        self._total = 0
        self._limit = 25
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
        header_layout.addWidget(QLabel("Per page:"))
        header_layout.addWidget(self.page_size_combo)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        header_layout.addWidget(self.refresh_button)

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

    def update_pireps(self, pireps_data: List[Pirep]):
        """Update the PIREPs table"""
        self.table.setRowCount(len(pireps_data))

        for row, pirep in enumerate(pireps_data):
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
        """Enable/disable refresh button"""
        self.refresh_button.setEnabled(enabled)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
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
        self.tabs.addTab(flights_info_container, "Flights")
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

        # Logout button (initially hidden)
        self.logout_button = QPushButton("Logout")
        self.logout_button.setVisible(False)
        self.logout_button.clicked.connect(self.logout)
        
        # Internal caches and pagination state
        self._airport_icaos_cache = set()
        self._airports_list = []
        self._airport_lookup_cache: Dict[str, Dict[str, Any]] = {}
        # Pagination defaults
        settings = QSettings()
        self._pireps_limit = int(settings.value("ui/pireps_limit", 25))
        self._pireps_page = 1
        self._airports_limit = int(settings.value("ui/airports_limit", 25))
        self._airports_page = 1

    def setup_connections(self):
        """Set up signal connections"""
        # Login widget
        self.login_widget.login_requested.connect(self.on_login_requested)

        # PIREPs widget
        self.pireps_widget.refresh_requested.connect(self.refresh_pireps)
        self.pireps_widget.page_change_requested.connect(self._on_pireps_page_change)
        self.pireps_widget.page_size_change_requested.connect(self._on_pireps_page_size_change)

        # Airports widget
        self.airports_widget.refresh_requested.connect(self.refresh_airports)
        self.airports_widget.lookup_requested.connect(self.lookup_airport)
        self.airports_widget.page_change_requested.connect(self._on_airports_page_change)
        self.airports_widget.page_size_change_requested.connect(self._on_airports_page_size_change)

        # Worker signals are connected per-operation when spawning workers

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
        worker.lookup_airport_result.connect(self.on_lookup_airport_result)
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

    def lookup_airport(self, icao: str):
        if not self.client:
            return
        # Remember whether we already had it
        already_cached = icao.upper() in self._airport_icaos_cache
        self._pending_lookup_was_new = not already_cached
        self._pending_lookup_icao = icao.upper()

        self.status_bar.showMessage(f"Looking up {icao}...")
        self.show_progress(True)
        self.airports_widget.set_refresh_enabled(False)
        worker = self._create_worker()
        worker.set_lookup_airport_operation(self.client, icao.upper())
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

    def on_lookup_airport_result(self, success: bool, message: str, airport_data: Dict[str, Any]):
        self.show_progress(False)
        # Re-enable buttons
        self.airports_widget.set_refresh_enabled(True)
        if success:
            self.status_bar.showMessage(message)
            # Keep the looked-up airport only in memory and display it next to the input
            if not hasattr(self, '_airport_lookup_cache'):
                self._airport_lookup_cache: Dict[str, Dict[str, Any]] = {}
            icao = (self._pending_lookup_icao if hasattr(self, '_pending_lookup_icao') else '') or airport_data.get('icao') or airport_data.get('id') or ''
            if isinstance(icao, str):
                self._airport_lookup_cache[icao.upper()] = airport_data or {}
            self.airports_widget.set_lookup_info(airport_data or {})
        else:
            self.airports_widget.set_lookup_info(None)
            QMessageBox.warning(self, "Lookup Failed", message)
            self.status_bar.showMessage("Lookup failed")

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
        self.pireps_widget.set_refresh_enabled(True)

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

    def logout(self):
        """Handle logout"""
        # Clear data
        self.client = None
        self.user_data = None

        # Hide main interface
        self.tabs.setVisible(False)
        self.logout_button.setVisible(False)

        # Show login widget
        self.login_widget.setVisible(True)

        # Clear status
        self.status_bar.showMessage("Ready - Please login to continue")

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
