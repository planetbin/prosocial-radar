"""
Profile loading utilities for Prosocial Research Radar.

Profiles keep research interests, filters, output preferences, and delivery
settings outside the code so each project can tune the radar without editing
Python modules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised in user environments
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_NAME = "default"
DEFAULT_PROFILE_PATH = REPO_ROOT / "profiles" / f"{DEFAULT_PROFILE_NAME}.yml"


class ProfileError(RuntimeError):
    """Raised when a research profile cannot be loaded."""


def resolve_profile_path() -> Path:
    """Resolve the active profile path from environment variables."""
    explicit_path = os.environ.get("RADAR_PROFILE_PATH", "").strip()
    if explicit_path:
        path = Path(explicit_path)
        return path if path.is_absolute() else REPO_ROOT / path

    profile_name = os.environ.get("RADAR_PROFILE", DEFAULT_PROFILE_NAME).strip()
    if not profile_name:
        profile_name = DEFAULT_PROFILE_NAME

    candidate = Path(profile_name)
    if candidate.suffix in {".yml", ".yaml"}:
        return candidate if candidate.is_absolute() else REPO_ROOT / candidate

    return REPO_ROOT / "profiles" / f"{profile_name}.yml"


def load_profile(path: Path | None = None) -> Dict[str, Any]:
    """Load a YAML profile and return it as a dictionary."""
    if yaml is None:
        raise ProfileError(
            "PyYAML is required to load radar profiles. Run `pip install -r requirements.txt`."
        ) from _YAML_IMPORT_ERROR

    profile_path = path or resolve_profile_path()
    if not profile_path.exists():
        raise ProfileError(f"Research profile not found: {profile_path}")

    with profile_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    if not isinstance(data, dict):
        raise ProfileError(f"Research profile must be a YAML mapping: {profile_path}")

    data["__path__"] = str(profile_path)
    return data
