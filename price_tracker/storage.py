"""Append-only CSV price history."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class PriceRecord:
    timestamp: datetime
    asin: str
    name: str
    title: str
    price: float
    currency: str


FIELDNAMES = [f.name for f in fields(PriceRecord)]


def append_record(path: Path, record: PriceRecord) -> None:
    """Add one row to the history file, writing the header if the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    row = asdict(record) | {"timestamp": record.timestamp.isoformat(timespec="seconds")}
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def read_history(path: Path) -> list[PriceRecord]:
    """Load every record, oldest first. A missing file means no history yet."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        records = [
            PriceRecord(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                asin=row["asin"],
                name=row["name"],
                title=row["title"],
                price=float(row["price"]),
                currency=row["currency"],
            )
            for row in csv.DictReader(handle)
        ]
    return sorted(records, key=lambda r: r.timestamp)


def latest_by_asin(records: list[PriceRecord]) -> dict[str, PriceRecord]:
    """Most recent record for each product."""
    latest: dict[str, PriceRecord] = {}
    for record in sorted(records, key=lambda r: r.timestamp):
        latest[record.asin] = record
    return latest
