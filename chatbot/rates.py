"""Exchange-rate service.

Fetches one USD-based rate table, caches it, and derives any pair from it.
Provider order (first that works wins):
  1. ExchangeRate-API v6 with your key  (only if EXCHANGE_RATE_API_KEY is set)
  2. open.er-api.com                    (free, no key, ~160 currencies)
  3. Frankfurter                        (free, no key, ~30 currencies)
If every provider fails, the last good table is reused ("stale"); if there
never was one, built-in approximate rates are used ("offline"), so the chatbot
keeps working with no internet at all.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Mapping, Optional

import requests

log = logging.getLogger(__name__)

# Approximate USD-based rates, used ONLY when no live source is reachable.
OFFLINE_RATES: dict[str, float] = {
    "USD": 1.0, "EUR": 0.86, "GBP": 0.75, "INR": 88.5, "JPY": 150.0, "AUD": 1.52,
    "CAD": 1.39, "CHF": 0.80, "CNY": 7.1, "AED": 3.6725, "SAR": 3.75, "SGD": 1.30,
    "HKD": 7.78, "NZD": 1.70, "KRW": 1400.0, "BRL": 5.4, "MXN": 18.4, "ZAR": 17.5,
    "RUB": 80.0, "TRY": 41.0, "SEK": 9.5, "NOK": 10.2, "DKK": 6.4, "PLN": 3.65,
    "THB": 32.5, "IDR": 16500.0, "MYR": 4.2, "PHP": 58.0, "PKR": 281.0, "BDT": 122.0,
    "LKR": 303.0, "NPR": 141.0, "VND": 26300.0, "EGP": 48.0, "NGN": 1500.0,
    "KES": 129.0, "ILS": 3.3, "QAR": 3.64, "KWD": 0.307, "BHD": 0.376, "OMR": 0.385,
}


class RateProviderError(Exception):
    """A provider failed or returned unusable data."""


@dataclass(frozen=True)
class RateSnapshot:
    rates: Mapping[str, float]       # units of currency per 1 USD
    provider: str
    fetched_at: datetime
    status: str                      # "live" | "stale" | "offline"

    @property
    def is_estimate(self) -> bool:
        return self.status in ("stale", "offline")


def _clean(rates: Mapping) -> dict[str, float]:
    clean = {}
    for code, value in rates.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value > 0:
                clean[str(code).upper()] = float(value)
    if "USD" not in clean or len(clean) < 5:
        raise RateProviderError("rate table looks invalid")
    return clean


def _parse_er_api(data: dict) -> tuple[dict[str, float], Optional[datetime]]:
    if data.get("result") != "success":
        raise RateProviderError(f"provider said: {data.get('error-type', 'failure')}")
    ts = data.get("time_last_update_unix")
    when = datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None
    return _clean(data["rates"]), when


def _parse_keyed(data: dict) -> tuple[dict[str, float], Optional[datetime]]:
    if data.get("result") != "success":
        raise RateProviderError(f"provider said: {data.get('error-type', 'failure')}")
    ts = data.get("time_last_update_unix")
    when = datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None
    return _clean(data["conversion_rates"]), when


def _parse_frankfurter(data: dict) -> tuple[dict[str, float], Optional[datetime]]:
    rates = dict(data["rates"])
    rates["USD"] = 1.0
    return _clean(rates), None


class RateService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        ttl_seconds: float = 3600,
        timeout: float = 6.0,
        retry_cooldown: float = 60.0,
        session: Optional[requests.Session] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl = ttl_seconds
        self.timeout = timeout
        self.retry_cooldown = retry_cooldown
        self.session = session or requests.Session()
        self._clock = clock
        self._lock = threading.Lock()
        self._data: Optional[RateSnapshot] = None
        self._fresh_until = 0.0
        self._cooldown_until = 0.0

        self.providers: list[tuple[str, str, Callable]] = []
        if api_key:
            self.providers.append((
                "exchangerate-api.com",
                f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD",
                _parse_keyed,
            ))
        self.providers += [
            ("open.er-api.com", "https://open.er-api.com/v6/latest/USD", _parse_er_api),
            ("frankfurter.dev", "https://api.frankfurter.dev/v1/latest?base=USD", _parse_frankfurter),
            ("frankfurter.app", "https://api.frankfurter.app/latest?from=USD", _parse_frankfurter),
        ]

    # ------------------------------------------------------------ public
    def get_snapshot(self) -> RateSnapshot:
        with self._lock:
            now = self._clock()
            if self._data and now < self._fresh_until:
                return self._data
            if now < self._cooldown_until:
                return self._fallback()
            try:
                self._data = self._fetch()
                self._fresh_until = now + self.ttl
                return self._data
            except RateProviderError as exc:
                log.warning("All rate providers failed: %s", exc)
                self._cooldown_until = now + self.retry_cooldown
                return self._fallback()

    @staticmethod
    def convert(amount: float, source: str, target: str, snapshot: RateSnapshot) -> float:
        return amount * snapshot.rates[target] / snapshot.rates[source]

    @staticmethod
    def rate(source: str, target: str, snapshot: RateSnapshot) -> float:
        return snapshot.rates[target] / snapshot.rates[source]

    # ----------------------------------------------------------- private
    def _fallback(self) -> RateSnapshot:
        if self._data:
            return replace(self._data, status="stale")
        return RateSnapshot(
            rates=dict(OFFLINE_RATES),
            provider="built-in estimates",
            fetched_at=datetime.now(timezone.utc),
            status="offline",
        )

    def _fetch(self) -> RateSnapshot:
        errors = []
        for name, url, parser in self.providers:
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                rates, when = parser(resp.json())
                return RateSnapshot(rates, name, when or datetime.now(timezone.utc), "live")
            except (requests.RequestException, ValueError, KeyError, TypeError, RateProviderError) as exc:
                errors.append(f"{name}: {exc.__class__.__name__}")
                log.info("Rate provider %s failed: %s", name, exc)
        raise RateProviderError("; ".join(errors))
