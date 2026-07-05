# turtle/metrics.py — Calcul des metriques de performance
# ======================================================================
# Calcule toutes les metriques demandees :
#   - CAGR, Sharpe, Sortino
#   - Max drawdown et duree
#   - Profit factor
#   - Win rate, ratio gain/perte moyen
#   - Distribution des rendements
# ======================================================================

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from turtle.engine import BacktestResult, Trade


def compute_all_metrics(result: BacktestResult) -> BacktestResult:
    """Calcule et remplit toutes les metriques dans un BacktestResult.

    Modifie le resultat en place ET le retourne.
    """
    trades = result.trades
    n = len(trades)

    if n == 0:
        result.total_return = 0.0
        result.n_trades = 0
        return result

    # -- Total return --
    result.total_return = (
        (result.final_capital - result.initial_capital)
        / result.initial_capital * 100
    )

    # -- CAGR (Compound Annual Growth Rate) --
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        days = (
            result.equity_curve.index[-1] - result.equity_curve.index[0]
        ).days
        years = max(days / 365.25, 0.01)
        result.cagr = (
            (result.final_capital / result.initial_capital) ** (1 / years) - 1
        ) * 100
    else:
        result.cagr = 0.0

    # -- Returns quotidiens (pour Sharpe, Sortino, DD) --
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        daily_returns = result.equity_curve.pct_change().dropna()
    else:
        daily_returns = pd.Series(dtype=float)

    # -- Sharpe ratio (annualise) --
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        result.sharpe = (
            daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        )
    else:
        result.sharpe = 0.0

    # -- Sortino ratio (annualise) --
    downside = daily_returns[daily_returns < 0]
    if len(downside) > 1 and downside.std() > 0:
        result.sortino = (
            daily_returns.mean() / downside.std() * np.sqrt(252)
        )
    else:
        result.sortino = 0.0

    # -- Max drawdown --
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        eq = result.equity_curve
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max * 100
        result.max_dd = drawdown.min()

        # Duree du drawdown (en jours)
        dd_start = None
        max_dd_duration = 0
        for i in range(len(drawdown)):
            if drawdown.iloc[i] < 0 and dd_start is None:
                dd_start = i
            elif drawdown.iloc[i] >= 0 and dd_start is not None:
                duration = i - dd_start
                max_dd_duration = max(max_dd_duration, duration)
                dd_start = None
        if dd_start is not None:
            duration = len(drawdown) - dd_start
            max_dd_duration = max(max_dd_duration, duration)
        result.max_dd_duration = max_dd_duration

    # -- Profit factor --
    gross_profit = sum(t.pnl_abs for t in trades if t.pnl_abs > 0)
    gross_loss = abs(sum(t.pnl_abs for t in trades if t.pnl_abs < 0))
    result.profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float('inf')
    )

    # -- Win rate --
    wins = [t for t in trades if t.pnl_pct > 0]
    result.win_rate = len(wins) / n * 100 if n > 0 else 0.0

    # -- Avg win / avg loss --
    win_pnls = [t.pnl_pct for t in trades if t.pnl_pct > 0]
    loss_pnls = [abs(t.pnl_pct) for t in trades if t.pnl_pct < 0]
    result.avg_win = np.mean(win_pnls) if win_pnls else 0.0
    result.avg_loss = np.mean(loss_pnls) if loss_pnls else 0.0

    result.n_trades = n
    return result


def compute_distribution(trades: List[Trade]) -> dict:
    """Analyse la distribution des rendements par trade."""
    pnls = [t.pnl_pct for t in trades]
    if not pnls:
        return {}

    return {
        "mean": np.mean(pnls),
        "median": np.median(pnls),
        "std": np.std(pnls),
        "skew": float(pd.Series(pnls).skew()),
        "kurtosis": float(pd.Series(pnls).kurtosis()),
        "min": np.min(pnls),
        "max": np.max(pnls),
        "p5": np.percentile(pnls, 5),
        "p25": np.percentile(pnls, 25),
        "p75": np.percentile(pnls, 75),
        "p95": np.percentile(pnls, 95),
    }


def metrics_summary(result: BacktestResult) -> str:
    """Genere un resume textuel des metriques."""
    trades = result.trades
    n = len(trades)
    if n == 0:
        return f"{result.strategy} / {result.symbol}: 0 trades"

    exits = {}
    for t in trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    exit_str = ", ".join(f"{k}={v}" for k, v in exits.items())

    lines = [
        f"{result.strategy:<20} {result.symbol:<12} "
        f"Trades={n:>4}  Win={result.win_rate:.1f}%  "
        f"CAGR={result.cagr:>6.1f}%  Sharpe={result.sharpe:.2f}  "
        f"MaxDD={result.max_dd:>5.1f}%  PF={result.profit_factor:.2f}",
        f"  AvgWin={result.avg_win:.2f}%  AvgLoss={result.avg_loss:.2f}%  "
        f"TotalRet={result.total_return:.1f}%  Sortino={result.sortino:.2f}  "
        f"Exits: {exit_str}",
    ]
    if result.max_dd_duration > 0:
        lines.append(f"  MaxDD duration: {result.max_dd_duration} jours")
    return "\n".join(lines)
