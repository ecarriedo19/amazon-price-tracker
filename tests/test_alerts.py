import pytest

from price_tracker.alerts import Alert, Reason, evaluate, format_message


@pytest.mark.parametrize(
    ("previous", "current", "target", "expected"),
    [
        (None, 2000, None, None),  # first observation: nothing to compare
        (2000, 2000, None, None),  # unchanged
        (2000, 1950, None, None),  # -2.5%, below the 5% threshold
        (2000, 1900, None, Reason.PRICE_DROP),  # exactly -5%
        (2000, 2150, None, Reason.PRICE_RISE),  # +7.5%
        (2000, 1790, 1800, Reason.TARGET_REACHED),  # crossed the target
        (None, 1790, 1800, Reason.TARGET_REACHED),  # first run already under target
        (1795, 1790, 1800, None),  # already under target, tiny move: no repeat alert
        (1795, 1500, 1800, Reason.PRICE_DROP),  # already under target but big drop
    ],
)
def test_evaluate(previous, current, target, expected):
    reason = evaluate(
        previous_price=previous, current_price=current, threshold_pct=5, target_price=target
    )
    assert reason == expected


def _alert(**overrides):
    values = dict(
        name="Karcher K2",
        title="Kärcher Hidrolavadora K2",
        url="https://www.amazon.com.mx/dp/B0CM49Z6SN",
        currency="MXN",
        previous_price=2000.0,
        current_price=1800.0,
        reason=Reason.PRICE_DROP,
    )
    return Alert(**(values | overrides))


def test_message_english():
    message = format_message(_alert())
    assert "Price dropped" in message
    assert "Was: $2,000.00 MXN" in message
    assert "Now: $1,800.00 MXN" in message
    assert "Change: -10.0%" in message


def test_message_spanish_and_no_previous_price():
    message = format_message(_alert(previous_price=None, reason=Reason.TARGET_REACHED), "es")
    assert "Precio objetivo alcanzado" in message
    assert "Antes" not in message
    assert "Cambio" not in message
