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
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QStatusBar, QProgressBar, QSplitter, QTabWidget
)

from airports_widget import AirportsWidget
from bridge_status_widget import BridgeStatusWidget
from current_flight_widget import CurrentFlightWidget
from login_widget import LoginWidget
from pireps_widget import PirepsWidget
from udp_bridge import UdpBridge
from user_info_widget import UserInfoWidget
from vms_types import Pirep

NO_ACTIVE_TEXT = "(no active)"

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
                if 0 < v < 60*24*24:
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
        self._initial_block_fuel_kg = None
        self.tabs = None
        self.bridge_status_widget = None
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
        self.setMinimumSize(800, 800)

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

        # Actions under User Information: Refresh / Set Active / Cancel Selected (moved from PIREPs header)
        actions_row = QHBoxLayout()
        self.pireps_refresh_btn = QPushButton("Refresh")
        self.pireps_set_active_btn = QPushButton("Set Active")
        self.pireps_cancel_btn = QPushButton("Cancel")
        self.pireps_set_active_btn.setEnabled(False)
        self.pireps_cancel_btn.setEnabled(False)
        actions_row.addWidget(self.pireps_refresh_btn)
        actions_row.addWidget(self.pireps_set_active_btn)
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
        flights_info_container = QWidget()
        fic_layout = QVBoxLayout()
        fic_layout.setContentsMargins(0, 0, 0, 0)
        fic_layout.addWidget(self.splitter)
        flights_info_container.setLayout(fic_layout)
        self.tabs.addTab(flights_info_container, "PIREPs")
        self.tabs.addTab(self.airports_widget, "Airports")
        self.bridge_status_widget = BridgeStatusWidget()
        self.tabs.addTab(self.bridge_status_widget, "Status")
        self.tabs.setVisible(False)

        # Initialize API debug checkbox from settings
        settings = QSettings()
        debug_enabled = bool(settings.value("api/debug", False, type=bool))
        try:
            self.bridge_status_widget.set_debug_checked(debug_enabled)
        except Exception:
            pass

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

        # Active PIREP summary label (shows route or '(no active)')
        self.active_pirep_label = QLabel(NO_ACTIVE_TEXT)
        self.active_pirep_label.setVisible(False)

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
        # Snapshot of block fuel (kg) taken at flight start; not affected by later UI edits
        self._initial_block_fuel_kg: Optional[float] = None

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
        self.pireps_set_active_btn.clicked.connect(self.on_set_active_selected_left)
        # Enable/disable action buttons based on selection presence/state
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
                # Apply persisted debug flag at client creation
                settings = QSettings()
                debug_enabled = bool(settings.value("api/debug", False, type=bool))
                self.client = create_client(self._base_url, api_key=self._api_key, debug=debug_enabled)
            else:
                # Fallback: try to reconstruct from user settings (shouldn't happen normally)
                settings = QSettings()
                base_url = str(settings.value("api/base_url", ""))
                api_key = str(settings.value("api/api_key", ""))
                if base_url and api_key:
                    if not base_url.startswith(("http://", "https://")):
                        base_url = "https://" + base_url
                    debug_enabled = bool(settings.value("api/debug", False, type=bool))
                    self.client = create_client(base_url, api_key=api_key, debug=debug_enabled)
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

        # Add active PIREP summary, bridge summary, and logout button to status bar
        if self.active_pirep_label not in self.status_bar.children():
            self.status_bar.addPermanentWidget(self.active_pirep_label, 1)
        if self.bridge_summary_label not in self.status_bar.children():
            self.status_bar.addPermanentWidget(self.bridge_summary_label, 1)
        self.active_pirep_label.setVisible(True)
        self.bridge_summary_label.setVisible(True)
        self.logout_button.setVisible(True)
        self.status_bar.addPermanentWidget(self.logout_button)
        # Initialize as no active on entry
        try:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except Exception:
            pass

        # Wire bridge tab controls
        self.bridge_status_widget.start_requested.connect(self._on_bridge_start)
        self.bridge_status_widget.stop_requested.connect(self._on_bridge_stop)
        # Wire debug toggle to persist and apply immediately
        try:
            self.bridge_status_widget.debug_toggled.connect(self._on_debug_toggled)
        except Exception:
            pass

        # Start UDP bridge automatically with default port
        self._start_udp_bridge()

    def _on_debug_toggled(self, enabled: bool):
        """Persist and apply API debug logging immediately."""
        settings = QSettings()
        settings.setValue("api/debug", bool(enabled))
        # Reflect state in the checkbox without feedback loops
        try:
            self.bridge_status_widget.set_debug_checked(bool(enabled))
        except Exception:
            pass
        # Apply to existing client without restart
        try:
            if self.client and hasattr(self.client, 'set_debug'):
                self.client.set_debug(bool(enabled))
        except Exception:
            pass

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
            self.pireps_set_active_btn.setEnabled(False)
        except Exception:
            pass

        if success:
            self.pireps_widget.update_pireps(pireps_data)
            # Update active route label based on current active ID
            try:
                text_set = False
                if self._active_pirep_id:
                    for pr in pireps_data:
                        try:
                            if str(pr.get('id')) == str(self._active_pirep_id):
                                dep = str(pr.get('dpt_airport_id') or "").upper()
                                arv = str(pr.get('arr_airport_id') or "").upper()
                                if dep and arv:
                                    self.active_pirep_label.setText(f"{dep} → {arv}")
                                    text_set = True
                                break
                        except Exception:
                            pass
                if not text_set:
                    self.active_pirep_label.setText(NO_ACTIVE_TEXT)
            except Exception:
                pass
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
            try:
                QSettings().setValue("simbrief/userid", sb_id)
            except Exception:
                pass
            # Build URL
            url = f"https://www.simbrief.com/api/xml.fetcher.php?userid={sb_id}&json=1"
            self.status_bar.showMessage("Importing SimBrief...")
            self.show_progress(True)
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

        try:
            origin = ((data or {}).get("origin") or {})
            dest = ((data or {}).get("destination") or {})
            alt = ((data or {}).get("alternate") or {})
            general = ((data or {}).get("general") or {})
            times = ((data or {}).get("times") or {})
            fuel = ((data or {}).get("fuel") or {})

            dep_icao = origin.get("icao_code") or origin.get("icao") or origin.get("iata_code") or ""
            arr_icao = dest.get("icao_code") or dest.get("icao") or dest.get("iata_code") or ""
            alt_icao = alt.get("icao_code") or dest.get("icao") or dest.get("iata_code") or ""
            if dep_icao:
                self.current_flight_widget.dep_input.setText(str(dep_icao).upper())
            if arr_icao:
                self.current_flight_widget.arr_input.setText(str(arr_icao).upper())
            if alt_icao:
                self.current_flight_widget.alt_input.setText(str(alt_icao).upper())

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

            block_fuel = fuel.get("plan_ramp")
            if block_fuel:
                self.current_flight_widget.block_fuel_input.setText(str(int(block_fuel)))

            simbrief_flight_number = general.get("flight_number")
            if simbrief_flight_number:
                self.current_flight_widget.simbrief_flight_number_input.setText(simbrief_flight_number)

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
            flight_type = self.current_flight_widget.flight_type_combo.currentData()
            flight_number = self.current_flight_widget.acars_flight_number_input.text().strip() or None
            dpt = self.current_flight_widget.dep_input.text().strip().upper()
            arr = self.current_flight_widget.arr_input.text().strip().upper()
            alt = self.current_flight_widget.alt_input.text().strip().upper()
            route = self.current_flight_widget.route_text.toPlainText().strip() or None
            level_text = self.current_flight_widget.level_input.text().strip()
            planned_distance_text = self.current_flight_widget.planned_distance_input.text().strip()
            planned_time_text = self.current_flight_widget.planned_time_input.text().strip()
            level = int(level_text) if level_text != "" else None
            planned_distance = int(planned_distance_text) if planned_distance_text != "" else None
            planned_flight_time = int(planned_time_text) if planned_time_text != "" else None
            block_fuel_text = self.current_flight_widget.block_fuel_input.text().strip()
            block_fuel = int(block_fuel_text) if block_fuel_text != "" else None
            simbrief_flight_number = self.current_flight_widget.simbrief_flight_number_input.text().strip() or None
            flight_data: Dict[str, Any] = {
                "airline_id": int(airline.get('id')) if isinstance(airline, dict) and airline.get('id') else None,
                "aircraft_id": int(aircraft.get('id')) if isinstance(aircraft, dict) and aircraft.get('id') else None,
                "flight_type": flight_type,
                "flight_number": int(flight_number),
                "dpt_airport_id": dpt,
                "arr_airport_id": arr,
                "alt_airport_id": alt,
                "route": route,
                "level": level,
                "planned_distance": planned_distance,
                "planned_flight_time": planned_flight_time,
                "block_fuel": block_fuel,
                "source": 1,
                "source_name": "vmsacars",
                "fields": {
                    "Simulator": "X-Plane 12",
                    "Unlimited Fuel": "Off",
                    "Network Online": "VATSIM",
                    "Network Callsign Check": "0",
                    "Network Callsign Used": simbrief_flight_number,
                }
            }
            # Remove None values
            flight_data = {k: v for k, v in flight_data.items() if v is not None}
            if not flight_data.get('airline_id') or not flight_data.get('aircraft_id') or not dpt or not arr:
                QMessageBox.warning(self, "Missing fields", "Please select airline, aircraft, and enter both departure and arrival.")
                return
            self.show_progress(True)
            # Snapshot initial block fuel for this flight; this will be used to compute fuel_used
            try:
                self._initial_block_fuel_kg = float(block_fuel) if block_fuel is not None else None
            except Exception:
                self._initial_block_fuel_kg = None
            pirep = self._workflow.start_flight(flight_data)
        except Exception as e:
            self.show_progress(False)
            QMessageBox.warning(self, "Prefile failed", str(e))
            return
        finally:
            pass
        self.show_progress(False)
        try:
            # phpVMS API responses generally include the resource under a 'data' key
            pirep_data = pirep.get('data') if isinstance(pirep, dict) and 'data' in pirep else pirep
            pid_val = (pirep_data or {}).get('id')
            pid = str(pid_val) if pid_val is not None else None
            if not pid:
                raise ValueError("No PIREP id in response")
            self._active_pirep_id = pid
            self.update_active_route_label(arr, dpt, pirep_data)
            # also reflect in user_data for persistence, if desired
            try:
                if isinstance(self.user_data, dict):
                    self.user_data['last_pirep_id'] = pid
            except Exception:
                pass
            self.status_bar.showMessage(f"Prefiled PIREP #{pid} (IN_PROGRESS)")
        except Exception:
            self.status_bar.showMessage("Prefiled PIREP (id unknown)")

    def update_active_route_label(self, arr, dpt, pirep_data):
        try:
            dpt_txt = dpt if isinstance(dpt, str) else ""
            arr_txt = arr if isinstance(arr, str) else ""
            if dpt_txt and arr_txt:
                self.active_pirep_label.setText(f"{dpt_txt} → {arr_txt}")
            else:
                # Fallback to data returned from server
                dep = str((pirep_data or {}).get('dpt_airport_id') or "").upper()
                arv = str((pirep_data or {}).get('arr_airport_id') or "").upper()
                self.active_pirep_label.setText(f"{dep} → {arv}" if dep and arv else NO_ACTIVE_TEXT)
        except Exception:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)

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
        # Clear snapshot so next flight starts fresh
        self._initial_block_fuel_kg = None
        try:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except Exception:
            pass
        self.status_bar.showMessage(f"Cancelled PIREP #{pid}")

    def on_file_clicked(self):
        if not self.client or not self._workflow:
            return
        if not self._active_pirep_id:
            QMessageBox.information(self, "No active PIREP", "There is no active PIREP to file.")
            return
        pid = self._active_pirep_id
        final_data: Dict[str, Any] = {
            "flight_time": 0,
            "fuel_used": 0,
            "distance": 0,
        }
        self.show_progress(True)
        try:
            self._workflow.complete_flight(pid, final_data)
        except Exception as e:
            self.show_progress(False)
            QMessageBox.warning(self, "File failed", str(e))
            return
        self.show_progress(False)
        self.status_bar.showMessage(f"Filed PIREP #{pid} (PENDING)")
        self._active_pirep_id = None
        self._initial_block_fuel_kg = None
        try:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except:
            pass

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

    def on_set_active_selected_left(self):
        """Set the currently selected IN_PROGRESS PIREP as the active one for ACARS updates."""
        pid = self.pireps_widget.get_selected_pirep_id()
        state = self.pireps_widget.get_selected_pirep_state()
        if not pid:
            QMessageBox.information(self, "No selection", "Select a PIREP to set active.")
            return
        try:
            if state != PirepState.IN_PROGRESS.value:
                QMessageBox.information(self, "Not IN_PROGRESS", "Only IN_PROGRESS PIREPs can be set active.")
                return
        except Exception:
            pass
        self._active_pirep_id = pid
        # Reset initial block fuel snapshot; will be set from first fuel packet for this active flight
        self._initial_block_fuel_kg = None
        # Update status bar active label with route text if available
        try:
            route_text = self.pireps_widget.get_selected_route()
            if route_text and route_text != "N/A":
                self.active_pirep_label.setText(route_text)
            else:
                self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except Exception:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        self.status_bar.showMessage(f"Active PIREP set to #{pid}")

    def _on_pireps_selection_changed(self):
        """Enable/disable the left-pane action buttons based on selection validity/state."""
        try:
            pid = self.pireps_widget.get_selected_pirep_id()
            state = self.pireps_widget.get_selected_pirep_state()
            has_valid = bool(pid)
            self.pireps_cancel_btn.setEnabled(has_valid)
            # Enable Set Active only for IN_PROGRESS
            try:
                in_progress_val = PirepState.IN_PROGRESS.value
            except Exception:
                in_progress_val = 0
            self.pireps_set_active_btn.setEnabled(has_valid and state == in_progress_val)
        except Exception:
            try:
                self.pireps_cancel_btn.setEnabled(False)
                self.pireps_set_active_btn.setEnabled(False)
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
        # Clear snapshot so next session starts fresh
        self._initial_block_fuel_kg = None
        try:
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except Exception:
            pass

        # Hide main interface
        self.tabs.setVisible(False)
        self.logout_button.setVisible(False)
        self.bridge_summary_label.setVisible(False)

        # Show login widget
        self.login_widget.setVisible(True)

        # Clear status
        self.status_bar.showMessage("Ready - Please login to continue")
        try:
            self.active_pirep_label.setVisible(False)
            self.active_pirep_label.setText(NO_ACTIVE_TEXT)
        except Exception:
            pass

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
        # Create/start new with handler callbacks; the handlers consult self._active_pirep_id internally
        def _status_handler(status: str, distance: Optional[float], fuel: Optional[float]):
            try:
                pid = self._active_pirep_id
                if not pid:
                    return
                payload: Dict[str, Any] = {"status": status}
                if distance is not None:
                    # Distance already in nautical miles from Lua; pass through
                    payload["distance"] = distance
                if fuel is not None:
                    # 'fuel' from UDP is fuel remaining (kg). Convert to fuel used using the initial snapshot.
                    try:
                        fuel_remaining = float(fuel)
                        if self._initial_block_fuel_kg is None:
                            # If no snapshot yet (e.g., user didn't enter block fuel or attached to existing flight),
                            # set the snapshot to the first observed remaining value.
                            self._initial_block_fuel_kg = fuel_remaining
                        fuel_used = max(0.0, float(self._initial_block_fuel_kg) - fuel_remaining)
                        payload["fuel_used"] = fuel_used
                    except Exception:
                        # If anything goes wrong, skip fuel_used for this update
                        pass
                # Send update; ignore failures here
                self.client.update_pirep(pid, payload)
            except Exception:
                pass

        def _position_handler(pos: Dict[str, Any]):
            try:
                pid = self._active_pirep_id
                if not pid:
                    return
                self.client.post_acars_position(pid, positions=[pos])
            except Exception:
                pass

        def _events_handler(events: List[Dict[str, Any]]):
            try:
                pid = self._active_pirep_id
                if not pid:
                    return
                # Currently not used; kept for parity
                self.client.post_acars_logs(pid, logs=events)
            except Exception:
                pass

        self._udp_bridge = UdpBridge(self.client, host=host, port=port, status_handler=_status_handler, position_handler=_position_handler, events_handler=_events_handler)
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
            debug_enabled = bool(settings.value("api/debug", False, type=bool))
            self.client = create_client(base_url, api_key=api_key, debug=debug_enabled)
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
