"""Render the price history as a PNG chart and an optional static HTML page."""

from __future__ import annotations

import html
import os
from collections import defaultdict
from pathlib import Path

import matplotlib.dates as mdates
from matplotlib.axes import Axes
from matplotlib.figure import Figure  # Figure directly (not pyplot): no GUI backend needed
from matplotlib.ticker import FuncFormatter

from price_tracker.alerts import format_money
from price_tracker.storage import PriceRecord, read_history

SERIES_COLORS = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300")
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e4e3df"


def group_by_product(records: list[PriceRecord]) -> dict[str, list[PriceRecord]]:
    grouped: dict[str, list[PriceRecord]] = defaultdict(list)
    for record in records:
        grouped[record.name].append(record)
    return dict(sorted(grouped.items()))  # stable order keeps each product's color fixed


def _style_axes(ax: Axes, currency: str) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_MUTED, length=0, labelsize=10)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_xlabel("Date", color=INK_MUTED, fontsize=10, labelpad=8)
    ax.set_ylabel(f"Price ({currency})", color=INK_MUTED, fontsize=10, labelpad=8)


def _plot_product(ax: Axes, name: str, history: list[PriceRecord], color: str) -> None:
    dates = [r.timestamp for r in history]
    prices = [r.price for r in history]
    ax.plot(dates, prices, color=color, linewidth=2, drawstyle="steps-post", label=name)

    drops = [(dates[i], prices[i]) for i in range(1, len(prices)) if prices[i] < prices[i - 1]]
    if drops:
        ax.scatter(
            *zip(*drops, strict=True),
            s=48,
            color=color,
            edgecolor=SURFACE,
            linewidth=2,
            zorder=3,
        )
    ax.annotate(
        f"${prices[-1]:,.0f}",
        xy=(dates[-1], prices[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize=10,
        color=INK,
    )


def render_chart(history_path: Path, output: Path) -> Path:
    """Draw one stepped line per product with dots on every price drop."""
    records = read_history(history_path)
    if not records:
        raise RuntimeError(f"No price history in {history_path}; run a check first")

    grouped = group_by_product(records)
    currency = records[-1].currency
    fig = Figure(figsize=(11, 5.2), dpi=150)
    ax = fig.subplots()
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax, currency)

    for index, (name, history) in enumerate(grouped.items()):
        _plot_product(ax, name, history, SERIES_COLORS[index % len(SERIES_COLORS)])

    ax.scatter([], [], s=48, color=INK_MUTED, edgecolor=SURFACE, label="Price drop")
    first, last = records[0].timestamp, records[-1].timestamp
    subtitle = f"{first:%b %d} - {last:%b %d, %Y}  ·  {len(grouped)} products"
    ax.text(
        0,
        1.22,
        "Amazon price history",
        transform=ax.transAxes,
        fontsize=15,
        color=INK,
        fontweight="bold",
    )
    ax.text(0, 1.135, subtitle, transform=ax.transAxes, fontsize=10, color=INK_MUTED)
    ax.legend(
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(-0.01, 1.0),
        ncol=len(grouped) + 1,
        fontsize=10,
        labelcolor=INK,
    )
    ax.margins(x=0.02, y=0.08)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.3)
    return output


def _summary_rows(records: list[PriceRecord]) -> str:
    rows = []
    for name, history in group_by_product(records).items():
        prices = [r.price for r in history]
        currency = history[-1].currency
        change = (prices[-1] - prices[0]) / prices[0] * 100
        cells = (
            html.escape(name),
            format_money(prices[-1], currency),
            format_money(min(prices), currency),
            format_money(max(prices), currency),
            f"{change:+.1f}%",
        )
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    return "\n".join(rows)


def render_html(history_path: Path, chart_path: Path, output: Path) -> Path:
    """Write a small static page with the chart and a summary table."""
    records = read_history(history_path)
    chart_src = os.path.relpath(chart_path, output.parent)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amazon Price History</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: {SURFACE}; color: {INK};
         max-width: 960px; margin: 2rem auto; padding: 0 16px; }}
  img {{ max-width: 100%; height: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }}
  th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid {GRID}; }}
  th {{ color: {INK_MUTED}; font-weight: 600; }}
  p {{ color: {INK_MUTED}; }}
</style>
</head>
<body>
<h1>Amazon price history</h1>
<p>{len(records)} observations, generated by <code>python -m price_tracker report</code>.</p>
<img src="{html.escape(chart_src)}" alt="Line chart of price history per product">
<table>
<thead><tr><th>Product</th><th>Latest</th><th>Lowest</th><th>Highest</th><th>Change</th></tr></thead>
<tbody>
{_summary_rows(records)}
</tbody>
</table>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output
