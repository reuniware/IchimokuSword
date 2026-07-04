"""
backtest_combined.py - Backtest combiné : scoring + Cloud+Chikou + SL/TP
=========================================================================

Combine les meilleurs filtres identifiés par le backtesting :

    1. Scoring Ichimoku > 80 + Confiance ELEVEE
    2. Cloud breakout frais + Chikou H4 > tous niveaux à 26p
    3. Chikou D1 + W1 libres (chaque TF sa propre Chikou)
    4. Proximité Kijun < 0.3% (entrée au bon endroit)
    5. Stop-loss = Kijun H4
    6. TP = niveau W1/D1 bloquant le plus proche (> 0.3%)
    7. LONG uniquement

Usage :
    python backtest_combined.py --timeframe H4
    python backtest_combined.py --symbols EURUSD,XAUUSD
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
    compute_single_tf_confidence,
    IchimokuResult,
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
}

MTF_TFS = {"D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1}
MIN_BARS = 78  # besoin de 78 barres pour Chikou vs SSB à 26p

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF",
    "EURJPY", "GBPJPY", "EURGBP", "AUDCAD", "EURCHF", "NZDJPY", "GBPCHF", "CHFJPY",
    "XAUUSD", "XAGUSD",
    "US30.cash", "US100.cash", "US500.cash",
    "GER40.cash", "UK100.cash", "FRA40.cash",
    "AUS200.cash", "HK50.cash",
]


# ===========================================================================
# FILTRE 1 : Scoring + Confiance
# ===========================================================================

def compute_backtest_score(result: IchimokuResult) -> int:
    """Score 0-100 single-TF (identique à backtest.py)."""
    score = 0
    if result.cloud:
        if result.cloud.above_cloud:
            ok = (result.cloud.cloud_color == "VERT")
            score += 20 if ok else 12
        elif result.cloud.inside_cloud:
            score += 4
        elif result.cloud.below_cloud:
            ok = (result.cloud.cloud_color == "ROUGE")
            score += 16 if ok else 8
    else:
        score += 4

    if result.tk_cross:
        if result.tk_cross.cross_type == "TK_CROSS_HAUSSIER":
            score += 15
        elif result.tk_cross.current_position == "TENKAN_HAUT":
            score += 8
        elif result.tk_cross.cross_type:
            score += 8
    else:
        score += 3

    if result.chikou:
        if result.chikou.bullish_alignment:
            score += 15
        elif result.chikou.above_price_26:
            score += 7
    else:
        score += 2

    if result.three_rules:
        v = result.three_rules.rules_validated
        if v == 3: score += 20
        elif v == 2: score += 10
        elif v == 1: score += 4
    else:
        score += 2

    dist = result.distance_pct
    if dist < 0.1: score += 10
    elif dist < 0.3: score += 7
    elif dist < 0.5: score += 4
    elif dist < 1.0: score += 2

    if result.flat:
        if not result.flat.kijun_flat: score += 10
        elif result.flat.kijun_flat_bars < 10: score += 5
    else:
        score += 5

    if result.lagging_confirmation:
        if result.lagging_confirmation.power_confirmed: score += 10
        elif (result.lagging_confirmation.confirmation_bullish or
              result.lagging_confirmation.confirmation_bearish):
            score += 5
    else:
        score += 3

    return min(score, 100)


# ===========================================================================
# FILTRE 2 : Cloud breakout + Chikou H4
# ===========================================================================

def check_cloud_chikou_h4(result, prev_above: bool, prev2_above: bool,
                          highs, lows, closes, bar_idx: int) -> bool:
    """Cloud breakout frais + Chikou H4 > tous niveaux à 26p."""
    if not result.cloud or not result.cloud.above_cloud:
        return False
    if not prev_above or prev2_above:
        return False

    if not result.chikou or not result.chikou.above_price_26:
        return False
    if not result.lagging_confirmation:
        return False
    if not result.lagging_confirmation.chikou_above_kijun_past:
        return False
    if not result.lagging_confirmation.chikou_above_cloud_past:
        return False

    if bar_idx >= 78:
        c = float(closes[-1])
        t26 = (np.max(highs[bar_idx-34:bar_idx-26+1]) +
               np.min(lows[bar_idx-34:bar_idx-26+1])) / 2.0
        k26 = (np.max(highs[bar_idx-51:bar_idx-26+1]) +
               np.min(lows[bar_idx-51:bar_idx-26+1])) / 2.0
        s26 = (np.max(highs[bar_idx-77:bar_idx-26+1]) +
               np.min(lows[bar_idx-77:bar_idx-26+1])) / 2.0
        if c <= t26 or c <= k26 or c <= s26:
            return False

    return True


# ===========================================================================
# FILTRE 3 : Chikou D1 + W1 libres
# ===========================================================================

def _find_bar_index(times: np.ndarray, target: int) -> int:
    idx = np.searchsorted(times, target, side='right') - 1
    return max(0, min(idx, len(times) - 1))


def chikou_free_mtf(h4_time: int, d1_rates, w1_rates) -> bool:
    """Chaque TF valide sa PROPRE Chikou contre ses PROPRES niveaux à 26p."""
    lookback = h4_time - 3600
    for rates, min_b in [(d1_rates, 78), (w1_rates, 78)]:
        if rates is None:
            continue
        idx = _find_bar_index(rates['time'], lookback)
        if idx < min_b:
            continue
        c = float(rates['close'][idx])
        h = rates['high'][:idx+1]
        l = rates['low'][:idx+1]
        t26 = (np.max(h[idx-34:idx-26+1]) + np.min(l[idx-34:idx-26+1])) / 2.0
        k26 = (np.max(h[idx-51:idx-26+1]) + np.min(l[idx-51:idx-26+1])) / 2.0
        s26 = (np.max(h[idx-77:idx-26+1]) + np.min(l[idx-77:idx-26+1])) / 2.0
        if c <= t26 or c <= k26 or c <= s26:
            return False
    return True


# ===========================================================================
# SL / TP
# ===========================================================================

def find_sl_tp(result, entry_price: float, h4_time: int,
               d1_rates, w1_rates,
               tp_min_pct: float = 0.3) -> Tuple[float, Optional[float], Optional[str]]:
    """Calcule SL = SSB H4 (Senkou B), TP = 1er niveau D1/W1 au-dessus (> 0.3%)."""
    sl = result.senkou_span_b if result.senkou_span_b > 0 else 0
    if sl <= 0 or sl >= entry_price:
        sl = result.kijun_sen  # fallback: Kijun
    if sl <= 0 or sl >= entry_price:
        sl = entry_price * 0.99  # dernier recours

    # TP = résistance D1/W1 la plus proche
    d1_idx = _find_bar_index(d1_rates['time'], h4_time - 3600) if d1_rates is not None else -1
    w1_idx = _find_bar_index(w1_rates['time'], h4_time - 3600) if w1_rates is not None else -1

    levels = []
    for label, rates, idx in [("D1", d1_rates, d1_idx), ("W1", w1_rates, w1_idx)]:
        if rates is None or idx < 52:
            continue
        h = rates['high'][:idx+1]
        l = rates['low'][:idx+1]
        for name, fn, period in [("tenkan", compute_tenkan_sen, 9),
                                  ("kijun", compute_kijun_sen, 26),
                                  ("ssb", compute_senkou_span_b, 52)]:
            if len(h) >= period:
                v = float(fn(h, l, period))
                if not np.isnan(v) and v > entry_price:
                    levels.append((f"{label}_{name}", v))
        # Senkou A (signature différente)
        if len(h) >= 26:
            sa = float(compute_senkou_span_a(h, l, 9, 26, 26))
            if not np.isnan(sa) and sa > entry_price:
                levels.append((f"{label}_senkou_a", sa))

    if not levels:
        return sl, None, None

    nearest_src, nearest_lvl = min(levels, key=lambda x: x[1])
    dist = (nearest_lvl - entry_price) / entry_price * 100.0
    if dist < tp_min_pct:
        return sl, None, None

    return sl, nearest_lvl, nearest_src


# ===========================================================================
# Backtest
# ===========================================================================

def backtest_symbol(mt5_name: str, max_bars: int = 5000,
                    quiet: bool = False,
                    tp_min_pct: float = 0.3,
                    kijun_max_pct: float = 0.3) -> Tuple[List[dict], dict]:
    """Backtest combiné LONG uniquement."""
    tf_cfg = TIMEFRAMES["H4"]
    lookaheads = tf_cfg["lookaheads"]

    if not quiet:
        print(f"  {mt5_name} (H4 combine)... ", end="", flush=True)

    mt5.symbol_select(mt5_name, True)
    rates = mt5.copy_rates_from_pos(mt5_name, tf_cfg["mt5"], 0, max_bars)
    if rates is None or len(rates) < MIN_BARS:
        n = len(rates) if rates is not None else 0
        if not quiet:
            print(f"PAS ASSEZ DE DONNEES ({n} barres)")
        return [], {"d1": 0, "d2": 0, "d3": 0, "d4": 0}

    d1_rates = mt5.copy_rates_from_pos(mt5_name, MTF_TFS["D1"], 0, 2000)
    w1_rates = mt5.copy_rates_from_pos(mt5_name, MTF_TFS["W1"], 0, 500)

    n = len(rates)
    trades = []
    drops = {"score_conf": 0, "cloud_chikou": 0, "chikou_mtf": 0, "kijun_dist": 0}
    max_i = n - max(lookaheads) - 1

    prev_above = False
    prev2_above = False

    for i in range(MIN_BARS - 1, max_i + 1):
        highs = rates['high'][:i+1]
        lows = rates['low'][:i+1]
        closes = rates['close'][:i+1]
        opens = rates['open'][:i+1]
        price = float(closes[-1])

        result = compute_full_ichimoku(mt5_name, "H4", price,
                                       highs, lows, closes, opens)
        if result is None:
            prev2_above = prev_above
            prev_above = False
            continue

        cur_above = result.cloud.above_cloud if result.cloud else False

        # --- Filtre 1 : Score > 80 + Confiance ELEVEE ---
        score = compute_backtest_score(result)
        conf = compute_single_tf_confidence(result)
        if score < 80 or conf.label != "ELEVEE":
            drops["score_conf"] += 1
            prev2_above = prev_above
            prev_above = cur_above
            continue

        # --- Filtre 2 : Cloud breakout + Chikou H4 ---
        if not check_cloud_chikou_h4(result, prev_above, prev2_above,
                                     highs, lows, closes, i):
            drops["cloud_chikou"] += 1
            prev2_above = prev_above
            prev_above = cur_above
            continue

        # --- Filtre 3 : Chikou D1/W1 libres ---
        h4_time = int(rates['time'][i])
        if not chikou_free_mtf(h4_time, d1_rates, w1_rates):
            drops["chikou_mtf"] += 1
            prev2_above = prev_above
            prev_above = cur_above
            continue

        # --- Filtre 4 : Proximité Kijun ---
        if result.distance_pct > kijun_max_pct:
            drops["kijun_dist"] += 1
            prev2_above = prev_above
            prev_above = cur_above
            continue

        # --- Tous les filtres passés : entrée LONG ---
        sl, tp_price, tp_source = find_sl_tp(
            result, price, h4_time, d1_rates, w1_rates, tp_min_pct)

        risk = price - sl
        reward = (tp_price - price) if tp_price else None
        rr = round(reward / risk, 2) if tp_price and risk > 0 else None

        entry = {
            "bar_index": i,
            "date": datetime.fromtimestamp(
                int(rates['time'][i]), tz=UTC).strftime("%Y-%m-%d %H:%M"),
            "symbol": mt5_name,
            "price": round(price, 5),
            "direction": "LONG",
            "score": score,
            "conf_score": conf.score,
            "conf_label": conf.label,
            "kijun": round(result.kijun_sen, 5),
            "distance_pct": round(result.distance_pct, 4),
            "sl": round(sl, 5),
            "tp_price": round(tp_price, 5) if tp_price else None,
            "tp_source": tp_source,
            "rr": rr,
        }

        # Lookahead avec SL/TP
        for la in lookaheads:
            if i + la >= n:
                continue
            fp = float(rates['close'][i+la])
            change = (fp - price) / price * 100.0
            entry[f"change_{la}"] = round(change, 3)
            entry[f"win_{la}"] = 1 if fp > price else 0

            # Déterminer l'issue : TP touché > SL touché > Win/Loss
            outcome = "WIN" if fp > price else "LOSS"
            for k in range(1, la + 1):
                hi = float(rates['high'][i+k])
                lo = float(rates['low'][i+k])
                if tp_price and hi >= tp_price:
                    outcome = "TP_HIT"
                    break
                if lo <= sl:
                    outcome = "SL_HIT"
                    break
            else:
                outcome = "WIN" if fp > price else "LOSS"

            entry[f"outcome_{la}"] = outcome

        trades.append(entry)

        prev2_above = prev_above
        prev_above = cur_above

    if not quiet and trades:
        la_mid = lookaheads[2]
        wins = sum(1 for t in trades if t.get(f"win_{la_mid}") == 1)
        tp_hits = sum(1 for t in trades if t.get(f"outcome_{la_mid}") == "TP_HIT")
        print(f"{len(trades)} trades, Win{la_mid}={wins/len(trades)*100:.0f}% "
              f"(TP={tp_hits})  "
              f"({trades[0]['date'][:10]}->{trades[-1]['date'][:10]})")
    elif not quiet:
        print(f"0 trades (filtres: score={drops['score_conf']} "
              f"cloud={drops['cloud_chikou']} mtf={drops['chikou_mtf']} "
              f"kijun={drops['kijun_dist']})")

    return trades, drops


# ===========================================================================
# Rapport
# ===========================================================================

def print_report(all_results: Dict[str, List[dict]],
                 lookaheads: List[int],
                 la_display: List[str]) -> None:
    all_trades = []
    for sym, trades in all_results.items():
        for t in trades:
            t["symbol"] = sym
            all_trades.append(t)

    mid_la = lookaheads[2]
    mid_disp = la_display[2]

    print(f"\n{'='*110}")
    print("  BACKTEST COMBINÉ — SCORING + CLOUD+CHIKOU + SL/TP")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Filtres: Score>80 + Conf.ELEVEE + Cloud+Chikou H4/D1/W1 + Kijun<0.3%")
    print(f"  SL=SSB H4 | TP=W1/D1 blocking level | LONG only")
    print(f"{'='*110}")

    # Stats globales
    n = len(all_trades)
    n_tp = sum(1 for t in all_trades if t.get("tp_price"))
    avg_score = sum(t["score"] for t in all_trades) / n if n else 0
    avg_rr = sum(t["rr"] for t in all_trades if t["rr"]) / max(
        sum(1 for t in all_trades if t["rr"]), 1)

    print(f"\n  TRADES: {n} | Score moy: {avg_score:.1f} | RR moyen: {avg_rr:.2f}")
    print(f"  Avec TP: {n_tp}/{n} ({n_tp/max(n,1)*100:.0f}%)")

    # Win rates + outcomes
    h_cols = [f"Win{d}" for d in la_display]
    print(f"\n  {' ':<10} " + " ".join(f"{h:<8}" for h in h_cols))
    print(f"  {'-'*10} " + " ".join("-"*8 for _ in h_cols))

    for la, ld in zip(lookaheads, la_display):
        wins = sum(1 for t in all_trades if t.get(f"win_{la}") == 1)
        tp_h = sum(1 for t in all_trades if t.get(f"outcome_{la}") == "TP_HIT")
        sl_h = sum(1 for t in all_trades if t.get(f"outcome_{la}") == "SL_HIT")
        other = n - tp_h - sl_h
        print(f"  {ld:<10} {wins/n*100:<8.1f}%  "
              f"TP={tp_h}({tp_h/n*100:.0f}%) SL={sl_h}({sl_h/n*100:.0f}%) "
              f"Win/Loss={other}")

    # TP vs no-TP
    with_tp = [t for t in all_trades if t.get("tp_price")]
    without_tp = [t for t in all_trades if not t.get("tp_price")]
    if with_tp and without_tp:
        print(f"\n  {'='*60}")
        print(f"  TP vs SANS TP ({mid_disp})")
        print(f"  {'='*60}")
        for label, grp in [("Avec TP", with_tp), ("Sans TP", without_tp)]:
            w = sum(1 for t in grp if t.get(f"win_{mid_la}") == 1)
            tp_h = sum(1 for t in grp if t.get(f"outcome_{mid_la}") == "TP_HIT")
            sl_h = sum(1 for t in grp if t.get(f"outcome_{mid_la}") == "SL_HIT")
            rr_g = [t["rr"] for t in grp if t["rr"]]
            print(f"    {label:<10} {len(grp):>5} tr | Win={w/len(grp)*100:.1f}% "
                  f"| TP={tp_h} SL={sl_h} "
                  f"| RR moy={sum(rr_g)/len(rr_g):.2f}" if rr_g else
                  f"    {label:<10} {len(grp):>5} tr | Win={w/len(grp)*100:.1f}%")

    # Top sources TP
    if with_tp:
        sources = {}
        for t in with_tp:
            s = t.get("tp_source", "?")
            sources[s] = sources.get(s, 0) + 1
        top5 = sorted(sources.items(), key=lambda x: -x[1])[:5]
        print(f"    Sources TP: {', '.join(f'{s}({c})' for s,c in top5)}")

    # Par symbole
    print(f"\n  {'='*110}")
    print(f"  PAR SYMBOLE")
    print(f"  {'='*110}")
    header = (f"  {'Symbole':<16} {'Tr':<5} {'Win'+mid_disp:<8} {'TP':<5} {'SL':<5} "
              f"{'Score':<7} {'RR':<6} {'Periode'}")
    print(header)
    print(f"  {'-'*16} {'-'*5} {'-'*8} {'-'*5} {'-'*5} {'-'*7} {'-'*6} {'-'*22}")

    sorted_syms = sorted(all_results.items(),
                         key=lambda kv: (sum(1 for t in kv[1]
                                             if t.get(f"win_{mid_la}") == 1)
                                         / max(len(kv[1]), 1)), reverse=True)
    for sym, trades in sorted_syms:
        if not trades:
            continue
        ns = len(trades)
        w = sum(1 for t in trades if t.get(f"win_{mid_la}") == 1)
        tp = sum(1 for t in trades if t.get(f"outcome_{mid_la}") == "TP_HIT")
        sl = sum(1 for t in trades if t.get(f"outcome_{mid_la}") == "SL_HIT")
        sc = sum(t["score"] for t in trades) / ns
        rr = [t["rr"] for t in trades if t["rr"]]
        rr_avg = sum(rr) / len(rr) if rr else 0
        period = f"{trades[0]['date'][:10]}->{trades[-1]['date'][:10]}"
        print(f"  {sym:<16} {ns:<5} {w/ns*100:<8.1f} {tp:<5} {sl:<5} "
              f"{sc:<7.1f} {rr_avg:<6.2f} {period}")

    # Top 10
    print(f"\n  TOP 10 ({mid_disp})")
    top = sorted(all_trades, key=lambda t: t.get(f"change_{mid_la}", -999), reverse=True)[:10]
    print(f"  {'Date':<12} {'Symbole':<16} {'Prix':<10} {'Chg'+mid_disp:<10} "
          f"{'Outcome':<8} {'SL':<10} {'TP':<10} {'RR':<6}")
    for t in top:
        tp_s = f"{t['tp_price']:.5f}" if t.get("tp_price") else "-"
        print(f"  {t['date'][:10]:<12} {t['symbol']:<16} {t['price']:<10.5f} "
              f"{t.get(f'change_{mid_la}',0):<10.3f} "
              f"{t.get(f'outcome_{mid_la}','?'):<8} "
              f"{t['sl']:<10.5f} {tp_s:<10} {t.get('rr','-')}")

    # Pire 10
    print(f"\n  PIRE 10 ({mid_disp})")
    bot = sorted(all_trades, key=lambda t: t.get(f"change_{mid_la}", 999))[:10]
    for t in bot:
        tp_s = f"{t['tp_price']:.5f}" if t.get("tp_price") else "-"
        print(f"  {t['date'][:10]:<12} {t['symbol']:<16} {t['price']:<10.5f} "
              f"{t.get(f'change_{mid_la}',0):<10.3f} "
              f"{t.get(f'outcome_{mid_la}','?'):<8} "
              f"{t['sl']:<10.5f} {tp_s:<10} {t.get('rr','-')}")

    print(f"\n{'='*110}")
    print("  FIN DU RAPPORT")
    print(f"{'='*110}\n")


# ===========================================================================
# Helpers
# ===========================================================================

def _convert_native(obj):
    if isinstance(obj, dict):
        return {k: _convert_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_native(v) for v in obj]
    if hasattr(obj, 'item'):
        return obj.item()
    return obj


def save_report(all_results: Dict[str, List[dict]], output_dir: str = "reports"):
    os.makedirs(output_dir, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_symbols": len(all_results),
        "total_signals": sum(len(v) for v in all_results.values()),
        "symbols": _convert_native(all_results),
    }
    fname = f"backtest_combined_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Rapport sauvegarde: {fpath}")


def resolve_symbols(mt5_symbols, watchlist):
    resolved = []
    for sym in watchlist:
        if sym in mt5_symbols:
            r = mt5_symbols[sym]
            resolved.append((sym, r.name if hasattr(r, 'name') else r))
        else:
            for k, v in mt5_symbols.items():
                if hasattr(v, 'name') and sym.upper() == k.upper().replace('.CASH', ''):
                    resolved.append((sym, v.name))
                    break
            else:
                print(f"  {sym}: NON DISPONIBLE")
    return resolved


def main():
    parser = ArgumentParser(description="Backtest combiné Ichimoku")
    parser.add_argument("--symbols", type=str, default=None)
    parser.add_argument("--timeframe", type=str, default="H4",
                        choices=["H4"], help="H4 uniquement pour le combine")
    parser.add_argument("--max-bars", type=int, default=5000)
    parser.add_argument("--output", type=str, default="reports")
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--tp-min-pct", type=float, default=0.3,
                        help="Distance min entree->TP en %% (defaut: 0.3)")
    parser.add_argument("--kijun-max-pct", type=float, default=0.3,
                        help="Distance max Kijun en %% (defaut: 0.3)")
    args = parser.parse_args()

    load_env()
    if not mt5.initialize():
        print("ERREUR: MT5")
        sys.exit(1)

    tf_cfg = TIMEFRAMES["H4"]
    lookaheads = tf_cfg["lookaheads"]
    la_display = tf_cfg["la_display"]

    mt5_symbols = {s.name: s for s in mt5.symbols_get()}
    for sym in list(mt5_symbols.keys()):
        if sym.endswith('.cash'):
            mt5_symbols[sym.replace('.cash', '')] = sym
        else:
            mt5_symbols[f'{sym}.cash'] = sym

    watchlist = ([s.strip() for s in args.symbols.split(",")]
                 if args.symbols else SYMBOLS)
    syms = resolve_symbols(mt5_symbols, watchlist)
    if not syms:
        print("Aucun symbole.")
        mt5.shutdown()
        return

    print("=" * 110)
    print(f"  BACKTEST COMBINÉ H4 — Scoring + Cloud+Chikou + SL/TP")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {len(syms)} symboles | Filtres: Score>80, Conf.ELEVEE, "
          f"Cloud+Chikou H4/D1/W1, Kijun<{args.kijun_max_pct}%")
    print(f"  SL=SSB H4 | TP=W1/D1 >{args.tp_min_pct}% | LONG only")
    print("=" * 110)

    all_results = {}
    total_drops = {}
    t0 = time.time()

    for display_name, mt5_name in syms:
        trades, drops = backtest_symbol(
            mt5_name, max_bars=args.max_bars, quiet=args.quiet,
            tp_min_pct=args.tp_min_pct, kijun_max_pct=args.kijun_max_pct)
        for k, v in drops.items():
            total_drops[k] = total_drops.get(k, 0) + v
        if trades:
            all_results[display_name] = trades

    elapsed = time.time() - t0
    total = sum(len(v) for v in all_results.values())
    print(f"\n  Backtest termine en {elapsed:.0f}s — "
          f"{total} trades sur {len(all_results)} symboles")
    if total_drops:
        print(f"  Filtres: score_conf={total_drops.get('score_conf',0)} "
              f"cloud_chikou={total_drops.get('cloud_chikou',0)} "
              f"chikou_mtf={total_drops.get('chikou_mtf',0)} "
              f"kijun_dist={total_drops.get('kijun_dist',0)}")

    if all_results:
        print_report(all_results, lookaheads, la_display)
        if not args.no_save:
            save_report(all_results, args.output)
    else:
        print("\n  Aucun trade genere.")
    mt5.shutdown()


if __name__ == "__main__":
    main()
