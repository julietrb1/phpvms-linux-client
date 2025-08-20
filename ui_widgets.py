"""
UI Widgets for phpVMS client, extracted from the monolithic UI file
- LoginWidget
- UserInfoWidget
- AirportsWidget
- CurrentFlightWidget
- PirepsWidget
- BridgeStatusWidget
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox, QFormLayout, QTextEdit, QHeaderView, QComboBox
)

from vms_types import Pirep
try:
    # Only used for state display and selection logic inside PirepsWidget
    from phpvms_api_client import PirepState
except Exception:  # pragma: no cover
    class PirepState:  # type: ignore
        IN_PROGRESS = type("EnumValue", (), {"value": 0})


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


class UserInfoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

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

        self.alt_input = QLineEdit()
        form.addRow("Alternate Airport:", self.alt_input)

        self.route_text = QTextEdit()
        self.route_text.setPlaceholderText("Enter route (free text)")
        form.addRow("Flight Route:", self.route_text)

        # New integer fields
        self.level_input = QLineEdit()
        self.level_input.setPlaceholderText("ft")
        self.level_input.setValidator(QIntValidator(0, 9999, self))
        form.addRow("Level:", self.level_input)

        self.planned_distance_input = QLineEdit()
        self.planned_distance_input.setPlaceholderText("nm")
        self.planned_distance_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Planned Distance:", self.planned_distance_input)

        self.planned_time_input = QLineEdit()
        self.planned_time_input.setPlaceholderText("minutes")
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
        self._row_states: List[Optional[int]] = []
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
        self._row_states = []

        for row, pirep in enumerate(pireps_data):
            try:
                pid = pirep.get('id')
            except Exception:
                pid = "-"
            self._row_pirep_ids.append(pid)

            # State tracking for selection logic
            state_value = pirep.get('state', 0)
            try:
                state_int = int(state_value)
            except Exception:
                state_int = None
            self._row_states.append(state_int)

            # Route
            dep = pirep.get('dpt_airport_id', '')
            arr = pirep.get('arr_airport_id', '')
            route = f"{dep} → {arr}" if dep and arr else "N/A"
            self.table.setItem(row, 0, QTableWidgetItem(route))

            # State
            state_value = pirep.get('state', 0)
            try:
                state_name = PirepState(state_value).name
            except Exception:
                state_name = f"Unknown ({state_value})"
            self.table.setItem(row, 1, QTableWidgetItem(state_name))

            # Date
            created_at = pirep.get('created_at', '')
            if created_at:
                try:
                    # Parse ISO date and format it nicely
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d %H:%M')
                except Exception:
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

    def get_selected_pirep_state(self) -> Optional[int]:
        """Return the state int for the currently selected row, or None."""
        try:
            row = self.table.currentRow()
            if row is None or row < 0:
                return None
            if row >= len(self._row_states):
                return None
            return self._row_states[row]
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
            from datetime import datetime as _dt
            last_time = _dt.fromtimestamp(last_ts).strftime("%H:%M:%S")
        self.running_label.setText(f"Bridge: {'running' if running else 'stopped'}")
        self.addr_label.setText(f"Addr: {host}:{port}")
        self.pkts_label.setText(f"Packets: {ok} ok / {err} err")
        self.last_label.setText(f"Last: {last_time} | {snap.get('last_status') or '-'}")

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
