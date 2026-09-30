"""Live Visual Sectors Data API adapter using only the Python standard library."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from statistics import stdev
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models import DatasetManifest, Evidence, Level, MarketSnapshot, require_ticker
from .base import MarketDataProvider, ProviderCapabilities

DEFAULT_API_BASE_URL = "https://api.visualsectors.com"
SIGNUP_URL = f"{DEFAULT_API_BASE_URL}/signup"
PLAN_INDICATORS = ("atr14", "rsi14", "sma20", "sma50", "sma200")


class VisualSectorsProviderError(RuntimeError):
    """Base error for live-provider failures safe to present in the CLI."""


class MissingApiKeyError(VisualSectorsProviderError):
    def __init__(self) -> None:
        super().__init__(
            "VISUALSECTORS_API_KEY is not set. Get a free key at " + SIGNUP_URL
        )


class RateLimitError(VisualSectorsProviderError):
    def __init__(self, retry_after: str | None) -> None:
        self.retry_after = retry_after
        suffix = f" Retry after {retry_after} seconds." if retry_after else " Retry later."
        super().__init__("Visual Sectors API rate limit reached." + suffix)


class ApiResponseError(VisualSectorsProviderError):
    def __init__(self, status: int | None, message: str) -> None:
        self.status = status
        if status == 401:
            # Never echo an authentication response that could contain the key.
            message = f"Key is missing, invalid, revoked, or expired. Get a free key at {SIGNUP_URL}, then run: vstoolkit login"
        prefix = f"Visual Sectors API returned HTTP {status}: " if status else "Visual Sectors API failed: "
        super().__init__(prefix + message)


def _dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _iso_datetime(value: Any, fallback_date: str | None = None) -> str:
    if isinstance(value, str) and value.strip():
        candidate = value.strip()
        if len(candidate) == 10:
            return candidate + "T00:00:00Z"
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            pass
        else:
            return candidate + "Z" if parsed.tzinfo is None else candidate
    if fallback_date:
        return fallback_date + "T00:00:00Z"
    raise ApiResponseError(None, "a source row contained no usable timestamp")


def _rows(payload: Mapping[str, Any], label: str) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ApiResponseError(None, f"{label} response did not contain a rows array")
    return rows


class VisualSectorsProvider(MarketDataProvider):
    """Map live, non-PIT Stage 1 API responses into the toolkit model."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        env_file: str | Path = ".env",
        cache_dir: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        file_values = _dotenv(Path(env_file))
        self._api_key = (
            api_key
            or os.environ.get("VISUALSECTORS_API_KEY")
            or file_values.get("VISUALSECTORS_API_KEY")
            or ""
        ).strip()
        if not self._api_key:
            raise MissingApiKeyError()
        if any(character.isspace() for character in self._api_key):
            raise ValueError("API key must be a single token, not a key file or multiline text; run: vstoolkit login")
        self._base_url = (
            base_url
            or os.environ.get("VISUALSECTORS_API_BASE_URL")
            or file_values.get("VISUALSECTORS_API_BASE_URL")
            or DEFAULT_API_BASE_URL
        ).rstrip("/")
        if not self._base_url.startswith(("https://", "http://")):
            raise ValueError("VISUALSECTORS_API_BASE_URL must be an HTTP(S) URL")
        default_cache = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "visualsectors-toolkit" / "cache"
        self._cache_dir = Path(cache_dir) if cache_dir is not None else default_cache
        self._timeout = timeout
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._decision_times: list[str] = []

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            assets=("US-listed equities",),
            intervals=("daily",),
            history="limited by the API-key entitlement and retained source data",
            delay="declared by the Visual Sectors Data API response",
            adjustment="raw, unadjusted daily OHLCV; split coefficient is supplied separately",
            mode="live",
        )

    @property
    def manifest(self) -> DatasetManifest:
        if not self._snapshots:
            self.universe()
        decision_time = min(self._decision_times) if self._decision_times else datetime.now(timezone.utc).isoformat()
        return DatasetManifest(
            schema_version="visualsectors-toolkit.dataset.v1",
            dataset_id="visualsectors-api-live",
            generated_at=datetime.now(timezone.utc).isoformat(),
            synthetic=False,
            license="Visual Sectors Data API terms; raw value redistribution is prohibited.",
            source="Visual Sectors Data API",
            decision_time=decision_time,
            snapshots=tuple(self._snapshots[key] for key in sorted(self._snapshots)),
        )

    def universe(self) -> tuple[MarketSnapshot, ...]:
        return self.screen_universe("oversold_at_support", limit=25)

    def verify(self) -> tuple[str, ...]:
        """Exercise every plan endpoint uncached; return any explicit data gaps."""
        health = self._request_json("GET", "/v1/health", cache=False)
        if health.get("ok") is not True:
            raise ApiResponseError(None, "health check did not report ok=true")
        snapshot = self._load_snapshot("AAPL", cache=False)
        self._snapshots["AAPL"] = snapshot
        return snapshot.warnings

    def screen_universe(self, preset: str, *, limit: int) -> tuple[MarketSnapshot, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be from 1 to 100")
        criteria: list[dict[str, Any]] = [
            {"id": "support", "dataset": "levels", "field": "side", "op": "eq", "value": "Support"},
            {"id": "distance", "dataset": "levels", "field": "dist_atr", "op": "lte", "value": 1.5},
        ]
        sort = {"field": "dist_atr", "direction": "asc"}
        if preset == "oversold_at_support":
            criteria.append(
                {"id": "rsi", "dataset": "technicals", "field": "rsi14", "op": "lte", "value": 35}
            )
            sort = {"field": "rsi14", "direction": "asc"}
        elif preset == "trend_continuation":
            criteria = [
                {"id": "trend", "dataset": "technicals", "field": "sma50", "op": "gt", "value": 0},
                {"id": "momentum", "dataset": "prices", "field": "return_60_sessions_pct", "op": "gt", "value": 0},
            ]
            sort = {"field": "return_60_sessions_pct", "direction": "desc"}
        elif preset != "near_support":
            raise ValueError(f"unknown preset: {preset}")
        payload = self._request_json(
            "POST",
            "/v1/screen",
            body={"version": 1, "match": "all", "criteria": criteria, "sort": sort, "limit": limit},
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise ApiResponseError(None, "screen response did not contain a results array")
        tickers = [require_ticker(str(row.get("ticker", ""))) for row in results if isinstance(row, dict)]
        return tuple(self.get(ticker) for ticker in tickers)

    def get(self, ticker: str) -> MarketSnapshot:
        normalized = require_ticker(ticker)
        if normalized not in self._snapshots:
            self._snapshots[normalized] = self._load_snapshot(normalized)
        return self._snapshots[normalized]

    def _load_snapshot(self, ticker: str, *, cache: bool = True) -> MarketSnapshot:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=75)
        warnings = [
            "Daily prices are raw and unadjusted; corporate actions can distort derived returns and volatility.",
            "Stage 1 API data is date-bounded but non-point-in-time; do not use it as a historical backtest feed.",
            "Earnings growth is unavailable from the Stage 1 public mapping and remains null.",
            "Days to earnings is unavailable: earnings calendar data is not served by API 2.2.0; no event-risk clearance is implied.",
        ]
        levels_response = self._get_pages("/v1/levels", {"ticker": ticker}, cache=cache)
        technical_responses = {
            indicator: self._get_pages(f"/v1/technicals/{indicator}", {"ticker": ticker}, cache=cache)
            for indicator in PLAN_INDICATORS
        }
        bars_response = self._get_pages(
            "/v1/timeseries/history",
            {"ticker": ticker, "view": "daily", "from": start.isoformat(), "to": today.isoformat(), "limit": "100"},
            cache=cache,
        )
        metrics_response = self._optional_pages(
            "/v1/fundamentals", {"ticker": ticker, "view": "metrics"}, warnings, cache=cache
        )
        news_response = self._optional_pages(
            "/v1/news", {"ticker": ticker, "view": "headlines", "limit": "25"}, warnings, cache=cache
        )

        decision_times = [
            str(response.get("as_of"))
            for response in (
                levels_response,
                *technical_responses.values(),
                bars_response,
                metrics_response,
                news_response,
            )
            if isinstance(response.get("as_of"), str)
        ]
        if not decision_times:
            raise ApiResponseError(None, "API responses did not include an as_of decision time")
        decision_time = min(decision_times)
        self._decision_times.extend(decision_times)

        levels = tuple(self._map_level(row) for row in _rows(levels_response, "levels"))
        indicators: dict[str, float | None] = {}
        for indicator, response in technical_responses.items():
            rows = sorted(_rows(response, indicator), key=lambda row: str(row.get("date", "")), reverse=True)
            if any(row.get("indicator") != indicator for row in rows):
                raise ApiResponseError(None, f"{indicator} response contained a different indicator")
            indicators[indicator] = _number(rows[0].get("value")) if rows else None
            if indicators[indicator] is None:
                warnings.append(f"{indicator} is unavailable from the technicals endpoint and remains null.")
        bars = sorted(_rows(bars_response, "timeseries"), key=lambda row: str(row.get("date", "")))
        if not bars:
            raise ApiResponseError(None, f"no daily bars were returned for {ticker}")
        latest_close = _number(bars[-1].get("close"))
        if latest_close is None or latest_close <= 0:
            raise ApiResponseError(None, f"the latest daily close for {ticker} is invalid")
        momentum, volatility, adv = self._derived_bar_fields(bars)
        metrics = _rows(metrics_response, "fundamentals metrics")
        pe_ratio = _number(metrics[0].get("pe_ratio")) if metrics else None
        if pe_ratio is None:
            warnings.append("P/E is unavailable from fundamentals metrics and remains null.")
        evidence_by_id: dict[str, Evidence] = {}
        for source_row in _rows(news_response, "news"):
            try:
                item = self._map_news(source_row, ticker)
            except (VisualSectorsProviderError, ValueError):
                warnings.append("A malformed news item was omitted; news evidence is incomplete.")
                continue
            evidence_by_id.setdefault(item.id, item)
        evidence = tuple(evidence_by_id[key] for key in sorted(evidence_by_id))
        if not evidence:
            warnings.append("No usable news evidence was returned; absence of evidence is not absence of risk.")
        return MarketSnapshot(
            ticker=ticker,
            as_of=decision_time,
            price=latest_close,
            atr14=_number(indicators.get("atr14")),
            average_dollar_volume_20d=adv,
            rsi14=_number(indicators.get("rsi14")),
            sma20=_number(indicators.get("sma20")),
            sma50=_number(indicators.get("sma50")),
            sma200=_number(indicators.get("sma200")),
            momentum_20d_pct=momentum,
            volatility_20d_pct=volatility,
            pe_ratio=pe_ratio,
            earnings_growth_pct=None,
            days_to_earnings=None,
            levels=levels,
            evidence=evidence,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _optional_pages(
        self, path: str, query: Mapping[str, str], warnings: list[str], *, cache: bool
    ) -> dict[str, Any]:
        """Optional evidence may degrade, but authentication and quota never do."""
        try:
            return self._get_pages(path, query, cache=cache)
        except ApiResponseError as exc:
            if exc.status == 401:
                raise
            reason = f"HTTP {exc.status}" if exc.status else "invalid response or connection failure"
            warnings.append(f"{path} view={query.get('view')} is unavailable ({reason}); continuing with a data gap.")
            return {"rows": []}

    @staticmethod
    def _map_level(row: Mapping[str, Any]) -> Level:
        return Level(
            level_date=str(row.get("level_date", "")),
            side=str(row.get("side", "")),  # type: ignore[arg-type]
            level_type=str(row.get("level_type", "")),
            price=_number(row.get("price")) or 0,
            score=_number(row.get("score")),
            p_hold_7d_pct=_number(row.get("p_hold_7d_pct")),
            exp_bounce_pct=_number(row.get("exp_bounce_pct")),
            hard_break_pct=_number(row.get("hard_break_pct")),
            reward_risk=_number(row.get("reward_risk")),
            dist_atr=_number(row.get("dist_atr")),
            confluence_count=_integer(row.get("confluence_count")),
            approach=str(row["approach"]) if row.get("approach") is not None else None,
        )

    @staticmethod
    def _derived_bar_fields(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, float | None, float | None]:
        usable = [
            (str(row.get("date", "")), _number(row.get("close")), _number(row.get("volume")))
            for row in rows
        ]
        usable = [(day, close, volume) for day, close, volume in usable if close is not None and close > 0]
        if len(usable) < 21:
            return None, None, None
        window = usable[-21:]
        closes = [row[1] for row in window]
        assert all(value is not None for value in closes)
        returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
        momentum = (closes[-1] / closes[0] - 1) * 100
        volatility = stdev(returns) * math.sqrt(252) * 100 if len(returns) >= 2 else None
        dollar_volumes = [
            close * volume
            for _day, close, volume in window[-20:]
            if close is not None and volume is not None and volume >= 0
        ]
        adv = sum(dollar_volumes) / 20 if len(dollar_volumes) == 20 else None
        return momentum, volatility, adv

    @staticmethod
    def _map_news(row: Mapping[str, Any], ticker: str) -> Evidence:
        """Map sentiment >= +0.15 to support, <= -0.15 to opposition, otherwise neutral."""
        score = _number(row.get("ticker_sentiment_score"))
        stance = "support" if score is not None and score >= 0.15 else (
            "opposition" if score is not None and score <= -0.15 else "neutral"
        )
        statement = str(row.get("title") or row.get("teaser") or "Untitled news item").strip()
        stable_id = str(row.get("id") or sha256(
            f"{ticker}|{row.get('created')}|{statement}".encode("utf-8")
        ).hexdigest()[:16])
        event_date = str(row.get("event_date", ""))[:10] or None
        return Evidence(
            id=f"news:{stable_id}",
            category="news",
            statement=statement,
            as_of=_iso_datetime(row.get("created"), event_date),
            source=str(row.get("author") or "Visual Sectors news feed"),
            stance=stance,  # type: ignore[arg-type]
            url=str(row["url"]) if row.get("url") else None,
        )

    def _get_pages(self, path: str, query: Mapping[str, str], *, cache: bool = True) -> dict[str, Any]:
        combined: list[dict[str, Any]] = []
        cursor: str | None = None
        envelope: dict[str, Any] | None = None
        seen: set[str] = set()
        while True:
            page_query = dict(query)
            if cursor:
                page_query["cursor"] = cursor
            page = self._request_json("GET", path, query=page_query, cache=cache)
            if envelope is None:
                envelope = dict(page)
            combined.extend(_rows(page, path))
            next_cursor = page.get("next_cursor")
            if next_cursor is None:
                break
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen:
                raise ApiResponseError(None, f"{path} returned an invalid pagination cursor")
            seen.add(next_cursor)
            cursor = next_cursor
        assert envelope is not None
        envelope["rows"] = combined
        envelope["count"] = len(combined)
        envelope["next_cursor"] = None
        return envelope

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
        cache: bool = True,
    ) -> dict[str, Any]:
        query_text = urlencode(query or {})
        url = self._base_url + path + ("?" + query_text if query_text else "")
        body_bytes = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        cache_day = datetime.now(timezone.utc).date().isoformat()
        cache_key = sha256(
            b"\0".join((cache_day.encode(), method.encode(), url.encode(), body_bytes or b""))
        ).hexdigest()
        cache_path = self._cache_dir / cache_day / f"{cache_key}.json"
        if cache and cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                cached = None
            if isinstance(cached, dict):
                return cached
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": "visualsectors-toolkit/0.1.0",
        }
        if body_bytes is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                raise RateLimitError(retry_after) from exc
            try:
                detail = json.loads(exc.read().decode("utf-8"))
                message = str(detail.get("message") or detail.get("error") or exc.reason)
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                message = str(exc.reason)
            raise ApiResponseError(exc.code, message) from exc
        except URLError as exc:
            raise ApiResponseError(None, str(exc.reason)) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiResponseError(None, "response was not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ApiResponseError(None, "response root was not an object")
        if cache:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        return payload
