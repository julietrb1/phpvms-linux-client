"""
CurrentFlightWidget - enter current flight information, SimBrief import controls
"""
from typing import List, Dict, Any
from PySide6.QtCore import QSettings
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QComboBox
)


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

        self.level_input = QLineEdit()
        self.level_input.setPlaceholderText("ft")
        self.level_input.setValidator(QIntValidator(0, 9999, self))
        form.addRow("Level:", self.level_input)

        self.block_fuel_input = QLineEdit()
        self.block_fuel_input.setPlaceholderText("kg")
        self.block_fuel_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Block fuel (kg):", self.block_fuel_input)

        self.planned_distance_input = QLineEdit()
        self.planned_distance_input.setPlaceholderText("nm")
        self.planned_distance_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Planned Distance:", self.planned_distance_input)

        self.planned_time_input = QLineEdit()
        self.planned_time_input.setPlaceholderText("minutes")
        self.planned_time_input.setValidator(QIntValidator(0, 100000, self))
        form.addRow("Planned Flight Time:", self.planned_time_input)

        layout.addLayout(form)

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
        import re
        self.aircraft_combo.clear()

        def _normalize_ac_name(s: Any) -> str:  # type: ignore[name-defined]
            try:
                s = str(s)
                if '|' in s:
                    left, sep, right = s.partition('|')
                    left = left.strip()
                    left = re.sub(r'([A-Za-z])\s+(\d)', r'\1\2', left)
                    return f"{left} | {right.strip()}"
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
