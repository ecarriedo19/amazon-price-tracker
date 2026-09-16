from datetime import UTC, datetime

from price_tracker.storage import PriceRecord, append_record, latest_by_asin, read_history


def _record(day: int, asin: str = "B0CM49Z6SN", price: float = 1899.0) -> PriceRecord:
    return PriceRecord(
        timestamp=datetime(2026, 9, day, 14, 0, tzinfo=UTC),
        asin=asin,
        name="Karcher, K2",  # comma checks CSV quoting
        title='Kärcher "K2"',
        price=price,
        currency="MXN",
    )


def test_missing_file_is_empty_history(tmp_path):
    assert read_history(tmp_path / "nope.csv") == []


def test_append_and_read_round_trip(tmp_path):
    path = tmp_path / "data" / "history.csv"
    records = [_record(2, price=1999.0), _record(1)]
    for record in records:
        append_record(path, record)

    assert path.read_text(encoding="utf-8").count("timestamp,asin") == 1  # header once
    assert read_history(path) == sorted(records, key=lambda r: r.timestamp)


def test_latest_by_asin(tmp_path):
    records = [_record(3, price=1800.0), _record(1), _record(2, asin="B0BNW5RQN6", price=2050.0)]
    latest = latest_by_asin(records)
    assert latest["B0CM49Z6SN"].price == 1800.0
    assert latest["B0BNW5RQN6"].price == 2050.0
