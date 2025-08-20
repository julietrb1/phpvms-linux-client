import json
import socket
import threading
import time
from typing import Dict, Any, Optional, List

try:
    from phpvms_api_client import FlightProgressTracker
except Exception:  # pragma: no cover - allow import in editors without module path
    FlightProgressTracker = object  # type: ignore


class UdpBridge:
    """
    Lightweight UDP JSON bridge for FlyWithLua -> Python client.

    - Binds to 0.0.0.0 (all interfaces) or specified host on a given port (default 47777)
    - Expects JSON payloads with keys:
        {
          "pirep_id": 1234,
          "status": "ENR",              # optional
          "distance": 217.4,             # optional
          "fuel_used": 452.0,            # optional
          "position": {                   # optional
            "lat": 40.1, "lon": -73.9,
            "altitude": 12000, "heading": 255, "gs": 320, "sim_time": 1724167500
          },
          "events": [{"log": "Passing 10k", "sim_time": 1724167400}]  # optional
        }
    - For each pirep_id, a FlightProgressTracker is created on demand and reused.
    - Maintains counters and last-seen info for UI.
    """

    def __init__(self, api_client, host: str = "0.0.0.0", port: int = 47777, pirep_id_provider=None):
        self.api_client = api_client
        self.host = host
        self.port = int(port)
        # Provide a callable returning current pirep_id, or an int, else None
        self._pirep_id_provider = pirep_id_provider
        if isinstance(pirep_id_provider, int):
            pid_val = int(pirep_id_provider)
            self._pirep_id_provider = lambda: pid_val

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.Lock()

        # Trackers by pirep_id
        self._trackers: Dict[int, FlightProgressTracker] = {}

        # Metrics/state for UI
        self._running: bool = False
        self._packets_ok: int = 0
        self._packets_err: int = 0
        self._last_packet_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._last_pirep_id: Optional[int] = None
        self._last_status: Optional[str] = None
        self._last_position: Optional[Dict[str, Any]] = None
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
            last_pid = self._last_pirep_id if self._last_pirep_id is not None else "-"
            last_stat = self._last_status or "-"
            return f"Bridge: {running} {self.host}:{self.port} | last {last_ts} | ok {self._packets_ok} err {self._packets_err} | PIREP {last_pid} {last_stat}"

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
                "last_pirep_id": self._last_pirep_id,
                "last_status": self._last_status,
                "last_position": dict(self._last_position) if isinstance(self._last_position, dict) else None,
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

        pirep_id = payload.get("pirep_id")
        if not isinstance(pirep_id, int):
            # tolerate numeric strings
            try:
                pirep_id = int(pirep_id)
            except Exception:
                # Try provider from UI
                try:
                    if callable(self._pirep_id_provider):
                        provided = self._pirep_id_provider()
                        if provided is not None:
                            pirep_id = int(provided)
                except Exception:
                    pirep_id = None
        # Status and position may be processed even without active PIREP for UI metrics
        if not isinstance(pirep_id, int):
            with self._lock:
                self._last_status = payload.get("status") or self._last_status
                pos = payload.get("position") or {}
                if isinstance(pos, dict):
                    self._last_position = {k: pos.get(k) for k in ("lat", "lon", "altitude", "heading", "gs", "sim_time")}
            # No active PIREP to send to; count as ok receipt but skip API calls
            with self._lock:
                self._packets_ok += 1
                self._last_packet_time = now
                self._append_log("OK: no active PIREP; received status/position")
            return

        tracker = self._get_tracker(pirep_id)
        # Status update
        status = payload.get("status")
        # if isinstance(status, str) and status:
        #     dist = payload.get("distance")
        #     fuel = payload.get("fuel_used")
        #     try:
        #         tracker.update_phase(status, dist, fuel)
        #     except Exception as e:
        #         with self._lock:
        #             self._packets_err += 1
        #             self._last_error = f"update_phase: {e}"
        #             self._append_log(self._last_error)
        #     else:
        #         with self._lock:
        #             self._last_status = status

        # Position update
        pos = payload.get("position")
        if isinstance(pos, dict):
            try:
                alt_val = pos.get("altitude") if pos.get("altitude") is not None else pos.get("altitude_msl")
                tracker.send_position(
                    lat=float(pos["lat"]),
                    lon=float(pos["lon"]),
                    altitude=alt_val,
                    heading=pos.get("heading"),
                    gs=pos.get("gs"),
                    sim_time=pos.get("sim_time"),
                )
            except Exception as e:
                with self._lock:
                    self._packets_err += 1
                    self._last_error = f"send_position: {e}"
                    self._append_log(self._last_error)
            else:
                with self._lock:
                    self._last_position = {
                        k: pos.get(k) for k in ("lat", "lon", "altitude", "heading", "gs", "sim_time")
                    }

        # Events/logs
        events = payload.get("events")
        # if isinstance(events, list) and events:
        #     try:
        #         tracker.post_events(events)
        #     except Exception as e:
        #         with self._lock:
        #             self._packets_err += 1
        #             self._last_error = f"post_events: {e}"
        #             self._append_log(self._last_error)

        # Success accounting
        with self._lock:
            self._packets_ok += 1
            self._last_packet_time = now
            self._last_pirep_id = int(pirep_id)
            # brief concise log line
            s = status or "-"
            p = self._last_position or {}
            self._append_log(
                f"OK: id={pirep_id} st={s} lat={p.get('lat')} lon={p.get('lon')} alt={p.get('altitude')} gs={p.get('gs')}"
            )

    def _get_tracker(self, pirep_id: int) -> FlightProgressTracker:
        # Create tracker on demand
        if pirep_id not in self._trackers:
            self._trackers[pirep_id] = FlightProgressTracker(self.api_client, pirep_id)
        return self._trackers[pirep_id]

    def _append_log(self, line: str) -> None:
        ts = time.strftime("%H:%M:%S", time.localtime())
        entry = f"[{ts}] {line}"
        self._log.append(entry)
        if len(self._log) > self._max_log_lines:
            # keep last N lines
            self._log = self._log[-self._max_log_lines:]
