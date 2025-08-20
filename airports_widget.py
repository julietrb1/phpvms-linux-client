"""
AirportsWidget - lists airports with pagination controls
"""
from typing import List, Dict, Any
from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QTableWidget, QHeaderView, QTableWidgetItem
)


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
            lat = ap.get('lat') or ap.get('latitude') or ap.get('ground_lat')
            lon = ap.get('lon') or ap.get('longitude') or ap.get('ground_lon')
            elev = ap.get('elevation') or ap.get('altitude')
            self.table.setItem(row, 5, QTableWidgetItem(str(lat or '')))
            self.table.setItem(row, 6, QTableWidgetItem(str(lon or '')))
            self.table.setItem(row, 7, QTableWidgetItem(str(elev or '')))

    def set_refresh_enabled(self, enabled: bool):
        self.refresh_button.setEnabled(enabled)
