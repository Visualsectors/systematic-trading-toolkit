"""Command-line interface for offline and file-backed toolkit workflows."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Sequence

from .levels import build_level_plan
from .models import Severity, to_dict
from .monitoring import MonitorState, TrackedRisk, evaluate_monitor
from .providers import JsonFileProvider, MarketDataProvider, SyntheticFixtureProvider
from .report import render_markdown
from .research import build_research_brief
from .risk import build_risk_register
from .screening import PRESETS, run_screen
from .sizing import SizingPick, size_by_portfolio_slots, size_by_stop_risk
from .workflow import run_reference_workflow


def _provider(path: str | None) -> MarketDataProvider:
    return JsonFileProvider(path) if path else SyntheticFixtureProvider()


def _print(value: object) -> None:
    print(json.dumps(to_dict(value), indent=2, sort_keys=True, allow_nan=False))


def _plan(provider: MarketDataProvider, ticker: str):
    row = provider.get(ticker)
    return row, build_level_plan(
        ticker=row.ticker,
        as_of=row.as_of,
        direction="long",
        current_price=row.price,
        atr=row.atr14,
        levels=row.levels,
    )


def _state_from_json(path: Path) -> MonitorState | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {"ticker", "evaluated_at", "active", "failure"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValueError("monitor state has invalid fields")
    active = []
    for item in raw.get("active", []):
        if not isinstance(item, dict) or set(item) != {"id", "severity", "statement"}:
            raise ValueError("monitor state has invalid active risk fields")
        severity: Severity = item["severity"]
        if severity not in ("low", "medium", "high"):
            raise ValueError("monitor state has invalid severity")
        active.append(TrackedRisk(item["id"], severity, item["statement"]))
    return MonitorState(raw["ticker"], raw["evaluated_at"], tuple(active), raw.get("failure"))


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(to_dict(value), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vstoolkit",
        description="Deterministic trading research tools. Fixture mode is offline and synthetic.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="Run all six outcomes over the bundled synthetic fixture.")
    demo.add_argument("--output", default="toolkit-report.md", help="Markdown report path.")

    screen = commands.add_parser("screen", help="Run a disclosed screen and emit JSON.")
    screen.add_argument("--data", help="Dataset JSON; omit for the synthetic fixture.")
    screen.add_argument("--preset", choices=sorted(PRESETS), default="oversold_at_support")
    screen.add_argument("--limit", type=int, default=25)

    stop = commands.add_parser("size-stop", help="Size a position from entry/stop risk and an allocation cap.")
    stop.add_argument("--capital", type=float, required=True)
    stop.add_argument("--risk-fraction", type=float, required=True)
    stop.add_argument("--entry", type=float, required=True)
    stop.add_argument("--stop", type=float, required=True)
    stop.add_argument("--max-allocation", type=float, required=True)
    stop.add_argument("--side", choices=("long", "short"), default="long")

    slots = commands.add_parser("size-portfolio", help="Apply the portfolio-slot/inverse-volatility method.")
    slots.add_argument("--data", help="Dataset JSON; omit for the synthetic fixture.")
    slots.add_argument("--tickers", required=True, help="Comma-separated tickers present in the dataset.")
    slots.add_argument("--portfolio", type=float, required=True)
    slots.add_argument("--intended-holdings", type=int, required=True)

    research = commands.add_parser("research", help="Build an evidence-first research brief.")
    research.add_argument("--data", help="Dataset JSON; omit for the synthetic fixture.")
    research.add_argument("--ticker", required=True)
    research.add_argument("--thesis")

    monitor = commands.add_parser("monitor", help="Update a local change-detection state file.")
    monitor.add_argument("--data", help="Dataset JSON; omit for the synthetic fixture.")
    monitor.add_argument("--ticker", required=True)
    monitor.add_argument("--state", required=True, help="State JSON path, created atomically.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "demo":
        provider = SyntheticFixtureProvider()
        run = run_reference_workflow(provider)
        monitor = evaluate_monitor(None, observed_at=provider.manifest.generated_at, register=run.risk)
        output = Path(args.output)
        output.write_text(render_markdown(run, monitor), encoding="utf-8", newline="\n")
        print(f"Wrote synthetic report to {output.resolve()}")
        return 0
    if args.command == "screen":
        provider = _provider(args.data)
        _print(run_screen(provider.universe(), args.preset, limit=args.limit))
        return 0
    if args.command == "size-stop":
        _print(
            size_by_stop_risk(
                capital=args.capital,
                risk_fraction=args.risk_fraction,
                entry=args.entry,
                stop=args.stop,
                max_allocation_fraction=args.max_allocation,
                side=args.side,
            )
        )
        return 0
    if args.command == "size-portfolio":
        provider = _provider(args.data)
        tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()]
        picks = [
            SizingPick(row.ticker, row.price, row.volatility_20d_pct)
            for row in (provider.get(ticker) for ticker in tickers)
        ]
        _print(size_by_portfolio_slots(portfolio=args.portfolio, intended_holdings=args.intended_holdings, picks=picks))
        return 0
    if args.command == "research":
        provider = _provider(args.data)
        row, plan = _plan(provider, args.ticker)
        _print(build_research_brief(row, thesis=args.thesis, level_plan=plan))
        return 0
    if args.command == "monitor":
        provider = _provider(args.data)
        row, plan = _plan(provider, args.ticker)
        register = build_risk_register(row, level_plan=plan)
        state_path = Path(args.state)
        result = evaluate_monitor(
            _state_from_json(state_path),
            observed_at=provider.manifest.generated_at,
            register=register,
        )
        _atomic_json(state_path, result.state)
        _print(result)
        return 0
    raise AssertionError("unreachable")
