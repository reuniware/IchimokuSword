# turtle/data_fetcher.py — Recuperation de donnees via MetaTrader5
# ======================================================================
# Telecharge les donnees OHLCV pour un symbole et un timeframe donnes.
# Supporte les exports CSV et le cache local.
# ======================================================================

import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# Ajouter le projet parent au path pour importer src.config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

from turtle.config import SYMBOLS, TF_LABELS

UTC = timezone.utc


def connect_mt5() -> bool:
    """Etablit la connexion MetaTrader5."""
    load_env()
    if not mt5.initialize():
        print("ERREUR: Impossible de se connecter a MT5")
        return False
    print(f"  MT5 connecte — {mt5.account_info().login}")
    return True


def fetch_rates(symbol: str, timeframe: int, count: int,
                start_pos: int = 0) -> Optional[pd.DataFrame]:
    """Recupere les donnees OHLCV pour un symbole/timeframe.

    Args:
        symbol: Nom du symbole MT5 (ex: 'EURUSD', 'XAUUSD')
        timeframe: Constante MT5 (16385=H1, 16388=H4, 16408=D1)
        count: Nombre de barres a recuperer
        start_pos: Position de depart (0 = plus recent)

    Returns:
        DataFrame avec colonnes: time, open, high, low, close, tick_volume
        ou None si echec.
    """
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    return df


def fetch_all_symbols(
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    min_bars: int = 2500,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Recupere les donnees pour tous les symboles et timeframes.

    Args:
        symbols: Liste de symboles (None = tous les symboles configures)
        timeframes: Liste de timeframes (None = ['H1','H4','D1'])
        min_bars: Nombre minimum de barres (2500 = ~10 ans en D1)

    Returns:
        Dict[symbol][timeframe_label] = DataFrame OHLCV
    """
    from turtle.config import TIMEFRAMES

    if symbols is None:
        symbols = []
        for cat in SYMBOLS.values():
            symbols.extend(cat)

    if timeframes is None:
        timeframes = list(TIMEFRAMES.keys())

    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}

    for sym in symbols:
        all_data[sym] = {}
        for tf_label in timeframes:
            tf_val = TIMEFRAMES[tf_label]
            df = fetch_rates(sym, tf_val, min_bars)
            if df is not None and len(df) > 50:
                all_data[sym][tf_label] = df
                start = df.index[0].strftime('%Y-%m-%d')
                end = df.index[-1].strftime('%Y-%m-%d')
                print(f"  {sym:<12} {tf_label:<4} — {len(df):>5} barres "
                      f"({start} -> {end})")
            else:
                print(f"  {sym:<12} {tf_label:<4} — PAS DE DONNEES")

    return all_data


def get_asset_class(symbol: str) -> str:
    """Determine la classe d'actif d'un symbole."""
    for cat, syms in SYMBOLS.items():
        if symbol in syms:
            return cat
    if symbol.endswith('.cash'):
        return "indices"
    if symbol in ("XAUUSD", "XAGUSD"):
        return "metaux"
    return "forex"


def get_symbol_info(symbol: str) -> dict:
    """Recupere les infos de trading d'un symbole MT5."""
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"point": 0.00001, "digits": 5}
    return {
        "point": info.point,
        "digits": info.digits,
        "spread": info.spread,
    }
