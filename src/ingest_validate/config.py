"""Read local connection settings without executing shell expressions."""

import json
import os
import re
from pathlib import Path


def read_settings(path):
    settings = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError(f"Invalid setting on line {number}")
        if value.startswith('"'):
            # Decode quoted data only; never expand variables or run commands.
            value = json.loads(value)
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if not isinstance(value, str):
            raise ValueError(f"Setting on line {number} must be a string")
        settings[key] = value
    return settings


def connection_settings(path=None):
    """Explicit environment variables take precedence over a local file."""
    candidate = Path(path) if path is not None else Path.cwd() / ".env"
    settings = read_settings(candidate) if candidate.is_file() else {}
    if path is not None and not candidate.is_file():
        raise ValueError(f"Settings file does not exist: {candidate}")
    settings.update({key: value for key, value in os.environ.items() if key.startswith("POCKETBASE_") and value})
    return settings
