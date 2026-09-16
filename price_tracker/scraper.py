"""Fetch product pages over HTTP (or from bundled demo files)."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from pathlib import Path

import requests

from price_tracker.config import Product
from price_tracker.parsing import BlockedError, is_captcha_page

logger = logging.getLogger(__name__)

DEMO_PAGES_DIR = Path(__file__).parent / "demo_pages"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """The page could not be downloaded after all retries."""


def fetch_html(
    url: str,
    *,
    session: requests.Session | None = None,
    retries: int = 3,
    backoff_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """GET ``url`` with exponential backoff on network errors and 429/5xx responses."""
    session = session or requests.Session()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,es-MX;q=0.8"}

    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=headers, timeout=(5, 15))
        except (requests.ConnectionError, requests.Timeout) as exc:
            problem = str(exc)
        else:
            if is_captcha_page(response.text):
                raise BlockedError(f"Amazon served a robot-check page for {url}")
            if response.status_code not in RETRYABLE_STATUS:
                response.raise_for_status()  # 4xx like 404: retrying won't help
                return response.text
            problem = f"HTTP {response.status_code}"

        if attempt == retries:
            break
        wait = backoff_seconds * 2 ** (attempt - 1) + random.uniform(0, 1)
        logger.warning(
            "Attempt %d/%d failed (%s); retrying in %.1fs", attempt, retries, problem, wait
        )
        sleep(wait)

    raise FetchError(f"Giving up on {url} after {retries} attempts: {problem}")


def load_demo_html(product: Product) -> str:
    """Return the saved demo page for ``product`` (named ``<ASIN>.html``)."""
    path = DEMO_PAGES_DIR / f"{product.asin}.html"
    if not path.exists():
        raise FetchError(f"No demo page for {product.asin} (expected {path})")
    return path.read_text(encoding="utf-8")


def polite_delay(min_seconds: float, max_seconds: float) -> None:
    """Pause a random amount of time between requests so we don't hammer the site."""
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug("Sleeping %.1fs before next request", delay)
    time.sleep(delay)
