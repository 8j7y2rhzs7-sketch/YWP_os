"""Read-only markets mode (Phase 1).

Public prices only. This package does not place orders, hold API keys, or
paper-trade. Paper trading is Phase 2. Live trading is Phase 3.
"""

CRYPTO_MODEL_VERSION = "ywp-markets-crypto-v1.0.0"
EXCHANGE_MODEL_VERSION = "ywp-markets-kalshi-v1.0.0"

# Spot majors for the first crypto board. No leverage, no perpetuals.
CRYPTO_WHITELIST = ("BTC-USD", "ETH-USD", "SOL-USD")

COINBASE_TAKER_FEE = 0.006
KRAKEN_TAKER_FEE = 0.008
KALSHI_TAKER_COEFFICIENT = 0.07
