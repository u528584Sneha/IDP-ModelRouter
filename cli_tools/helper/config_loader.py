"""Unified JSON config loader for tool execution mode.

Supports layered config resolution:
- project root: `config/config.json`
- local scope nearest to the target file: `<tool_dir>/config/config.json`

This module exports loaded settings to `os.environ` so existing code using
`os.getenv` continues to work.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_IGNORED_KEYS = {"tool_id", "parent_tool", "description", "name"}


class ConfigLoader:
    """Class-based config loader with level-aware validation."""

    def __init__(
        self,
        *,
        file_path: str,
        override: bool = True,
        validation_level: str = "auto",
        required_keys: Optional[Sequence[str]] = None,
    ) -> None:
        self.file_path = Path(file_path).resolve()
        self.override = override
        self.validation_level = validation_level
        self.required_keys = tuple(required_keys) if required_keys else None

        self._scope = self._detect_scope()
        self._config_chain = self._build_config_chain()
        self._settings, self._required_map = self._load_settings_and_required_map()
        self._validate()

    @property
    def settings(self) -> Dict[str, Any]:
        return dict(self._settings)

    @property
    def scope(self) -> str:
        return self._scope

    @property
    def config_chain(self) -> List[Path]:
        return list(self._config_chain)

    @property
    def required_variables(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._required_map.items()}

    def apply_to_env(self) -> None:
        for key, value in self._settings.items():
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            if self.override or key not in os.environ:
                os.environ[key] = str(value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def require_str(self, key: str) -> str:
        value = self.get(key, "")
        text = str(value).strip() if value is not None else ""
        if not text:
            raise KeyError(f"Missing required configuration key: {key}")
        return text

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._settings.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self._settings.get(key, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._settings.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return bool(value)

    def get_list(
        self,
        key: str,
        default: Optional[List[str]] = None,
        separator: str = ",",
    ) -> List[str]:
        if default is None:
            default = []
        value = self._settings.get(key)
        if value is None:
            return default
        if isinstance(value, list):
            return [str(x) for x in value]
        if isinstance(value, str):
            return [x.strip() for x in value.split(separator) if x.strip()]
        return default

    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if default is None:
            default = {}
        value = self._settings.get(key)
        if value is None:
            return default
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return default
        return default

    def _detect_scope(self) -> str:
        if self.validation_level in ("tool",):
            return self.validation_level
        if "tools" in self.file_path.parts:
            return "tool"
        return "tool"

    @staticmethod
    def _extract_settings(data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if isinstance(data.get("settings"), dict):
            return data["settings"]
        return {k: v for k, v in data.items() if k not in _IGNORED_KEYS}

    @staticmethod
    def _extract_required_variables(data: Dict[str, Any]) -> Dict[str, List[str]]:
        if not isinstance(data, dict):
            return {}

        source = data.get("REQUIRED_VARIABLES")
        if source is None and isinstance(data.get("settings"), dict):
            source = data["settings"].get("REQUIRED_VARIABLES")
        if source is None:
            return {}

        def _to_list(value: Any) -> List[str]:
            if isinstance(value, list):
                return [str(x).strip() for x in value if str(x).strip()]
            if isinstance(value, str):
                txt = value.strip()
                return [txt] if txt else []
            return []

        if isinstance(source, list):
            vals = _to_list(source)
            return {"tool": vals}

        if isinstance(source, dict):
            out: Dict[str, List[str]] = {}
            common = _to_list(source.get("common"))
            tool = _to_list(source.get("tool"))
            if common:
                tool = [*common, *tool]
            if tool:
                out["tool"] = tool
            return out

        return {}

    @staticmethod
    def _read_config(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {
            "settings": ConfigLoader._extract_settings(raw),
            "required_variables": ConfigLoader._extract_required_variables(raw),
        }

    def _build_config_chain(self) -> List[Path]:
        chain: List[Path] = []
        for folder in [self.file_path.parent, *self.file_path.parents]:
            cfg_dir = folder / "config" / "config.json"
            if cfg_dir.exists():
                chain.append(cfg_dir)
                continue
            cfg_legacy = folder / "config.json"
            if cfg_legacy.exists():
                chain.append(cfg_legacy)
        chain.reverse()
        return chain

    def _load_settings_and_required_map(self) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        merged: Dict[str, Any] = {}
        required_map: Dict[str, List[str]] = {"tool": []}
        for cfg in self._config_chain:
            parsed = self._read_config(cfg)
            merged.update(parsed.get("settings", {}))
            req = parsed.get("required_variables", {})
            vals = req.get("tool", [])
            if vals:
                required_map["tool"] = vals
        return merged, required_map

    def _validation_keys(self) -> Tuple[str, ...]:
        if self.required_keys:
            return tuple(self.required_keys)
        return tuple(self._required_map.get(self._scope, ()))

    def _validate(self) -> None:
        required = self._validation_keys()
        if not required:
            return
        missing = [key for key in required if key not in self._settings or str(self._settings[key]).strip() == ""]
        if missing:
            raise KeyError(
                f"Missing required configuration keys for {self._scope}: {', '.join(missing)}"
            )


_loader_cache: Dict[Tuple[str, bool, str, Tuple[str, ...]], ConfigLoader] = {}


def get_config(
    file_path: str,
    *,
    override: bool = True,
    validation_level: str = "auto",
    required_keys: Optional[Sequence[str]] = None,
) -> ConfigLoader:
    key_tuple = tuple(required_keys) if required_keys else ()
    cache_key = (str(Path(file_path).resolve()), override, validation_level, key_tuple)
    loader = _loader_cache.get(cache_key)
    if loader is None:
        loader = ConfigLoader(
            file_path=file_path,
            override=override,
            validation_level=validation_level,
            required_keys=required_keys,
        )
        _loader_cache[cache_key] = loader
    return loader


def load_config_for_file(
    file_path: str,
    *,
    override: bool = True,
    validation_level: str = "auto",
    required_keys: Optional[Sequence[str]] = None,
) -> None:
    loader = get_config(
        file_path,
        override=override,
        validation_level=validation_level,
        required_keys=required_keys,
    )
    loader.apply_to_env()


def get_setting(key: str, default: Any = None) -> Any:
    return os.getenv(key, default)
