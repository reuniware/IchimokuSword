# turtle/comparison.py — Analyse comparative Turtle Originale vs Turtle Soup
# ======================================================================
# Objectif : tester l'hypothese que les deux strategies sont
# anti-correlees (les pertes de l'une = gains de l'autre).
#
# Analyses :
#   1. Correlation des rendements quotidiens/hebdomadaires
#   2. Episodes de pertes extremes de Turtle orig -> performance Soup
#   3. Portefeuille combine (50/50, volatilite inverse)
#   4. Performance par regime de marche (ADX)
# ======================================================================

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from turtle.engine import BacktestResult, Trade


def compute_correlation(
    result_orig: BacktestResult,
    result_soup: BacktestResult,
    freq: str = 'W',
) -> float:
    """Calcule la correlation des rendements entre les deux strategies.

    Args:
        result_orig: Resultat Turtle originale
        result_soup: Resultat Turtle Soup
        freq: Frequence de resampling ('D' ou 'W')

    Returns:
        Coefficient de correlation de Pearson (-1 a +1).
    """
    if (result_orig.equity_curve is None or result_soup.equity_curve is None):
        return 0.0

    daily_orig = result_orig.equity_curve.resample('D').last().ffill()
    daily_soup = result_soup.equity_curve.resample('D').last().ffill()

    rets_orig = daily_orig.pct_change().dropna()
    rets_soup = daily_soup.pct_change().dropna()

    if freq == 'W':
        rets_orig = rets_orig.resample('W').apply(lambda x: (1 + x).prod() - 1)
        rets_soup = rets_soup.resample('W').apply(lambda x: (1 + x).prod() - 1)

    common_idx = rets_orig.index.intersection(rets_soup.index)
    if len(common_idx) < 5:
        return 0.0

    return float(rets_orig[common_idx].corr(rets_soup[common_idx]))


def analyze_worst_periods(
    result_orig: BacktestResult,
    result_soup: BacktestResult,
    window_days: int = 90,
    top_n: int = 5,
) -> List[dict]:
    """Identifie les pires periodes de Turtle originale et verifie
    si Turtle Soup performe bien sur ces memes fenetres.

    Returns:
        Liste de dicts {orig_pnl, soup_pnl, start_date, end_date}
        pour les top_n pires periodes de la Turtle originale.
    """
    if (result_orig.equity_curve is None or result_soup.equity_curve is None):
        return []

    daily_orig = result_orig.equity_curve.resample('D').last().ffill()
    daily_soup = result_soup.equity_curve.resample('D').last().ffill()

    rolling_orig = daily_orig.pct_change(periods=window_days).dropna() * 100
    rolling_soup = daily_soup.pct_change(periods=window_days).dropna() * 100

    # Trouver les top_n pires fenetres
    worst_indices = rolling_orig.nsmallest(top_n).index

    periods = []
    for idx in worst_indices:
        start = idx - pd.Timedelta(days=window_days)
        if start in rolling_orig.index and idx in rolling_orig.index:
            periods.append({
                'start_date': start.strftime('%Y-%m-%d'),
                'end_date': idx.strftime('%Y-%m-%d'),
                'orig_pnl_pct': round(rolling_orig[idx], 2),
                'soup_pnl_pct': round(
                    rolling_soup[idx] if idx in rolling_soup.index else 0, 2
                ),
            })
    return periods


def combined_portfolio(
    result_orig: BacktestResult,
    result_soup: BacktestResult,
    weight_orig: float = 0.5,
    inverse_vol: bool = True,
) -> Tuple[pd.Series, float]:
    """Calcule l'equity curve d'un portefeuille combinant les deux strategies.

    Args:
        result_orig, result_soup: Resultats des deux strategies
        weight_orig: Poids de la Turtle originale (0.5 = 50/50)
        inverse_vol: Si True, pondere par l'inverse de la volatilite

    Returns:
        (equity_curve, correlation)
    """
    if (result_orig.equity_curve is None or result_soup.equity_curve is None):
        return pd.Series(), 0.0

    daily_orig = result_orig.equity_curve.resample('D').last().ffill().pct_change().dropna()
    daily_soup = result_soup.equity_curve.resample('D').last().ffill().pct_change().dropna()

    common_idx = daily_orig.index.intersection(daily_soup.index)
    if len(common_idx) < 5:
        return pd.Series(), 0.0

    r1 = daily_orig[common_idx]
    r2 = daily_soup[common_idx]
    correlation = float(r1.corr(r2))

    if inverse_vol:
        vol1 = r1.std()
        vol2 = r2.std()
        if vol1 > 0 and vol2 > 0:
            w1 = (1.0 / vol1) / (1.0 / vol1 + 1.0 / vol2)
            w2 = 1.0 - w1
        else:
            w1 = weight_orig
            w2 = 1 - weight_orig
    else:
        w1 = weight_orig
        w2 = 1 - weight_orig

    combined_rets = w1 * r1 + w2 * r2
    combined_equity = 100000 * (1 + combined_rets).cumprod()

    return combined_equity, correlation
