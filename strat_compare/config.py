# strat_compare/config.py — Configuration du comparateur de strategies
# ======================================================================
# Backtest sur la periode 01/01/2026 → 03/07/2026
# 7 strategies testees en parallele sur les memes donnees
# ======================================================================

import MetaTrader5 as mt5

# --- Periode du backtest ---
START_DATE = "2026-01-01"
END_DATE = "2026-07-03"

# --- Timeframes ---
TIMEFRAMES = {
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
}

# --- Symboles a tester ---
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]

# --- Capital et couts ---
INITIAL_CAPITAL = 10_000.0

COSTS = {
    "EURUSD":  {"spread_pct": 0.005, "slippage_pct": 0.01},
    "GBPUSD":  {"spread_pct": 0.008, "slippage_pct": 0.01},
    "XAUUSD":  {"spread_pct": 0.02,  "slippage_pct": 0.02},
}

# --- Parametres communs de risk management ---
ATR_PERIOD = 14
RISK_PER_TRADE_PCT = 1.0  # 1% du capital par trade

# --- Strategies ---
# Chaque strategie a un dict de parametres.
# sl_atr / tp_atr : multiples d'ATR pour stop-loss et take-profit.
# 0 pour tp_atr = pas de TP (sortie sur signal oppose uniquement).

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
}
