"""Canonical public models and strict JSON parsing."""

from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass, is_dataclass
from datetime import date, datetime
from math import isfinite
import re
from typing import Any, Literal, Mapping, Sequence

LevelSide = Literal["Support", "Resistance"]
EvidenceStance = Literal["support", "opposition", "neutral"]
RiskKind = Literal["headwind", "tailwind", "uncertainty"]
Severity = Literal["low", "medium", "high"]


def require_finite(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if positive and result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def optional_finite(value: Any, name: str, *, positive: bool = False) -> float | None:
    if value is None:
        return None
    return require_finite(value, name, positive=positive)


def require_ticker(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("ticker must be a string")
    ticker = value.strip().upper()
    if len(ticker) > 12 or re.fullmatch(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*", ticker) is None:
        raise ValueError(f"invalid ticker: {value!r}")
    return ticker


def require_iso_datetime(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 datetime")
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    category: str
    statement: str
    as_of: str
    source: str
    stance: EvidenceStance
    url: str | None = None

    def __post_init__(self) -> None:
        text = (self.id, self.category, self.statement, self.source)
        if any(not isinstance(item, str) or not item.strip() for item in text):
            raise ValueError("evidence id, category, statement and source are required")
        if self.stance not in ("support", "opposition", "neutral"):
            raise ValueError("evidence.stance must be support, opposition or neutral")
        require_iso_datetime(self.as_of, "evidence.as_of")


@dataclass(frozen=True, slots=True)
class Level:
    level_date: str
    side: LevelSide
    level_type: str
    price: float
    score: float | None = None
    p_hold_7d_pct: float | None = None
    exp_bounce_pct: float | None = None
    hard_break_pct: float | None = None
    reward_risk: float | None = None
    dist_atr: float | None = None
    confluence_count: int | None = None
    approach: str | None = None

    def __post_init__(self) -> None:
        if self.side not in ("Support", "Resistance"):
            raise ValueError("level.side must be Support or Resistance")
        try:
            date.fromisoformat(self.level_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("level.level_date must be YYYY-MM-DD") from exc
        if len(self.level_date) != 10:
            raise ValueError("level.level_date must be YYYY-MM-DD")
        if not isinstance(self.level_type, str) or not self.level_type.strip():
            raise ValueError("level.level_type is required")
        require_finite(self.price, "level.price", positive=True)
        for name in ("score", "p_hold_7d_pct", "exp_bounce_pct", "hard_break_pct", "reward_risk", "dist_atr"):
            optional_finite(getattr(self, name), f"level.{name}")
        if self.confluence_count is not None and (
            isinstance(self.confluence_count, bool)
            or not isinstance(self.confluence_count, int)
            or self.confluence_count < 0
        ):
            raise ValueError("level.confluence_count must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    ticker: str
    as_of: str
    price: float
    atr14: float | None
    average_dollar_volume_20d: float | None
    rsi14: float | None
    sma20: float | None
    sma50: float | None
    sma200: float | None
    momentum_20d_pct: float | None
    volatility_20d_pct: float | None
    pe_ratio: float | None = None
    earnings_growth_pct: float | None = None
    days_to_earnings: int | None = None
    levels: tuple[Level, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", require_ticker(self.ticker))
        require_iso_datetime(self.as_of, "snapshot.as_of")
        require_finite(self.price, "snapshot.price", positive=True)
        optional_finite(self.atr14, "snapshot.atr14", positive=True)
        optional_finite(self.average_dollar_volume_20d, "snapshot.average_dollar_volume_20d", positive=True)
        optional_finite(self.rsi14, "snapshot.rsi14")
        if self.rsi14 is not None and not 0 <= self.rsi14 <= 100:
            raise ValueError("snapshot.rsi14 must be between 0 and 100")
        for name in ("sma20", "sma50", "sma200", "volatility_20d_pct"):
            optional_finite(getattr(self, name), f"snapshot.{name}", positive=True)
        for name in ("momentum_20d_pct", "pe_ratio", "earnings_growth_pct"):
            optional_finite(getattr(self, name), f"snapshot.{name}")
        if self.days_to_earnings is not None and (
            isinstance(self.days_to_earnings, bool) or not isinstance(self.days_to_earnings, int)
        ):
            raise ValueError("snapshot.days_to_earnings must be an integer")
        if any(not isinstance(item, Level) for item in self.levels):
            raise ValueError("snapshot.levels must contain Level values")
        if any(not isinstance(item, Evidence) for item in self.evidence):
            raise ValueError("snapshot.evidence must contain Evidence values")
        evidence_ids = [item.id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("snapshot evidence IDs must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.warnings):
            raise ValueError("snapshot.warnings must contain non-empty strings")


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    schema_version: str
    dataset_id: str
    generated_at: str
    synthetic: bool
    license: str
    source: str
    decision_time: str
    snapshots: tuple[MarketSnapshot, ...]
    bars: Mapping[str, Any] | None = None
    market: Mapping[str, Any] | None = None
    peers: Mapping[str, Any] | None = None
    headlines: Sequence[Mapping[str, Any]] | None = None
    headline_peers: Mapping[str, Any] | None = None
    context_provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.schema_version not in ("visualsectors-toolkit.dataset.v1", "visualsectors-toolkit.dataset.v2"):
            raise ValueError("unsupported dataset schema_version")
        if any(
            not isinstance(item, str) or not item.strip()
            for item in (self.dataset_id, self.license, self.source)
        ):
            raise ValueError("dataset_id, license and source are required")
        if not isinstance(self.synthetic, bool):
            raise ValueError("synthetic must be a boolean")
        require_iso_datetime(self.generated_at, "manifest.generated_at")
        require_iso_datetime(self.decision_time, "manifest.decision_time")
        cutoff = datetime.fromisoformat(self.decision_time.replace("Z", "+00:00"))
        for snapshot in self.snapshots:
            snapshot_time = datetime.fromisoformat(snapshot.as_of.replace("Z", "+00:00"))
            if snapshot_time > cutoff:
                raise ValueError(f"snapshot {snapshot.ticker} is after manifest.decision_time")
            for evidence in snapshot.evidence:
                evidence_time = datetime.fromisoformat(evidence.as_of.replace("Z", "+00:00"))
                if evidence_time > cutoff:
                    raise ValueError(
                        f"evidence {evidence.id} for {snapshot.ticker} is after manifest.decision_time"
                    )
            for level in snapshot.levels:
                if date.fromisoformat(level.level_date) > cutoff.date():
                    raise ValueError(
                        f"level dated {level.level_date} for {snapshot.ticker} is after manifest.decision_time"
                    )
        tickers = [row.ticker for row in self.snapshots]
        if len(tickers) != len(set(tickers)):
            raise ValueError("duplicate ticker in dataset")
        extensions = (self.bars, self.market, self.peers, self.headlines, self.headline_peers, self.context_provenance)
        if any(item is not None for item in extensions):
            if self.schema_version.endswith(".v1"):
                raise ValueError("context sections require dataset.v2; v1 stays snapshot-only")
            from .context_dataset import dataset_context
            dataset_context(to_dict(self))


def _exact_keys(raw: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")


def _construct(model: type[Any], raw: Mapping[str, Any], label: str, **overrides: Any) -> Any:
    fields = model.__dataclass_fields__.values()
    missing = sorted(
        item.name
        for item in fields
        if item.default is MISSING and item.default_factory is MISSING and item.name not in raw
    )
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")
    values = dict(raw)
    values.update(overrides)
    try:
        return model(**values)
    except TypeError as exc:
        raise ValueError(f"{label} is invalid: {exc}") from exc


def _level(raw: Mapping[str, Any]) -> Level:
    if not isinstance(raw, Mapping):
        raise ValueError("level must be an object")
    fields = {field.name for field in Level.__dataclass_fields__.values()}
    _exact_keys(raw, fields, "level")
    return _construct(Level, raw, "level")


def _evidence(raw: Mapping[str, Any]) -> Evidence:
    if not isinstance(raw, Mapping):
        raise ValueError("evidence must be an object")
    fields = {field.name for field in Evidence.__dataclass_fields__.values()}
    _exact_keys(raw, fields, "evidence")
    return _construct(Evidence, raw, "evidence")


def _snapshot(raw: Mapping[str, Any]) -> MarketSnapshot:
    if not isinstance(raw, Mapping):
        raise ValueError("snapshot must be an object")
    fields = {field.name for field in MarketSnapshot.__dataclass_fields__.values()}
    _exact_keys(raw, fields, "snapshot")
    levels = raw.get("levels", ())
    evidence = raw.get("evidence", ())
    if not isinstance(levels, Sequence) or isinstance(levels, (str, bytes)):
        raise ValueError("snapshot.levels must be a list")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        raise ValueError("snapshot.evidence must be a list")
    warnings = raw.get("warnings", ())
    if not isinstance(warnings, Sequence) or isinstance(warnings, (str, bytes)):
        raise ValueError("snapshot.warnings must be a list")
    return _construct(
        MarketSnapshot,
        raw,
        "snapshot",
        levels=tuple(_level(row) for row in levels),
        evidence=tuple(_evidence(row) for row in evidence),
        warnings=tuple(warnings),
    )


def parse_manifest(raw: Mapping[str, Any]) -> DatasetManifest:
    if not isinstance(raw, Mapping):
        raise ValueError("manifest must be an object")
    fields = {field.name for field in DatasetManifest.__dataclass_fields__.values()}
    _exact_keys(raw, fields, "manifest")
    snapshots = raw.get("snapshots")
    if not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes)):
        raise ValueError("manifest.snapshots must be a list")
    return _construct(DatasetManifest, raw, "manifest", snapshots=tuple(_snapshot(row) for row in snapshots))


def to_dict(value: Any) -> Any:
    """Convert immutable toolkit outputs into JSON-safe primitives."""
    if is_dataclass(value):
        return {key: to_dict(item) for key, item in asdict(value).items()
                if not isinstance(value, DatasetManifest) or key not in {"bars", "market", "peers", "headlines", "headline_peers", "context_provenance"} or item is not None}
    if isinstance(value, Mapping):
        return {str(key): to_dict(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_dict(item) for item in value]
    return value
