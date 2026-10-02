"""Public exchange adapters. No API keys and no order methods."""

from app.services.markets.adapters.coinbase import CoinbaseAdapter
from app.services.markets.adapters.kalshi import KalshiAdapter
from app.services.markets.adapters.kraken import KrakenAdapter

__all__ = ["CoinbaseAdapter", "KalshiAdapter", "KrakenAdapter"]
