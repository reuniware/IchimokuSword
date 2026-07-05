# turtle/config.py — Configuration du backtester Turtle
# ======================================================================
# Parametres configurables pour les deux strategies :
#   - Turtle originale (trend-following)
#   - Turtle Soup (contrarian / faux breakout)
# ======================================================================

# Timeframes MT5
TIMEFRAMES = {
    "H1": 16385,   # mt5.TIMEFRAME_H1
    "H4": 16388,   # mt5.TIMEFRAME_H4
    "D1": 16408,   # mt5.TIMEFRAME_D1
}

TF_LABELS = {"H1": "H1", "H4": "H4", "D1": "Daily"}

# Symboles a backtester (multi-classes d'actifs)
SYMBOLS = {
    "forex":    ["EURUSD", "USDJPY", "GBPUSD"],
    "indices":  ["US500.cash", "GER40.cash"],
    "metaux":   ["XAUUSD", "XAGUSD"],
    "actions":  [],  # MT5 n'a pas d'actions typiques, on peut en ajouter
}

# -- Turtle originale (trend-following) --
TURTLE_ORIG_CONFIG = {
    "n1": 20,             # canal entree Systeme 1
    "n2": 55,             # canal entree Systeme 2 (filtre optionnel)
    "n_exit": 10,         # canal de sortie
    "atr_period": 20,     # periode ATR
    "stop_multiplier": 2.0,  # multiple d'ATR pour le stop-loss
    "max_units": 4,       # unites max en pyramidage
    "pyramid_step": 0.5,  # pas de pyramidage en multiple d'ATR
    "use_system2": True,  # activer le filtre Systeme 2
    "pyramiding": True,   # activer le pyramidage
}

# -- Turtle Soup (contrarian) --
TURTLE_SOUP_CONFIG = {
    "n": 20,              # periode du canal
    "min_ecart": 3,       # barres minimum entre ancien et nouveau extreme
    "stop_buffer": 1.0,   # multiple d'ATR pour le stop
    "take_profit_mode": "milieu_range",  # milieu_range | swing_oppose | rr_fixe
    "rr_ratio": 2.0,      # ratio risque/rendement si tp_mode = rr_fixe
}

# -- Couts de transaction realistes --
COSTS = {
    "forex":    {"spread_pct": 0.01, "slippage_pct": 0.02, "commission_pct": 0.0},
    "indices":  {"spread_pct": 0.02, "slippage_pct": 0.03, "commission_pct": 0.0},
    "metaux":   {"spread_pct": 0.03, "slippage_pct": 0.03, "commission_pct": 0.0},
}

# -- Filtre de regime de marche (ADX) --
MARKET_REGIME = {
    "adx_period": 14,
    "adx_threshold": 25,  # ADX > 25 = tendance, ADX < 25 = range
    "enabled": False,      # activer/desactiver le filtre
}

# -- Anti-overfitting --
WALK_FORWARD = {
    "train_pct": 0.70,    # 70% train, 30% test
    "window_months": 12,  # fenetre de reoptimisation
}

# -- Parametres de grid search --
GRID_SEARCH = {
    "turtle_soup": {
        "n": [10, 20, 30, 55],
        "min_ecart": [2, 3, 5],
        "stop_buffer": [0.5, 1.0, 1.5],
        "take_profit_mode": ["milieu_range", "swing_oppose", "rr_fixe"],
    },
    "turtle_orig": {
        "n1": [10, 20, 30],
        "n2": [40, 55, 70],
        "n_exit": [10, 20],
        "atr_period": [14, 20],
        "stop_multiplier": [1.5, 2.0, 2.5],
        "max_units": [1, 2, 4],
    },
}

# Capital initial
INITIAL_CAPITAL = 100_000.0
RISK_PER_TRADE_PCT = 1.0  # 1% du capital par trade (unit size Turtle)
