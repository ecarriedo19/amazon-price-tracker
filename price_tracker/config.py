"""Load and validate ``products.yaml``."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

ASIN_PATTERN = re.compile(r"/(?:dp|gp/product|gp/aw/d|exec/obidos/asin)/([A-Z0-9]{10})(?:[/?]|$)")
SUPPORTED_LOCALES = ("en", "es")


class ConfigError(ValueError):
    """Raised when products.yaml is missing or invalid."""


@dataclass(frozen=True)
class Product:
    name: str
    url: str
    asin: str
    target_price: float | None = None
    threshold_pct: float | None = None


@dataclass(frozen=True)
class Settings:
    threshold_pct: float = 5.0
    locale: str = "en"
    min_delay: float = 3.0
    max_delay: float = 8.0


@dataclass(frozen=True)
class Config:
    products: list[Product]
    settings: Settings = field(default_factory=Settings)


def extract_asin(url: str) -> str:
    """Return the 10-character Amazon product ID (ASIN) found in ``url``."""
    match = ASIN_PATTERN.search(urlparse(url).path + "/")
    if not match:
        raise ConfigError(f"Could not find an ASIN in URL: {url}")
    return match.group(1)


def normalize_url(url: str) -> str:
    """Strip tracking paths and query strings: keep ``https://host/dp/ASIN``."""
    host = urlparse(url).netloc
    if "amazon." not in host:
        raise ConfigError(f"Not an Amazon URL: {url}")
    return f"https://{host}/dp/{extract_asin(url)}"


def _optional_float(raw: dict, key: str, context: str) -> float | None:
    value = raw.get(key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{context}: '{key}' must be a number, got {value!r}") from exc
    if number <= 0:
        raise ConfigError(f"{context}: '{key}' must be positive, got {number}")
    return number


def _parse_product(raw: dict, index: int) -> Product:
    context = f"products[{index}]"
    if not isinstance(raw, dict) or not raw.get("name") or not raw.get("url"):
        raise ConfigError(f"{context}: each product needs a 'name' and a 'url'")
    url = normalize_url(str(raw["url"]))
    return Product(
        name=str(raw["name"]),
        url=url,
        asin=extract_asin(url),
        target_price=_optional_float(raw, "target_price", context),
        threshold_pct=_optional_float(raw, "threshold_pct", context),
    )


def _parse_settings(raw: dict) -> Settings:
    defaults = Settings()
    locale = str(raw.get("locale", defaults.locale))
    if locale not in SUPPORTED_LOCALES:
        raise ConfigError(f"settings.locale must be one of {SUPPORTED_LOCALES}, got {locale!r}")
    delay = raw.get("delay_seconds", [defaults.min_delay, defaults.max_delay])
    if not (isinstance(delay, list) and len(delay) == 2 and 0 <= delay[0] <= delay[1]):
        raise ConfigError("settings.delay_seconds must be [min, max] with 0 <= min <= max")
    return Settings(
        threshold_pct=_optional_float(raw, "threshold_pct", "settings") or defaults.threshold_pct,
        locale=locale,
        min_delay=float(delay[0]),
        max_delay=float(delay[1]),
    )


def load_config(path: Path) -> Config:
    """Read a YAML config file and return a validated :class:`Config`."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_products = data.get("products") or []
    if not raw_products:
        raise ConfigError(f"{path}: no products configured")
    products = [_parse_product(raw, i) for i, raw in enumerate(raw_products)]
    return Config(products=products, settings=_parse_settings(data.get("settings") or {}))
