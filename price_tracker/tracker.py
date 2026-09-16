"""One tracking run: fetch each product, store the price, alert if needed."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from price_tracker.alerts import Alert, evaluate, format_message
from price_tracker.config import Config, Product
from price_tracker.notifiers import Notifier
from price_tracker.parsing import BlockedError, PriceNotFoundError, parse_product_page
from price_tracker.scraper import FetchError, fetch_html, load_demo_html, polite_delay
from price_tracker.storage import PriceRecord, append_record, latest_by_asin, read_history

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    checked: int = 0
    failed: int = 0
    alerts: int = 0


def check_product(
    product: Product,
    *,
    previous: PriceRecord | None,
    threshold_pct: float,
    demo: bool,
) -> tuple[PriceRecord, Alert | None]:
    """Fetch and parse one product; return the new record and an alert (if any)."""
    html = load_demo_html(product) if demo else fetch_html(product.url)
    page = parse_product_page(html, product.url, fallback_title=product.name)
    record = PriceRecord(
        timestamp=datetime.now(UTC),
        asin=product.asin,
        name=product.name,
        title=page.title,
        price=page.price,
        currency=page.currency,
    )
    previous_price = previous.price if previous else None
    reason = evaluate(
        previous_price=previous_price,
        current_price=page.price,
        threshold_pct=product.threshold_pct or threshold_pct,
        target_price=product.target_price,
    )
    alert = None
    if reason:
        alert = Alert(
            name=product.name,
            title=page.title,
            url=product.url,
            currency=page.currency,
            previous_price=previous_price,
            current_price=page.price,
            reason=reason,
        )
    return record, alert


def run(
    config: Config, history_path: Path, notifier: Notifier, *, demo: bool = False
) -> RunSummary:
    settings = config.settings
    latest = latest_by_asin(read_history(history_path))
    summary = RunSummary()

    for index, product in enumerate(config.products):
        if index and not demo:
            polite_delay(settings.min_delay, settings.max_delay)
        try:
            record, alert = check_product(
                product,
                previous=latest.get(product.asin),
                threshold_pct=settings.threshold_pct,
                demo=demo,
            )
        except (BlockedError, FetchError, PriceNotFoundError) as exc:
            summary.failed += 1
            logger.error("%s: %s", product.name, exc)
            continue

        append_record(history_path, record)
        summary.checked += 1
        logger.info("%s: %s %.2f", product.name, record.currency, record.price)
        if alert:
            summary.alerts += 1
            notifier.send(format_message(alert, settings.locale))

    return summary
