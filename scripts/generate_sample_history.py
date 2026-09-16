"""Generate a fictional but plausible 60-day price history for the example products.

The prices are made up. They mimic how Amazon listings usually behave: a stable
list price with occasional step changes, short "deal" dips, and slow drifts.

Usage: python scripts/generate_sample_history.py [--output data/sample_history.csv]
"""

from __future__ import annotations

import argparse
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from price_tracker.storage import PriceRecord, append_record

DAYS = 60
END_DATE = datetime(2026, 9, 15, tzinfo=UTC)

# (ASIN, name, title, starting price, {day: new price})
PRODUCTS = [
    (
        "B0CM49Z6SN",
        "Karcher K2 Pressure Washer",
        "Kärcher Hidrolavadora Eléctrica K2 Compact",
        2184.00,
        {9: 1999.00, 16: 2184.00, 27: 1899.00, 31: 2099.00, 44: 2049.00, 52: 1949.00},
    ),
    (
        "B0BNW5RQN6",
        "Truper Orbital Polisher",
        "Truper PULA-6A, Pulidora doble acción 6 pulgadas",
        2050.00,
        {12: 2199.00, 24: 1989.00, 38: 2050.00, 47: 1969.00},
    ),
]


def build_records(seed: int = 42) -> list[PriceRecord]:
    rng = random.Random(seed)  # only used for the time of day, so output is reproducible
    start = END_DATE - timedelta(days=DAYS - 1)
    records = []
    for day in range(DAYS):
        for asin, name, title, price, changes in PRODUCTS:
            current = price
            for change_day, new_price in sorted(changes.items()):
                if day >= change_day:
                    current = new_price
            timestamp = start + timedelta(days=day, hours=14, minutes=rng.randint(0, 59))
            records.append(PriceRecord(timestamp, asin, name, title, current, "MXN"))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/sample_history.csv"))
    args = parser.parse_args()

    args.output.unlink(missing_ok=True)
    records = build_records()
    for record in records:
        append_record(args.output, record)
    print(f"Wrote {len(records)} rows to {args.output}")


if __name__ == "__main__":
    main()
