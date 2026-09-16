"""Command-line interface: ``python -m price_tracker [check|report] ...``."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

from price_tracker import report, tracker
from price_tracker.config import ConfigError, load_config
from price_tracker.notifiers import ConsoleNotifier, Notifier, TwilioWhatsAppNotifier

logger = logging.getLogger("price_tracker")

DEFAULT_CONFIG = Path("products.yaml")
DEFAULT_HISTORY = Path("data/price_history.csv")
SAMPLE_HISTORY = Path("data/sample_history.csv")
DEMO_HISTORY = Path("data/demo_history.csv")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="show debug logs")

    parser = argparse.ArgumentParser(prog="price_tracker", description="Track Amazon prices.")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check", parents=[common], help="fetch current prices (default command)"
    )
    check.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    check.add_argument("--history", type=Path, default=None, help="CSV file to append to")
    check.add_argument("--dry-run", action="store_true", help="print alerts instead of sending")
    check.add_argument(
        "--demo", action="store_true", help="parse bundled HTML pages instead of hitting Amazon"
    )

    rep = commands.add_parser("report", parents=[common], help="render a price-history chart")
    rep.add_argument("--history", type=Path, default=None)
    rep.add_argument("--output", type=Path, default=Path("docs/price-history.png"))
    rep.add_argument("--html", type=Path, default=None, help="also write a static HTML report")
    return parser


def _prepare_demo_history(path: Path) -> None:
    """Start each demo run from the sample history so alerts are reproducible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if SAMPLE_HISTORY.exists():
        shutil.copyfile(SAMPLE_HISTORY, path)
    else:
        path.unlink(missing_ok=True)


def run_check(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    history = args.history or (DEMO_HISTORY if args.demo else DEFAULT_HISTORY)
    if args.demo:
        if args.history is None:
            _prepare_demo_history(history)
        logger.info("Demo mode: reading saved pages, history in %s", history)

    notifier: Notifier
    if args.dry_run or args.demo:
        notifier = ConsoleNotifier()
    else:
        notifier = TwilioWhatsAppNotifier.from_env()

    summary = tracker.run(config, history, notifier, demo=args.demo)
    logger.info(
        "Done: %d checked, %d failed, %d alert(s)", summary.checked, summary.failed, summary.alerts
    )
    return 1 if summary.failed and not summary.checked else 0


def run_report(args: argparse.Namespace) -> int:
    history = args.history or DEFAULT_HISTORY
    if args.history is None and not history.exists():
        logger.info("No %s yet; using sample data from %s", history, SAMPLE_HISTORY)
        history = SAMPLE_HISTORY
    chart = report.render_chart(history, args.output)
    logger.info("Chart written to %s", chart)
    if args.html:
        logger.info("HTML report written to %s", report.render_html(history, chart, args.html))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not {"check", "report", "-h", "--help"} & set(argv):
        argv.insert(0, "check")  # `python -m price_tracker --demo` means `check --demo`
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return run_report(args) if args.command == "report" else run_check(args)
    except (ConfigError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 2
