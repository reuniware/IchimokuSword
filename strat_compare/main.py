# strat_compare/main.py — CLI de comparaison de strategies
# ======================================================================
# Usage:
#   python -m strat_compare.main compare
#
# Execute un backtest comparatif de 7 strategies sur la periode
# 01/01/2026 -> 03/07/2026. Toutes les strategies tournent sur les
# memes donnees pour une comparaison equitable.
# ======================================================================

import os
import sys
from datetime import datetime, timezone
from argparse import ArgumentParser
from typing import Dict, List

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

from strat_compare.config import (
    START_DATE, END_DATE, TIMEFRAMES, SYMBOLS,
    INITIAL_CAPITAL, STRATEGIES,
)
from strat_compare.signals import SIGNAL_FUNCTIONS
from strat_compare.engine import run_backtest, result_summary, BacktestResult

UTC = timezone.utc


def connect_mt5() -> bool:
    """Connexion MT5."""
    load_env()
    if not mt5.initialize():
        print("ERREUR: Impossible de se connecter a MT5")
        return False
    print(f"MT5 connecte - login: {mt5.account_info().login}")
    return True


def fetch_data(symbols: List[str], timeframes: Dict[str, int],
               min_bars: int = 5000) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Recupere les donnees et les filtre a la periode cible.

    Retourne: {symbol: {tf_label: DataFrame}}
    """
    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}

    start_dt = pd.Timestamp(START_DATE, tz='UTC')
    end_dt = pd.Timestamp(END_DATE, tz='UTC')

    for sym in symbols:
        all_data[sym] = {}
        for tf_label, tf_val in timeframes.items():
            mt5.symbol_select(sym, True)
            rates = mt5.copy_rates_from_pos(sym, tf_val, 0, min_bars)

            if rates is None or len(rates) == 0:
                print(f"  {sym:<10} {tf_label:<4} — PAS DE DONNEES")
                continue

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)

            # Filtrer a la periode
            mask = (df.index >= start_dt) & (df.index <= end_dt)
            df_filtered = df.loc[mask].copy()

            if len(df_filtered) < 30:
                print(f"  {sym:<10} {tf_label:<4} — {len(df_filtered)} barres "
                      f"(insuffisant, skip)")
                continue

            all_data[sym][tf_label] = df_filtered
            print(f"  {sym:<10} {tf_label:<4} — {len(df_filtered):>5} barres "
                  f"({df_filtered.index[0].strftime('%Y-%m-%d')} -> "
                  f"{df_filtered.index[-1].strftime('%Y-%m-%d')})")

    return all_data


def run_all_strategies(data: Dict[str, Dict[str, pd.DataFrame]],
                       ftmo: bool = False,
                       ftmo_risk: float = 2.0
                       ) -> List[BacktestResult]:
    """Execute toutes les strategies sur toutes les paires (sym, tf)."""
    all_results: List[BacktestResult] = []

    for sym, tf_data in data.items():
        for tf_label, df in tf_data.items():
            for strat_name, strat_cfg in STRATEGIES.items():
                signal_fn = SIGNAL_FUNCTIONS[strat_name]
                params = strat_cfg["params"].copy()

                # Generer signaux
                try:
                    signals = signal_fn(df, **params)
                except Exception as e:
                    print(f"  ERREUR {strat_name}/{sym}/{tf_label}: {e}")
                    continue

                # Backtest
                result = run_backtest(df, signals, sym, strat_name,
                                      ftmo_mode=ftmo,
                                      ftmo_risk_pct=ftmo_risk)
                result.timeframe = tf_label
                all_results.append(result)

    return all_results


def print_comparison_table(results: List[BacktestResult]) -> None:
    """Affiche un tableau comparatif trie par Sharpe ratio."""
    if not results:
        print("\nAucun resultat a afficher.")
        return

    # Trier par Sharpe descendant
    sorted_results = sorted(results, key=lambda r: -r.sharpe)

    # En-tete
    print(f"\n{'='*130}")
    print(f"  COMPARAISON DES STRATEGIES — {START_DATE} -> {END_DATE}")
    print(f"  Capital initial: ${INITIAL_CAPITAL:,.0f} | "
          f"Strategies testees: {len(STRATEGIES)} | "
          f"Symboles: {', '.join(SYMBOLS)}")
    print(f"{'='*130}")
    print(f"{'#':<3} {'Strategie':<16} {'Symbole':<10} {'TF':<5} "
          f"{'Trades':>5} {'WinRate':>7} {'Ret%':>8} {'CAGR%':>8} "
          f"{'Sharpe':>7} {'MaxDD%':>7} {'PF':>6} {'AvgW%':>7} {'AvgL%':>7} "
          f"{'Sorties'}")
    print(f"{'-'*130}")

    for rank, r in enumerate(sorted_results, 1):
        if r.n_trades == 0:
            continue
        exits = {}
        for t in r.trades:
            exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
        exit_str = "/".join(f"{k}={v}" for k, v in exits.items())

        print(f"{rank:<3} {r.strategy:<16} {r.symbol:<10} {r.timeframe:<5} "
              f"{r.n_trades:>5} {r.win_rate:>6.1f}% {r.total_return:>7.2f}% "
              f"{r.cagr:>7.2f}% {r.sharpe:>6.2f} {r.max_dd:>6.1f}% "
              f"{r.profit_factor:>5.2f} {r.avg_win:>6.2f}% "
              f"{r.avg_loss:>6.2f}% [{exit_str}]")

    print(f"{'='*130}")

    # --- Synthese par strategie (moyenne sur tous les symboles/TF) ---
    print(f"\n{'='*130}")
    print(f"  SYNTHESE PAR STRATEGIE (moyenne sur tous les symboles/timeframes)")
    print(f"{'='*130}")
    print(f"{'Strategie':<16} {'#Tests':>6} {'Trades':>7} {'WinRate':>8} "
          f"{'Ret%':>8} {'Sharpe':>7} {'MaxDD%':>7} {'PF':>6}")

    strat_summary: Dict[str, List[BacktestResult]] = {}
    for r in results:
        strat_summary.setdefault(r.strategy, []).append(r)

    rows = []
    for name, res_list in strat_summary.items():
        valid = [r for r in res_list if r.n_trades > 0]
        if not valid:
            rows.append((name, len(res_list), 0, 0, 0, 0, 0, 0))
            continue
        n_tests = len(res_list)
        avg_trades = np.mean([r.n_trades for r in valid])
        avg_wr = np.mean([r.win_rate for r in valid])
        avg_ret = np.mean([r.total_return for r in valid])
        avg_sharpe = np.mean([r.sharpe for r in valid])
        avg_mdd = np.mean([r.max_dd for r in valid])
        avg_pf = np.mean([r.profit_factor for r in valid if r.profit_factor < 999])
        rows.append((name, n_tests, avg_trades, avg_wr, avg_ret,
                     avg_sharpe, avg_mdd, avg_pf))

    rows.sort(key=lambda x: -x[5])  # trier par Sharpe

    for name, nt, tr, wr, ret, sh, mdd, pf in rows:
        print(f"{name:<16} {nt:>6} {tr:>7.0f} {wr:>7.1f}% {ret:>7.2f}% "
              f"{sh:>6.2f} {mdd:>6.1f}% {pf:>5.2f}")

    # --- TOP 3 ---
    print(f"\n{'='*80}")
    print(f"  TOP 3 MEILLEURES CONFIGURATIONS")
    print(f"{'='*80}")
    for rank, r in enumerate(sorted_results[:3], 1):
        exits = {}
        for t in r.trades:
            exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
        print(f"\n  #{rank} : {r.strategy} / {r.symbol} / {r.timeframe}")
        print(f"  {STRATEGIES[r.strategy]['desc']}")
        print(f"  Trades={r.n_trades}  WinRate={r.win_rate:.1f}%  "
              f"Return={r.total_return:.2f}%  CAGR={r.cagr:.2f}%")
        print(f"  Sharpe={r.sharpe:.2f}  Sortino={r.sortino:.2f}  "
              f"MaxDD={r.max_dd:.1f}%  PF={r.profit_factor:.2f}")
        print(f"  AvgWin={r.avg_win:.2f}%  AvgLoss={r.avg_loss:.2f}%  "
              f"Sorties: {' / '.join(f'{k}={v}' for k,v in exits.items())}")

        # Pires trades
        sorted_trades = sorted(r.trades, key=lambda t: t.pnl_pct)
        print(f"  Pire trade: {sorted_trades[0].pnl_pct:.2f}% "
              f"({sorted_trades[0].exit_reason})  "
              f"Meilleur trade: {sorted_trades[-1].pnl_pct:.2f}% "
              f"({sorted_trades[-1].exit_reason})")


def cmd_compare(ftmo: bool = False, ftmo_risk: float = 2.0,
                symbols: str = None) -> None:
    """Lance la comparaison de toutes les strategies."""
    if not connect_mt5():
        return

    mode_str = f" (FTMO risk={ftmo_risk}%)" if ftmo else ""
    syms = symbols.split(",") if symbols else SYMBOLS

    print(f"\n{'='*80}")
    print(f"  STRATEGY COMPARISON{mode_str} — {START_DATE} -> {END_DATE}")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*80}\n")

    # 1. Fetch data
    print("--- FETCHING DATA ---")
    data = fetch_data(syms, TIMEFRAMES, min_bars=5000)

    if not data:
        print("ERREUR: Aucune donnee recuperee.")
        mt5.shutdown()
        return

    # 2. Run all strategies
    print(f"\n--- RUNNING {len(STRATEGIES)} STRATEGIES ---")
    results = run_all_strategies(data, ftmo=ftmo, ftmo_risk=ftmo_risk)
    print(f"  Total: {len(results)} backtests executes")

    # 3. Print comparison
    print_comparison_table(results)

    # 4. Detailed trades for top strategies
    print(f"\n{'='*80}")
    print(f"  DETAILS DES TRADES — TOP 3")
    print(f"{'='*80}")
    sorted_results = sorted(results, key=lambda r: -r.sharpe)
    for r in sorted_results[:3]:
        if r.n_trades == 0:
            continue
        print(f"\n  [{r.strategy}] {r.symbol} {r.timeframe} "
              f"({r.n_trades} trades)")
        print(f"  {'Time':<20} {'Dir':<6} {'Entry':>10} {'Exit':>10} "
              f"{'PnL%':>8} {'PnL$':>10} {'Reason':<8}")
        print(f"  {'-'*72}")
        for t in r.trades:
            print(f"  {str(t.entry_time)[:19]:<20} {t.direction:<6} "
                  f"{t.entry_price:>10.5f} {t.exit_price:>10.5f} "
                  f"{t.pnl_pct:>7.2f}% {t.pnl_abs:>9.2f}$ "
                  f"{t.exit_reason:<8}")

    mt5.shutdown()


def main():
    parser = ArgumentParser(
        description="Comparaison de strategies sur periode 01/01-03/07/2026"
    )
    sub = parser.add_subparsers(dest="command")

    p_comp = sub.add_parser("compare",
                            help="Lancer la comparaison de toutes les strategies")
    p_comp.add_argument("--ftmo", action="store_true",
                        help="Mode FTMO: position sizing risque% + levier 1:30")
    p_comp.add_argument("--ftmo-risk", type=float, default=2.0,
                        help="% risque par trade FTMO (defaut: 2.0)")
    p_comp.add_argument("--symbols", type=str, default=None,
                        help="Symboles (ex: EURUSD,XAUUSD)")

    args = parser.parse_args()

    if args.command == "compare":
        cmd_compare(ftmo=args.ftmo, ftmo_risk=args.ftmo_risk,
                    symbols=args.symbols)
    else:
        cmd_compare()


if __name__ == "__main__":
    main()
