"""
PirepsWidget - lists PIREPs, supports selection helpers and pagination
"""
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTableWidget, QHeaderView, QMessageBox, QTableWidgetItem
)

from vms_types import Pirep

try:
    from phpvms_api_client import PirepState
except Exception:  # pragma: no cover
    class PirepState:  # type: ignore
        IN_PROGRESS = type("EnumValue", (), {"value": 0})


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
        self.table.setRowCount(len(pireps_data))
        self._row_pirep_ids = []
        self._row_states = []

        for row, pirep in enumerate(pireps_data):
            try:
                pid = pirep.get('id')
            except Exception:
                pid = "-"
            self._row_pirep_ids.append(pid)

            # State for selection logic
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

            # State name
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

            # Distance (nm)
            distance = pirep.get('distance', {}).get('nmi', -1)
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
        try:
            if hasattr(self, 'refresh_button') and self.refresh_button is not None:
                self.refresh_button.setEnabled(enabled)
        except Exception:
            pass

    def get_selected_pirep_id(self) -> Optional[str]:
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
        try:
            row = self.table.currentRow()
            if row is None or row < 0:
                return None
            if row >= len(self._row_states):
                return None
            return self._row_states[row]
        except Exception:
            return None

    def get_selected_route(self) -> Optional[str]:
        """Return the 'Route' cell text (e.g., "DEP → ARR") for the selected row, if any."""
        try:
            row = self.table.currentRow()
            if row is None or row < 0:
                return None
            item = self.table.item(row, 0)
            if item is None:
                return None
            text = item.text().strip()
            return text if text else None
        except Exception:
            return None
