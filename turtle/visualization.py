# turtle/visualization.py — Visualisations du backtest comparatif
# ======================================================================
# Genere les graphiques demandes :
#   - Courbes d'equity superposees (Turtle orig vs Soup vs Buy&Hold)
#   - Heatmaps de performance (Sharpe selon N, min_ecart, etc.)
#   - Comparaison par UT (H1 vs H4 vs Daily)
#   - Distribution des rendements par trade (histogramme)
#   - PnL glissant superposes (correlation temporelle)
#   - Performance par regime de marche (ADX)
# ======================================================================

import os
from typing import Dict, List, Optional

import matplotlib
matplotlib.use('Agg')  # Mode non-interactif
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from turtle.engine import BacktestResult


# Style global
try:
    plt.style.use('seaborn-v0_8-darkgrid')
except Exception:
    try:
        plt.style.use('ggplot')
    except Exception:
        pass
COLORS = {
    'turtle_original': '#2196F3',  # bleu
    'turtle_soup': '#FF5722',      # orange
    'buy_hold': '#4CAF50',         # vert
    'combined': '#9C27B0',         # violet
}


def plot_equity_curves(
    results: Dict[str, BacktestResult],
    output_path: str,
    title: str = "Equity Curves — Turtle Original vs Turtle Soup",
    buy_hold_equity: Optional[pd.Series] = None,
) -> str:
    """Trace les courbes d'equity superposees.

    Args:
        results: Dict {label: BacktestResult}
        output_path: Chemin du fichier de sortie (.png)
        title: Titre du graphique
        buy_hold_equity: Serie equity Buy & Hold (optionnel)
    """
    fig, ax = plt.subplots(figsize=(14, 7))

    for label, res in results.items():
        if res.equity_curve is not None and len(res.equity_curve) > 1:
            eq = res.equity_curve
            color = COLORS.get(label, '#333333')
            ax.plot(eq.index, eq.values, label=label,
                    color=color, linewidth=1.5, alpha=0.9)

    if buy_hold_equity is not None:
        ax.plot(buy_hold_equity.index, buy_hold_equity.values,
                label='Buy & Hold', color=COLORS['buy_hold'],
                linewidth=1, linestyle='--', alpha=0.7)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('Date')
    ax.set_ylabel('Capital ($)')
    ax.legend(loc='upper left')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f'${x:,.0f}'))
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return output_path


def plot_returns_distribution(
    results: Dict[str, BacktestResult],
    output_path: str,
) -> str:
    """Histogramme des rendements par trade pour chaque strategie."""
    fig, axes = plt.subplots(1, len(results), figsize=(7 * len(results), 5))
    if len(results) == 1:
        axes = [axes]

    for ax, (label, res) in zip(axes, results.items()):
        pnls = [t.pnl_pct for t in res.trades]
        if not pnls:
            ax.text(0.5, 0.5, 'Aucun trade', ha='center', transform=ax.transAxes)
            continue

        color = COLORS.get(label, '#333333')
        ax.hist(pnls, bins=30, color=color, alpha=0.7, edgecolor='white')
        ax.axvline(x=0, color='red', linestyle='--', linewidth=1)
        ax.axvline(x=np.mean(pnls), color='black', linestyle='-', linewidth=1.5,
                   label=f'Moy={np.mean(pnls):.2f}%')
        ax.set_title(f'{label} — Distribution des trades')
        ax.set_xlabel('P&L (%)')
        ax.set_ylabel('Nb trades')
        ax.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return output_path


def plot_rolling_pnl(
    results: Dict[str, BacktestResult],
    output_path: str,
    window_days: int = 90,
) -> str:
    """PnL glissant superpose (analyse de correlation temporelle).

    Affiche le P&L glissant mensuel des deux strategies pour verifier
    visuellement si les gains de l'une coincident avec les pertes de l'autre.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    rolling_data = {}
    for label, res in results.items():
        if res.equity_curve is not None and len(res.equity_curve) > 1:
            daily = res.equity_curve.resample('D').last().ffill()
            rolling = daily.pct_change(periods=window_days).dropna() * 100
            rolling_data[label] = rolling

    if len(rolling_data) >= 2:
        labels = list(rolling_data.keys())
        r1 = rolling_data[labels[0]]
        r2 = rolling_data[labels[1]]

        common_idx = r1.index.intersection(r2.index)
        r1 = r1[common_idx]
        r2 = r2[common_idx]

        ax1.fill_between(common_idx, 0, r1.values,
                         where=r1.values >= 0,
                         color=COLORS.get(labels[0], 'blue'), alpha=0.5,
                         label=labels[0])
        ax1.fill_between(common_idx, 0, r1.values,
                         where=r1.values < 0,
                         color=COLORS.get(labels[0], 'blue'), alpha=0.3)
        ax1.fill_between(common_idx, 0, r2.values,
                         where=r2.values >= 0,
                         color=COLORS.get(labels[1], 'orange'), alpha=0.5,
                         label=labels[1])
        ax1.fill_between(common_idx, 0, r2.values,
                         where=r2.values < 0,
                         color=COLORS.get(labels[1], 'orange'), alpha=0.3)
        ax1.set_title(f'PnL glissant {window_days}j superposes')
        ax1.legend()

        # Correlation scatter
        ax2.scatter(r1.values, r2.values, alpha=0.4, s=10)
        corr = r1.corr(r2)
        ax2.set_xlabel(f'{labels[0]} PnL%')
        ax2.set_ylabel(f'{labels[1]} PnL%')
        ax2.set_title(f'Correlation: r = {corr:.3f}')
        ax2.axhline(y=0, color='gray', linestyle='--')
        ax2.axvline(x=0, color='gray', linestyle='--')

    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return output_path


def plot_drawdown_comparison(
    results: Dict[str, BacktestResult],
    output_path: str,
) -> str:
    """Comparaison des drawdowns des deux strategies."""
    fig, ax = plt.subplots(figsize=(14, 5))

    for label, res in results.items():
        if res.equity_curve is not None and len(res.equity_curve) > 1:
            eq = res.equity_curve
            rolling_max = eq.cummax()
            dd = (eq - rolling_max) / rolling_max * 100
            color = COLORS.get(label, '#333333')
            ax.fill_between(dd.index, 0, dd.values,
                           color=color, alpha=0.3, label=f'{label}')
            ax.plot(dd.index, dd.values, color=color, linewidth=0.8)

    ax.set_title('Drawdown Compare — Turtle vs Turtle Soup')
    ax.set_ylabel('Drawdown (%)')
    ax.legend()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f'{x:.0f}%'))
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return output_path
