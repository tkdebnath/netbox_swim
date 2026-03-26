"""
SWIM Plugin — Centralized Logging
==================================
Controlled entirely by two keys in PLUGINS_CONFIG:

    PLUGINS_CONFIG = {
        'netbox_swim': {
            'logging':  True,                    # Enable SWIM logging (default: False)
            'log_file': '/path/to/swim.log',     # Optional file path; omit to log stderr only
        }
    }

When `logging` is False (or absent), all SWIM log calls are silently discarded.
When `logging` is True:
  - Logs always go to stderr  → visible in `docker logs netbox` / RQ worker output
  - If `log_file` is set      → also written to a rotating file (10 MB × 5 backups)

Log level is always DEBUG when logging is enabled so you see every connection
detail, command sent, and response received.
"""

import logging
import logging.handlers
import sys
from functools import lru_cache


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_swim_config() -> dict:
    try:
        from django.conf import settings
        return settings.PLUGINS_CONFIG.get('netbox_swim', {})
    except Exception:
        return {}


def _logging_enabled() -> bool:
    return bool(_get_swim_config().get('logging', False))


def _log_file_path():
    return _get_swim_config().get('log_file', None)


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------

def _build_swim_logger() -> logging.Logger:
    logger = logging.getLogger('netbox_swim')

    # Avoid adding duplicate handlers on Django hot-reload
    if logger.handlers:
        return logger

    if not _logging_enabled():
        # Logging disabled — attach a NullHandler so callsites don't error
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)-8s [SWIM] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Always: stderr (Docker logs / RQ worker output)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    # Optional: rotating file
    log_path = _log_file_path()
    if log_path:
        import pathlib
        path = pathlib.Path(log_path)
        try:
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            # Touch the file to create it if it doesn't exist yet
            path.touch(exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(path),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
        except OSError as e:
            # Print directly to stderr — visible in docker logs even if file logging fails
            print(
                f"[SWIM] ERROR: Could not create log file '{log_path}': {type(e).__name__}: {e}\n"
                f"[SWIM] Falling back to stderr-only logging.",
                file=sys.stderr,
                flush=True
            )

    logger.propagate = False
    return logger


# Module-level logger — import this anywhere in the plugin
swim_log = _build_swim_logger()


# ---------------------------------------------------------------------------
# SwimSessionLogger — per-connection structured tracer
# ---------------------------------------------------------------------------

class SwimSessionLogger:
    """
    Wraps a single device connection session with structured, per-device logging.

    All output goes through `swim_log` and is therefore controlled by the
    `logging` / `log_file` plugin config keys — no extra configuration needed.

    Usage in execute():
        session = SwimSessionLogger(device, library='Scrapli')
        session.connecting(host, username)
        session.connected()
        session.command("show version")
        session.response("show version", raw_output)
        session.command_failed("show inventory", exc)
        session.error("Unexpected state", exc=e)
        session.disconnected()
    """

    def __init__(self, device, library: str = 'unknown'):
        self.device_name = getattr(device, 'name', str(device))
        self.library = library.upper()
        self._enabled = _logging_enabled()
        self._prefix = f"[{self.library}] [{self.device_name}]"

    # --- Connection lifecycle ---

    def connecting(self, host: str, username: str):
        if self._enabled:
            swim_log.info(f"{self._prefix} Initiating connection → host={host} user={username}")

    def connected(self):
        if self._enabled:
            swim_log.info(f"{self._prefix} ✓ Connection established")

    def disconnected(self):
        if self._enabled:
            swim_log.info(f"{self._prefix} Connection closed")

    def connect_failed(self, exc: Exception):
        if self._enabled:
            swim_log.error(f"{self._prefix} ✗ Connection FAILED: {type(exc).__name__}: {exc}")

    # --- Command / response tracing ---

    def command(self, cmd: str):
        if self._enabled:
            swim_log.debug(f"{self._prefix} >> CMD: {cmd.strip()}")

    def response(self, cmd: str, output: str):
        if self._enabled:
            preview = (output or '').strip()
            max_chars = 2000
            if len(preview) > max_chars:
                preview = preview[:max_chars] + f"\n... [truncated {len(output) - max_chars} chars]"
            swim_log.debug(f"{self._prefix} << RESPONSE [{cmd.strip()}]:\n{preview}")

    def command_failed(self, cmd: str, exc: Exception):
        if self._enabled:
            swim_log.error(
                f"{self._prefix} ✗ Command FAILED [{cmd.strip()}]: {type(exc).__name__}: {exc}"
            )

    # --- General event logging ---

    def error(self, message: str, exc: Exception = None):
        if self._enabled:
            if exc:
                swim_log.error(f"{self._prefix} ERROR — {message}: {type(exc).__name__}: {exc}")
            else:
                swim_log.error(f"{self._prefix} ERROR — {message}")

    def warning(self, message: str):
        if self._enabled:
            swim_log.warning(f"{self._prefix} WARNING — {message}")

    def info(self, message: str):
        if self._enabled:
            swim_log.info(f"{self._prefix} {message}")

    def debug(self, message: str):
        if self._enabled:
            swim_log.debug(f"{self._prefix} {message}")
