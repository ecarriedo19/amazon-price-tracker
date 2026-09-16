"""Decide when a price change is worth an alert, and word the message."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Reason(Enum):
    TARGET_REACHED = "target_reached"
    PRICE_DROP = "price_drop"
    PRICE_RISE = "price_rise"


@dataclass(frozen=True)
class Alert:
    name: str
    title: str
    url: str
    currency: str
    previous_price: float | None
    current_price: float
    reason: Reason

    @property
    def change_pct(self) -> float | None:
        if not self.previous_price:
            return None
        return (self.current_price - self.previous_price) / self.previous_price * 100


def evaluate(
    *,
    previous_price: float | None,
    current_price: float,
    threshold_pct: float,
    target_price: float | None = None,
) -> Reason | None:
    """Return why we should alert, or ``None``.

    - Target: alert when the price is at or below ``target_price`` and it was
      not already there last time (so you get one alert, not one per run).
    - Threshold: alert when the price moved by at least ``threshold_pct`` percent.
    """
    newly_under_target = (
        target_price is not None
        and current_price <= target_price
        and (previous_price is None or previous_price > target_price)
    )
    if newly_under_target:
        return Reason.TARGET_REACHED

    if previous_price is None or previous_price <= 0:
        return None
    change_pct = (current_price - previous_price) / previous_price * 100
    if abs(change_pct) >= threshold_pct:
        return Reason.PRICE_DROP if change_pct < 0 else Reason.PRICE_RISE
    return None


MESSAGES = {
    "en": {
        Reason.TARGET_REACHED: "Target price reached",
        Reason.PRICE_DROP: "Price dropped",
        Reason.PRICE_RISE: "Price went up",
        "was": "Was",
        "now": "Now",
        "change": "Change",
        "link": "Link",
    },
    "es": {
        Reason.TARGET_REACHED: "Precio objetivo alcanzado",
        Reason.PRICE_DROP: "Bajó de precio",
        Reason.PRICE_RISE: "Subió de precio",
        "was": "Antes",
        "now": "Ahora",
        "change": "Cambio",
        "link": "Ver en",
    },
}


def format_money(amount: float, currency: str) -> str:
    return f"${amount:,.2f} {currency}"


def format_message(alert: Alert, locale: str = "en") -> str:
    """Plain-text alert body suitable for WhatsApp or a terminal."""
    text = MESSAGES.get(locale, MESSAGES["en"])
    lines = [f"Price Tracker: {text[alert.reason]}", alert.title or alert.name]
    if alert.previous_price is not None:
        lines.append(f"{text['was']}: {format_money(alert.previous_price, alert.currency)}")
    lines.append(f"{text['now']}: {format_money(alert.current_price, alert.currency)}")
    if alert.change_pct is not None:
        lines.append(f"{text['change']}: {alert.change_pct:+.1f}%")
    lines.append(f"{text['link']}: {alert.url}")
    return "\n".join(lines)
