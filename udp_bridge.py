import json
import socket
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List


class UdpBridge:
    """
    Lightweight UDP JSON bridge for FlyWithLua -> Python client.

    - Binds to 0.0.0.0 (all interfaces) or specified host on a given port (default 47777)
    - Expects JSON payloads with keys:
        {
          "status": "ENR",              # optional
          "dist": 217.4,                 # optional (nm remaining)
          "fuel": 452.0,                 # optional (kg remaining)
          "position": {                   # optional
            "lat": 40.1, "lon": -73.9,
            "altitude": 12000, "heading": 255, "gs": 320, "sim_time": 1724167500
          },
          "events": [{"log": "Passing 10k", "sim_time": 1724167400}]  # optional
        }
    - Maintains counters and last-seen info for UI.
    """

    def __init__(self, api_client, host: str = "0.0.0.0", port: int = 47777, status_handler=None, position_handler=None, events_handler=None):
        self.api_client = api_client
        self.host = host
        self.port = int(port)
        # Handlers provided by UI; they must not expose any PIREP ID here
        self._status_handler = status_handler
        self._position_handler = position_handler
        self._events_handler = events_handler

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

        # Metrics/state for UI
        self._running: bool = False
        self._packets_ok: int = 0
        self._packets_err: int = 0
        self._last_packet_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._last_status: Optional[str] = None
        self._last_position: Optional[Dict[str, Any]] = None
        self._last_dist: Optional[float] = None
        self._last_fuel: Optional[float] = None
        self._last_flight_time: Optional[float] = None
        self._log: List[str] = []  # rolling log strings
        self._max_log_lines: int = 500

    # ----------------------- Public control -----------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="UdpBridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        with self._lock:
            self._running = False

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    # ----------------------- UI helpers -----------------------
    def status_summary(self) -> str:
        with self._lock:
            running = "running" if self._running else "stopped"
            last_ts = time.strftime("%H:%M:%S", time.localtime(self._last_packet_time)) if self._last_packet_time else "-"
            last_stat = self._last_status or "-"
            return f"Bridge: {running} {self.host}:{self.port} | last {last_ts} | ok {self._packets_ok} err {self._packets_err} | {last_stat}"

    def status_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "host": self.host,
                "port": self.port,
                "packets_ok": self._packets_ok,
                "packets_err": self._packets_err,
                "last_packet_time": self._last_packet_time,
                "last_error": self._last_error,
                "last_status": self._last_status,
                "last_position": dict(self._last_position) if isinstance(self._last_position, dict) else None,
                "last_dist": self._last_dist,
                "last_fuel": self._last_fuel,
                "last_flight_time": self._last_flight_time,
                "log": list(self._log),
            }

    # ----------------------- Internal loop -----------------------
    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.host, self.port))
            sock.settimeout(0.5)
            with self._lock:
                self._running = True
                self._append_log(f"UDP bridge listening on {self.host}:{self.port}")
        except Exception as e:
            with self._lock:
                self._last_error = f"Bind failed: {e}"
                self._append_log(self._last_error)
                self._running = False
            sock.close()
            return

        while not self._stop_evt.is_set():
            try:
                try:
                    data, _ = sock.recvfrom(64 * 1024)
                except socket.timeout:
                    continue
                self._handle_packet(data)
            except Exception as e:
                with self._lock:
                    self._packets_err += 1
                    self._last_error = str(e)
                    self._append_log(f"ERR: {e}")
        try:
            sock.close()
        finally:
            with self._lock:
                self._running = False
                self._append_log("UDP bridge stopped")

    def _handle_packet(self, data: bytes) -> None:
        now = time.time()
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception as e:
            with self._lock:
                self._packets_err += 1
                self._last_error = f"JSON decode error: {e}"
                self._append_log(self._last_error)
            return

        payload["position"]["flight_time"] = int(payload["position"]["flight_time"])
        payload["position"]["sim_time"] = datetime.fromtimestamp(float(payload["position"]["sim_time"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = payload.get("status")
        if isinstance(status, str) and status:
            with self._lock:
                self._last_status = status
        # Root-level flight_time (minutes or seconds as provided by Lua)
        ft_val = payload.get("flight_time")
        if isinstance(ft_val, (int, float)):
            with self._lock:
                self._last_flight_time = float(ft_val)
        pos = payload.get("position") or {}
        if isinstance(pos, dict):
            with self._lock:
                self._last_position = {k: pos.get(k) for k in ("lat", "lon", "altitude_msl", "altitude_agl", "heading", "gs", "sim_time", "distance", "ias", "vs")}
        try:
            dist_val = pos.get("distance")
            fuel_val = payload.get("fuel")
            with self._lock:
                if isinstance(dist_val, (int, float)):
                    self._last_dist = float(dist_val)
                if isinstance(fuel_val, (int, float)):
                    self._last_fuel = float(fuel_val)
        except Exception:
            pass

        try:
            if isinstance(status, str) and status and callable(self._status_handler):
                self._status_handler(status, pos.get("distance"), payload.get("fuel"), self._last_flight_time)
        except Exception as e:
            with self._lock:
                self._packets_err += 1
                self._last_error = f"status_handler: {e}"
                self._append_log(self._last_error)
        try:
            if isinstance(pos, dict) and callable(self._position_handler):
                self._position_handler(pos)
        except Exception as e:
            with self._lock:
                self._packets_err += 1
                self._last_error = f"position_handler: {e}"
                self._append_log(self._last_error)
        try:
            events = payload.get("events")
            if isinstance(events, list) and events and callable(self._events_handler):
                self._events_handler(events)
        except Exception as e:
            with self._lock:
                self._packets_err += 1
                self._last_error = f"events_handler: {e}"
                self._append_log(self._last_error)

        # Success accounting
        with self._lock:
            self._packets_ok += 1
            self._last_packet_time = now
            s = status or "-"
            p = self._last_position or {}
            self._append_log(
                f"OK: st={s} lat={p.get('lat')} lon={p.get('lon')} alt_msl={p.get('altitude_msl')} alt_agl={p.get('altitude_agl')} gs={p.get('gs')} dist={self._last_dist}nm fuel={self._last_fuel}kg ft={self._last_flight_time}"
            )


    def _append_log(self, line: str) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime())
        entry = f"[{ts}] {line}"
        self._log.append(entry)
        if len(self._log) > self._max_log_lines:
            # keep last N lines
            self._log = self._log[-self._max_log_lines:]
