"""
SWIM Plugin — Centralized Logging
==================================
Controlled entirely by two keys in PLUGINS_CONFIG:

    PLUGINS_CONFIG = {
        'netbox_swim': {
            'logging':  True,                    # Full DEBUG logging (default: False)
            'log_file': '/path/to/swim.log',     # Optional file path; omit to log stderr only
        }
    }

Regardless of 'logging' setting:
  - ERROR and WARNING always go to stderr → always visible in docker logs

When `logging` is True:
  - Full DEBUG output goes to stderr
  - If `log_file` is set → also written to a rotating file (10 MB x 5 backups)
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

    fmt = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)-8s [SWIM] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if not _logging_enabled():
        # Logging disabled — but ERROR/WARNING still go to stderr
        # so problems are NEVER invisible in docker logs
        logger.setLevel(logging.WARNING)
        err_handler = logging.StreamHandler(sys.stderr)
        err_handler.setLevel(logging.WARNING)
        err_handler.setFormatter(fmt)
        logger.addHandler(err_handler)
        logger.propagate = False
        return logger

    # Full logging enabled
    logger.setLevel(logging.DEBUG)

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
            # Guard: if Docker mounted an empty volume here it creates a directory
            # instead of a file. Detect this early and explain exactly how to fix it.
            if path.is_dir():
                print(
                    f"[SWIM] ERROR: '{log_path}' is a directory, not a file.\n"
                    f"[SWIM] This is a Docker volume mount issue. Fix it on the host:\n"
                    f"[SWIM]   touch {log_path}   # create the file first\n"
                    f"[SWIM]   docker compose up -d netbox  # restart the container\n"
                    f"[SWIM] Falling back to stderr-only logging.",
                    file=sys.stderr,
                    flush=True
                )
            else:
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
            _correct_paths = (
                "  Option A (persistent): /opt/netbox/swim.log\n"
                "            → add to docker-compose: - /host/path/swim.log:/opt/netbox/swim.log\n"
                "  Option B (ephemeral): /tmp/swim.log   ← note: /tmp not /temp\n"
                "            → no volume mount needed, file lives in container only"
            )
            print(
                f"[SWIM] ERROR: Could not create log file '{log_path}': {type(e).__name__}: {e}\n"
                f"[SWIM] Common cause: path typo (e.g. '/temp' should be '/tmp') or directory not writable.\n"
                f"[SWIM] Suggested paths that work in Docker:\n{_correct_paths}\n"
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

    ERROR and WARNING always emit to stderr regardless of 'logging' config.
    DEBUG and INFO are only emitted when 'logging: True' is set.
    """

    def __init__(self, device, library: str = 'unknown'):
        self.device_name = getattr(device, 'name', str(device))
        self.library = library.upper()
        self._verbose = _logging_enabled()  # True = DEBUG+INFO also emitted
        self._prefix = f"[{self.library}] [{self.device_name}]"

    # --- Connection lifecycle ---

    def connecting(self, host: str, username: str):
        if self._verbose:
            swim_log.info(f"{self._prefix} Initiating connection -> host={host} user={username}")

    def connected(self):
        if self._verbose:
            swim_log.info(f"{self._prefix} Connection established")

    def disconnected(self):
        if self._verbose:
            swim_log.info(f"{self._prefix} Connection closed")

    def connect_failed(self, exc: Exception):
        # Always emit — connection failures must always be visible
        swim_log.error(f"{self._prefix} Connection FAILED: {type(exc).__name__}: {exc}")

    # --- Command / response tracing ---

    def command(self, cmd: str):
        if self._verbose:
            swim_log.debug(f"{self._prefix} >> CMD: {cmd.strip()}")

    def response(self, cmd: str, output: str):
        if self._verbose:
            preview = (output or '').strip()
            max_chars = 2000
            if len(preview) > max_chars:
                preview = preview[:max_chars] + f"\n... [truncated {len(output) - max_chars} chars]"
            swim_log.debug(f"{self._prefix} << RESPONSE [{cmd.strip()}]:\n{preview}")

    def command_failed(self, cmd: str, exc: Exception):
        # Always emit — command failures must always be visible
        swim_log.error(
            f"{self._prefix} Command FAILED [{cmd.strip()}]: {type(exc).__name__}: {exc}"
        )

    # --- General event logging ---

    def error(self, message: str, exc: Exception = None):
        # Always emit
        if exc:
            swim_log.error(f"{self._prefix} ERROR: {message}: {type(exc).__name__}: {exc}")
        else:
            swim_log.error(f"{self._prefix} ERROR: {message}")

    def warning(self, message: str):
        # Always emit
        swim_log.warning(f"{self._prefix} WARNING: {message}")

    def info(self, message: str):
        if self._verbose:
            swim_log.info(f"{self._prefix} {message}")

    def debug(self, message: str):
        if self._verbose:
            swim_log.debug(f"{self._prefix} {message}")
