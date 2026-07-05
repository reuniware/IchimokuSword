"""
backtest_cloud_cross.py - Backtest mécanique : franchissement nuage + Chikou
============================================================================

Stratégie purement mécanique (sans scoring) :

LONG :
    1. Prix franchit le nuage (breakout) : barre actuelle et précédente
       au-dessus, mais 2 barres avant PAS au-dessus
    2. Chikou Span au-dessus de TOUS ses niveaux :
       - Au-dessus du prix d'il y a 26 périodes
       - Au-dessus de la Kijun d'il y a 26 périodes
       - Au-dessus du nuage d'il y a 26 périodes

SHORT (inverse).

Nouveau — validation Chikou Span multi-timeframe :
    La Chikou Span ne doit pas être bloquée par Tenkan/Kijun/SSB
    à sa position projetée (26 barres en arrière), sur H4, D1 ET W1.

Option --mtf : vérifie D1 et W1 pour des niveaux bloquants
(SSB, Tenkan, Kijun, Senkou A) et définit un TP si assez loin,
+ valide que la Chikou n'est pas bloquée sur les UT supérieures.

Usage :
    python backtest_cloud_cross.py                              # D1
    python backtest_cloud_cross.py --timeframe H4 --mtf        # H4 + TP D1/W1
    python backtest_cloud_cross.py --tp-min-distance 0.5       # TP min 0.5%
"""

import json
import os
import sys
import time
from argparse import ArgumentParser
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np

from src.config import load_env
from src.ichimoku import (
    compute_full_ichimoku,
    compute_kijun_sen,
    compute_tenkan_sen,
    compute_senkou_span_a,
    compute_senkou_span_b,
)

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Timeframes
# ---------------------------------------------------------------------------

TIMEFRAMES = {
    "D1": {"mt5": mt5.TIMEFRAME_D1, "label": "D1",
           "lookaheads": [1, 3, 5, 10, 20],
           "la_display": ["1j", "3j", "5j", "10j", "20j"],
           "max_bars_default": 2000},
    "H4": {"mt5": mt5.TIMEFRAME_H4, "label": "H4",
           "lookaheads": [6, 18, 30, 60, 120],
           "la_display": ["6H", "18H", "30H", "60H", "120H"],
           "max_bars_default": 5000},
    "H1": {"mt5": mt5.TIMEFRAME_H1, "label": "H1",
           "lookaheads": [6, 18, 30, 60, 120],
           "la_display": ["6H", "18H", "30H", "60H", "120H"],
           "max_bars_default": 10000},
}

# MTF pairs: entry TF -> [higher TFs for Chikou validation + TP]
MTF_PAIRS = {
    "D1": {"tfs": [(None, "W1", mt5.TIMEFRAME_W1, 500)], "mtf_label": "W1"},
    "H4": {"tfs": [("D1", mt5.TIMEFRAME_D1, 2000), ("W1", mt5.TIMEFRAME_W1, 500)],
            "mtf_label": "D1/W1"},
    "H1": {"tfs": [("H4", mt5.TIMEFRAME_H4, 5000), ("D1", mt5.TIMEFRAME_D1, 2000)],
            "mtf_label": "H4/D1"},
}

MIN_BARS = 53
MIN_MTF_BARS = 53

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF",
    "EURJPY", "GBPJPY", "EURGBP", "AUDCAD", "EURCHF", "NZDJPY", "GBPCHF", "CHFJPY",
    "XAUUSD", "XAGUSD",
    "US30.cash", "US100.cash", "US500.cash",
    "GER40.cash", "UK100.cash", "FRA40.cash",
    "AUS200.cash", "HK50.cash",
]

DEFAULT_TP_MIN_DISTANCE = 0.3  # %
DEFAULT_SL_TYPE = "ssb"  # kijun, ssb, fixed
DEFAULT_SL_PCT = 0.5  # % for fixed SL
FTMO_RISK_PCT = 2.0  # % du capital risqué par trade
FTMO_CAPITAL = 10000  # capital initial


# ---------------------------------------------------------------------------
# Critères d'entrée mécaniques
# ---------------------------------------------------------------------------

def check_long_conditions(result, prev_above_cloud: bool,
                          prev2_above_cloud: bool,
                          highs=None, lows=None, closes=None,
                          bar_idx: int = 0) -> Tuple[bool, List[str]]:
    """Vérifie les conditions pour entrer LONG.

    Retourne (ok, blocked_by) où blocked_by liste les niveaux bloquants.
    """
    blocked = []

    if not result.cloud or not result.cloud.above_cloud:
        return False, blocked
    if not prev_above_cloud:
        return False, blocked
    if prev2_above_cloud:
        return False, blocked

    if not result.chikou:
        return False, blocked
    if not result.chikou.above_price_26:
        blocked.append("H4_Prix26")

    if not result.lagging_confirmation:
        return False, blocked
    if not result.lagging_confirmation.chikou_above_kijun_past:
        blocked.append("H4_Kijun26")
    if not result.lagging_confirmation.chikou_above_cloud_past:
        blocked.append("H4_Cloud26")

    # --- Chikou vs Tenkan et SSB à 26 barres (H4) ---
    if highs is not None and lows is not None and closes is not None and bar_idx >= 78:
        chikou_val = float(closes[-1])
        # Tenkan à i-26 (9 périodes finissant à i-26)
        t26 = (np.max(highs[bar_idx-34:bar_idx-26+1]) +
               np.min(lows[bar_idx-34:bar_idx-26+1])) / 2.0
        if chikou_val <= t26:
            blocked.append("H4_Tenkan26")
        # Kijun à i-26
        k26 = (np.max(highs[bar_idx-51:bar_idx-26+1]) +
               np.min(lows[bar_idx-51:bar_idx-26+1])) / 2.0
        if chikou_val <= k26:
            blocked.append("H4_Kijun26")
        # SSB à i-26
        s26 = (np.max(highs[bar_idx-77:bar_idx-26+1]) +
               np.min(lows[bar_idx-77:bar_idx-26+1])) / 2.0
        if chikou_val <= s26:
            blocked.append("H4_SSB26")

    return len(blocked) == 0, blocked


def check_short_conditions(result, prev_below_cloud: bool,
                           prev2_below_cloud: bool,
                           highs=None, lows=None, closes=None,
                           bar_idx: int = 0) -> Tuple[bool, List[str]]:
    """Vérifie les conditions pour entrer SHORT.

    Retourne (ok, blocked_by).
    """
    blocked = []

    if not result.cloud or not result.cloud.below_cloud:
        return False, blocked
    if not prev_below_cloud:
        return False, blocked
    if prev2_below_cloud:
        return False, blocked

    if not result.chikou:
        return False, blocked
    if result.chikou.above_price_26:
        blocked.append("H4_Prix26")

    if not result.lagging_confirmation:
        return False, blocked
    if result.lagging_confirmation.chikou_above_kijun_past:
        blocked.append("H4_Kijun26")
    if not result.lagging_confirmation.chikou_below_cloud_past:
        blocked.append("H4_Cloud26")

    # --- Chikou vs Tenkan et SSB à 26 barres (H4) ---
    if highs is not None and lows is not None and closes is not None and bar_idx >= 78:
        chikou_val = float(closes[-1])
        t26 = (np.max(highs[bar_idx-34:bar_idx-26+1]) +
               np.min(lows[bar_idx-34:bar_idx-26+1])) / 2.0
        if chikou_val >= t26:
            blocked.append("H4_Tenkan26")
        s26 = (np.max(highs[bar_idx-77:bar_idx-26+1]) +
               np.min(lows[bar_idx-77:bar_idx-26+1])) / 2.0
        if chikou_val >= s26:
            blocked.append("H4_SSB26")

    return len(blocked) == 0, blocked


# ---------------------------------------------------------------------------
# MTF : Détection des niveaux bloquants D1/W1
# ---------------------------------------------------------------------------

def _find_bar_index(times: np.ndarray, target_time: int) -> int:
    """Trouve l'index de la dernière barre avec time <= target_time."""
    idx = np.searchsorted(times, target_time, side='right') - 1
    return max(0, min(idx, len(times) - 1))


def _compute_ichimoku_levels(highs, lows) -> dict:
    """Calcule les niveaux Ichimoku clés pour un instant donné.

    Retourne un dict avec tenkan, kijun, ssb, senkou_a.
    Les valeurs sont None si pas assez de données.
    """
    levels = {}
    if len(highs) >= 9:
        levels["tenkan"] = float(compute_tenkan_sen(highs, lows, 9))
    else:
        levels["tenkan"] = None

    if len(highs) >= 26:
        levels["kijun"] = float(compute_kijun_sen(highs, lows, 26))
    else:
        levels["kijun"] = None

    if len(highs) >= 52:
        levels["ssb"] = float(compute_senkou_span_b(highs, lows, 52, 26))
    else:
        levels["ssb"] = None

    if len(highs) >= 26:
        levels["senkou_a"] = float(compute_senkou_span_a(highs, lows, 9, 26, 26))
    else:
        levels["senkou_a"] = None

    return levels


def compute_mtf_tp(
    mt5_name: str,
    h4_time: int,
    entry_price: float,
    direction: str,
    d1_rates,
    w1_rates,
    min_distance_pct: float = 0.3,
) -> Optional[dict]:
    """Calcule le TP basé sur les niveaux bloquants D1 et W1.

    Pour LONG : cherche la résistance la plus proche au-dessus du prix.
    Pour SHORT : cherche le support le plus proche en-dessous du prix.

    Retourne un dict {tp_price, tp_source, tp_distance_pct} ou None.
    """
    # Reculer d'1h pour éviter le lookahead bias : utiliser la dernière
    # barre D1/W1 CLÔTURÉE, pas celle du jour en cours.
    d1_idx = _find_bar_index(d1_rates['time'], h4_time - 3600)
    w1_idx = _find_bar_index(w1_rates['time'], h4_time - 3600)

    all_levels = []  # list of (source_label, level_price)

    # --- D1 ---
    if d1_idx >= 52:  # assez de barres pour Ichimoku complet
        d1_highs = d1_rates['high'][:d1_idx + 1]
        d1_lows = d1_rates['low'][:d1_idx + 1]
        lv = _compute_ichimoku_levels(d1_highs, d1_lows)
        for name in ["tenkan", "kijun", "ssb", "senkou_a"]:
            if lv[name] is not None and not np.isnan(lv[name]):
                all_levels.append((f"D1_{name}", lv[name]))

    # --- W1 ---
    if w1_idx >= 52:
        w1_highs = w1_rates['high'][:w1_idx + 1]
        w1_lows = w1_rates['low'][:w1_idx + 1]
        lv = _compute_ichimoku_levels(w1_highs, w1_lows)
        for name in ["tenkan", "kijun", "ssb", "senkou_a"]:
            if lv[name] is not None and not np.isnan(lv[name]):
                all_levels.append((f"W1_{name}", lv[name]))

    if not all_levels:
        return None

    if direction == "LONG":
        # Chercher la résistance la plus proche AU-DESSUS du prix
        resistances = [(src, lvl) for src, lvl in all_levels if lvl > entry_price]
        if not resistances:
            return None
        nearest_src, nearest_lvl = min(resistances, key=lambda x: x[1])
    else:
        # Chercher le support le plus proche EN-DESSOUS du prix
        supports = [(src, lvl) for src, lvl in all_levels if lvl < entry_price]
        if not supports:
            return None
        nearest_src, nearest_lvl = max(supports, key=lambda x: x[1])

    distance_pct = abs(nearest_lvl - entry_price) / entry_price * 100.0

    if distance_pct < min_distance_pct:
        return None  # trop proche, pas de TP

    return {
        "tp_price": round(nearest_lvl, 5),
        "tp_source": nearest_src,
        "tp_distance_pct": round(distance_pct, 3),
    }


# ---------------------------------------------------------------------------
# MTF : Validation Chikou Span libre sur D1 et W1
# ---------------------------------------------------------------------------

def chikou_free_mtf(
    h4_time: int,
    direction: str,
    d1_rates,
    w1_rates,
) -> Tuple[bool, List[str]]:
    """Vérifie que chaque Chikou (D1, W1) n'est pas bloquée par ses
    propres niveaux Tenkan/Kijun/SSB à 26 barres en arrière.

    Chaque timeframe valide sa PROPRE Chikou contre ses PROPRES niveaux.

    Retourne (is_free, blocked_by).
    """
    blocked = []
    lookback = h4_time - 3600  # dernière barre clôturée

    for tf_name, rates, min_bars in [("D1", d1_rates, 78), ("W1", w1_rates, 78)]:
        if rates is None:
            continue
        idx = _find_bar_index(rates['time'], lookback)
        if idx < min_bars:
            continue

        # Chikou de CE timeframe = son close
        chikou_val = float(rates['close'][idx])
        highs = rates['high'][:idx + 1]
        lows = rates['low'][:idx + 1]

        # Tenkan à idx-26 (9p finissant à idx-26)
        t26 = (np.max(highs[idx-34:idx-26+1]) +
               np.min(lows[idx-34:idx-26+1])) / 2.0
        # Kijun à idx-26
        k26 = (np.max(highs[idx-51:idx-26+1]) +
               np.min(lows[idx-51:idx-26+1])) / 2.0
        # SSB à idx-26
        s26 = (np.max(highs[idx-77:idx-26+1]) +
               np.min(lows[idx-77:idx-26+1])) / 2.0

        if direction == "LONG":
            if chikou_val <= t26:
                blocked.append(f"{tf_name}_Tenkan26")
            if chikou_val <= k26:
                blocked.append(f"{tf_name}_Kijun26")
            if chikou_val <= s26:
                blocked.append(f"{tf_name}_SSB26")
        else:
            if chikou_val >= t26:
                blocked.append(f"{tf_name}_Tenkan26")
            if chikou_val >= k26:
                blocked.append(f"{tf_name}_Kijun26")
            if chikou_val >= s26:
                blocked.append(f"{tf_name}_SSB26")

    return len(blocked) == 0, blocked


# --- Versions dynamiques (utilisent MTF_PAIRS) ---

def chikou_free_mtf_dyn(entry_time: int, direction: str,
                         mtf_pair: dict, mtf_rates: dict) -> Tuple[bool, List[str]]:
    """Version dynamique de chikou_free_mtf utilisant MTF_PAIRS."""
    blocked = []
    lookback = entry_time - 3600
    for name, _, _ in mtf_pair["tfs"]:
        rates = mtf_rates.get(name)
        if rates is None:
            continue
        idx = _find_bar_index(rates['time'], lookback)
        if idx < 78:
            continue
        chikou_val = float(rates['close'][idx])
        highs = rates['high'][:idx+1]
        lows = rates['low'][:idx+1]
        t26 = (np.max(highs[idx-34:idx-26+1]) + np.min(lows[idx-34:idx-26+1])) / 2.0
        k26 = (np.max(highs[idx-51:idx-26+1]) + np.min(lows[idx-51:idx-26+1])) / 2.0
        s26 = (np.max(highs[idx-77:idx-26+1]) + np.min(lows[idx-77:idx-26+1])) / 2.0
        if direction == "LONG":
            if chikou_val <= t26: blocked.append(f"{name}_Tenkan26")
            if chikou_val <= k26: blocked.append(f"{name}_Kijun26")
            if chikou_val <= s26: blocked.append(f"{name}_SSB26")
        else:
            if chikou_val >= t26: blocked.append(f"{name}_Tenkan26")
            if chikou_val >= k26: blocked.append(f"{name}_Kijun26")
            if chikou_val >= s26: blocked.append(f"{name}_SSB26")
    return len(blocked) == 0, blocked


def compute_mtf_tp_dyn(entry_time: int, entry_price: float, direction: str,
                        mtf_pair: dict, mtf_rates: dict,
                        min_distance_pct: float = 0.3) -> Optional[dict]:
    """Version dynamique de compute_mtf_tp utilisant MTF_PAIRS."""
    all_levels = []
    lookback = entry_time - 3600
    for name, _, _ in mtf_pair["tfs"]:
        rates = mtf_rates.get(name)
        if rates is None:
            continue
        idx = _find_bar_index(rates['time'], lookback)
        if idx < 52:
            continue
        lv = _compute_ichimoku_levels(rates['high'][:idx+1], rates['low'][:idx+1])
        for lname in ["tenkan", "kijun", "ssb", "senkou_a"]:
            if lv[lname] is not None and not np.isnan(lv[lname]):
                all_levels.append((f"{name}_{lname}", lv[lname]))
    if not all_levels:
        return None
    if direction == "LONG":
        candidates = [(s, l) for s, l in all_levels if l > entry_price]
        if not candidates: return None
        src, lvl = min(candidates, key=lambda x: x[1])
    else:
        candidates = [(s, l) for s, l in all_levels if l < entry_price]
        if not candidates: return None
        src, lvl = max(candidates, key=lambda x: x[1])
    dist = abs(lvl - entry_price) / entry_price * 100.0
    if dist < min_distance_pct:
        return None
    return {"tp_price": round(lvl, 5), "tp_source": src, "tp_distance_pct": round(dist, 3)}


# ---------------------------------------------------------------------------
# Backtest d'un symbole (avec ou sans MTF)
# ---------------------------------------------------------------------------

def backtest_symbol(mt5_name: str, max_bars: int = 2000,
                    quiet: bool = False,
                    timeframe: str = "D1",
                    use_mtf: bool = False,
                    tp_min_distance: float = 0.3,
                    sl_type: str = "ssb",
                    sl_pct: float = 0.5) -> Tuple[List[dict], dict]:
    """Backtest un symbole avec les critères mécaniques cloud + chikou.

    Si use_mtf=True, vérifie D1/W1 pour les niveaux bloquants et TP.
    sl_type: "kijun", "ssb", ou "fixed" (% du prix d'entrée).
    Retourne (trades, stats) où stats = {mtf_chikou_skipped, mtf_chikou_ok}.
    """
    tf_cfg = TIMEFRAMES[timeframe]
    lookaheads = tf_cfg["lookaheads"]
    tf_lbl = tf_cfg["label"]

    mtf_pair = MTF_PAIRS.get(timeframe) if use_mtf else None
    if not quiet:
        mtf_str = f" + MTF({mtf_pair['mtf_label']}) TP" if mtf_pair else ""
        print(f"  {mt5_name} ({tf_lbl}{mtf_str})... ", end="", flush=True)

    mt5.symbol_select(mt5_name, True)
    rates = mt5.copy_rates_from_pos(mt5_name, tf_cfg["mt5"], 0, max_bars)
    if rates is None or len(rates) < MIN_BARS:
        n = len(rates) if rates is not None else 0
        if not quiet:
            print(f"PAS ASSEZ DE DONNEES ({n} barres)")
        return [], {"mtf_chikou_checked": 0, "mtf_chikou_skipped": 0}

    # --- Pré-charger les UT supérieures si MTF activé ---
    mtf_rates = {}
    if mtf_pair:
        for name, tf_mt5, max_b in mtf_pair["tfs"]:
            mtf_rates[name] = mt5.copy_rates_from_pos(mt5_name, tf_mt5, 0, max_b)

    n = len(rates)
    trades = []
    mtf_chikou_checked = 0
    mtf_chikou_skipped = 0
    max_i = n - max(lookaheads) - 1

    prev_above = False
    prev2_above = False
    prev_below = False
    prev2_below = False

    for i in range(MIN_BARS - 1, max_i + 1):
        highs = rates['high'][:i + 1]
        lows = rates['low'][:i + 1]
        closes = rates['close'][:i + 1]
        opens = rates['open'][:i + 1]
        price = float(closes[-1])

        result = compute_full_ichimoku(mt5_name, tf_lbl, price,
                                       highs, lows, closes, opens)
        if result is None:
            prev2_above = prev_above
            prev2_below = prev_below
            prev_above = False
            prev_below = False
            continue

        current_above = result.cloud.above_cloud if result.cloud else False
        current_below = result.cloud.below_cloud if result.cloud else False

        direction = None
        blocked_h4 = []

        ok_l, blocked_l = check_long_conditions(
            result, prev_above, prev2_above,
            highs, lows, closes, i)
        if ok_l:
            direction = "LONG"
            blocked_h4 = blocked_l

        if not direction:
            ok_s, blocked_s = check_short_conditions(
                result, prev_below, prev2_below,
                highs, lows, closes, i)
            if ok_s:
                direction = "SHORT"
                blocked_h4 = blocked_s

        if direction:
            blocked_mtf = []
            tp_info = None

            if mtf_pair and mtf_rates:
                entry_time = int(rates['time'][i])
                mtf_chikou_checked += 1

                # Validation Chikou libre sur UT supérieures
                chikou_ok_mtf, blocked_mtf = chikou_free_mtf_dyn(
                    entry_time, direction, mtf_pair, mtf_rates)
                if not chikou_ok_mtf:
                    mtf_chikou_skipped += 1
                    prev2_above = prev_above
                    prev2_below = prev_below
                    prev_above = current_above
                    prev_below = current_below
                    continue

                tp_info = compute_mtf_tp_dyn(
                    entry_time, price, direction, mtf_pair, mtf_rates,
                    tp_min_distance,
                )

            # --- Calculer SL ---
            sl_price = _compute_sl(price, direction, sl_type, sl_pct,
                                   highs, lows, closes, i)

            entry = _build_entry(i, rates, price, direction, lookaheads,
                                 n, result, tp_info, sl_price, sl_type,
                                 blocked_h4=blocked_h4,
                                 blocked_mtf=blocked_mtf)
            trades.append(entry)

        prev2_above = prev_above
        prev2_below = prev_below
        prev_above = current_above
        prev_below = current_below

    stats = {
        "mtf_chikou_checked": mtf_chikou_checked,
        "mtf_chikou_skipped": mtf_chikou_skipped,
    }

    if not quiet and trades:
        n_long = sum(1 for t in trades if t["direction"] == "LONG")
        n_short = sum(1 for t in trades if t["direction"] == "SHORT")
        n_tp = sum(1 for t in trades if t.get("has_tp"))
        la_mid = lookaheads[len(lookaheads) // 2]
        wins = sum(1 for t in trades if t.get(f"win_{la_mid}") == 1)
        tp_str = f", TP={n_tp}" if n_tp else ""
        skip_str = f", ChikouSkip={mtf_chikou_skipped}" if mtf_chikou_skipped else ""
        print(f"{len(trades)} trades (L:{n_long} S:{n_short}{tp_str}{skip_str}), "
              f"Win{la_mid}={wins/len(trades)*100:.0f}%  "
              f"({trades[0]['date'][:10]}->{trades[-1]['date'][:10]})")
    elif not quiet:
        print("0 trades")

    return trades, stats


def _compute_sl(entry_price: float, direction: str,
                 sl_type: str, sl_pct: float,
                 highs, lows, closes, bar_idx: int) -> Optional[float]:
    """Calcule le prix du stop-loss selon le type choisi.

    - kijun: Kijun H4 à l'entrée
    - ssb: SSB H4 à l'entrée
    - fixed: pourcentage fixe depuis le prix d'entrée
    """
    if sl_type == "fixed":
        factor = 1.0 - sl_pct / 100.0 if direction == "LONG" else 1.0 + sl_pct / 100.0
        return round(entry_price * factor, 5)

    if bar_idx < 52:
        return None

    if sl_type == "kijun":
        if len(highs) >= 26:
            sl = float(compute_kijun_sen(highs, lows, 26))
        else:
            return None
    elif sl_type == "ssb":
        if len(highs) >= 52:
            sl = float(compute_senkou_span_b(highs, lows, 52, 26))
        else:
            return None
    else:
        return None

    # Vérifier que le SL est du bon côté
    if direction == "LONG" and sl >= entry_price:
        return None  # SL au-dessus ou égal au prix d'entrée = invalide
    if direction == "SHORT" and sl <= entry_price:
        return None

    return round(sl, 5)


def _build_entry(i: int, rates, price: float, direction: str,
                 lookaheads: List[int],                 n: int, result,
                 tp_info: Optional[dict] = None,
                 sl_price: Optional[float] = None,
                 sl_type: str = "ssb",
                 blocked_h4: List[str] = None,
                 blocked_mtf: List[str] = None) -> dict:
    """Construit une entrée de trade avec lookahead, TP et Chikou blocked."""
    entry = {
        "bar_index": i,
        "date": datetime.fromtimestamp(
            int(rates['time'][i]), tz=UTC
        ).strftime("%Y-%m-%d %H:%M"),
        "price": round(price, 5),
        "direction": direction,
        "cloud_above": result.cloud.above_cloud if result.cloud else False,
        "cloud_below": result.cloud.below_cloud if result.cloud else False,
        "chikou_above_price": result.chikou.above_price_26 if result.chikou else False,
        "chikou_above_kijun": (
            result.lagging_confirmation.chikou_above_kijun_past
            if result.lagging_confirmation else False
        ),
        "chikou_above_cloud": (
            result.lagging_confirmation.chikou_above_cloud_past
            if result.lagging_confirmation else False
        ),
        "cloud_color": result.cloud.cloud_color if result.cloud else "",
        "distance_pct": round(result.distance_pct, 4),
        "chikou_blocked_h4": blocked_h4 or [],
        "chikou_blocked_mtf": blocked_mtf or [],
    }

    # TP info
    if tp_info:
        entry["has_tp"] = True
        entry["tp_price"] = tp_info["tp_price"]
        entry["tp_source"] = tp_info["tp_source"]
        entry["tp_distance_pct"] = tp_info["tp_distance_pct"]
    else:
        entry["has_tp"] = False

    # SL info
    if sl_price is not None:
        entry["has_sl"] = True
        entry["sl_price"] = sl_price
        entry["sl_type"] = sl_type
        entry["sl_distance_pct"] = round(abs(sl_price - price) / price * 100.0, 3)
    else:
        entry["has_sl"] = False

    for la in lookaheads:
        if i + la >= n:
            continue

        fp = float(rates['close'][i + la])
        change = (fp - price) / price * 100.0
        entry[f"change_{la}"] = round(change, 3)
        predicted_up = (direction == "LONG")
        actual_up = fp > price
        entry[f"win_{la}"] = 1 if predicted_up == actual_up else 0
        entry[f"mag_{la}"] = round(abs(change), 3)

        # Check TP hit within lookahead
        tp_hit = False
        if entry["has_tp"]:
            tp_price = entry["tp_price"]
            if direction == "LONG":
                highs_slice = rates['high'][i + 1:i + la + 1]
                tp_hit = bool(np.any(highs_slice >= tp_price))
            else:
                lows_slice = rates['low'][i + 1:i + la + 1]
                tp_hit = bool(np.any(lows_slice <= tp_price))
        entry[f"tp_hit_{la}"] = 1 if tp_hit else 0

        # Check SL hit within lookahead
        sl_hit = False
        if entry["has_sl"]:
            sl_p = entry["sl_price"]
            if direction == "LONG":
                lows_slice = rates['low'][i + 1:i + la + 1]
                sl_hit = bool(np.any(lows_slice <= sl_p))
            else:
                highs_slice = rates['high'][i + 1:i + la + 1]
                sl_hit = bool(np.any(highs_slice >= sl_p))
        entry[f"sl_hit_{la}"] = 1 if sl_hit else 0

        # Outcome: what happened first within lookahead?
        # Priority: TP_HIT > SL_HIT > WIN > LOSS > OPEN
        if tp_hit:
            entry[f"outcome_{la}"] = "TP_HIT"
        elif sl_hit:
            entry[f"outcome_{la}"] = "SL_HIT"
        elif entry[f"win_{la}"] == 1:
            entry[f"outcome_{la}"] = "WIN"
        else:
            entry[f"outcome_{la}"] = "LOSS"

    return entry


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def print_report(all_results: Dict[str, List[dict]],
                 lookaheads: List[int],
                 la_display: List[str],
                 sl_type: str = "ssb",
                 ftmo: bool = False) -> None:
    """Affiche le rapport: win rates, SL stats, TP stats, FTMO P&L."""
    all_trades = []
    for sym, trades in all_results.items():
        for t in trades:
            t["symbol"] = sym
            all_trades.append(t)

    longs = [t for t in all_trades if t["direction"] == "LONG"]
    shorts = [t for t in all_trades if t["direction"] == "SHORT"]
    mid_la = lookaheads[2]
    mid_disp = la_display[2]

    has_tp = any(t.get("has_tp") for t in all_trades)
    has_sl = any(t.get("has_sl") for t in all_trades)

    print(f"\n{'='*110}")
    print("  BACKTEST MÉCANIQUE - FRANCHISSEMENT NUAGE + CHIKOU"
          + (" + MTF TP D1/W1" if has_tp else ""))
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Critères: breakout frais + Chikou au-dessus/bas de TOUS ses niveaux")
    if has_tp:
        print(f"  TP: niveau bloquant D1/W1 le plus proche (SSB/Tenkan/Kijun/SenkouA)")
    print(f"{'='*110}")

    # --- Résumé global ---
    print(f"\n  TRADES: {len(all_trades)} total "
          f"(LONG={len(longs)}, SHORT={len(shorts)})")
    print(f"  Ratio: L/S = {len(longs)/max(len(shorts),1):.1f}")

    if has_sl:
        n_sl = sum(1 for t in all_trades if t.get("has_sl"))
        sl_distances = [t.get("sl_distance_pct", 0) for t in all_trades if t.get("has_sl")]
        avg_sl = sum(sl_distances) / len(sl_distances) if sl_distances else 0
        print(f"  SL       : {sl_type} — {n_sl}/{len(all_trades)} trades "
              f"— distance moy={avg_sl:.2f}%")
    if has_tp:
        n_tp = sum(1 for t in all_trades if t.get("has_tp"))
        tp_distances = [t.get("tp_distance_pct", 0) for t in all_trades if t.get("has_tp")]
        print(f"  Avec TP  : {n_tp}/{len(all_trades)} "
              f"({n_tp/len(all_trades)*100:.0f}%) "
              f"— distance moy={sum(tp_distances)/len(tp_distances):.2f}%"
              if tp_distances else f"  Avec TP  : {n_tp}")
    print()

    # --- Par direction (win rates standard + TP hit rate) ---
    h_cols = [f"Win{d}" for d in la_display]
    tp_cols = [f"TP{d}" for d in la_display] if has_tp else []
    print(f"  {'Direction':<10} {'Trades':<8} " +
          " ".join(f"{h:<8}" for h in h_cols) +
          ((" " + " ".join(f"{h:<8}" for h in tp_cols)) if has_tp else "") +
          f"  {'Moy.Chg'+mid_disp:<12} {'Best'+mid_disp:<12} {'Pire'+mid_disp:<12}")
    print(f"  {'-'*10} {'-'*8} " +
          " ".join("-"*8 for _ in h_cols) +
          ((" " + " ".join("-"*8 for _ in tp_cols)) if has_tp else "") +
          f"  {'-'*12} {'-'*12} {'-'*12}")

    for label, group in [("LONG", longs), ("SHORT", shorts)]:
        if not group:
            continue
        n_grp = len(group)
        line = f"  {label:<10} {n_grp:<8} "
        for la in lookaheads:
            wins = sum(1 for t in group if t.get(f"win_{la}") == 1)
            line += f"{wins/n_grp*100:<8.1f} "

        # TP hit rates
        if has_tp:
            for la in lookaheads:
                tp_trades = [t for t in group if t.get("has_tp")]
                if tp_trades:
                    tp_hits = sum(1 for t in tp_trades if t.get(f"tp_hit_{la}") == 1)
                    line += f"{tp_hits/len(tp_trades)*100:<8.1f} "
                else:
                    line += f"{'N/A':<8} "

        changes = [t.get(f"change_{mid_la}", 0) for t in group]
        line += (f"  {sum(changes)/len(changes):<12.3f} "
                 f"{max(changes):<12.3f} "
                 f"{min(changes):<12.3f}")
        print(line)

    # --- TP : win rate avec TP vs sans TP ---
    if has_tp:
        print(f"\n{'='*110}")
        print(f"  TP : COMPARAISON AVEC vs SANS TP ({mid_disp})")
        print(f"{'='*110}")

        for label, group in [("LONG", longs), ("SHORT", shorts)]:
            if not group:
                continue
            with_tp = [t for t in group if t.get("has_tp")]
            without_tp = [t for t in group if not t.get("has_tp")]
            if not with_tp:
                continue

            wins_with = sum(1 for t in with_tp if t.get(f"win_{mid_la}") == 1)
            wins_without = sum(1 for t in without_tp if t.get(f"win_{mid_la}") == 1) if without_tp else 0
            avg_dist = sum(t.get("tp_distance_pct", 0) for t in with_tp) / len(with_tp)
            tp_hits = sum(1 for t in with_tp if t.get(f"tp_hit_{mid_la}") == 1)

            print(f"  {label}:")
            print(f"    Avec TP    : {len(with_tp):>5} trades | Win={wins_with/len(with_tp)*100:.1f}% "
                  f"| TP touché={tp_hits/len(with_tp)*100:.1f}% "
                  f"| Dist.moy={avg_dist:.2f}%")
            if without_tp:
                print(f"    Sans TP    : {len(without_tp):>5} trades | Win={wins_without/len(without_tp)*100:.1f}%")

            # Top TP sources
            sources = {}
            for t in with_tp:
                src = t.get("tp_source", "?")
                sources[src] = sources.get(src, 0) + 1
            top_src = sorted(sources.items(), key=lambda x: -x[1])[:5]
            src_str = ", ".join(f"{s}({c})" for s, c in top_src)
            print(f"    Sources TP : {src_str}")

    # --- Par symbole ---
    print(f"\n{'='*110}")
    print(f"  PAR SYMBOLE (LONGS + SHORTS)")
    print(f"{'='*110}")
    header = (f"  {'Symbole':<16} {'Trades':<8} {'L/S':<8} {'Periode':<22} "
              + " ".join(f"{h:<8}" for h in h_cols))
    print(header)
    print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*22} " +
          " ".join("-"*8 for _ in h_cols))

    sorted_syms = sorted(
        all_results.items(),
        key=lambda kv: (
            sum(1 for t in kv[1] if t.get(f"win_{mid_la}") == 1)
            / max(len(kv[1]), 1)
        ),
        reverse=True,
    )

    for sym, trades in sorted_syms:
        if not trades:
            continue
        n_sym = len(trades)
        n_l = sum(1 for t in trades if t["direction"] == "LONG")
        n_s = sum(1 for t in trades if t["direction"] == "SHORT")
        period = f"{trades[0]['date'][:10]}->{trades[-1]['date'][:10]}"
        line = f"  {sym:<16} {n_sym:<8} {n_l}/{n_s:<5} {period:<22} "
        for la in lookaheads:
            wins = sum(1 for t in trades if t.get(f"win_{la}") == 1)
            line += f"{wins/n_sym*100:<8.1f} "
        print(line)

    # --- Top 10 trades ---
    print(f"\n{'='*110}")
    print(f"  TOP 10 TRADES (plus gros gain {mid_disp})")
    print(f"{'='*110}")
    top = sorted(all_trades, key=lambda t: t.get(f"change_{mid_la}", -999), reverse=True)[:10]
    print(f"  {'Date':<12} {'Symbole':<16} {'Dir':<6} {'Prix':<10} "
          f"{'Change'+mid_disp:<10} {'Win':<4} {'TP':<10} {'TPHit':<6}")
    print(f"  {'-'*12} {'-'*16} {'-'*6} {'-'*10} {'-'*10} {'-'*4} {'-'*10} {'-'*6}")
    for t in top:
        tp_str = f"{t['tp_price']:.5f}" if t.get("has_tp") else "—"
        tp_hit = "OUI" if t.get(f"tp_hit_{mid_la}") == 1 else ("NON" if t.get("has_tp") else "—")
        print(f"  {t['date'][:10]:<12} {t['symbol']:<16} {t['direction']:<6} "
              f"{t['price']:<10.5f} {t.get(f'change_{mid_la}',0):<10.3f} "
              f"{'OUI' if t.get(f'win_{mid_la}')==1 else 'NON':<4} "
              f"{tp_str:<10} {tp_hit:<6}")

    # --- Pire 10 trades ---
    print(f"\n  PIRE 10 TRADES (plus grosse perte {mid_disp})")
    bot = sorted(all_trades, key=lambda t: t.get(f"change_{mid_la}", 999))[:10]
    print(f"  {'Date':<12} {'Symbole':<16} {'Dir':<6} {'Prix':<10} "
          f"{'Change'+mid_disp:<10} {'Win':<4} {'TP':<10} {'TPHit':<6}")
    print(f"  {'-'*12} {'-'*16} {'-'*6} {'-'*10} {'-'*10} {'-'*4} {'-'*10} {'-'*6}")
    for t in bot:
        tp_str = f"{t['tp_price']:.5f}" if t.get("has_tp") else "—"
        tp_hit = "OUI" if t.get(f"tp_hit_{mid_la}") == 1 else ("NON" if t.get("has_tp") else "—")
        print(f"  {t['date'][:10]:<12} {t['symbol']:<16} {t['direction']:<6} "
              f"{t['price']:<10.5f} {t.get(f'change_{mid_la}',0):<10.3f} "
              f"{'OUI' if t.get(f'win_{mid_la}')==1 else 'NON':<4} "
              f"{tp_str:<10} {tp_hit:<6}")

    # --- FTMO Simulation ---
    if ftmo and has_sl:
        _print_ftmo_simulation(all_trades, longs, shorts, lookaheads,
                               la_display, mid_la, mid_disp, sl_type)

    print(f"\n{'='*110}")
    print("  FIN DU RAPPORT")
    print(f"{'='*110}\n")


# ---------------------------------------------------------------------------
# Sauvegarde JSON
# ---------------------------------------------------------------------------

def _convert_native(obj):
    if isinstance(obj, dict):
        return {k: _convert_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_native(v) for v in obj]
    if hasattr(obj, 'item'):
        return obj.item()
    return obj


def _print_ftmo_simulation(all_trades, longs, shorts, lookaheads,
                           la_display, mid_la, mid_disp, sl_type):
    """Simulation FTMO: risque 2% par trade, capital $10k, levier 1:30."""
    capital = FTMO_CAPITAL

    # Trier par date
    sorted_trades = sorted(all_trades, key=lambda t: t["date"])

    print(f"\n{'='*110}")
    print(f"  FTMO SIMULATION — Capital: ${FTMO_CAPITAL:,.0f} | Risque/trade: {FTMO_RISK_PCT}% | SL: {sl_type}")
    print(f"{'='*110}")
    print(f"  {'Date':<12} {'Symbole':<16} {'Dir':<6} {'Entree':<10} {'SL':<10} {'Outcome':<8} {'30H Chg%':<10} {'P&L':<10} {'Capital':<12}")
    print(f"  {'-'*12} {'-'*16} {'-'*6} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*10} {'-'*12}")

    monthly_capital = {}
    wins = 0
    losses = 0

    for t in sorted_trades:
        if not t.get("has_sl"):
            continue

        sl_dist_pct = t.get("sl_distance_pct", 0.5)
        outcome = t.get(f"outcome_{mid_la}", "LOSS")
        change_pct = t.get(f"change_{mid_la}", 0)

        # Position sizing: risk 2% of capital per trade
        # position_value = risk_amount / sl_distance_pct * 100
        risk_amount = capital * FTMO_RISK_PCT / 100.0
        safe_sl = max(sl_dist_pct, 0.05)
        position_value = risk_amount / (safe_sl / 100.0)
        max_position = capital * 30
        position_value = min(position_value, max_position)

        if outcome == "SL_HIT":
            pnl = -risk_amount
            losses += 1
        elif outcome == "TP_HIT":
            tp_dist = t.get("tp_distance_pct", 0)
            pnl = position_value * (tp_dist / 100.0)
            wins += 1
        elif outcome == "WIN":
            raw_pnl = position_value * (change_pct / 100.0)
            pnl = min(raw_pnl, risk_amount * 3)
            wins += 1
        else:
            raw_pnl = position_value * (change_pct / 100.0)
            pnl = max(raw_pnl, -risk_amount * 2)
            if pnl < 0:
                losses += 1
            else:
                wins += 1

        capital += pnl
        month_key = t["date"][:7]
        monthly_capital[month_key] = capital

        print(f"  {t['date'][:10]:<12} {t['symbol']:<16} {t['direction']:<6} "
              f"{t['price']:<10.5f} {t.get('sl_price',0):<10.5f} {outcome:<8} "
              f"{change_pct:<10.3f} ${pnl:<9.0f} ${capital:<11,.0f}")

    roi = (capital - FTMO_CAPITAL) / FTMO_CAPITAL * 100.0
    n_trades = wins + losses
    wr = wins / max(n_trades, 1) * 100

    print(f"\n  {'-'*100}")
    print(f"  RESUME FTMO:")
    print(f"    Trades   : {n_trades} (W={wins}, L={losses})")
    print(f"    Win rate : {wr:.1f}%")
    print(f"    P&L      : ${capital - FTMO_CAPITAL:,.0f}")
    print(f"    ROI      : {roi:.1f}%")
    print(f"    Capital  : ${capital:,.0f}")

    # Monthly breakdown
    if monthly_capital:
        print(f"\n    CAPITAL PAR MOIS:")
        for month in sorted(monthly_capital.keys()):
            print(f"      {month}: ${monthly_capital[month]:,.0f}")


def save_report(all_results: Dict[str, List[dict]],
                output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_symbols": len(all_results),
        "total_signals": sum(len(v) for v in all_results.values()),
        "symbols": _convert_native(all_results),
    }
    fname = f"backtest_cloud_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Rapport sauvegardé: {fpath}")
    return fpath


# ---------------------------------------------------------------------------
# Résolution symboles
# ---------------------------------------------------------------------------

def resolve_symbols(mt5_symbols: dict, watchlist: List[str]) -> List[Tuple[str, str]]:
    resolved = []
    for sym in watchlist:
        if sym in mt5_symbols:
            r = mt5_symbols[sym]
            n = r.name if hasattr(r, 'name') else r
            resolved.append((sym, n))
        else:
            found = False
            for k, v in mt5_symbols.items():
                if hasattr(v, 'name') and sym.upper() == k.upper().replace('.CASH', ''):
                    resolved.append((sym, v.name))
                    found = True
                    break
            if not found:
                print(f"  {sym}: NON DISPONIBLE")
    return resolved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = ArgumentParser(
        description="Backtest mécanique Ichimoku : franchissement nuage + Chikou"
    )
    parser.add_argument("--symbols", type=str, default=None,
                        help="Symboles (séparés par virgules)")
    parser.add_argument("--timeframe", type=str, default="D1",
                        choices=list(TIMEFRAMES.keys()),
                        help="Timeframe: D1 ou H4")
    parser.add_argument("--max-bars", type=int, default=None,
                        help="Max barres (défaut: selon timeframe)")
    parser.add_argument("--output", type=str, default="reports",
                        help="Dossier de sortie JSON")
    parser.add_argument("--no-save", action="store_true",
                        help="Ne pas sauvegarder JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Mode silencieux")
    parser.add_argument("--mtf", action="store_true",
                        help="Activer le TP multi-timeframe (D1 + W1)")
    parser.add_argument("--tp-min-distance", type=float,
                        default=DEFAULT_TP_MIN_DISTANCE,
                        help=f"Distance min entree->TP en %% (defaut: {DEFAULT_TP_MIN_DISTANCE})")
    parser.add_argument("--sl-type", type=str,
                        default=DEFAULT_SL_TYPE,
                        choices=["kijun", "ssb", "fixed"],
                        help=f"Type de stop-loss (defaut: {DEFAULT_SL_TYPE})")
    parser.add_argument("--sl-pct", type=float,
                        default=DEFAULT_SL_PCT,
                        help=f"Distance SL en %% pour type=fixed (defaut: {DEFAULT_SL_PCT})")
    parser.add_argument("--ftmo", action="store_true",
                        help="Simuler P&L FTMO (risque 2%%, capital 10k)")
    args = parser.parse_args()

    load_env()
    if not mt5.initialize():
        print("ERREUR: Impossible de se connecter à MT5")
        sys.exit(1)

    tf_cfg = TIMEFRAMES[args.timeframe]
    lookaheads = tf_cfg["lookaheads"]
    la_display = tf_cfg["la_display"]
    tf_lbl = tf_cfg["label"]
    max_bars = args.max_bars or tf_cfg["max_bars_default"]

    # Symboles
    mt5_symbols = {s.name: s for s in mt5.symbols_get()}
    for sym in list(mt5_symbols.keys()):
        if sym.endswith('.cash'):
            mt5_symbols[sym.replace('.cash', '')] = sym
        else:
            mt5_symbols[f'{sym}.cash'] = sym

    watchlist = (
        [s.strip() for s in args.symbols.split(",")]
        if args.symbols else SYMBOLS
    )
    symbols_to_test = resolve_symbols(mt5_symbols, watchlist)
    if not symbols_to_test:
        print("Aucun symbole disponible.")
        mt5.shutdown()
        return

    mtf_str = " + MTF TP D1/W1" if args.mtf else ""
    print("=" * 110)
    print(f"  BACKTEST MÉCANIQUE - FRANCHISSEMENT NUAGE + CHIKOU ({tf_lbl}{mtf_str})")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {len(symbols_to_test)} symboles, max {max_bars} barres {tf_lbl}")
    print(f"  Critères: Breakout frais + Chikou au-dessus/bas de TOUS niveaux")
    if args.mtf:
        print(f"  TP: niveau D1/W1 bloquant (SSB/Tenkan/Kijun/SenkouA), "
              f"min {args.tp_min_distance}%")
    print(f"  SL: {args.sl_type}" + (f" (pct={args.sl_pct}%)" if args.sl_type == "fixed" else "") +
          (" | FTMO sim" if args.ftmo else ""))
    print("=" * 110)

    all_results: Dict[str, List[dict]] = {}
    t0 = time.time()

    total_mtf_skipped = 0
    total_mtf_checked = 0

    for display_name, mt5_name in symbols_to_test:
        trades, stats = backtest_symbol(
            mt5_name, max_bars=max_bars,
            quiet=args.quiet,
            timeframe=args.timeframe,
            use_mtf=args.mtf,
            tp_min_distance=args.tp_min_distance,
            sl_type=args.sl_type,
            sl_pct=args.sl_pct,
        )
        total_mtf_skipped += stats.get("mtf_chikou_skipped", 0)
        total_mtf_checked += stats.get("mtf_chikou_checked", 0)
        if trades:
            all_results[display_name] = trades

    elapsed = time.time() - t0
    total = sum(len(v) for v in all_results.values())
    print(f"\n  Backtest terminé en {elapsed:.0f}s — "
          f"{total} trades sur {len(all_results)} symboles")
    if total_mtf_skipped:
        print(f"  Chikou MTF bloquee -> {total_mtf_skipped} trades SKIPPES "
              f"({total_mtf_skipped/max(total_mtf_checked,1)*100:.0f}%)")

    if all_results:
        print_report(all_results, lookaheads, la_display,
                     sl_type=args.sl_type, ftmo=args.ftmo)
        if not args.no_save:
            save_report(all_results, args.output)
    else:
        print("\n  Aucun trade généré.")

    mt5.shutdown()


if __name__ == "__main__":
    main()
