"""End-to-end: the offline demo run and the report command."""

from pathlib import Path

from price_tracker.cli import main

ROOT = Path(__file__).parents[1]


def test_demo_dry_run_sends_alerts(tmp_path, monkeypatch, capsys):
    history = tmp_path / "history.csv"
    history.write_text((ROOT / "data" / "sample_history.csv").read_text(encoding="utf-8"))
    config = ROOT / "products.yaml"

    exit_code = main(["--demo", "--dry-run", "--config", str(config), "--history", str(history)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Target price reached" in output
    assert "Price went up" in output
    assert (
        history.read_text(encoding="utf-8").count("\n") == 123
    )  # header + 120 sample rows + 2 new


def test_report_writes_png_and_html(tmp_path):
    png, page = tmp_path / "chart.png", tmp_path / "report.html"
    history = ROOT / "data" / "sample_history.csv"
    args = ["report", "--history", str(history), "--output", str(png), "--html", str(page)]
    assert main(args) == 0
    assert png.read_bytes().startswith(b"\x89PNG")
    assert 'src="chart.png"' in page.read_text(encoding="utf-8")
