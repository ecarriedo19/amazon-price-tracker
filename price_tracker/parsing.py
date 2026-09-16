"""Turn an Amazon product page (HTML) into a title, price and currency."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

# Tried in order; Amazon moves prices between these containers depending on
# the product type, the marketplace and whether a deal is running.
PRICE_SELECTORS = (
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#corePrice_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    "#priceblock_dealprice",
    "#priceblock_saleprice",
    "#priceblock_ourprice",
    "#price_inside_buybox",
)

CAPTCHA_MARKERS = (
    "/errors/validatecaptcha",
    "enter the characters you see below",
    "type the characters you see in this image",
    "introduce los caracteres que ves",
    "api-services-support@amazon.com",
)

CURRENCY_BY_DOMAIN = {"amazon.com.mx": "MXN", "amazon.com": "USD", "amazon.ca": "CAD"}


class BlockedError(RuntimeError):
    """Amazon served a captcha / robot-check page instead of the product."""


class PriceNotFoundError(RuntimeError):
    """The page loaded but no price could be found (out of stock or layout change)."""


@dataclass(frozen=True)
class ParsedPage:
    title: str
    price: float
    currency: str


def is_captcha_page(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in CAPTCHA_MARKERS)


def currency_for_url(url: str) -> str:
    """Best guess at the marketplace currency from the domain (``$`` is ambiguous)."""
    for domain, currency in CURRENCY_BY_DOMAIN.items():
        if re.search(rf"//(www\.)?{re.escape(domain)}(/|$)", url):
            return currency
    return "USD"


def detect_currency(text: str) -> str | None:
    """Return a currency code if the price text names one explicitly."""
    upper = text.upper()
    if "MX$" in upper or "MXN" in upper:
        return "MXN"
    if "US$" in upper or "USD" in upper:
        return "USD"
    if "CA$" in upper or "CAD" in upper:
        return "CAD"
    return None


def parse_price_text(text: str) -> float | None:
    """Parse a price like ``MX$1,899.00``, ``$24.99``, ``1.899,00`` or ``2050``.

    Returns ``None`` when there is no number in ``text``.
    """
    match = re.search(r"\d[\d.,\s\xa0]*", text)
    if not match:
        return None
    number = re.sub(r"[\s\xa0]", "", match.group()).rstrip(".,")

    # The last separator is a decimal point only if 1-2 digits follow it;
    # otherwise (e.g. "1,899" or "1.899") it separates thousands.
    decimal_pos = max(number.rfind("."), number.rfind(","))
    if decimal_pos == -1 or len(number) - decimal_pos - 1 not in (1, 2):
        return float(re.sub(r"[.,]", "", number))
    whole = re.sub(r"[.,]", "", number[:decimal_pos])
    fraction = number[decimal_pos + 1 :]
    return float(f"{whole}.{fraction}")


def _find_price_text(soup: BeautifulSoup) -> str | None:
    for selector in PRICE_SELECTORS:
        element = soup.select_one(selector)
        if element and element.get_text(strip=True):
            return element.get_text(strip=True)

    whole = soup.select_one("span.a-price-whole")
    if whole:
        fraction = soup.select_one("span.a-price-fraction")
        symbol = soup.select_one("span.a-price-symbol")
        whole_digits = whole.get_text(strip=True).rstrip(".,")
        fraction_digits = fraction.get_text(strip=True) if fraction else "00"
        prefix = symbol.get_text(strip=True) if symbol else ""
        return f"{prefix}{whole_digits}.{fraction_digits}"

    meta = soup.find("meta", attrs={"itemprop": "price"})
    if meta and meta.get("content"):
        return str(meta["content"])
    return None


def parse_product_page(html: str, url: str, fallback_title: str = "") -> ParsedPage:
    """Extract title, price and currency. Raises on captcha or missing price."""
    if is_captcha_page(html):
        raise BlockedError(
            "Amazon returned a captcha / robot-check page. Try again later, "
            "run less often, or use --demo to work offline."
        )

    soup = BeautifulSoup(html, "html.parser")
    title_element = soup.select_one("#productTitle")
    title = title_element.get_text(" ", strip=True) if title_element else fallback_title

    price_text = _find_price_text(soup)
    price = parse_price_text(price_text) if price_text else None
    if price is None:
        raise PriceNotFoundError(f"No price found on page for {url}")

    currency = detect_currency(price_text or "") or currency_for_url(url)
    return ParsedPage(title=title, price=price, currency=currency)
