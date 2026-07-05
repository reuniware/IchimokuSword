# strat_compare/engine.py — Moteur de backtesting leger
# ======================================================================
# Moteur commun pour toutes les strategies :
#   - Une position a la fois (pas de pyramiding)
#   - SL et TP geres
#   - Couts de transaction
#   - Equity curve
# ======================================================================

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from strat_compare.config import INITIAL_CAPITAL, COSTS


@dataclass
class Trade:
    """Un trade complet (entree -> sortie)."""
    direction: str          # 'LONG' ou 'SHORT'
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_abs: float
    exit_reason: str        # 'stop', 'tp', 'signal', 'end'
    costs_pct: float


@dataclass
class BacktestResult:
    """Resultats complets d'un backtest."""
    strategy: str
    symbol: str
    timeframe: str
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = None
    initial_capital: float = INITIAL_CAPITAL
    final_capital: float = INITIAL_CAPITAL

    # Metriques
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_dd: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    n_trades: int = 0


def _apply_costs(price: float, symbol: str, direction: str, is_entry: bool) -> float:
    """Applique les couts de transaction.

    LONG  : entry = achat (ask = price + costs), exit = vente (bid = price - costs)
    SHORT : entry = vente (bid = price - costs), exit = achat (ask = price + costs)
    """
    costs = COSTS.get(symbol, COSTS["EURUSD"])
    total_pct = (costs["spread_pct"] + costs["slippage_pct"]) / 100.0
    # Achat = price * (1 + total_pct), Vente = price * (1 - total_pct)
    is_buy = (direction == 'LONG' and is_entry) or (direction == 'SHORT' and not is_entry)
    return price * (1 + total_pct) if is_buy else price * (1 - total_pct)


def compute_metrics(result: BacktestResult) -> BacktestResult:
    """Calcule et remplit toutes les metriques."""
    trades = result.trades
    n = len(trades)

    if n == 0:
        return result

    result.total_return = (
        (result.final_capital - result.initial_capital)
        / result.initial_capital * 100
    )
    result.n_trades = n

    # CAGR
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        days = (result.equity_curve.index[-1] -
                result.equity_curve.index[0]).days
        years = max(days / 365.25, 0.01)
        result.cagr = (
            (result.final_capital / result.initial_capital) ** (1 / years) - 1
        ) * 100

    # Daily returns
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        daily = result.equity_curve.resample('D').last().dropna()
        daily_returns = daily.pct_change().dropna()
    else:
        daily_returns = pd.Series(dtype=float)

    # Sharpe
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        result.sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)

    # Sortino
    downside = daily_returns[daily_returns < 0]
    if len(downside) > 1 and downside.std() > 0:
        result.sortino = daily_returns.mean() / downside.std() * np.sqrt(252)

    # Max Drawdown
    if result.equity_curve is not None and len(result.equity_curve) > 1:
        eq = result.equity_curve
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max * 100
        result.max_dd = drawdown.min()

    # Profit Factor
    gross_profit = sum(t.pnl_abs for t in trades if t.pnl_abs > 0)
    gross_loss = abs(sum(t.pnl_abs for t in trades if t.pnl_abs < 0))
    result.profit_factor = (
        gross_profit / gross_loss if gross_loss > 0 else float('inf')
    )

    # Win Rate
    wins = [t for t in trades if t.pnl_pct > 0]
    result.win_rate = len(wins) / n * 100 if n > 0 else 0

    # Avg Win / Loss
    win_pnls = [t.pnl_pct for t in trades if t.pnl_pct > 0]
    loss_pnls = [abs(t.pnl_pct) for t in trades if t.pnl_pct < 0]
    result.avg_win = np.mean(win_pnls) if win_pnls else 0
    result.avg_loss = np.mean(loss_pnls) if loss_pnls else 0

    return result


def run_backtest(df: pd.DataFrame, signals: pd.DataFrame,
                 symbol: str, strategy: str,
                 ftmo_mode: bool = False,
                 ftmo_risk_pct: float = 2.0,
                 ftmo_daily_loss_limit: float = 485.0) -> BacktestResult:
    """Execute un backtest sur les signaux generes.

    Args:
        df: DataFrame OHLCV original
        signals: DataFrame avec entry_signal, sl_price, tp_price
        symbol: Nom du symbole MT5
        strategy: Nom de la strategie
        ftmo_mode: Si True, position sizing FTMO (risque% du capital,
                   position calculee a partir de la distance du SL,
                   cap levier 1:30)
        ftmo_risk_pct: % du capital risque par trade (defaut 2.0)
        ftmo_daily_loss_limit: Perte max par jour en $ (defaut 485, marge 3%)

    Returns:
        BacktestResult avec tous les trades et metriques.
    """
    capital = INITIAL_CAPITAL
    max_leverage = 30
    equity = [capital]
    equity_dates = [signals.index[0]]

    trades: List[Trade] = []
    position = None
    # FTMO daily tracking
    daily_pnl = 0.0
    current_day = None
    days_lost = 0  # nombre de jours ou la limite a ete atteinte
    daily_limit_hit = False  # evite d'incrementer days_lost plusieurs fois le meme jour

    close = df['close']
    high = df['high']
    low = df['low']

    for i in range(1, len(signals)):
        current_time = signals.index[i]
        curr_high = high.iloc[i]
        curr_low = low.iloc[i]
        curr_close = close.iloc[i]

        # --- Reset quotidien si nouveau jour ---
        bar_day = current_time.date() if hasattr(current_time, 'date') else current_time
        if current_day is not None and bar_day != current_day:
            daily_pnl = 0.0
            daily_limit_hit = False
        current_day = bar_day

        # --- Si en position, verifier sorties ---
        if position is not None:
            exit_now = False
            exit_price = curr_close
            exit_reason = "signal"

            # Stop-loss
            if position['direction'] == 'LONG':
                if curr_low <= position['sl']:
                    exit_now = True
                    exit_price = position['sl']
                    exit_reason = "stop"
            else:
                if curr_high >= position['sl']:
                    exit_now = True
                    exit_price = position['sl']
                    exit_reason = "stop"

            # Take-profit
            if not exit_now and position['tp'] > 0:
                if position['direction'] == 'LONG' and curr_high >= position['tp']:
                    exit_now = True
                    exit_price = position['tp']
                    exit_reason = "tp"
                elif position['direction'] == 'SHORT' and curr_low <= position['tp']:
                    exit_now = True
                    exit_price = position['tp']
                    exit_reason = "tp"

            # Signal oppose
            if not exit_now:
                sig = signals['entry_signal'].iloc[i]
                if (position['direction'] == 'LONG' and sig == 'SHORT') or \
                   (position['direction'] == 'SHORT' and sig == 'LONG'):
                    exit_now = True
                    exit_reason = "signal"

            if exit_now:
                exit_price_cost = _apply_costs(exit_price, symbol, position['direction'], False)

                pnl_pct = (exit_price_cost / position['entry_price'] - 1) * 100
                if position['direction'] == 'SHORT':
                    pnl_pct = -pnl_pct

                if ftmo_mode and 'position_value' in position:
                    # FTMO: PnL base sur la taille de position, pas tout le capital
                    pnl_abs = position['position_value'] * (pnl_pct / 100)
                else:
                    pnl_abs = capital * (pnl_pct / 100)
                capital += pnl_abs

                # FTMO daily tracking
                if ftmo_mode:
                    daily_pnl += pnl_abs
                    if daily_pnl <= -ftmo_daily_loss_limit and not daily_limit_hit:
                        days_lost += 1
                        daily_limit_hit = True

                entry_cost_pct = abs(
                    (_apply_costs(position['entry_price_raw'], symbol, position['direction'], True)
                     - position['entry_price_raw'])
                    / position['entry_price_raw'] * 100
                )
                exit_cost_pct = abs(
                    (_apply_costs(exit_price, symbol, position['direction'], False) - exit_price)
                    / exit_price * 100
                )

                trades.append(Trade(
                    direction=position['direction'],
                    entry_time=position['entry_time'],
                    exit_time=current_time,
                    entry_price=position['entry_price'],
                    exit_price=exit_price_cost,
                    pnl_pct=round(pnl_pct, 4),
                    pnl_abs=round(pnl_abs, 2),
                    exit_reason=exit_reason,
                    costs_pct=round(entry_cost_pct + exit_cost_pct, 4),
                ))
                position = None

        # --- FTMO: skip si la limite quotidienne est deja atteinte ---
        if ftmo_mode and daily_pnl <= -ftmo_daily_loss_limit:
            equity.append(capital)
            equity_dates.append(current_time)
            continue

        # --- Verifier signal d'entree ---
        if position is None:
            sig = signals['entry_signal'].iloc[i]
            if sig in ('LONG', 'SHORT'):
                sl = signals['sl_price'].iloc[i]
                tp = signals['tp_price'].iloc[i]

                if pd.isna(sl):
                    continue

                entry_price_raw = curr_close
                entry_price_cost = _apply_costs(curr_close, symbol, sig, True)

                pos_data = {
                    'direction': sig,
                    'entry_time': current_time,
                    'entry_price': entry_price_cost,
                    'entry_price_raw': entry_price_raw,
                    'sl': sl,
                    'tp': tp if not pd.isna(tp) and tp > 0 else 0,
                }

                if ftmo_mode:
                    # Position sizing FTMO
                    sl_dist_pct = abs(sl - entry_price_cost) / entry_price_cost * 100
                    safe_sl = max(sl_dist_pct, 0.01)  # eviter division par zero
                    risk_amount = capital * ftmo_risk_pct / 100.0
                    # Cap au daily loss restant
                    remaining = ftmo_daily_loss_limit + daily_pnl
                    if remaining <= 0:
                        continue  # skip, limite deja atteinte
                    risk_amount = min(risk_amount, remaining)
                    position_value = risk_amount / (safe_sl / 100.0)
                    max_position = capital * max_leverage
                    position_value = min(position_value, max_position)
                    pos_data['position_value'] = position_value

                position = pos_data

        # --- Equity ---
        equity.append(capital)
        equity_dates.append(current_time)

    # Cloture forcee en fin de backtest
    if position is not None:
        last_close = close.iloc[-1]
        exit_price_cost = _apply_costs(last_close, symbol, position['direction'], False)
        pnl_pct = (exit_price_cost / position['entry_price'] - 1) * 100
        if position['direction'] == 'SHORT':
            pnl_pct = -pnl_pct
        if ftmo_mode and 'position_value' in position:
            pnl_abs = position['position_value'] * (pnl_pct / 100)
        else:
            pnl_abs = capital * (pnl_pct / 100)
        capital += pnl_abs
        trades.append(Trade(
            direction=position['direction'],
            entry_time=position['entry_time'],
            exit_time=signals.index[-1],
            entry_price=position['entry_price'],
            exit_price=exit_price_cost,
            pnl_pct=round(pnl_pct, 4),
            pnl_abs=round(pnl_abs, 2),
            exit_reason="end",
            costs_pct=0,
        ))

    result = BacktestResult(
        strategy=strategy,
        symbol=symbol,
        timeframe="unknown",
        trades=trades,
        equity_curve=pd.Series(equity, index=equity_dates),
        final_capital=capital,
    )
    result = compute_metrics(result)
    if ftmo_mode:
        result.max_dd = min(result.max_dd, 0)  # garder la metrique
        # Stocker days_lost dans un attribut custom (pas dans le dataclass)
        result.ftmo_days_lost = days_lost  # type: ignore
    return result


def result_summary(result: BacktestResult) -> str:
    """Resume textuel d'un BacktestResult."""
    n = result.n_trades
    if n == 0:
        return (f"{result.strategy:<16} {result.symbol:<10} "
                f"{result.timeframe:<5}  0 trades  --")

    exits = {}
    for t in result.trades:
        exits[t.exit_reason] = exits.get(t.exit_reason, 0) + 1
    exit_str = "/".join(f"{k}={v}" for k, v in exits.items())

    return (
        f"{result.strategy:<16} {result.symbol:<10} {result.timeframe:<5} "
        f"{n:>4}t  WR={result.win_rate:>5.1f}%  "
        f"Ret={result.total_return:>7.2f}%  "
        f"CAGR={result.cagr:>7.2f}%  "
        f"Sharpe={result.sharpe:>6.2f}  "
        f"MaxDD={result.max_dd:>6.1f}%  "
        f"PF={result.profit_factor:>5.2f}  "
        f"AvgW={result.avg_win:>5.2f}%  AvgL={result.avg_loss:>5.2f}%  "
        f"[{exit_str}]"
    )
