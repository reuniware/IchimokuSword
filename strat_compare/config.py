# strat_compare/config.py — Configuration du comparateur de strategies
# ======================================================================
# Backtest sur la periode 01/01/2026 → 03/07/2026
# Tous les instruments FTMO + 6 timeframes + 7 strategies
# ======================================================================

import MetaTrader5 as mt5

# --- Periode du backtest ---
START_DATE = "2026-01-01"
END_DATE = "2026-07-03"

# --- Timeframes (M1 → D1) ---
TIMEFRAMES = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}

# --- Symboles FTMO (tous les instruments disponibles) ---
SYMBOLS = [
    # Forex Majors (7)
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD", "USDCAD",
    # Forex Minors (10)
    "EURGBP", "EURJPY", "GBPJPY", "EURCHF", "GBPCHF",
    "EURAUD", "GBPAUD", "AUDJPY", "NZDJPY", "CADJPY",
    # Indices (6)
    "US30", "US100", "US500", "GER40", "UK100", "JPN225",
    # Commodities (5)
    "XAUUSD", "XAGUSD", "USOIL", "UKOIL", "XNGUSD",
    # Crypto (4)
    "BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD",
]

# --- Capital et couts ---
INITIAL_CAPITAL = 10_000.0

# Couts par categorie (spread + slippage en %)
_FX_MAJOR_COST  = {"spread_pct": 0.005, "slippage_pct": 0.010}
_FX_MINOR_COST  = {"spread_pct": 0.015, "slippage_pct": 0.015}
_INDEX_COST     = {"spread_pct": 0.020, "slippage_pct": 0.030}
_COMMODITY_COST = {"spread_pct": 0.025, "slippage_pct": 0.030}
_CRYPTO_COST    = {"spread_pct": 0.080, "slippage_pct": 0.050}

COSTS = {
    # Forex Majors
    "EURUSD": _FX_MAJOR_COST, "GBPUSD": {"spread_pct": 0.008, "slippage_pct": 0.010},
    "USDJPY": _FX_MAJOR_COST, "USDCHF": _FX_MAJOR_COST,
    "AUDUSD": _FX_MAJOR_COST, "NZDUSD": {"spread_pct": 0.010, "slippage_pct": 0.015},
    "USDCAD": _FX_MAJOR_COST,
    # Forex Minors
    "EURGBP": _FX_MINOR_COST, "EURJPY": _FX_MINOR_COST,
    "GBPJPY": {"spread_pct": 0.020, "slippage_pct": 0.020},
    "EURCHF": _FX_MINOR_COST, "GBPCHF": _FX_MINOR_COST,
    "EURAUD": _FX_MINOR_COST, "GBPAUD": _FX_MINOR_COST,
    "AUDJPY": _FX_MINOR_COST, "NZDJPY": _FX_MINOR_COST,
    "CADJPY": _FX_MINOR_COST,
    # Indices
    "US30":   _INDEX_COST, "US100":  _INDEX_COST, "US500":  _INDEX_COST,
    "GER40":  _INDEX_COST, "UK100":  _INDEX_COST, "JPN225": _INDEX_COST,
    # Commodities
    "XAUUSD": {"spread_pct": 0.020, "slippage_pct": 0.020},
    "XAGUSD": {"spread_pct": 0.030, "slippage_pct": 0.030},
    "USOIL":  _COMMODITY_COST, "UKOIL":  _COMMODITY_COST,
    "XNGUSD": _COMMODITY_COST,
    # Crypto
    "BTCUSD": _CRYPTO_COST, "ETHUSD": _CRYPTO_COST,
    "LTCUSD": _CRYPTO_COST, "XRPUSD": _CRYPTO_COST,
}

# Fallback par defaut si un symbole n'est pas dans COSTS
DEFAULT_COST = {"spread_pct": 0.015, "slippage_pct": 0.015}


def get_costs(symbol: str) -> dict:
    """Retourne les couts pour un symbole, avec fallback."""
    if symbol in COSTS:
        return COSTS[symbol]
    print(f"  [WARN] {symbol}: couts par defaut utilises ({DEFAULT_COST['spread_pct']}% spread)")
    return DEFAULT_COST


# --- Parametres communs de risk management ---
ATR_PERIOD = 14

# --- Strategies ---
STRATEGIES = {
    "RSI": {
        "desc": "RSI(14) mean reversion — achat survendu, vente surachete",
        "params": {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "Bollinger": {
        "desc": "Bollinger Bands(20,2) mean reversion — rebond sur bandes",
        "params": {
            "bb_period": 20,
            "bb_std": 2.0,
            "sl_atr": 1.5,
            "tp_atr": 1.5,
        },
    },
    "MACD": {
        "desc": "MACD(12,26,9) crossover — suivi de tendance",
        "params": {
            "fast": 12,
            "slow": 26,
            "signal": 9,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "Stochastic": {
        "desc": "Stochastic(14,3) oversold/overbought crossover",
        "params": {
            "stoch_k": 14,
            "stoch_d": 3,
            "stoch_smooth": 3,
            "oversold": 20,
            "overbought": 80,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "EMA_Cross": {
        "desc": "EMA(9,21) crossover — suivi de tendance",
        "params": {
            "fast": 9,
            "slow": 21,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "Swing_SR": {
        "desc": "Swing High/Low — bounces sur supports/resistances horizontaux",
        "params": {
            "swing_window": 20,
            "proximity_atr": 0.8,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "Parabolic_SAR": {
        "desc": "Parabolic SAR(0.02, 0.2) — suivi de tendance",
        "params": {
            "step": 0.02,
            "maximum": 0.2,
            "sl_atr": 1.5,
            "tp_atr": 2.0,
        },
    },
    "Ichimoku_Scalp": {
        "desc": "Ichimoku flat-line scalping — cassure de Kijun/Senkou B plates",
        "params": {
            "flat_window": 7,
            "flat_threshold_atr": 0.01,
            "sl_atr": 0.6,
            "tp_atr": 1.5,
        },
    },
    "Ichimoku_MTF": {
        "desc": "Ichimoku MTF flat-line scalping — flat lines H4/D1, scalping M1/M5/M15",
        "params": {
            "higher_tfs": "4h,D",
            "flat_window": 5,
            "flat_threshold_atr": 0.01,
            "sl_atr": 0.6,
            "tp_atr": 1.5,
        },
    },
}
