"""
CurrentFlightWidget - enter current flight information, SimBrief import controls
"""
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QComboBox, QLabel
)


class CurrentFlightWidget(QWidget):
    """Widget for entering current flight information"""

    def __init__(self):
        super().__init__()
        # Action buttons wired by MainWindow
        self.prefile_button = QPushButton("Prefile")
        self.file_button = QPushButton("File PIREP")
        self.cancel_button = QPushButton("Cancel PIREP")
        # Placeholders for UDP labels initialized in setup_ui
        self.udp_status: Optional[QLabel] = None
        self.udp_flight_time: Optional[QLabel] = None
        self.udp_distance: Optional[QLabel] = None
        self.udp_fuel: Optional[QLabel] = None
        self.udp_lat: Optional[QLabel] = None
        self.udp_lon: Optional[QLabel] = None
        self.udp_alt_msl: Optional[QLabel] = None
        self.udp_alt_agl: Optional[QLabel] = None
        self.udp_heading: Optional[QLabel] = None
        self.udp_gs: Optional[QLabel] = None
        self.udp_sim_time: Optional[QLabel] = None
        self.setup_ui()

    def setup_ui(self):
        # Split into two columns: left (form) and right (live UDP data)
        outer = QHBoxLayout()

        left_col = QVBoxLayout()

        form = QFormLayout()

        # SimBrief import controls
        simbrief_row = QHBoxLayout()
        self.simbrief_id_input = QLineEdit()
        self.simbrief_id_input.setPlaceholderText("SimBrief ID (numeric)")
        self.simbrief_id_input.setValidator(QIntValidator(0, 99999999, self))
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

        self.acars_flight_number_input = QLineEdit()
        self.acars_flight_number_input.setText("1")
        form.addRow("ACARS flight number:", self.acars_flight_number_input)

        self.simbrief_flight_number_input = QLineEdit()
        form.addRow("SimBrief flight number:", self.simbrief_flight_number_input)

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

        # Left column content
        left_col.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self.prefile_button)
        btn_row.addWidget(self.file_button)
        btn_row.addWidget(self.cancel_button)
        left_col.addLayout(btn_row)
        left_col.addStretch()

        # Right column with latest UDP data
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Latest UDP Data"))
        self.udp_status = QLabel("-")
        self.udp_flight_time = QLabel("-")
        self.udp_distance = QLabel("-")
        self.udp_fuel = QLabel("-")
        self.udp_lat = QLabel("-")
        self.udp_lon = QLabel("-")
        self.udp_alt_msl = QLabel("-")
        self.udp_alt_agl = QLabel("-")
        self.udp_heading = QLabel("-")
        self.udp_gs = QLabel("-")
        self.udp_ias = QLabel("-")
        self.udp_vs = QLabel("-")
        self.udp_sim_time = QLabel("-")

        # Use simple rows
        def row(lbl: str, widget: QLabel):
            r = QHBoxLayout()
            r.addWidget(QLabel(lbl))
            r.addStretch()
            r.addWidget(widget)
            return r
        right_col.addLayout(row("Status:", self.udp_status))
        right_col.addLayout(row("Flight Time:", self.udp_flight_time))
        right_col.addLayout(row("Distance (nm):", self.udp_distance))
        right_col.addLayout(row("Fuel (kg):", self.udp_fuel))
        right_col.addLayout(row("Lat:", self.udp_lat))
        right_col.addLayout(row("Lon:", self.udp_lon))
        right_col.addLayout(row("Alt MSL (ft):", self.udp_alt_msl))
        right_col.addLayout(row("Alt AGL (ft):", self.udp_alt_agl))
        right_col.addLayout(row("Heading:", self.udp_heading))
        right_col.addLayout(row("GS (kts):", self.udp_gs))
        right_col.addLayout(row("IAS (kts):", self.udp_ias))
        right_col.addLayout(row("VS (fpm):", self.udp_vs))
        right_col.addLayout(row("Sim Time:", self.udp_sim_time))
        right_col.addStretch()

        # Assemble outer layout
        outer.addLayout(left_col, 3)
        outer.addSpacing(12)
        outer.addLayout(right_col, 2)
        self.setLayout(outer)

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

    def update_udp_snapshot(self, snap: Dict[str, Any]):
        try:
            if not isinstance(snap, dict):
                return
            st = snap.get("last_status")
            if self.udp_status is not None:
                self.udp_status.setText(str(st) if st is not None else "-")
            # Flight time may be minutes or seconds depending on Lua; display raw number with unit hint
            ft = snap.get("last_flight_time")
            if self.udp_flight_time is not None:
                try:
                    self.udp_flight_time.setText(f"{float(ft):.1f}")
                except Exception:
                    self.udp_flight_time.setText(str(ft) if ft is not None else "-")
            dist = snap.get("last_dist")
            if self.udp_distance is not None:
                try:
                    self.udp_distance.setText(f"{float(dist):.1f}")
                except Exception:
                    self.udp_distance.setText(str(dist) if dist is not None else "-")
            fuel = snap.get("last_fuel")
            if self.udp_fuel is not None:
                try:
                    self.udp_fuel.setText(f"{float(fuel):.1f}")
                except Exception:
                    self.udp_fuel.setText(str(fuel) if fuel is not None else "-")
            pos = snap.get("last_position") or {}
            if isinstance(pos, dict):
                def _set(lbl: Optional[QLabel], key: str, fmt: str = "{}"):  # type: ignore
                    if lbl is None:
                        return
                    val = pos.get(key)
                    try:
                        if isinstance(val, (int, float)):
                            lbl.setText(fmt.format(val))
                        else:
                            lbl.setText(str(val) if val is not None else "-")
                    except Exception:
                        lbl.setText(str(val) if val is not None else "-")
                _set(self.udp_lat, "lat", "{:.6f}")
                _set(self.udp_lon, "lon", "{:.6f}")
                _set(self.udp_alt_msl, "altitude_msl", "{:.0f}")
                _set(self.udp_alt_agl, "altitude_agl", "{:.0f}")
                _set(self.udp_heading, "heading", "{:.0f}")
                _set(self.udp_gs, "gs", "{:.0f}")
                _set(self.udp_ias, "ias", "{:.0f}")
                _set(self.udp_vs, "vs", "{:.0f}")
                # sim_time might be ISO string
                if self.udp_sim_time is not None:
                    stime = pos.get("sim_time")
                    self.udp_sim_time.setText(str(stime) if stime is not None else "-")
        except Exception:
            pass
