"""Abstract provider contract.

Providers perform I/O. Calculation modules never import them, which keeps the
financial logic replayable and simple to test.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from ..models import DatasetManifest, MarketSnapshot


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    assets: tuple[str, ...]
    intervals: tuple[str, ...]
    history: str
    delay: str
    adjustment: str
    mode: Literal["synthetic", "file", "live"]


class MarketDataProvider(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @property
    @abstractmethod
    def manifest(self) -> DatasetManifest:
        raise NotImplementedError

    @abstractmethod
    def universe(self) -> tuple[MarketSnapshot, ...]:
        raise NotImplementedError

    def get(self, ticker: str) -> MarketSnapshot:
        normalized = ticker.strip().upper()
        for snapshot in self.universe():
            if snapshot.ticker == normalized:
                return snapshot
        raise KeyError(f"ticker not present in provider dataset: {normalized}")
