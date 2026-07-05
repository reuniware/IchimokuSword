# turtle/main.py — CLI pour le backtest comparatif Turtle
# ======================================================================
# Usage:
#   python -m turtle.main run                  # Backtest simple
#   python -m turtle.main grid                 # Grid search
#   python -m turtle.main compare              # Analyse comparative
#   python -m turtle.main test                 # Tests unitaires
# ======================================================================

import os
import sys
from argparse import ArgumentParser
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# Ajouter le projet parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from turtle.config import (
    SYMBOLS, TF_LABELS, TIMEFRAMES,
    TURTLE_ORIG_CONFIG, TURTLE_SOUP_CONFIG,
    INITIAL_CAPITAL, MARKET_REGIME, COSTS,
)

# Extraire uniquement les cles acceptees par chaque fonction de signaux
_TURTLE_ORIG_SIGNAL_KEYS = {'n1', 'n2', 'n_exit', 'atr_period', 'use_system2'}
_TURTLE_SOUP_SIGNAL_KEYS = {'n', 'min_ecart', 'atr_period', 'stop_buffer', 'take_profit_mode', 'rr_ratio'}
_TURTLE_ORIG_ENGINE_KEYS = {'pyramiding', 'max_units', 'pyramid_step_atr'}
from turtle.data_fetcher import fetch_all_symbols, connect_mt5, get_asset_class
from turtle.signals import (
    turtle_original_signals,
    turtle_soup_signals,
    compute_atr,
)
from turtle.engine import run_backtest, BacktestResult
from turtle.metrics import compute_all_metrics, metrics_summary, compute_distribution
from turtle.comparison import (
    compute_correlation,
    analyze_worst_periods,
    combined_portfolio,
)

UTC = timezone.utc


def cmd_run(args) -> None:
    """Execute un backtest simple sur les symboles/config par defaut."""
    if not connect_mt5():
        return

    symbols = args.symbols.split(",") if args.symbols else None
    timeframes = args.timeframes.split(",") if args.timeframes else ["H4", "D1"]

    print(f"\n{'='*90}")
    print(f"  TURTLE BACKTEST — {len(timeframes)} timeframes")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*90}\n")

    tf_list = [t.strip() for t in timeframes]
    data = fetch_all_symbols(symbols=symbols, timeframes=tf_list, min_bars=2500)

    all_orig: list = []
    all_soup: list = []

    for sym, tf_data in data.items():
        for tf_label, df in tf_data.items():
            # Turtle originale
            orig_kwargs = {k: v for k, v in TURTLE_ORIG_CONFIG.items()
                          if k in _TURTLE_ORIG_SIGNAL_KEYS}
            sigs_orig = turtle_original_signals(df, **orig_kwargs)

            eng_kwargs = {k: v for k, v in TURTLE_ORIG_CONFIG.items()
                         if k in _TURTLE_ORIG_ENGINE_KEYS}
            res_orig = run_backtest(df, sigs_orig, sym, "turtle_original",
                                    costs_enabled=args.costs, **eng_kwargs)
            compute_all_metrics(res_orig)
            res_orig.timeframe = tf_label
            all_orig.append(res_orig)

            # Turtle Soup
            soup_kwargs = {k: v for k, v in TURTLE_SOUP_CONFIG.items()
                          if k in _TURTLE_SOUP_SIGNAL_KEYS}
            sigs_soup = turtle_soup_signals(df, **soup_kwargs)
            res_soup = run_backtest(df, sigs_soup, sym, "turtle_soup",
                                    costs_enabled=args.costs)
            compute_all_metrics(res_soup)
            res_soup.timeframe = tf_label
            all_soup.append(res_soup)

    # --- Affichage ---
    print(f"\n{'='*90}")
    print(f"  TURTLE ORIGINALE")
    print(f"{'='*90}")
    for r in sorted(all_orig, key=lambda x: -x.sharpe):
        print(metrics_summary(r))

    print(f"\n{'='*90}")
    print(f"  TURTLE SOUP")
    print(f"{'='*90}")
    for r in sorted(all_soup, key=lambda x: -x.sharpe):
        print(metrics_summary(r))

    # Analyse comparative
    if args.compare and all_orig and all_soup:
        print(f"\n{'='*90}")
        print(f"  ANALYSE COMPARATIVE")
        print(f"{'='*90}")
        _print_comparison(all_orig, all_soup)

    import MetaTrader5 as mt5
    mt5.shutdown()


def cmd_compare(args) -> None:
    """Analyse comparative entre les deux strategies."""
    if not connect_mt5():
        return

    symbols = args.symbols.split(",") if args.symbols else list(
        next(iter(SYMBOLS.values()))
    )
    tf_list = ["D1"]

    data = fetch_all_symbols(symbols=symbols, timeframes=tf_list, min_bars=2500)

    all_orig = []
    all_soup = []

    for sym, tf_data in data.items():
        for tf_label, df in tf_data.items():
            orig_kwargs = {k: v for k, v in TURTLE_ORIG_CONFIG.items()
                          if k in _TURTLE_ORIG_SIGNAL_KEYS}
            sigs_orig = turtle_original_signals(df, **orig_kwargs)

            eng_kwargs = {k: v for k, v in TURTLE_ORIG_CONFIG.items()
                         if k in _TURTLE_ORIG_ENGINE_KEYS}
            res_orig = run_backtest(df, sigs_orig, sym, "turtle_original",
                                    **eng_kwargs)
            compute_all_metrics(res_orig)
            res_orig.timeframe = tf_label
            all_orig.append(res_orig)

            soup_kwargs = {k: v for k, v in TURTLE_SOUP_CONFIG.items()
                          if k in _TURTLE_SOUP_SIGNAL_KEYS}
            sigs_soup = turtle_soup_signals(df, **soup_kwargs)
            res_soup = run_backtest(df, sigs_soup, sym, "turtle_soup")
            compute_all_metrics(res_soup)
            res_soup.timeframe = tf_label
            all_soup.append(res_soup)

    _print_comparison(all_orig, all_soup)

    import MetaTrader5 as mt5
    mt5.shutdown()


def _print_comparison(all_orig: list, all_soup: list) -> None:
    """Affiche l'analyse comparative."""
    for r_o, r_s in zip(all_orig, all_soup):
        corr_daily = compute_correlation(r_o, r_s, 'D')
        corr_weekly = compute_correlation(r_o, r_s, 'W')

        print(f"\n  {r_o.symbol} ({r_o.timeframe}):")
        print(f"    Correlation quotidienne : r = {corr_daily:.3f}")
        print(f"    Correlation hebdomadaire: r = {corr_weekly:.3f}")

        worst = analyze_worst_periods(r_o, r_s, window_days=90, top_n=3)
        if worst:
            print(f"    Pires periodes Turtle Orig (90j) vs Soup :")
            for w in worst:
                sign = "+" if w['soup_pnl_pct'] > 0 else ""
                print(f"      {w['start_date']}->{w['end_date']}: "
                      f"Orig={w['orig_pnl_pct']:.1f}%  "
                      f"Soup={sign}{w['soup_pnl_pct']:.1f}%")

        combined_eq, _ = combined_portfolio(r_o, r_s)
        if len(combined_eq) > 0:
            combined_ret = (
                combined_eq.iloc[-1] / combined_eq.iloc[0] - 1
            ) * 100
            print(f"    Portefeuille combine (vol-inv): "
                  f"Return={combined_ret:.1f}%")


def main():
    parser = ArgumentParser(
        description="Backtest comparatif Turtle Originale vs Turtle Soup"
    )
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="Backtest simple")
    p_run.add_argument("--symbols", type=str, default=None)
    p_run.add_argument("--timeframes", type=str, default="H4,D1")
    p_run.add_argument("--costs", action="store_true", default=True)
    p_run.add_argument("--no-costs", dest="costs", action="store_false")
    p_run.add_argument("--compare", action="store_true")

    p_cmp = sub.add_parser("compare", help="Analyse comparative")
    p_cmp.add_argument("--symbols", type=str, default=None)

    p_test = sub.add_parser("test", help="Tests unitaires")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "test":
        from turtle.test_turtle import run_tests
        run_tests()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
