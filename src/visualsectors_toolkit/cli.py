"""Command-line interface for live, offline, and file-backed workflows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Sequence

from . import __version__
from .levels import build_level_plan
from .models import Severity, to_dict
from .monitoring import MonitorState, TrackedPlan, TrackedRisk, evaluate_monitor
from .providers import (
    JsonFileProvider,
    MarketDataProvider,
    SyntheticFixtureProvider,
    VisualSectorsProvider,
    VisualSectorsProviderError,
    MissingApiKeyError,
)
from .providers.visualsectors import SIGNUP_URL
from .report import render_markdown
from .research import build_research_brief
from .risk import build_risk_register
from .screening import PRESETS, run_screen
from .sizing import SizingPick, size_by_portfolio_slots, size_by_stop_risk
from .workflow import run_reference_workflow


def _provider(path: str | None, offline: bool = False) -> MarketDataProvider:
    if path:
        return JsonFileProvider(path)
    if offline:
        return SyntheticFixtureProvider()
    return VisualSectorsProvider()


def _print(value: object) -> None:
    print(json.dumps(to_dict(value), indent=2, sort_keys=True, allow_nan=False))


def _plan(provider: MarketDataProvider, ticker: str, direction: str):
    row = provider.get(ticker)
    return row, build_level_plan(
        ticker=row.ticker,
        as_of=row.as_of,
        direction=direction,  # type: ignore[arg-type]
        current_price=row.price,
        atr=row.atr14,
        levels=row.levels,
    )


def _state_from_json(path: Path) -> MonitorState | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {
        "ticker",
        "evaluated_at",
        "active",
        "failure",
        "plan",
        "invalidation_breached",
        "inside_entry_zone",
        "inside_reassessment_zone",
    }
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
    plan_raw = raw.get("plan")
    if plan_raw is not None:
        plan_fields = {
            "direction", "entry_low", "entry_high", "invalidation_price",
            "reassessment_low", "reassessment_high",
        }
        if not isinstance(plan_raw, dict) or set(plan_raw) - plan_fields:
            raise ValueError("monitor state has invalid plan fields")
        try:
            plan = TrackedPlan(**plan_raw)
        except TypeError as exc:
            raise ValueError(f"monitor state plan is invalid: {exc}") from exc
    else:
        plan = None
    return MonitorState(
        raw["ticker"],
        raw["evaluated_at"],
        tuple(active),
        raw.get("failure"),
        plan,
        raw.get("invalidation_breached", False),
        raw.get("inside_entry_zone", False),
        raw.get("inside_reassessment_zone", False),
    )


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


def _limit(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer from 1 to 100") from exc
    if not 1 <= result <= 100:
        raise argparse.ArgumentTypeError("limit must be an integer from 1 to 100")
    return result


def _add_data_source(command: argparse.ArgumentParser) -> None:
    sources = command.add_mutually_exclusive_group()
    sources.add_argument("--offline", action="store_true", help="Use the bundled synthetic fixture; no network.")
    sources.add_argument("--data", help="Read a toolkit dataset JSON instead of the live API.")


def _save_api_key(key: str, *, env_path: Path = Path(".env"), gitignore_path: Path = Path(".gitignore")) -> None:
    if not key or "\n" in key or "\r" in key:
        raise ValueError("API key must be a non-empty single line")
    lines = env_path.read_text(encoding="utf-8-sig").splitlines() if env_path.exists() else []
    replacement = f"VISUALSECTORS_API_KEY={key}"
    replaced = False
    updated: list[str] = []
    for line in lines:
        if line.strip().startswith("VISUALSECTORS_API_KEY="):
            if not replaced:
                updated.append(replacement)
                replaced = True
            continue
        updated.append(line)
    if not replaced:
        updated.append(replacement)
    env_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8", newline="\n")

    ignored = gitignore_path.read_text(encoding="utf-8-sig").splitlines() if gitignore_path.exists() else []
    if ".env" not in (line.strip() for line in ignored):
        ignored.append(".env")
        gitignore_path.write_text("\n".join(ignored).rstrip() + "\n", encoding="utf-8", newline="\n")


def _confirm_high_risk(args: argparse.Namespace) -> None:
    if args.risk_fraction <= 0.05 and args.max_allocation <= 0.50:
        return
    if args.yes:
        return
    answer = input(
        "The requested risk fraction exceeds 5% or allocation exceeds 50%. "
        "Type YES to confirm this arithmetic scenario: "
    )
    if answer != "YES":
        raise ValueError("high-risk sizing was not confirmed")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vstoolkit",
        description="Deterministic trading research tools. Live API mode is the default.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}", help="Print version and exit.")
    commands = parser.add_subparsers(dest="command", required=True)

    login = commands.add_parser("login", help="Open free-key signup and save a hidden key to .env.")
    login.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)

    demo = commands.add_parser("demo", help="Run all six outcomes over the bundled synthetic fixture.")
    demo.add_argument("--offline", action="store_true", help="Use the bundled synthetic fixture (always true for demo).")
    demo.add_argument("--output", default="toolkit-report.md", help="Markdown report path.")

    screen = commands.add_parser("screen", help="Run a disclosed screen and emit JSON.")
    _add_data_source(screen)
    screen.add_argument("--preset", choices=sorted(PRESETS), default="oversold_at_support", help="Named disclosed filter set.")
    screen.add_argument("--limit", type=_limit, default=25, help="Maximum returned tickers (1-100).")

    plan = commands.add_parser("plan", help="Build a conditional entry, invalidation, and reassessment plan.")
    _add_data_source(plan)
    plan.add_argument("ticker", help="US-listed ticker, for example AAPL.")
    plan.add_argument("--direction", choices=("long", "short"), default="long", help="Scenario direction.")
    plan.add_argument("--capital", type=float, default=100_000, help="Portfolio capital in account currency.")
    plan.add_argument("--risk-fraction", type=float, default=0.005, help="Fraction at risk; 0.005 means 0.5%.")
    plan.add_argument("--max-allocation", type=float, default=0.10, help="Capital cap; 0.10 means 10%.")
    plan.add_argument("--yes", action="store_true", help="Confirm a risk fraction over 5% or allocation over 50%.")

    stop = commands.add_parser("size-stop", help="Size a position from entry/stop risk and an allocation cap.")
    stop.add_argument("--capital", type=float, required=True, help="Portfolio capital in account currency.")
    stop.add_argument("--risk-fraction", type=float, required=True, help="Fraction of capital at risk; 0.01 means 1%.")
    stop.add_argument("--entry", type=float, required=True, help="Planned entry price per share.")
    stop.add_argument("--stop", type=float, required=True, help="Scenario invalidation price per share.")
    stop.add_argument("--max-allocation", type=float, required=True, help="Maximum capital fraction; 0.10 means 10%.")
    stop.add_argument("--side", choices=("long", "short"), default="long", help="Position direction.")
    stop.add_argument("--yes", action="store_true", help="Confirm a risk fraction over 5% or allocation over 50%.")

    slots = commands.add_parser("size-portfolio", help="Apply the portfolio-slot/inverse-volatility method.")
    _add_data_source(slots)
    slots.add_argument("--tickers", required=True, help="Comma-separated US-listed tickers.")
    slots.add_argument("--portfolio", type=float, required=True, help="Portfolio capital in account currency.")
    slots.add_argument("--intended-holdings", type=int, required=True, help="Positive count of intended holdings.")

    research = commands.add_parser("research", help="Build an evidence-first research brief.")
    _add_data_source(research)
    research.add_argument("--ticker", required=True, help="US-listed ticker, for example AAPL.")
    research.add_argument("--thesis", help="Falsifiable thesis text to examine.")
    research.add_argument("--direction", choices=("long", "short"), default="long", help="Scenario direction.")

    monitor = commands.add_parser("monitor", help="Update a local change-detection state file.")
    _add_data_source(monitor)
    monitor.add_argument("--ticker", required=True, help="US-listed ticker, for example AAPL.")
    monitor.add_argument("--direction", choices=("long", "short"), default="long", help="Scenario direction.")
    monitor.add_argument("--state", required=True, help="State JSON path, created atomically.")

    report = commands.add_parser("report", help="Run the six-outcome workflow and write Markdown.")
    _add_data_source(report)
    report.add_argument("--output", default="toolkit-report.md", help="Markdown report path.")
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "login":
        if not args.no_open:
            webbrowser.open(SIGNUP_URL)
        key = getpass.getpass("Visual Sectors API key (input hidden): ").strip()
        _save_api_key(key)
        VisualSectorsProvider(api_key=key).verify()
        print("Saved VISUALSECTORS_API_KEY to .env and verified live AAPL levels; .env is excluded from Git.")
        return 0
    if args.command == "demo":
        provider = SyntheticFixtureProvider()
        run = run_reference_workflow(provider)
        monitor = evaluate_monitor(
            None,
            observed_at=provider.manifest.generated_at,
            register=run.risk,
            current_price=run.selected.price,
            level_plan=run.level_plan,
        )
        output = Path(args.output)
        output.write_text(render_markdown(run, monitor), encoding="utf-8", newline="\n")
        print(f"Wrote synthetic report to {output.resolve()}")
        return 0
    if args.command == "screen":
        provider = _provider(args.data, args.offline)
        universe = (
            provider.screen_universe(args.preset, limit=args.limit)
            if isinstance(provider, VisualSectorsProvider)
            else provider.universe()
        )
        _print(run_screen(universe, args.preset, limit=args.limit))
        return 0
    if args.command == "plan":
        provider = _provider(args.data, args.offline)
        _row, plan = _plan(provider, args.ticker, args.direction)
        _confirm_high_risk(args)
        stop_size = None
        if plan.entry_zone is not None and plan.invalidation_price is not None:
            entry = plan.entry_zone.high if plan.direction == "long" else plan.entry_zone.low
            stop_size = size_by_stop_risk(
                capital=args.capital,
                risk_fraction=args.risk_fraction,
                entry=entry,
                stop=plan.invalidation_price,
                max_allocation_fraction=args.max_allocation,
                side=plan.direction,
            )
        _print({"plan": plan, "stop_risk_size": stop_size})
        return 0
    if args.command == "size-stop":
        _confirm_high_risk(args)
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
        provider = _provider(args.data, args.offline)
        tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()]
        picks = [
            SizingPick(row.ticker, row.price, row.volatility_20d_pct)
            for row in (provider.get(ticker) for ticker in tickers)
        ]
        _print(size_by_portfolio_slots(portfolio=args.portfolio, intended_holdings=args.intended_holdings, picks=picks))
        return 0
    if args.command == "research":
        provider = _provider(args.data, args.offline)
        row, plan = _plan(provider, args.ticker, args.direction)
        _print(build_research_brief(row, thesis=args.thesis, level_plan=plan))
        return 0
    if args.command == "monitor":
        state_path = Path(args.state)
        previous = _state_from_json(state_path)
        try:
            provider = _provider(args.data, args.offline)
            row, plan = _plan(provider, args.ticker, args.direction)
            register = build_risk_register(row, level_plan=plan)
            result = evaluate_monitor(
                previous,
                observed_at=provider.manifest.generated_at,
                register=register,
                current_price=row.price,
                level_plan=plan,
            )
        except (VisualSectorsProviderError, OSError) as exc:
            result = evaluate_monitor(
                previous,
                observed_at=datetime.now(timezone.utc).isoformat(),
                failure=str(exc),
                ticker=args.ticker,
            )
            _atomic_json(state_path, result.state)
            _print(result)
            return 2
        _atomic_json(state_path, result.state)
        _print(result)
        return 0
    if args.command == "report":
        provider = _provider(args.data, args.offline)
        run = run_reference_workflow(provider)
        monitor = evaluate_monitor(
            None,
            observed_at=provider.manifest.generated_at,
            register=run.risk,
            current_price=run.selected.price,
            level_plan=run.level_plan,
        )
        output = Path(args.output)
        output.write_text(render_markdown(run, monitor), encoding="utf-8", newline="\n")
        print(f"Wrote report to {output.resolve()}")
        return 0
    raise AssertionError("unreachable")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except MissingApiKeyError:
        ticker = getattr(args, "ticker", None)
        if ticker:
            print(
                f"{str(ticker).upper()} needs live data. Get a free key (no card) at "
                f"{SIGNUP_URL}, then run: vstoolkit login",
                file=sys.stderr,
            )
        else:
            print(f"Get a free key (no card) at {SIGNUP_URL}, then run: vstoolkit login", file=sys.stderr)
        return 2
    except (VisualSectorsProviderError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"vstoolkit: error: {exc}", file=sys.stderr)
        return 2
