from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings


class ConfigurationError(RuntimeError):
    """Raised when an internal bundled configuration cannot be loaded."""


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative


def load_json_config(name: str) -> dict[str, Any]:
    try:
        with resource_path(f"app/config/{name}").open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(
            f"No se pudo cargar la configuración interna «{name}». "
            "Reinstale la aplicación o genere nuevamente el paquete."
        ) from exc
    if not isinstance(config, dict):
        raise ConfigurationError(
            f"La configuración interna «{name}» no tiene el formato esperado."
        )
    return config


class AppSettings:
    """Only non-sensitive preferences are persisted."""

    def __init__(self) -> None:
        self._settings = QSettings("RuralFindMe", "RuralFindMe")

    @property
    def sound_enabled(self) -> bool:
        return self._settings.value("sound_enabled", True, type=bool)

    @sound_enabled.setter
    def sound_enabled(self, value: bool) -> None:
        self._settings.setValue("sound_enabled", value)

    @property
    def reduced_animation(self) -> bool:
        return self._settings.value("reduced_animation", False, type=bool)

    @reduced_animation.setter
    def reduced_animation(self, value: bool) -> None:
        self._settings.setValue("reduced_animation", value)
