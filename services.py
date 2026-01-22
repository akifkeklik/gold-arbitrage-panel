from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


class DataFetchError(RuntimeError):
    """Raised when upstream market data cannot be fetched or parsed."""


def _extract_close_column(df: pd.DataFrame, ticker: str) -> pd.Series:
    """
    yfinance can return:
      - single-index columns: ["Open","High","Low","Close",...]
      - multi-index columns if multiple tickers or different settings:
          [("Close","ALTIN.IS"), ...] or [("ALTIN.IS","Close"), ...]
    This helper extracts a close Series robustly.
    """
    if df.empty:
        raise DataFetchError("yfinance returned an empty DataFrame.")

    # Common case: single index columns
    if "Close" in df.columns:
        close = df["Close"]
        if isinstance(close, pd.DataFrame):
            # Rare: duplicated columns
            close = close.iloc[:, 0]
        return close.astype(float)

    # MultiIndex cases
    if isinstance(df.columns, pd.MultiIndex):
        # ("Close", "ALTIN.IS") style
        if ("Close", ticker) in df.columns:
            return df[("Close", ticker)].astype(float)
        # ("ALTIN.IS", "Close") style
        if (ticker, "Close") in df.columns:
            return df[(ticker, "Close")].astype(float)
        # Fallback: find any level named "Close"
        for col in df.columns:
            if "Close" in col:
                return df[col].astype(float)

    raise DataFetchError("Could not locate Close column in yfinance response.")


class CertificateGoldService:
    """
    Asset 1 (X - The Certificate)
    Fetches ALTIN.IS from yfinance and transforms Close price into X by multiplying by 100.
    """

    def __init__(self, ticker: str = "ALTIN.IS", price_multiplier: float = 100.0) -> None:
        self.ticker = ticker
        self.price_multiplier = float(price_multiplier)

    def fetch_history(self, period: str, interval: str) -> pd.DataFrame:
        """
        Returns a DataFrame indexed by datetime with one column:
          - x: transformed certificate value (Close * 100)
        """
        try:
            df = yf.download(
                tickers=self.ticker,
                period=period,
                interval=interval,
                group_by="column",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
        except Exception as e:
            raise DataFetchError(f"yfinance download failed: {e}") from e

        close = _extract_close_column(df, self.ticker)
        out = pd.DataFrame(index=close.index.copy())
        out["x"] = close * self.price_multiplier
        out = out.dropna()
        if out.empty:
            raise DataFetchError("No valid close values after cleaning.")
        return out


@dataclass(frozen=True)
class SpreadModelConfig:
    """
    Simple OU-like spread simulation (mean-reverting + noise), clipped to bounds.
    Units are the same as X (Close * 100).
    """
    base_spread: float = 25.0          # average spread above X
    volatility: float = 6.0           # noise scale
    mean_reversion: float = 0.15      # how quickly it reverts to base_spread
    min_spread: float = 5.0           # hard floor
    max_spread: float = 120.0         # hard ceiling


class PhysicalGoldService:
    """
    Asset 2 (Physical Gold)
    MVP uses a simulation derived from X + random spread.
    Structure is intentionally isolated so you can swap in a scraper later.
    """

    def __init__(self, config: SpreadModelConfig = SpreadModelConfig()) -> None:
        self.config = config

    def simulate_from_certificate(
        self,
        x: pd.Series,
        *,
        seed: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Given X series, returns DataFrame with:
          - physical: simulated physical price
          - spread: physical - x
        """
        if x.empty:
            raise ValueError("x series is empty.")

        rng = np.random.default_rng(seed)
        n = len(x)

        spread = np.empty(n, dtype=float)
        spread[0] = self.config.base_spread

        for i in range(1, n):
            eps = rng.normal(0.0, 1.0)
            drift = self.config.mean_reversion * (self.config.base_spread - spread[i - 1])
            shock = self.config.volatility * eps
            spread[i] = spread[i - 1] + drift + shock

        spread = np.clip(spread, self.config.min_spread, self.config.max_spread)
        physical = x.to_numpy(dtype=float) + spread

        out = pd.DataFrame(index=x.index.copy())
        out["physical"] = physical
        out["spread"] = spread
        return out

    # Future-proof hook for later:
    def fetch_physical_prices_live(self, *args, **kwargs) -> pd.DataFrame:
        """
        Placeholder for a real scraper/API implementation.
        Keep the same output schema: index datetime, column 'physical'.
        """
        raise NotImplementedError("Replace with a scraper/API for production physical prices.")


def trim_to_window(df: pd.DataFrame, window: pd.Timedelta) -> pd.DataFrame:
    """Trim a timeseries DataFrame to its last `window` duration."""
    if df.empty:
        return df
    last_ts = df.index.max()
    return df[df.index >= (last_ts - window)]


def utc_now_bucketed(seconds: int) -> Tuple[datetime, int]:
    """
    Returns (bucketed_datetime_utc, seed_int) where seed changes every `seconds`.
    Useful for stable simulation within a refresh window, but changing across refresh ticks.
    """
    now = datetime.now(timezone.utc)
    bucket = int(now.timestamp()) // max(1, seconds)
    bucket_dt = datetime.fromtimestamp(bucket * seconds, tz=timezone.utc)
    return bucket_dt, bucket
