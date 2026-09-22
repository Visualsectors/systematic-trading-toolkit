"""Strict local JSON and bundled synthetic providers."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from ..models import DatasetManifest, MarketSnapshot, parse_manifest
from .base import MarketDataProvider, ProviderCapabilities


class JsonFileProvider(MarketDataProvider):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        raw: Any = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("dataset root must be an object")
        self._manifest = parse_manifest(raw)

    @property
    def capabilities(self) -> ProviderCapabilities:
        mode = "synthetic" if self._manifest.synthetic else "file"
        return ProviderCapabilities(
            assets=("US equities",),
            intervals=("daily",),
            history="one point-in-time snapshot",
            delay="declared by each dataset manifest",
            adjustment="provider-declared; fixture prices are synthetic",
            mode=mode,
        )

    @property
    def manifest(self) -> DatasetManifest:
        return self._manifest

    def universe(self) -> tuple[MarketSnapshot, ...]:
        return self._manifest.snapshots


class SyntheticFixtureProvider(JsonFileProvider):
    def __init__(self) -> None:
        path = files("visualsectors_toolkit").joinpath("fixtures/sample_market.json")
        super().__init__(Path(str(path)))
        if not self.manifest.synthetic:
            raise ValueError("bundled fixture must declare synthetic=true")
