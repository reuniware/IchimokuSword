"""
backtest.py - Backtester du scoring Ichimoku Sword
===================================================

Valide le scoring Ichimoku sur historique D1 ou H4 :
- Pour chaque barre passee, calcule le score comme si on y etait
- Mesure ce qui s'est passe N barres plus tard
- Agrege les statistiques par bracket de score et de confiance

Usage:
    python backtest.py                          # Backtest D1 tous les actifs
    python backtest.py --timeframe H4           # Backtest H4 tous les actifs
    python backtest.py --symbols EURUSD         # Un seul actif
    python backtest.py --max-bars 500           # Limiter l'historique
    python backtest.py --output report          # Sauvegarder le rapport JSON
"""

import json
import os
import sys
import time
from argparse import ArgumentParser
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np

from src.config import load_env
from src.ichimoku import (
    compute_full_ichimoku,
    compute_single_tf_confidence,
    IchimokuResult,
    IchimokuConfidence,
)

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Timeframes disponibles
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

MIN_BARS = 53
SCORE_BRACKETS = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]
CONF_BRACKETS = ["FAIBLE", "PRUDENCE", "MOYENNE", "ELEVEE"]

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF",
    "EURJPY", "GBPJPY", "EURGBP", "AUDCAD", "EURCHF", "NZDJPY", "GBPCHF", "CHFJPY",
    "XAUUSD", "XAGUSD",
    "US30.cash", "US100.cash", "US500.cash",
    "GER40.cash", "UK100.cash", "FRA40.cash",
    "AUS200.cash", "HK50.cash",
]


# ---------------------------------------------------------------------------
# Scoring single-TF
# ---------------------------------------------------------------------------

def compute_backtest_score(result: IchimokuResult) -> int:
    """Score 0-100 pour une barre sur un seul timeframe."""
    score = 0

    if result.cloud:
        if result.cloud.above_cloud:
            ok = (result.cloud.cloud_color == "VERT") if result.above_kijun else (result.cloud.cloud_color == "ROUGE")
            score += 20 if ok else 12
        elif result.cloud.inside_cloud:
            score += 4
        elif result.cloud.below_cloud:
            ok = (result.cloud.cloud_color == "ROUGE") if not result.above_kijun else (result.cloud.cloud_color == "VERT")
            score += 16 if ok else 8
    else:
        score += 4

    if result.tk_cross:
        if result.tk_cross.cross_type == "TK_CROSS_HAUSSIER" and result.above_kijun:
            score += 15
        elif result.tk_cross.cross_type == "TK_CROSS_BAISSIER" and not result.above_kijun:
            score += 15
        elif result.tk_cross.current_position == "TENKAN_HAUT" and result.above_kijun:
            score += 8
        elif result.tk_cross.current_position == "KIJUN_HAUT" and not result.above_kijun:
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
        if v == 3:
            score += 20
        elif v == 2:
            score += 10
        elif v == 1:
            score += 4
    else:
        score += 2

    dist = result.distance_pct
    if dist < 0.1:
        score += 10
    elif dist < 0.3:
        score += 7
    elif dist < 0.5:
        score += 4
    elif dist < 1.0:
        score += 2

    if result.flat:
        if not result.flat.kijun_flat:
            score += 10
        elif result.flat.kijun_flat_bars < 10:
            score += 5
    else:
        score += 5

    if result.lagging_confirmation:
        if result.lagging_confirmation.power_confirmed:
            score += 10
        elif result.lagging_confirmation.confirmation_bullish or result.lagging_confirmation.confirmation_bearish:
            score += 5
    else:
        score += 3

    return min(score, 100)


# ---------------------------------------------------------------------------
# Backtest d'un symbole
# ---------------------------------------------------------------------------

def backtest_symbol(mt5_name: str, max_bars: int = 2000,
                    quiet: bool = False,
                    timeframe: str = "D1") -> List[dict]:
    """Backtest un symbole sur un timeframe donne."""
    tf_cfg = TIMEFRAMES[timeframe]
    lookaheads = tf_cfg["lookaheads"]
    tf_lbl = tf_cfg["label"]

    if not quiet:
        print(f"  {mt5_name} ({tf_lbl})... ", end="", flush=True)

    mt5.symbol_select(mt5_name, True)
    rates = mt5.copy_rates_from_pos(mt5_name, tf_cfg["mt5"], 0, max_bars)
    if rates is None or len(rates) < MIN_BARS:
        n = len(rates) if rates is not None else 0
        if not quiet:
            print(f"PAS ASSEZ DE DONNEES ({n} barres)")
        return []

    n = len(rates)
    results = []
    max_i = n - max(lookaheads) - 1

    for i in range(MIN_BARS - 1, max_i):
        highs = rates['high'][:i + 1]
        lows = rates['low'][:i + 1]
        closes = rates['close'][:i + 1]
        opens = rates['open'][:i + 1]
        price = float(closes[-1])

        result = compute_full_ichimoku(mt5_name, tf_lbl, price,
                                       highs, lows, closes, opens)
        if result is None:
            continue

        score = compute_backtest_score(result)
        conf = compute_single_tf_confidence(result)

        entry = {
            "bar_index": i,
            "date": datetime.fromtimestamp(int(rates['time'][i]), tz=UTC).strftime("%Y-%m-%d %H:%M"),
            "price": round(price, 5),
            "above_kijun": result.above_kijun,
            "distance_pct": round(result.distance_pct, 4),
            "score": score,
            "conf_score": conf.score,
            "conf_label": conf.label,
            "rules_validated": result.three_rules.rules_validated if result.three_rules else 0,
            "kijun_flat": result.flat.kijun_flat if result.flat else False,
            "cloud_above": result.cloud.above_cloud if result.cloud else False,
            "chikou_aligned": result.chikou.bullish_alignment if result.chikou else False,
            "lagging_confirmed": result.lagging_confirmation.power_confirmed if result.lagging_confirmation else False,
        }

        for la in lookaheads:
            if i + la < n:
                fp = float(rates['close'][i + la])
                change = (fp - price) / price * 100.0
                entry[f"change_{la}"] = round(change, 3)
                predicted_up = result.above_kijun
                actual_up = fp > price
                entry[f"win_{la}"] = 1 if predicted_up == actual_up else 0
                entry[f"mag_{la}"] = round(abs(change), 3)

        results.append(entry)

    if not quiet and results:
        la_mid = lookaheads[len(lookaheads)//2]
        wins = sum(1 for r in results if r.get(f"win_{la_mid}") == 1)
        print(f"{len(results)} trades, Win{la_mid}={wins/len(results)*100:.0f}%  "
              f"(deb:{results[0]['date']} fin:{results[-1]['date']})")
    elif not quiet:
        print("0 trades")

    return results


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BracketStats:
    bracket: str
    total_signals: int = 0
    wins: Dict[int, int] = field(default_factory=dict)
    total_magnitude: Dict[int, float] = field(default_factory=dict)
    avg_score: float = 0.0


@dataclass
class SymbolBacktest:
    symbol: str
    total_signals: int = 0
    date_start: str = ""
    date_end: str = ""
    win_rates: Dict[int, float] = field(default_factory=dict)
    avg_move: Dict[int, float] = field(default_factory=dict)
    avg_score: float = 0.0
    avg_conf: float = 0.0
    bracket_stats: Dict[str, BracketStats] = field(default_factory=dict)
    signals: List[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_results(all_results: Dict[str, List[dict]],
                      lookaheads: List[int]) -> Dict[str, SymbolBacktest]:
    analysis = {}
    for symbol, signals in all_results.items():
        if not signals:
            continue
        bt = SymbolBacktest(symbol=symbol)
        bt.signals = signals
        bt.total_signals = len(signals)
        bt.date_start = signals[0]["date"]
        bt.date_end = signals[-1]["date"]

        scores = [s["score"] for s in signals]
        confs = [s["conf_score"] for s in signals]
        bt.avg_score = sum(scores) / len(scores) if scores else 0
        bt.avg_conf = sum(confs) / len(confs) if confs else 0

        for la in lookaheads:
            wins = [s.get(f"win_{la}", 0) for s in signals]
            mags = [s.get(f"mag_{la}", 0.0) for s in signals]
            bt.win_rates[la] = sum(wins) / len(wins) * 100.0 if wins else 0
            bt.avg_move[la] = sum(mags) / len(mags) if mags else 0

        for lo, hi in SCORE_BRACKETS:
            bracket_signals = [s for s in signals if lo <= s["score"] < hi]
            if not bracket_signals:
                continue
            label = f"{lo}-{hi}"
            bs = BracketStats(bracket=label, total_signals=len(bracket_signals))
            bs.avg_score = sum(s["score"] for s in bracket_signals) / len(bracket_signals)
            for la in lookaheads:
                bs.wins[la] = sum(1 for s in bracket_signals if s.get(f"win_{la}") == 1)
                bs.total_magnitude[la] = sum(s.get(f"mag_{la}", 0.0) for s in bracket_signals)
            bt.bracket_stats[label] = bs

        analysis[symbol] = bt
    return analysis


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def print_report(analysis: Dict[str, SymbolBacktest],
                 lookaheads: List[int],
                 la_display: List[str]) -> None:
    """Affiche le rapport de backtest."""
    print(f"\n{'='*120}")
    print("  RAPPORT DE BACKTEST ICHIMOKU SWORD")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*120}")

    # Entetes dynamiques selon le timeframe
    h_cols = [f"Win{d}" for d in la_display]
    h_mag = [f"AvgMv{d}" for d in la_display]

    # --- Par symbole ---
    print(f"\n{'='*120}")
    print("  RESULTATS PAR SYMBOLE")
    print(f"{'='*120}")
    header = (f"  {'Symbole':<16} {'Trades':<8} {'Periode':<22} {'Score':<7} {'Conf.':<7} "
              + " ".join(f"{h:<7}" for h in h_cols) + " " + " ".join(f"{h:<9}" for h in [la_display[2]]))
    print(header)
    sep = "  " + "-"*16 + " " + "-"*8 + " " + "-"*22 + " " + "-"*7 + " " + "-"*7 + " "
    print(sep + " ".join("-"*7 for _ in h_cols) + " " + "-"*9)

    sorted_syms = sorted(analysis.values(),
                         key=lambda bt: bt.win_rates.get(lookaheads[2], 0), reverse=True)

    overall_wins = {la: [] for la in lookaheads}
    overall_scores = []

    for bt in sorted_syms:
        line = (f"  {bt.symbol:<16} {bt.total_signals:<8} "
                f"{bt.date_start[:10]}->{bt.date_end[:10]:<11} "
                f"{bt.avg_score:<7.1f} {bt.avg_conf:<7.1f} ")
        for la in lookaheads:
            line += f"{bt.win_rates.get(la, 0):<7.1f} "
        line += f"{bt.avg_move.get(lookaheads[2], 0):<9.3f}"
        print(line)
        for la in lookaheads:
            overall_wins[la].append(bt.win_rates.get(la, 0))
        overall_scores.append(bt.avg_score)

    # --- Globales ---
    print(f"\n{'='*120}")
    print("  STATISTIQUES GLOBALES")
    print(f"{'='*120}")
    total_trades = sum(bt.total_signals for bt in analysis.values())
    print(f"  Symboles  : {len(analysis)}")
    print(f"  Trades    : {total_trades}")
    if overall_scores:
        print(f"  Score moy : {sum(overall_scores)/len(overall_scores):.1f}")
    print()
    for la, ld in zip(lookaheads, la_display):
        w = overall_wins[la]
        if w:
            print(f"  Win rate {ld:<4}: {sum(w)/len(w):.1f}%  (min={min(w):.1f}%, max={max(w):.1f}%)")

    # Agregation tous signaux
    all_signals = []
    for bt in analysis.values():
        all_signals.extend(bt.signals)

    # --- Par bracket de score ---
    print(f"\n{'='*120}")
    print("  PERFORMANCE PAR BRACKET DE SCORE")
    print(f"{'='*120}")
    if all_signals:
        h2 = "".join(f"{'Win'+d:<8}" for d in la_display)
        print(f"  {'Bracket':<10} {'N':<8} {'Score':<7} {h2}")
        print(f"  {'-'*10} {'-'*8} {'-'*7} " + " ".join("-"*7 for _ in la_display))
        for lo, hi in SCORE_BRACKETS:
            b = [s for s in all_signals if lo <= s["score"] < hi]
            if not b:
                continue
            n = len(b)
            avg_s = sum(s["score"] for s in b) / n
            line = f"  {f'{lo}-{hi}':<10} {n:<8} {avg_s:<7.1f} "
            for la in lookaheads:
                w = sum(1 for s in b if s.get(f"win_{la}") == 1)
                line += f"{w/n*100:<8.1f} "
            print(line)

    # --- Par confiance ---
    print(f"\n{'='*120}")
    print("  PERFORMANCE PAR NIVEAU DE CONFIANCE")
    print(f"{'='*120}")
    if all_signals:
        h2 = "".join(f"{'Win'+d:<8}" for d in la_display)
        print(f"  {'Confiance':<12} {'N':<8} {'Score':<7} {h2}")
        print(f"  {'-'*12} {'-'*8} {'-'*7} " + " ".join("-"*7 for _ in la_display))
        for label in CONF_BRACKETS:
            b = [s for s in all_signals if s["conf_label"] == label]
            if not b:
                continue
            n = len(b)
            avg_s = sum(s["score"] for s in b) / n
            line = f"  {label:<12} {n:<8} {avg_s:<7.1f} "
            for la in lookaheads:
                w = sum(1 for s in b if s.get(f"win_{la}") == 1)
                line += f"{w/n*100:<8.1f} "
            print(line)

    # --- LONGS vs SHORTS ---
    mid_la = lookaheads[2]
    mid_disp = la_display[2]
    print(f"\n{'='*120}")
    print(f"  LONGS vs SHORTS - WIN RATE PAR BRACKET ({mid_disp})")
    print(f"{'='*120}")
    if all_signals:
        longs = [s for s in all_signals if s["above_kijun"]]
        shorts = [s for s in all_signals if not s["above_kijun"]]
        print(f"  Total: {len(longs)} LONGS ({len(longs)/len(all_signals)*100:.1f}%) / "
              f"{len(shorts)} SHORTS ({len(shorts)/len(all_signals)*100:.1f}%)")
        print()
        print(f"  {'Bracket':<10} {'Dir':<7} {'N':<8} {'Score':<7} "
              f"{'Win'+mid_disp:<10} {'Mag':<9}")
        print(f"  {'-'*10} {'-'*7} {'-'*8} {'-'*7} {'-'*10} {'-'*9}")
        for lo, hi in SCORE_BRACKETS:
            for direction, group, label in [
                ("LONG", longs, "L"),
                ("SHORT", shorts, "S"),
            ]:
                b = [s for s in group if lo <= s["score"] < hi]
                if not b:
                    continue
                n = len(b)
                avg_s = sum(s["score"] for s in b) / n
                wins = sum(1 for s in b if s.get(f"win_{mid_la}") == 1)
                mag = sum(s.get(f"mag_{mid_la}", 0) for s in b) / n
                print(f"  {f'{lo}-{hi}':<10} {label:<7} {n:<8} {avg_s:<7.1f} "
                      f"{wins/n*100:<10.1f} {mag:<9.3f}")
        # Difference line
        print(f"  {'-'*55}")
        for lo, hi in SCORE_BRACKETS:
            b_l = [s for s in longs if lo <= s["score"] < hi]
            b_s = [s for s in shorts if lo <= s["score"] < hi]
            if b_l and b_s:
                wl = sum(1 for s in b_l if s.get(f"win_{mid_la}") == 1) / len(b_l) * 100
                ws = sum(1 for s in b_s if s.get(f"win_{mid_la}") == 1) / len(b_s) * 100
                diff = wl - ws
                sign = "+" if diff > 0 else ""
                print(f"  {f'{lo}-{hi}':<10} {'DIFF':<7} {'':<8} {'':<7} "
                      f"{sign}{diff:<9.1f}% {'':<9}")

    # --- TOP 10 ---
    print(f"\n{'='*120}")
    print(f"  TOP 10 MEILLEURS SCORES - RESULTAT {mid_disp}")
    print(f"{'='*120}")
    if all_signals:
        top = sorted(all_signals, key=lambda s: s["score"], reverse=True)[:10]
        print(f"  {'Date':<12} {'Symbole':<16} {'Score':<6} {'Conf.':<8} {'Dir.':<6} "
              f"{'Change'+mid_disp:<10} {'Win':<5}")
        print(f"  {'-'*12} {'-'*16} {'-'*6} {'-'*8} {'-'*6} {'-'*10} {'-'*5}")
        for s in top:
            d = "LONG" if s["above_kijun"] else "SHORT"
            w = "OUI" if s.get(f"win_{mid_la}") == 1 else "NON"
            print(f"  {s['date'][:10]:<12} {s.get('symbol',''):<16} {s['score']:<6} "
                  f"{s['conf_score']}/{s['conf_label']:<5} {d:<6} "
                  f"{s.get(f'change_{mid_la}',0):<10.3f} {w:<5}")

    # --- BOTTOM 10 ---
    print(f"\n{'='*120}")
    print(f"  PIRE 10 SCORES - RESULTAT {mid_disp}")
    print(f"{'='*120}")
    if all_signals:
        bot = sorted(all_signals, key=lambda s: s["score"])[:10]
        print(f"  {'Date':<12} {'Symbole':<16} {'Score':<6} {'Conf.':<8} {'Dir.':<6} "
              f"{'Change'+mid_disp:<10} {'Win':<5}")
        print(f"  {'-'*12} {'-'*16} {'-'*6} {'-'*8} {'-'*6} {'-'*10} {'-'*5}")
        for s in bot:
            d = "LONG" if s["above_kijun"] else "SHORT"
            w = "OUI" if s.get(f"win_{mid_la}") == 1 else "NON"
            print(f"  {s['date'][:10]:<12} {s.get('symbol',''):<16} {s['score']:<6} "
                  f"{s['conf_score']}/{s['conf_label']:<5} {d:<6} "
                  f"{s.get(f'change_{mid_la}',0):<10.3f} {w:<5}")

    print(f"\n{'='*120}")
    print("  FIN DU RAPPORT")
    print(f"{'='*120}\n")


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


def save_report(analysis: Dict[str, SymbolBacktest],
                all_results: Dict[str, List[dict]],
                output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_symbols": len(analysis),
        "total_signals": sum(bt.total_signals for bt in analysis.values()),
        "symbols": {},
    }
    for sym, bt in analysis.items():
        d = asdict(bt)
        if len(d["signals"]) > 200:
            step = len(d["signals"]) // 200
            d["signals"] = d["signals"][::step]
        d = _convert_native(d)
        report["symbols"][sym] = d
    fname = f"backtest_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    fpath = os.path.join(output_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Rapport sauvegarde: {fpath}")
    return fpath


# ---------------------------------------------------------------------------
# Resolution symboles
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
    parser = ArgumentParser(description="Backtester Ichimoku Sword")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Symboles (separes par virgules)")
    parser.add_argument("--timeframe", type=str, default="D1",
                        choices=list(TIMEFRAMES.keys()),
                        help="Timeframe: D1 ou H4")
    parser.add_argument("--max-bars", type=int, default=None,
                        help="Max barres (defaut: selon timeframe)")
    parser.add_argument("--output", type=str, default="reports",
                        help="Dossier de sortie")
    parser.add_argument("--no-save", action="store_true",
                        help="Ne pas sauvegarder JSON")
    parser.add_argument("--quiet", action="store_true",
                        help="Mode silencieux")
    args = parser.parse_args()

    load_env()
    if not mt5.initialize():
        print("ERREUR: Impossible de se connecter a MT5")
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

    watchlist = [s.strip() for s in args.symbols.split(",")] if args.symbols else SYMBOLS
    symbols_to_test = resolve_symbols(mt5_symbols, watchlist)
    if not symbols_to_test:
        print("Aucun symbole disponible.")
        mt5.shutdown()
        return

    print("=" * 120)
    print(f"  BACKTEST ICHIMOKU SWORD - {tf_lbl}")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  {len(symbols_to_test)} symboles, max {max_bars} barres {tf_lbl}, "
          f"lookaheads={lookaheads}")
    print("=" * 120)

    all_results: Dict[str, List[dict]] = {}
    start_time = time.time()

    for display_name, mt5_name in symbols_to_test:
        signals = backtest_symbol(mt5_name, max_bars=max_bars,
                                  quiet=args.quiet,
                                  timeframe=args.timeframe)
        if signals:
            for s in signals:
                s["symbol"] = display_name
            all_results[display_name] = signals

    elapsed = time.time() - start_time
    total_signals = sum(len(v) for v in all_results.values())
    print(f"\n  Backtest termine en {elapsed:.0f}s - {total_signals} signaux "
          f"sur {len(all_results)} symboles")

    if all_results:
        analysis = aggregate_results(all_results, lookaheads)
        print_report(analysis, lookaheads, la_display)
        if not args.no_save:
            save_report(analysis, all_results, args.output)
    else:
        print("\n  Aucun signal genere.")

    mt5.shutdown()


if __name__ == "__main__":
    main()
