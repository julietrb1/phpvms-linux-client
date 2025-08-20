"""
BridgeStatusWidget - shows UDP bridge status and log, start/stop controls
"""
from typing import Dict, Any
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit
)


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
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Host (default 0.0.0.0)")
        self.host_input.setFixedWidth(160)
        ctrl.addWidget(QLabel("UDP Host:"))
        ctrl.addWidget(self.host_input)
        ctrl.addSpacing(6)
        ctrl.addWidget(QLabel("Port:"))
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
        if isinstance(logs, list):
            if len(logs) != self._last_log_len:
                view_lines = logs[-300:]
                self.log_view.setPlainText("\n".join(view_lines))
                self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
                self._last_log_len = len(logs)

    def set_controls_state(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
