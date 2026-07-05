# turtle/engine.py — Moteur de backtesting commun
# ======================================================================
# Gestion des positions, execution des ordres, couts de transaction,
# pyramidage (Turtle originale), verification anti-biais.
#
# Principes anti-biais :
#   - Look-ahead : tous les signaux utilisent close.shift(1), pas close
#   - Survivorship : gere par l'utilisateur (choix des symboles)
#   - Overfitting : split train/test + walk-forward gere par main.py
# ======================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from turtle.config import COSTS, INITIAL_CAPITAL, MARKET_REGIME
from turtle.signals import compute_adx
from turtle.data_fetcher import get_asset_class


@dataclass
class Position:
    """Une position ouverte (potentiellement multi-unites avec pyramidage)."""
    direction: str          # 'LONG' ou 'SHORT'
    entry_time: pd.Timestamp
    entry_price: float
    units: int = 1          # nombre d'unites accumulees
    last_add_price: float = 0.0  # prix du dernier ajout (pyramidage)
    stop_price: float = 0.0
    tp_price: float = 0.0
    pyramiding: bool = True

    def add_unit(self, price: float) -> None:
        """Ajoute une unite en pyramidage."""
        self.units += 1
        self.last_add_price = price
        self.entry_price = (
            (self.entry_price * (self.units - 1) + price) / self.units
        )


@dataclass
class Trade:
    """Un trade complet (entre -> sortie)."""
    direction: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    units: int
    pnl_pct: float
    pnl_abs: float
    exit_reason: str  # 'stop', 'tp', 'signal', 'end'
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
    # Metriques (calculees apres coup)
    total_return: float = 0.0
    cagr: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_dd: float = 0.0
    max_dd_duration: int = 0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    n_trades: int = 0


def _apply_costs(price: float, asset_class: str, is_entry: bool) -> float:
    """Applique les couts de transaction (spread + slippage + commission).

    Args:
        price: Prix de base
        asset_class: 'forex', 'indices', 'metaux'
        is_entry: True pour entree, False pour sortie

    Returns:
        Prix ajuste apres couts.
    """
    costs = COSTS.get(asset_class, COSTS["forex"])
    spread = costs["spread_pct"] / 100.0
    slippage = costs["slippage_pct"] / 100.0
    commission = costs["commission_pct"] / 100.0

    # Spread et slippage defavorisent toujours le trader
    total_cost_pct = spread + slippage + commission
    if is_entry:
        return price * (1 + total_cost_pct)
    else:
        return price * (1 - total_cost_pct)


def _compute_unit_size(capital: float, atr: float, point_value: float,
                       risk_pct: float = 0.01) -> int:
    """Calcule la taille d'une unite Turtle.

    unit = (risk_pct * capital) / (ATR * point_value)

    Pour le forex, point_value est approxime par le prix * 0.0001.
    """
    risk_amount = capital * risk_pct
    unit_size = risk_amount / (atr * point_value) if atr > 0 else 1
    return max(1, int(unit_size))


# ======================================================================
# Backtesting engine
# ======================================================================

def run_backtest(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    symbol: str,
    strategy: str,
    costs_enabled: bool = True,
    pyramiding: bool = True,
    max_units: int = 4,
    pyramid_step_atr: float = 0.5,
) -> BacktestResult:
    """Execute un backtest sur les signaux generes.

    Args:
        df: DataFrame OHLCV original (avec index datetime)
        signals: DataFrame avec colonnes entry_signal, exit_signal, atr, etc.
        symbol: Nom du symbole
        strategy: 'turtle_original' ou 'turtle_soup'
        costs_enabled: Appliquer les couts de transaction
        pyramiding: Activer le pyramidage (Turtle orig uniquement)
        max_units: Nombre max d'unites en pyramidage
        pyramid_step_atr: Pas de pyramidage en multiple d'ATR

    Returns:
        BacktestResult avec tous les trades et metriques.
    """
    asset_class = get_asset_class(symbol)
    capital = INITIAL_CAPITAL
    equity = [capital]
    equity_dates = [signals.index[0]]
    trades: List[Trade] = []
    position: Optional[Position] = None

    high = df['high']
    low = df['low']
    close = df['close']
    atr = signals.get('atr', pd.Series(0, index=signals.index))

    # Filtre ADX (regime de marche)
    if MARKET_REGIME["enabled"]:
        adx = compute_adx(high, low, close, MARKET_REGIME["adx_period"])
    else:
        adx = pd.Series(50, index=signals.index)  # tout est tendance

    # Point value (approxime)
    point_value = close.iloc[-1] * 0.0001

    for i in range(1, len(signals)):
        current_time = signals.index[i]
        current_high = high.iloc[i]
        current_low = low.iloc[i]
        current_close = close.iloc[i]
        current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0

        # --- Si en position, verifier sorties ---
        if position is not None:
            exit_now = False
            exit_price = current_close
            exit_reason = "signal"

            # Stop-loss
            if position.direction == 'LONG':
                if current_low <= position.stop_price:
                    exit_now = True
                    exit_price = position.stop_price
                    exit_reason = "stop"
            else:  # SHORT
                if current_high >= position.stop_price:
                    exit_now = True
                    exit_price = position.stop_price
                    exit_reason = "stop"

            # Take-profit
            if not exit_now and position.tp_price > 0:
                if position.direction == 'LONG' and current_high >= position.tp_price:
                    exit_now = True
                    exit_price = position.tp_price
                    exit_reason = "tp"
                elif position.direction == 'SHORT' and current_low <= position.tp_price:
                    exit_now = True
                    exit_price = position.tp_price
                    exit_reason = "tp"

            # Signal de sortie (Turtle originale)
            if not exit_now and strategy == 'turtle_original':
                exit_sig = signals['exit_signal'].iloc[i]
                if exit_sig:
                    exit_now = True
                    exit_reason = "signal"

            # --- Cloture de la position ---
            if exit_now:
                if costs_enabled:
                    exit_price = _apply_costs(exit_price, asset_class, False)

                pnl_pct = (exit_price / position.entry_price - 1) * 100
                if position.direction == 'SHORT':
                    pnl_pct = -pnl_pct

                pnl_pct_per_unit = pnl_pct  # % par unite
                pnl_abs = capital * (pnl_pct_per_unit / 100) * position.units
                capital += pnl_abs

                entry_cost = _apply_costs(
                    position.entry_price, asset_class, True
                ) - position.entry_price
                exit_cost = exit_price - (
                    _apply_costs(exit_price, asset_class, False)
                    if not costs_enabled else exit_price
                )
                total_cost_pct = abs(
                    (entry_cost + abs(exit_cost)) / position.entry_price * 100
                )

                trades.append(Trade(
                    direction=position.direction,
                    entry_time=position.entry_time,
                    exit_time=current_time,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    units=position.units,
                    pnl_pct=round(pnl_pct, 4),
                    pnl_abs=round(pnl_abs, 2),
                    exit_reason=exit_reason,
                    costs_pct=round(total_cost_pct, 4),
                ))
                position = None

        # --- Verifier signal d'entree ---
        if position is None:
            entry_sig = signals['entry_signal'].iloc[i]

            if strategy == 'turtle_original':
                if entry_sig in ('LONG', 'SHORT'):
                    # Turtle originale : entree standard
                    entry_p = _apply_costs(
                        current_close, asset_class, True
                    ) if costs_enabled else current_close

                    stop_p = _compute_turtle_stop(
                        entry_p, entry_sig, current_atr, signals, i
                    )
                    tp_p = 0  # Turtle originale n'a pas de TP fixe

                    position = Position(
                        direction=entry_sig,
                        entry_time=current_time,
                        entry_price=entry_p,
                        stop_price=stop_p,
                        tp_price=tp_p,
                        pyramiding=pyramiding,
                    )

            elif strategy == 'turtle_soup':
                trigger = signals['soup_trigger'].iloc[i]
                if trigger and entry_sig in ('LONG', 'SHORT'):
                    entry_p = _apply_costs(
                        current_close, asset_class, True
                    ) if costs_enabled else current_close

                    stop_p = signals['soup_stop'].iloc[i]
                    tp_p = signals['soup_tp'].iloc[i]

                    if pd.isna(stop_p):
                        stop_p = _compute_turtle_stop(
                            entry_p, entry_sig, current_atr, signals, i
                        )
                    if pd.isna(tp_p):
                        tp_p = 0

                    position = Position(
                        direction=entry_sig,
                        entry_time=current_time,
                        entry_price=entry_p,
                        stop_price=stop_p,
                        tp_price=tp_p,
                        pyramiding=False,  # Turtle Soup ne pyramid pas
                    )

        # --- Pyramidage (Turtle originale uniquement) ---
        if (position is not None and pyramiding
                and position.units < max_units
                and strategy == 'turtle_original'):
            step = pyramid_step_atr * current_atr
            if position.direction == 'LONG':
                add_level = position.last_add_price + step if position.last_add_price > 0 else position.entry_price + step
                if current_close >= add_level:
                    position.add_unit(current_close)
                    position.stop_price = current_close - 2 * current_atr
            else:
                add_level = position.last_add_price - step if position.last_add_price > 0 else position.entry_price - step
                if current_close <= add_level:
                    position.add_unit(current_close)
                    position.stop_price = current_close + 2 * current_atr

        # --- Equity curve ---
        equity.append(capital)
        equity_dates.append(current_time)

    # --- Construire le resultat ---
    result = BacktestResult(
        strategy=strategy,
        symbol=symbol,
        timeframe="unknown",
        trades=trades,
        equity_curve=pd.Series(equity, index=equity_dates),
        initial_capital=INITIAL_CAPITAL,
        final_capital=capital,
        n_trades=len(trades),
    )
    return result


def _compute_turtle_stop(entry_price: float, direction: str, atr_val: float,
                         signals: pd.DataFrame, idx: int) -> float:
    """Calcule le stop-loss Turtle standard (2x ATR)."""
    from turtle.config import TURTLE_ORIG_CONFIG
    mult = TURTLE_ORIG_CONFIG["stop_multiplier"]
    if direction == 'LONG':
        return entry_price - mult * atr_val
    else:
        return entry_price + mult * atr_val
