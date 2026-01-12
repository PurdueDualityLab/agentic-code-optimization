"""Base utilities for parsing configuration subsections."""

from __future__ import annotations

import os
import re
from abc import ABC
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, get_args, get_origin


class SubSectionParser(ABC):
    """Shared interface for configuration section loaders."""

    SECTION: str

    @staticmethod
    def _resolve_env_vars(value: Any) -> Any:
        """Resolve environment variable references in config values.

        Supports ${ENV_VAR} syntax. Examples:
            api_key = ${OPENAI_API_KEY}
            path = /data/${DATA_DIR}/files

        Args:
            value: Config value that may contain ${VAR_NAME} references

        Returns:
            Value with environment variables substituted

        Raises:
            KeyError: If referenced environment variable is not set
        """
        if not isinstance(value, str):
            return value

        def replace_env(match: re.Match[str]) -> str:
            env_var = match.group(1)
            env_value = os.environ[env_var]
            if env_value is None:
                raise KeyError(f"Environment variable '{env_var}' not found")
            return env_value

        # Replace ${VAR_NAME} with environment variable values
        return re.sub(r"\$\{([^}]+)\}", replace_env, value)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Any:
        """Instantiate the subclass using values from its named section."""
        section = payload.get(cls.SECTION, payload)

        if not is_dataclass(cls):
            raise TypeError(f"{cls.__name__} must be a dataclass to use SubSectionParser.")

        kwargs = {}
        for field in fields(cls):
            if not field.init:
                continue

            if field.name in section:
                value = section[field.name]
            elif field.default is not MISSING:
                value = field.default
            elif field.default_factory is not MISSING:  # type: ignore[attr-defined]
                value = field.default_factory()  # type: ignore[misc]
            else:
                raise KeyError(f"Missing required config value: {field.name}")

            if value is None:
                kwargs[field.name] = None
                continue

            # Resolve environment variables in string values
            value = cls._resolve_env_vars(value)

            field_type = field.type
            origin = get_origin(field_type)
            args = get_args(field_type)

            if field_type is Path or Path in args:
                if not isinstance(value, Path):
                    value = Path(value)

            kwargs[field.name] = value

        return cls(**kwargs)
