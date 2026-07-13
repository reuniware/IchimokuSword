"""
analyze_flat_lines.py — Analyse complete de TOUTES les lignes plates Ichimoku.

Detecte pour chaque symbole/timeframe :
  - Tenkan plate (actuelle + compteur de barres)
  - Kijun plate (actuelle + compteur de barres)
  - Senkou A plate (actuelle + periodes passees)
  - Senkou B plate (actuelle + periodes passees + SSB historiques)
  - Chikou passe plat
  - Nuage futur plat/fin
  - Cloud actuel fin

Usage:
    python analyze_flat_lines.py AUDUSD              # Un seul symbole
    python analyze_flat_lines.py AUDUSD --detail      # Avec details SSB
    python analyze_flat_lines.py GBPUSD,EURUSD,AUDUSD # Multi-symboles
"""

import argparse
import sys
from datetime import datetime, timezone

import numpy as np
import MetaTrader5 as mt5

from src.ichimoku import (
    detect_flat_line,
    detect_flat_bars,
    detect_ssb_flat_levels,
    compute_kijun_sen,
    compute_tenkan_sen,
    compute_senkou_span_a,
    compute_senkou_span_b,
)

# ─── ANSI ───────────────────────────────────────────────────────────────
_IS_TTY = sys.stdout.isatty()

def _c(code): return code if _IS_TTY else ""
BOLD = _c("\033[1m"); DIM = _c("\033[2m")
RED = _c("\033[31m"); GREEN = _c("\033[32m"); YELLOW = _c("\033[33m")
CYAN = _c("\033[36m"); MAGENTA = _c("\033[35m")
RESET = _c("\033[0m")

UTC = timezone.utc
TIMEFRAMES = {
    "H1": (mt5.TIMEFRAME_H1, 120),
    "H4": (mt5.TIMEFRAME_H4, 100),
    "D1": (mt5.TIMEFRAME_D1, 80),
    "W1": (mt5.TIMEFRAME_W1, 60),
}


def _fmt(v):
    if v is None: return "--"
    if v >= 1000: return f"{v:.2f}"
    if v >= 10: return f"{v:.4f}"
    return f"{v:.5f}"


def analyze_all_flat_lines(symbol, show_detail=False):
    """Analyse complete de toutes les lignes plates pour un symbole."""
    if not mt5.symbol_select(symbol, True):
        print(f"  {RED}{symbol}: symbole introuvable{RESET}")
        return

    tick = mt5.symbol_info_tick(symbol)
    price = float(tick.bid) if tick else 0
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  {symbol}  BID: {_fmt(price)}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")

    for tf_name, (tf_val, nb_bars) in TIMEFRAMES.items():
        rates = mt5.copy_rates_from_pos(symbol, tf_val, 0, nb_bars)
        if rates is None or len(rates) < 52:
            print(f"\n  {DIM}{tf_name}: donnees insuffisantes ({len(rates) if rates else 0} barres){RESET}")
            continue

        highs = np.array([float(r[2]) for r in rates])
        lows = np.array([float(r[3]) for r in rates])
        closes = np.array([float(r[4]) for r in rates])
        n = len(rates)
        close_price = float(closes[-1])

        # ── Valeurs actuelles ───────────────────────────────────
        kijun_val = compute_kijun_sen(highs, lows, 26)
        tenkan_val = compute_tenkan_sen(highs, lows, 9)
        senkou_a_val = compute_senkou_span_a(highs, lows, 9, 26, 26)
        senkou_b_val = compute_senkou_span_b(highs, lows, 52, 26)

        # ── Historiques pour flat detection ────────────────────
        kijun_hist = []
        tenkan_hist = []
        for i in range(26, n):
            k = (np.max(highs[i-25:i+1]) + np.min(lows[i-25:i+1])) / 2.0
            kijun_hist.append(float(k))
            t = (np.max(highs[i-8:i+1]) + np.min(lows[i-8:i+1])) / 2.0
            tenkan_hist.append(float(t))

        kijun_arr = np.array(kijun_hist)
        tenkan_arr = np.array(tenkan_hist)

        # ── Senkou A history ───────────────────────────────────
        senkou_a_hist = []
        for i in range(26, n):
            sa = (compute_tenkan_sen(highs[:i+1], lows[:i+1], 9) +
                  compute_kijun_sen(highs[:i+1], lows[:i+1], 26)) / 2.0
            if not np.isnan(sa):
                senkou_a_hist.append(float(sa))
        senkou_a_arr = np.array(senkou_a_hist) if senkou_a_hist else np.array([])

        # ── Senkou B history ───────────────────────────────────
        senkou_b_hist = []
        for i in range(52, n):
            sb = (np.max(highs[i-52:i]) + np.min(lows[i-52:i])) / 2.0
            senkou_b_hist.append(float(sb))
        senkou_b_arr = np.array(senkou_b_hist) if senkou_b_hist else np.array([])

        # ── Chikou passe ───────────────────────────────────────
        past_chikou = float(closes[-27]) if n >= 27 else 0
        chikou_hist = []
        for i in range(1, 8):
            idx = -(27 + i)
            if abs(idx) <= n:
                chikou_hist.append(float(closes[idx]))
        chikou_arr = np.array(chikou_hist)

        # ── FLAT DETECTION ─────────────────────────────────────
        kijun_flat = detect_flat_line(kijun_arr, 5, 0.05) if len(kijun_arr) >= 6 else False
        tenkan_flat = detect_flat_line(tenkan_arr, 5, 0.05) if len(tenkan_arr) >= 6 else False
        kijun_flat_bars = detect_flat_bars(kijun_arr, 0.05, 20) if len(kijun_arr) >= 3 else 0
        tenkan_flat_bars = detect_flat_bars(tenkan_arr, 0.05, 20) if len(tenkan_arr) >= 3 else 0
        senkou_a_flat = detect_flat_line(senkou_a_arr, 5, 0.05) if len(senkou_a_arr) >= 6 else False
        senkou_b_flat = detect_flat_line(senkou_b_arr, 5, 0.05) if len(senkou_b_arr) >= 6 else False
        senkou_a_flat_bars = detect_flat_bars(senkou_a_arr, 0.05, 20) if len(senkou_a_arr) >= 3 else 0
        senkou_b_flat_bars = detect_flat_bars(senkou_b_arr, 0.05, 20) if len(senkou_b_arr) >= 3 else 0

        # Chikou passe
        past_chikou_flat = detect_flat_line(chikou_arr, 5, 0.05) if len(chikou_arr) >= 5 else False

        # Nuage futur plat
        future_thickness = abs(senkou_a_val - senkou_b_val) if not np.isnan(senkou_a_val) and not np.isnan(senkou_b_val) else 0
        future_cloud_flat = (future_thickness / close_price * 100) < 0.05 if close_price > 0 and future_thickness > 0 else False

        # Nuage actuel fin
        cloud_thickness = future_thickness
        cloud_thin = (cloud_thickness / close_price * 100) < 0.1 if close_price > 0 and cloud_thickness > 0 else False

        # SSB historiques
        ssb_result = detect_ssb_flat_levels(highs, lows, close_price, 100, 3, 0.02)

        # ── AFFICHAGE ──────────────────────────────────────────
        print(f"\n  {BOLD}{tf_name}{RESET}  "
              f"T={_fmt(tenkan_val)} K={_fmt(kijun_val)} "
              f"SA={_fmt(senkou_a_val)} SB={_fmt(senkou_b_val)}")

        # Prix vs Kijun
        if not np.isnan(kijun_val):
            dist = (close_price - kijun_val) / kijun_val * 100
            side = "AU-DESSUS" if close_price > kijun_val else "EN-DESSOUS"
            print(f"    Prix vs Kijun: {dist:+.3f}% {side}")

        # ── Lignes plates ACTUELLES ────────────────────────────
        flat_parts = []
        if kijun_flat:
            flat_parts.append(f"{RED}KIJUN PLAT {kijun_flat_bars}B{RESET}")
        if tenkan_flat:
            flat_parts.append(f"{YELLOW}TENKAN PLAT {tenkan_flat_bars}B{RESET}")
        if senkou_a_flat:
            flat_parts.append(f"{MAGENTA}SENKOU A PLAT {senkou_a_flat_bars}B{RESET}")
        if senkou_b_flat:
            flat_parts.append(f"{MAGENTA}SENKOU B PLAT {senkou_b_flat_bars}B{RESET}")
        if past_chikou_flat:
            flat_parts.append(f"{DIM}CHIKOU PASSE PLAT{RESET}")
        if future_cloud_flat:
            flat_parts.append(f"{DIM}NUAGE FUTUR PLAT{RESET}")
        if cloud_thin:
            flat_parts.append(f"{DIM}NUAGE FIN{RESET}")

        if flat_parts:
            print(f"    LIGNES PLATES: {' | '.join(flat_parts)}")
        else:
            print(f"    {DIM}Aucune ligne plate active{RESET}")

        # ── SSB historiques ────────────────────────────────────
        if show_detail and ssb_result.levels:
            print(f"    SSB HISTORIQUES ({len(ssb_result.levels)} niveaux):")
            for lvl in ssb_result.levels[:5]:
                marker = " <<<" if lvl.price_distance_pct < 0.3 else ""
                print(f"      {lvl.level:.5f} ({lvl.bars_count}B) "
                      f"{lvl.position} dist={lvl.price_distance_pct:.3f}% age={lvl.age_bars}B{marker}")
            if len(ssb_result.levels) > 5:
                print(f"      ... et {len(ssb_result.levels) - 5} autres niveaux")

        # ── Résumé SSB proches ─────────────────────────────────
        if ssb_result.nearest_above:
            dist_pips = (ssb_result.nearest_above - close_price) * 10000
            print(f"    SSB resistance proche: {ssb_result.nearest_above:.5f} (+{dist_pips:.1f} pips)")
        if ssb_result.nearest_below:
            dist_pips = (close_price - ssb_result.nearest_below) * 10000
            print(f"    SSB support proche:    {ssb_result.nearest_below:.5f} (-{dist_pips:.1f} pips)")


def main():
    parser = argparse.ArgumentParser(description="Analyse complete des lignes plates Ichimoku")
    parser.add_argument("symbols", help="Symboles separes par des virgules (ex: AUDUSD,GBPUSD)")
    parser.add_argument("--detail", action="store_true", help="Afficher le detail des niveaux SSB")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    if not mt5.initialize():
        print(f"{RED}[ERREUR] Connexion MT5 impossible.{RESET}")
        return 1

    print(f"\n{BOLD}Analyse complete des lignes plates Ichimoku{RESET}")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Symboles: {', '.join(symbols)}")
    print(f"  Timeframes: {' '.join(TIMEFRAMES.keys())}")
    print(f"  Detection: Tenkan, Kijun, Senkou A, Senkou B, Chikou, Nuage, SSB")

    for sym in symbols:
        try:
            analyze_all_flat_lines(sym, show_detail=args.detail)
        except Exception as e:
            print(f"  {RED}{sym}: ERREUR {e}{RESET}")

    mt5.shutdown()
    print(f"\n{BOLD}{'='*70}{RESET}\n")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
