import pytest

from price_tracker.parsing import (
    BlockedError,
    PriceNotFoundError,
    currency_for_url,
    parse_price_text,
    parse_product_page,
)

MX_URL = "https://www.amazon.com.mx/dp/B0CM49Z6SN"
US_URL = "https://www.amazon.com/dp/B000000001"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,899.00", 1899.0),
        ("MX$2,050.00", 2050.0),
        ("$24.99", 24.99),
        ("US$1,234.5", 1234.5),
        ("1,899", 1899.0),
        ("2050", 2050.0),
        ("1.899,00", 1899.0),
        ("$\xa01,299.00", 1299.0),
        ("12,345,678.90 MXN", 12345678.90),
        ("Currently unavailable", None),
    ],
)
def test_parse_price_text(text, expected):
    assert parse_price_text(text) == expected


def test_core_price_block(load_fixture):
    page = parse_product_page(load_fixture("core_price_mxn.html"), MX_URL)
    assert page.title == "Kärcher Hidrolavadora K2"
    assert page.price == 1899.0
    assert page.currency == "MXN"


def test_whole_and_fraction_fallback(load_fixture):
    page = parse_product_page(load_fixture("whole_fraction_only.html"), MX_URL)
    assert page.price == 2050.50
    assert page.currency == "MXN"


def test_legacy_priceblock_uses_domain_currency(load_fixture):
    page = parse_product_page(load_fixture("legacy_priceblock_usd.html"), US_URL)
    assert page.price == 24.99
    assert page.currency == "USD"


def test_captcha_page_raises_blocked(load_fixture):
    with pytest.raises(BlockedError, match="captcha"):
        parse_product_page(load_fixture("captcha.html"), MX_URL)


def test_missing_price_raises(load_fixture):
    with pytest.raises(PriceNotFoundError):
        parse_product_page(load_fixture("unavailable.html"), MX_URL)


@pytest.mark.parametrize(
    ("url", "currency"),
    [(MX_URL, "MXN"), (US_URL, "USD"), ("https://amazon.com.mx/dp/X", "MXN")],
)
def test_currency_for_url(url, currency):
    assert currency_for_url(url) == currency
