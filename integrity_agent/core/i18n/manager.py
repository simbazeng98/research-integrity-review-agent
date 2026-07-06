from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_LOCALES = {"en", "zh"}


class I18nManager:
    _instance: "I18nManager | None" = None

    def __new__(cls) -> "I18nManager":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._current_locale = os.environ.get("INTEGRITY_LOCALE", "en")
            if instance._current_locale not in SUPPORTED_LOCALES:
                instance._current_locale = "en"
            instance._translations = instance._load_locales()
            cls._instance = instance
        return cls._instance

    def set_locale(self, locale: str) -> None:
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale: {locale}")
        self._current_locale = locale

    def get_locale(self) -> str:
        return self._current_locale

    def translate(self, key: str, default: str | None = None) -> str:
        value: Any = self._translations.get(self._current_locale, {})
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default or key
            value = value[part]
        if value is None:
            return default or key
        return str(value)

    def _load_locales(self) -> dict[str, Any]:
        locales_dir = Path(__file__).resolve().parent / "locales"
        translations: dict[str, Any] = {}
        for locale in sorted(SUPPORTED_LOCALES):
            path = locales_dir / f"{locale}.yml"
            if not path.exists():
                translations[locale] = {}
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            translations[locale] = data if isinstance(data, dict) else {}
        return translations


_i18n = I18nManager()


def _(key: str, default: str | None = None) -> str:
    return _i18n.translate(key, default)
