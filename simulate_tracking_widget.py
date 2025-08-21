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
        row1.addWidget(QLabel("Altitude (ft):"))
        self.alt_spin = QSpinBox()
        self.alt_spin.setRange(0, 60000)
        self.alt_spin.setValue(10000)
        self.alt_spin.setSingleStep(500)
        row1.addWidget(self.alt_spin)
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

        last_sent_lat = QSettings().value("bridge_status_widget/last_sent_lat")
        last_sent_lon = QSettings().value("bridge_status_widget/last_sent_lon")
        if last_sent_lat is not None and last_sent_lon is not None:
            self.base_lat.setValue(float(last_sent_lat))
            self.base_lon.setValue(float(last_sent_lon))

        # Row 4: Send
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
        alt = int(self.alt_spin.value())
        payload = {
            "status": status,
            "position": {
                "lat": round(new_lat, 6),
                "lon": round(new_lon, 6),
                "altitude": alt,
                "gs": gs,
                "sim_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
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
            self.info_label.setText(f"Sent {status} to {host}:{port} lat={payload['position']['lat']} lon={payload['position']['lon']}")
            self.base_lat.setValue(new_lat)
            self.base_lon.setValue(new_lon)
            QSettings().setValue("bridge_status_widget/last_sent_lat", new_lat)
            QSettings().setValue("bridge_status_widget/last_sent_lon", new_lon)
        except Exception as e:
            self.info_label.setText(f"Error: {e}")
