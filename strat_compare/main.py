# strat_compare/main.py — CLI de comparaison de strategies
# ======================================================================
# Usage:
#   python -m strat_compare.main compare
#   python -m strat_compare.main compare --ftmo --output results.csv
#
# Execute un backtest comparatif de 7 strategies sur la periode
# 01/01/2026 -> 03/07/2026.
# ======================================================================

import os
import sys
from datetime import datetime, timezone
from argparse import ArgumentParser
from typing import Dict, List, Optional

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
    account = mt5.account_info()
    print(f"MT5 connecte - login: {account.login}, broker: {account.company}")
    return True


def fetch_data(symbols: List[str], timeframes: Dict[str, int]
               ) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Recupere les donnees via copy_rates_range (precis, tous TFs).

    Retourne: {symbol: {tf_label: DataFrame}}
    """
    all_data: Dict[str, Dict[str, pd.DataFrame]] = {}

    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").replace(tzinfo=UTC)
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d").replace(tzinfo=UTC)

    n_success, n_skip = 0, 0

    for sym in symbols:
        all_data[sym] = {}
        for tf_label, tf_val in timeframes.items():
            # Selectionner le symbole
            if not mt5.symbol_select(sym, True):
                n_skip += 1
                continue

            # Fetch via copy_rates_range (precis, evite le probleme de
            # bar count insuffisant pour M1/M5)
            rates = mt5.copy_rates_range(sym, tf_val, start_dt, end_dt)

            if rates is None or len(rates) == 0:
                n_skip += 1
                continue

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)

            if len(df) < 30:
                n_skip += 1
                continue

            all_data[sym][tf_label] = df
            n_success += 1

    # Resume
    total_expected = len(symbols) * len(timeframes)
    print(f"  Data fetched: {n_success}/{total_expected} "
          f"({n_skip} skipped — symbole indisponible ou pas assez de barres)")

    return all_data


def run_all_strategies(data: Dict[str, Dict[str, pd.DataFrame]],
                       ftmo: bool = False,
                       ftmo_risk: float = 2.0
                       ) -> List[BacktestResult]:
    """Execute toutes les strategies sur toutes les paires (sym, tf)."""
    all_results: List[BacktestResult] = []

    total_combos = sum(len(tf_data) for tf_data in data.values()) * len(STRATEGIES)
    done = 0

    for sym, tf_data in data.items():
        for tf_label, df in tf_data.items():
            for strat_name, strat_cfg in STRATEGIES.items():
                signal_fn = SIGNAL_FUNCTIONS[strat_name]
                params = strat_cfg["params"].copy()

                try:
                    signals = signal_fn(df, **params)
                except Exception as e:
                    print(f"  ERREUR {strat_name}/{sym}/{tf_label}: {e}")
                    continue

                result = run_backtest(df, signals, sym, strat_name,
                                      ftmo_mode=ftmo,
                                      ftmo_risk_pct=ftmo_risk)
                result.timeframe = tf_label
                all_results.append(result)
                done += 1

    print(f"  Backtests executes: {done}/{total_combos}")
    return all_results


def print_comparison_table(results: List[BacktestResult],
                           symbols_used: List[str]) -> None:
    """Affiche un tableau comparatif trie par Sharpe ratio."""
    if not results:
        print("\nAucun resultat a afficher.")
        return

    sorted_results = sorted(results, key=lambda r: -r.sharpe)

    print(f"\n{'='*140}")
    print(f"  COMPARAISON DES STRATEGIES — {START_DATE} -> {END_DATE}")
    print(f"  Capital: ${INITIAL_CAPITAL:,.0f} | "
          f"Strategies: {len(STRATEGIES)} | "
          f"Symboles: {len(symbols_used)} | "
          f"Timeframes: {len(TIMEFRAMES)}")
    print(f"{'='*140}")
    print(f"{'#':<3} {'Strategie':<16} {'Symbole':<10} {'TF':<5} "
          f"{'Trades':>5} {'WR%':>6} {'Ret%':>8} {'CAGR%':>8} "
          f"{'Sharpe':>7} {'MaxDD%':>7} {'PF':>6} {'AvgW%':>7} {'AvgL%':>7}")
    print(f"{'-'*140}")

    for rank, r in enumerate(sorted_results, 1):
        if r.n_trades == 0:
            continue
        print(f"{rank:<3} {r.strategy:<16} {r.symbol:<10} {r.timeframe:<5} "
              f"{r.n_trades:>5} {r.win_rate:>5.1f}% {r.total_return:>7.2f}% "
              f"{r.cagr:>7.2f}% {r.sharpe:>6.2f} {r.max_dd:>6.1f}% "
              f"{r.profit_factor:>5.2f} {r.avg_win:>6.2f}% "
              f"{r.avg_loss:>6.2f}%")

    print(f"{'='*140}")

    # Synthese par strategie
    print(f"\n{'='*100}")
    print(f"  SYNTHESE PAR STRATEGIE (moyenne tous symboles/timeframes)")
    print(f"{'='*100}")
    print(f"{'Strategie':<16} {'#Tests':>6} {'Trades':>7} {'WR%':>7} "
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
        avg_pf = np.mean([r.profit_factor for r in valid
                          if r.profit_factor < 999])
        rows.append((name, n_tests, avg_trades, avg_wr, avg_ret,
                     avg_sharpe, avg_mdd, avg_pf))

    rows.sort(key=lambda x: -x[5])
    for name, nt, tr, wr, ret, sh, mdd, pf in rows:
        print(f"{name:<16} {nt:>6} {tr:>7.0f} {wr:>6.1f}% {ret:>7.2f}% "
              f"{sh:>6.2f} {mdd:>6.1f}% {pf:>5.2f}")

    # TOP 5
    print(f"\n{'='*120}")
    print(f"  TOP 5 MEILLEURES CONFIGURATIONS")
    print(f"{'='*120}")
    for rank, r in enumerate(sorted_results[:5], 1):
        if r.n_trades == 0:
            continue
        exits = {}
        for t in r.trades:
            exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
        exit_str = " / ".join(f"{k}={v}" for k, v in exits.items())
        print(f"\n  #{rank} : {r.strategy} / {r.symbol} / {r.timeframe}")
        print(f"  Trades={r.n_trades}  WR={r.win_rate:.1f}%  "
              f"Ret={r.total_return:.2f}%  CAGR={r.cagr:.2f}%")
        print(f"  Sharpe={r.sharpe:.2f}  Sortino={r.sortino:.2f}  "
              f"MaxDD={r.max_dd:.1f}%  PF={r.profit_factor:.2f}")
        print(f"  AvgW={r.avg_win:.2f}%  AvgL={r.avg_loss:.2f}%  "
              f"Sorties: {exit_str}")


def export_csv(results: List[BacktestResult], path: str) -> None:
    """Exporte les resultats en CSV."""
    rows = []
    for r in results:
        rows.append({
            "strategy": r.strategy,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "n_trades": r.n_trades,
            "win_rate": round(r.win_rate, 2),
            "total_return": round(r.total_return, 2),
            "cagr": round(r.cagr, 2),
            "sharpe": round(r.sharpe, 4),
            "sortino": round(r.sortino, 4),
            "max_dd": round(r.max_dd, 2),
            "profit_factor": round(r.profit_factor, 2),
            "avg_win": round(r.avg_win, 4),
            "avg_loss": round(r.avg_loss, 4),
            "final_capital": round(r.final_capital, 2),
        })
    df = pd.DataFrame(rows)
    df.sort_values("sharpe", ascending=False, inplace=True)
    df.to_csv(path, index=False)
    print(f"\nResultats exportes: {path} ({len(df)} lignes)")


def cmd_compare(ftmo: bool = False, ftmo_risk: float = 2.0,
                symbols: Optional[str] = None,
                timeframes: Optional[str] = None,
                output: Optional[str] = None) -> None:
    """Lance la comparaison de toutes les strategies."""
    if not connect_mt5():
        return

    mode_str = f" (FTMO risk={ftmo_risk}%)" if ftmo else ""
    syms = [s.strip() for s in symbols.split(",")] if symbols else SYMBOLS

    # Filtrer les timeframes si specifie
    if timeframes:
        tf_filter = [t.strip() for t in timeframes.split(",")]
        tfs = {k: v for k, v in TIMEFRAMES.items() if k in tf_filter}
    else:
        tfs = TIMEFRAMES

    print(f"\n{'='*80}")
    print(f"  STRATEGY COMPARISON{mode_str} — {START_DATE} -> {END_DATE}")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Symboles: {len(syms)} | Timeframes: {len(tfs)} "
          f"| Strategies: {len(STRATEGIES)}")
    print(f"  Total max: {len(syms) * len(tfs) * len(STRATEGIES)} backtests")
    print(f"{'='*80}\n")

    # 1. Fetch data
    print("--- FETCHING DATA ---")
    data = fetch_data(syms, tfs)

    if not data:
        print("ERREUR: Aucune donnee recuperee.")
        mt5.shutdown()
        return

    syms_ok = [s for s in syms if data.get(s)]
    print(f"  Symboles disponibles: {len(syms_ok)}/{len(syms)}")

    # 2. Run all strategies
    print(f"\n--- RUNNING {len(STRATEGIES)} STRATEGIES ---")
    results = run_all_strategies(data, ftmo=ftmo, ftmo_risk=ftmo_risk)

    # 3. Print comparison
    print_comparison_table(results, syms_ok)

    # 4. Export CSV
    if output:
        export_csv(results, output)

    mt5.shutdown()


def main():
    parser = ArgumentParser(
        description="Comparaison de strategies sur periode 01/01-03/07/2026"
    )
    sub = parser.add_subparsers(dest="command")

    p_comp = sub.add_parser("compare",
                            help="Lancer la comparaison de toutes les strategies")
    p_comp.add_argument("--ftmo", action="store_true",
                        help="Mode FTMO: position sizing risque%% + levier 1:30")
    p_comp.add_argument("--ftmo-risk", type=float, default=2.0,
                        help="%% risque par trade FTMO (defaut: 2.0)")
    p_comp.add_argument("--symbols", type=str, default=None,
                        help="Symboles (ex: EURUSD,XAUUSD) — defaut: tous FTMO")
    p_comp.add_argument("--tfs", type=str, default=None,
                        help="Timeframes (ex: H1,H4,D1) — defaut: M1,M5,M15,H1,H4,D1")
    p_comp.add_argument("--output", type=str, default=None,
                        help="Fichier CSV de sortie (ex: results.csv)")

    args = parser.parse_args()

    if args.command == "compare":
        cmd_compare(ftmo=args.ftmo, ftmo_risk=args.ftmo_risk,
                    symbols=args.symbols, timeframes=args.tfs,
                    output=args.output)
    else:
        cmd_compare()


if __name__ == "__main__":
    main()
