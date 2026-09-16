from pathlib import Path

import pytest

from price_tracker.config import ConfigError, load_config, normalize_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.amazon.com.mx/gp/product/B0CM49Z6SN/ref=ox_sc_act_title_14?smid=AVDBXBAVVSXLQ&psc=1",
            "https://www.amazon.com.mx/dp/B0CM49Z6SN",
        ),
        (
            "https://www.amazon.com/Some-Product-Name/dp/B000000001/ref=sr_1_3?keywords=x",
            "https://www.amazon.com/dp/B000000001",
        ),
    ],
)
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected


@pytest.mark.parametrize("url", ["https://example.com/dp/B0CM49Z6SN", "https://www.amazon.com/"])
def test_normalize_url_rejects_bad_urls(url):
    with pytest.raises(ConfigError):
        normalize_url(url)


def test_load_config(tmp_path):
    path = tmp_path / "products.yaml"
    path.write_text(
        """
settings:
  threshold_pct: 10
  locale: es
products:
  - name: Karcher
    url: https://www.amazon.com.mx/gp/product/B0CM49Z6SN/ref=abc?psc=1
    target_price: 1800
""",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.settings.threshold_pct == 10
    assert config.settings.locale == "es"
    product = config.products[0]
    assert product.asin == "B0CM49Z6SN"
    assert product.target_price == 1800
    assert product.threshold_pct is None


def test_example_config_is_valid():
    config = load_config(Path(__file__).parents[1] / "products.yaml")
    assert len(config.products) == 2
