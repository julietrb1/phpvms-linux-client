"""
SimulateTrackingWidget - send synthetic UDP packets to emulate Lua client -> UDP bridge

Placed under the Status page (BridgeStatusWidget) to help troubleshooting by
sending formatted JSON to localhost:<port> that UdpBridge listens on.

Defaults:
- Status: INI
- Speed (gs): 250
- Altitude: 10000
- Latitude/Longitude minute offsets: 1 and 1

Behavior:
- Maintains a base latitude/longitude (editable). On Send, it applies the
  minute-based offsets (N/S, E/W) to compute a new position, sends one packet,
  and updates the base to the new position to allow repeated stepping.

Note: Host is forced to 127.0.0.1 as per requirement; port is provided by a
parent via set_port_getter, default 47777 if not provided.
"""
from __future__ import annotations

import json
import socket
from datetime import datetime, timezone
from typing import Callable, Optional

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QGroupBox
)

try:
    from phpvms_api_client import PirepStatus as _PirepStatus
except Exception:
    # Fallback: lightweight stub if import fails in design-time
    class _PirepStatus:  # type: ignore
        INITIATED = type("E", (), {"value": "INI", "name": "INITIATED"})
        BOARDING = type("E", (), {"value": "BST", "name": "BOARDING"})
        DEPARTED = type("E", (), {"value": "OFB", "name": "DEPARTED"})
        TAXI = type("E", (), {"value": "TXI", "name": "TAXI"})
        TAKEOFF = type("E", (), {"value": "TOF", "name": "TAKEOFF"})
        AIRBORNE = type("E", (), {"value": "TKO", "name": "AIRBORNE"})
        ENROUTE = type("E", (), {"value": "ENR", "name": "ENROUTE"})
        APPROACH = type("E", (), {"value": "TEN", "name": "APPROACH"})
        LANDING = type("E", (), {"value": "LDG", "name": "LANDING"})
        LANDED = type("E", (), {"value": "LAN", "name": "LANDED"})
        ARRIVED = type("E", (), {"value": "ARR", "name": "ARRIVED"})
        CANCELLED = type("E", (), {"value": "DX", "name": "CANCELLED"})
        PAUSED = type("E", (), {"value": "PSD", "name": "PAUSED"})


class SimulateTrackingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._get_port: Optional[Callable[[], int]] = None
        self._setup_ui()

    def set_port_getter(self, fn: Callable[[], int]):
        """Provide a callable which returns the destination port to send to."""
        self._get_port = fn

    def _setup_ui(self):
        outer_layout = QVBoxLayout()

        group = QGroupBox("Simulate tracking")
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self._populate_statuses()
        row1.addWidget(self.status_combo)
        row1.addSpacing(12)
        row1.addWidget(QLabel("Speed (kts):"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(0, 2000)
        self.speed_spin.setValue(250)
        self.speed_spin.setSingleStep(10)
        row1.addWidget(self.speed_spin)
        row1.addSpacing(12)
        row1.addWidget(QLabel("Alt MSL (ft):"))
        self.alt_msl_spin = QSpinBox()
        self.alt_msl_spin.setRange(0, 60000)
        self.alt_msl_spin.setValue(10000)
        self.alt_msl_spin.setSingleStep(500)
        row1.addWidget(self.alt_msl_spin)
        row1.addSpacing(12)
        row1.addWidget(QLabel("Alt AGL (ft):"))
        self.alt_agl_spin = QSpinBox()
        self.alt_agl_spin.setRange(0, 60000)
        self.alt_agl_spin.setValue(10000)
        self.alt_agl_spin.setSingleStep(500)
        row1.addWidget(self.alt_agl_spin)
        row1.addStretch()
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Base Lat:"))
        self.base_lat = QDoubleSpinBox()
        self.base_lat.setDecimals(6)
        self.base_lat.setRange(-90.0, 90.0)
        self.base_lat.setValue(0.0)
        self.base_lat.setSingleStep(0.1)
        self.base_lat.setMinimumWidth(120)
        row2.addWidget(self.base_lat)
        row2.addSpacing(12)
        row2.addWidget(QLabel("Base Lon:"))
        self.base_lon = QDoubleSpinBox()
        self.base_lon.setDecimals(6)
        self.base_lon.setRange(-180.0, 180.0)
        self.base_lon.setValue(0.0)
        self.base_lon.setSingleStep(0.1)
        self.base_lon.setMinimumWidth(120)
        row2.addWidget(self.base_lon)
        row2.addStretch()
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Lat offset:"))
        self.lat_minutes = QSpinBox()
        self.lat_minutes.setRange(0, 10000)
        self.lat_minutes.setValue(1)
        row3.addWidget(self.lat_minutes)
        self.lat_dir = QComboBox()
        self.lat_dir.addItems(["N", "S"])  # N positive, S negative
        row3.addWidget(self.lat_dir)
        row3.addSpacing(16)
        row3.addWidget(QLabel("Lon offset:"))
        self.lon_minutes = QSpinBox()
        self.lon_minutes.setRange(0, 10000)
        self.lon_minutes.setValue(1)
        row3.addWidget(self.lon_minutes)
        self.lon_dir = QComboBox()
        self.lon_dir.addItems(["E", "W"])  # E positive, W negative
        row3.addWidget(self.lon_dir)
        row3.addStretch()
        layout.addLayout(row3)

        # Row for Distance (nm) and Fuel (kg) bases
        row3b = QHBoxLayout()
        row3b.addWidget(QLabel("Base Dist (nm):"))
        self.base_dist = QDoubleSpinBox()
        self.base_dist.setDecimals(1)
        self.base_dist.setRange(0.0, 100000.0)
        self.base_dist.setValue(500.0)
        self.base_dist.setSingleStep(5.0)
        self.base_dist.setMinimumWidth(110)
        row3b.addWidget(self.base_dist)
        row3b.addSpacing(16)
        row3b.addWidget(QLabel("Base Fuel (kg):"))
        self.base_fuel = QDoubleSpinBox()
        self.base_fuel.setDecimals(1)
        self.base_fuel.setRange(0.0, 200000.0)
        self.base_fuel.setValue(5000.0)
        self.base_fuel.setSingleStep(100.0)
        self.base_fuel.setMinimumWidth(110)
        row3b.addWidget(self.base_fuel)
        row3b.addStretch()
        layout.addLayout(row3b)

        # Row for Dist/Fuel offsets (similar to lat/lon)
        row3c = QHBoxLayout()
        row3c.addWidget(QLabel("Dist change:"))
        self.dist_delta = QDoubleSpinBox()
        self.dist_delta.setDecimals(1)
        self.dist_delta.setRange(0.0, 100000.0)
        self.dist_delta.setValue(5.0)
        self.dist_delta.setSingleStep(1.0)
        row3c.addWidget(self.dist_delta)
        self.dist_dir = QComboBox()
        self.dist_dir.addItems(["+", "-"])  # default increase remaining distance
        row3c.addWidget(self.dist_dir)
        row3c.addSpacing(16)
        row3c.addWidget(QLabel("Fuel change:"))
        self.fuel_delta = QDoubleSpinBox()
        self.fuel_delta.setDecimals(1)
        self.fuel_delta.setRange(0.0, 200000.0)
        self.fuel_delta.setValue(100.0)
        self.fuel_delta.setSingleStep(10.0)
        row3c.addWidget(self.fuel_delta)
        self.fuel_dir = QComboBox()
        self.fuel_dir.addItems(["-", "+"])  # default decrease remaining fuel
        row3c.addWidget(self.fuel_dir)
        row3c.addStretch()
        layout.addLayout(row3c)

        last_sent_lat = QSettings().value("bridge_status_widget/last_sent_lat")
        last_sent_lon = QSettings().value("bridge_status_widget/last_sent_lon")
        if last_sent_lat is not None and last_sent_lon is not None:
            self.base_lat.setValue(float(last_sent_lat))
            self.base_lon.setValue(float(last_sent_lon))
        # Restore last dist/fuel if available
        last_dist = QSettings().value("bridge_status_widget/last_sent_dist")
        last_fuel = QSettings().value("bridge_status_widget/last_sent_fuel")
        try:
            if last_dist is not None:
                self.base_dist.setValue(float(last_dist))
            if last_fuel is not None:
                self.base_fuel.setValue(float(last_fuel))
        except Exception:
            pass

        row4 = QHBoxLayout()
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row4.addWidget(self.send_btn)
        row4.addSpacing(12)
        row4.addWidget(self.info_label)
        row4.addStretch()
        layout.addLayout(row4)

        group.setLayout(layout)
        outer_layout.addWidget(group)
        self.setLayout(outer_layout)

    def _populate_statuses(self):
        # Populate from enum values
        try:
            # Preserve the order as defined
            items = []
            for name in dir(_PirepStatus):
                if name.startswith("_"):
                    continue
                member = getattr(_PirepStatus, name)
                try:
                    code = member.value
                except Exception:
                    continue
                if isinstance(code, str):
                    items.append((name, code))
            # Prefer a stable order; sort by code for consistency
            items = sorted(items, key=lambda x: x[1])
            for name, code in items:
                self.status_combo.addItem(f"{name} ({code})", code)
            # Default to INI if present
            idx = self.status_combo.findData("INI")
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        except Exception:
            # Fallback minimal set
            for code in ["INI", "BST", "TXI", "TOF", "ENR", "ARR", "PSD"]:
                self.status_combo.addItem(code, code)

    def _dest_port(self) -> int:
        try:
            if callable(self._get_port):
                p = int(self._get_port())
                if p > 0:
                    return p
        except Exception:
            pass
        return 47777

    def _on_send(self):
        # Compute new position by applying minute offsets to the base
        lat = float(self.base_lat.value())
        lon = float(self.base_lon.value())
        dlat = (self.lat_minutes.value() or 0) / 60.0
        dlon = (self.lon_minutes.value() or 0) / 60.0
        if self.lat_dir.currentText() == "S":
            dlat = -dlat
        if self.lon_dir.currentText() == "W":
            dlon = -dlon
        new_lat = max(-90.0, min(90.0, lat + dlat))
        new_lon = lon + dlon
        while new_lon > 180.0:
            new_lon -= 360.0
        while new_lon < -180.0:
            new_lon += 360.0

        status = self.status_combo.currentData() or "INI"
        gs = int(self.speed_spin.value())
        alt_msl = int(self.alt_msl_spin.value())
        alt_agl = int(self.alt_agl_spin.value())

        # Compute new dist/fuel using base +/- delta
        cur_dist = float(self.base_dist.value())
        cur_fuel = float(self.base_fuel.value())
        ddist = float(self.dist_delta.value())
        dfuel = float(self.fuel_delta.value())
        if self.dist_dir.currentText() == "-":
            new_dist = max(0.0, cur_dist - ddist)
        else:
            new_dist = cur_dist + ddist
        if self.fuel_dir.currentText() == "-":
            new_fuel = max(0.0, cur_fuel - dfuel)
        else:
            new_fuel = cur_fuel + dfuel

        payload = {
            "status": status,
            "position": {
                "lat": round(new_lat, 6),
                "lon": round(new_lon, 6),
                "altitude_msl": alt_msl,
                "altitude_agl": alt_agl,
                "gs": gs,
                "sim_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "distance": round(new_dist, 1),
            },
            # As per bridge expectations and docs, send these names:
            "fuel": round(new_fuel, 1),    # kilograms remaining
        }

        host = "127.0.0.1"
        port = self._dest_port()
        try:
            data = json.dumps(payload).encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.sendto(data, (host, port))
            finally:
                sock.close()
            self.info_label.setText(
                f"Sent {status} to {host}:{port} lat={payload['position']['lat']} lon={payload['position']['lon']} dist={payload['position']['distance']}nm fuel={payload['fuel']}kg"
            )
            # Update bases to the new values for step-wise repetition
            self.base_lat.setValue(new_lat)
            self.base_lon.setValue(new_lon)
            self.base_dist.setValue(new_dist)
            self.base_fuel.setValue(new_fuel)
            QSettings().setValue("bridge_status_widget/last_sent_lat", new_lat)
            QSettings().setValue("bridge_status_widget/last_sent_lon", new_lon)
            QSettings().setValue("bridge_status_widget/last_sent_dist", new_dist)
            QSettings().setValue("bridge_status_widget/last_sent_fuel", new_fuel)
        except Exception as e:
            self.info_label.setText(f"Error: {e}")
