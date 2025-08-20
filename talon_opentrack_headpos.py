"""
Talon -> opentrack UDP bridge (head position only)

Usage overview:
- This script is intended to run inside Talon as a user script so Talon can
  initialize and drive your Tobii Eye Tracker 5 without enabling head-mouse.
- Copy this file into your Talon user directory, e.g.:
    macOS:   ~/.talon/user/
    Windows: %AppData%/Talon/user/
    Linux:   ~/.talon/user/
- Restart Talon or reload scripts.
- In Talon, run the action `user.opentrack_start()` to begin streaming, and
  `user.opentrack_stop()` to stop.

opentrack configuration:
- Input: "UDP over network"
- Address: 127.0.0.1 (or the host in HOST below)
- Port: 4242 (or the PORT below)
- Protocol expects 6 DOF values as 64-bit little-endian floats in order:
  [yaw, pitch, roll, x, y, z]. We send yaw/pitch/roll = 0 and only provide
  x/y/z from Talon.
- Units/axes: Talon reports head position in millimeters in a right-handed
  coordinate system where +x is right, +y is up, +z is forward (away from screen)
  in most builds. opentrack mappings may expect different directions/units.
  If necessary, tweak SCALE_MM_TO_CM and AXIS_FLIPS below or remap axes inside
  opentrack.

Notes:
- This script enables head tracking via Talon’s tracking controls without
  enabling head-mouse cursor control.
- Talon’s public API surface can vary by version. The calls used here are
  guarded and will no-op if unavailable; check Talon log for warnings.
- If Tobii doesn’t start unless head-mouse is enabled in your setup, try
  the provided explicit tracking enable calls below.
"""

import socket
import struct
from typing import Optional, Tuple

# Talon APIs
try:
    # Newer Talon API modules
    from talon import cron
    try:
        # tracking API may be present in newer Talon versions
        from talon import tracking as talon_tracking  # type: ignore
    except Exception:  # pragma: no cover - depends on Talon environment
        talon_tracking = None  # type: ignore
    from talon import Module, app, actions
except Exception:  # pragma: no cover - running outside Talon
    cron = None
    talon_tracking = None
    Module = object  # type: ignore
    app = None
    actions = None

# ===================== Config =====================
HOST = "127.0.0.1"
PORT = 4242
SEND_INTERVAL_MS = 16  # ~60 Hz

# Convert Talon mm to cm for opentrack (commonly preferred). Set to 0.1 to convert mm->cm.
SCALE_MM_TO_CM = 0.1

# Send a zero-pose heartbeat when pose data is unavailable so opentrack sees the UDP stream.
SEND_ZERO_WHEN_NO_DATA = True

# Axis flips if your coordinate systems differ. 1 for normal, -1 to invert.
AXIS_FLIPS = {
    "x": 1.0,   # right (+) vs left (-)
    "y": 1.0,   # up (+) vs down (-)
    "z": -1.0,  # often Talon +z is forward, while opentrack often expects +z towards user. Flip if needed.
}

# ===================== UDP Sender =====================
_sock: Optional[socket.socket] = None
_job = None


def _udp_open():
    global _sock
    if _sock is None:
        _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def _udp_close():
    global _sock
    if _sock is not None:
        try:
            _sock.close()
        finally:
            _sock = None


# ===================== Talon Tracking Helpers =====================

def _enable_head_tracking(enable: bool) -> None:
    """Attempt to enable/disable head tracking without enabling head-mouse.

    Tries several Talon API variations seen across versions/community bundles.
    Sends a one-time notification on failure.
    """
    # Prefer explicit tracking control if available
    try:
        if talon_tracking and hasattr(talon_tracking, "control_head"):
            talon_tracking.control_head(enable)
            try:
                if app:
                    app.notify(f"Talon tracking: control_head({enable}) via talon.tracking")
            except Exception:
                pass
            return
    except Exception:
        pass

    # Fallback: generic actions from various bundles
    try:
        if actions and hasattr(actions, "tracking"):
            # 1) actions.tracking.control_head(bool)
            if hasattr(actions.tracking, "control_head"):
                actions.tracking.control_head(enable)  # type: ignore[attr-defined]
                try:
                    if app:
                        app.notify(f"Talon tracking: actions.tracking.control_head({enable})")
                except Exception:
                    pass
                return
            # 2) actions.tracking.control("head", bool)
            if hasattr(actions.tracking, "control"):
                try:
                    actions.tracking.control("head", enable)  # type: ignore[attr-defined]
                    try:
                        if app:
                            app.notify(f"Talon tracking: actions.tracking.control('head', {enable})")
                    except Exception:
                        pass
                    return
                except Exception:
                    pass
            # 3) actions.tracking.control_toggle("head") as last resort (unknown current state)
            if hasattr(actions.tracking, "control_toggle"):
                try:
                    # Toggle only on enable request to try to wake sensors; we won't toggle on disable
                    if enable:
                        actions.tracking.control_toggle("head")  # type: ignore[attr-defined]
                        try:
                            if app:
                                app.notify("Talon tracking: actions.tracking.control_toggle('head') used")
                        except Exception:
                            pass
                        return
                except Exception:
                    pass
    except Exception:
        pass

    # As a last resort, try toggling tracker power if available
    try:
        if talon_tracking and hasattr(talon_tracking, "start") and hasattr(talon_tracking, "stop"):
            (talon_tracking.start if enable else talon_tracking.stop)()
            try:
                if app:
                    app.notify(f"Talon tracking: {'start' if enable else 'stop'}() via talon.tracking")
            except Exception:
                pass
            return
    except Exception:
        pass

    # Log a warning if we couldn’t toggle tracking
    try:
        if app:
            app.notify("Talon tracking control API unavailable; streaming may fail")
    except Exception:
        pass


def _get_head_position_mm() -> Optional[Tuple[float, float, float]]:
    """Return head position in millimeters as (x, y, z), or None if unavailable.

    This tries multiple APIs to extract pose data depending on Talon version.
    """
    # API option 1: talon_tracking.get_pose() returning dict or tuple
    try:
        if talon_tracking and hasattr(talon_tracking, "get_pose"):
            pose = talon_tracking.get_pose()  # type: ignore[attr-defined]
            # Accept common forms
            if pose is None:
                return None
            if isinstance(pose, dict):
                # possible keys: x_mm, y_mm, z_mm
                x = float(pose.get("x_mm", 0.0))
                y = float(pose.get("y_mm", 0.0))
                z = float(pose.get("z_mm", 0.0))
                return (x, y, z)
            if isinstance(pose, (list, tuple)) and len(pose) >= 3:
                x, y, z = pose[0], pose[1], pose[2]
                return (float(x), float(y), float(z))
    except Exception:
        pass

    # API option 2: actions.user or actions.tracking may expose helpers
    try:
        if actions and hasattr(actions, "user") and hasattr(actions.user, "head_position_mm"):
            xyz = actions.user.head_position_mm()
            if isinstance(xyz, (list, tuple)) and len(xyz) >= 3:
                return (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    except Exception:
        pass

    # If not available, return None
    return None


# ===================== Streaming Job =====================

def _send_pose_tick():
    global _sock
    if _sock is None:
        return

    xyz_mm = _get_head_position_mm()
    if xyz_mm is None:
        # no data yet. Optionally send zeros so opentrack detects the stream
        if not SEND_ZERO_WHEN_NO_DATA:
            return
        x_cm = 0.0
        y_cm = 0.0
        z_cm = 0.0
    else:
        x_cm = xyz_mm[0] * SCALE_MM_TO_CM * AXIS_FLIPS["x"]
        y_cm = xyz_mm[1] * SCALE_MM_TO_CM * AXIS_FLIPS["y"]
        z_cm = xyz_mm[2] * SCALE_MM_TO_CM * AXIS_FLIPS["z"]

    # yaw/pitch/roll zeroed; positions in cm
    payload = struct.pack("<dddddd", 0.0, 0.0, 0.0, float(x_cm), float(y_cm), float(z_cm))
    try:
        _sock.sendto(payload, (HOST, PORT))
    except Exception:
        # swallow transient UDP/network errors
        pass


# ===================== Talon Actions =====================

mod = Module()


@mod.action_class
class Actions:
    def opentrack_start(self):
        """Start streaming Talon head position to opentrack via UDP."""
        global _job
        _udp_open()
        _enable_head_tracking(True)
        cron_ok = False
        try:
            # schedule periodic sends
            if cron is not None:
                # format: e.g., '16ms'
                _job = cron.interval(f"{SEND_INTERVAL_MS}ms", _send_pose_tick)  # type: ignore[arg-type]
                cron_ok = True
        except Exception:
            _job = None
        # Send an immediate heartbeat so opentrack sees the stream quickly
        try:
            _send_pose_tick()
        except Exception:
            pass
        try:
            if app:
                if cron_ok:
                    app.notify(f"opentrack UDP streaming started on {HOST}:{PORT}")
                else:
                    app.notify(f"opentrack UDP streaming started on {HOST}:{PORT} (no cron; only one-shot)")
        except Exception:
            pass

    def opentrack_stop(self):
        """Stop streaming to opentrack and disable head tracking if we enabled it."""
        global _job
        try:
            if _job is not None and cron is not None:
                cron.cancel(_job)
        except Exception:
            pass
        _job = None
        _udp_close()
        _enable_head_tracking(False)
        try:
            if app:
                app.notify("opentrack UDP streaming stopped")
        except Exception:
            pass
