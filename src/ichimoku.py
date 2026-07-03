"""
Calculs des indicateurs Ichimoku Kinko Hyo.
Focus principal : Kijun Sen (Base Line).
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class IchimokuResult:
    """Résultat du calcul Ichimoku pour un symbole sur un timeframe."""
    symbol: str
    timeframe_label: str
    current_price: float
    kijun_sen: float
    tenkan_sen: Optional[float] = None
    senkou_span_a: Optional[float] = None
    senkou_span_b: Optional[float] = None
    distance_pct: float = 0.0          # Distance price -> Kijun (%)
    above_kijun: bool = True           # True si price > Kijun
    bars_count: int = 0                # Nombre de bougies utilisées


def compute_kijun_sen(highs: np.ndarray, lows: np.ndarray,
                      period: int = 26) -> float:
    """Calcule la valeur actuelle du Kijun Sen.

    Kijun Sen = (Plus Haut(26) + Plus Bas(26)) / 2

    Args:
        highs: Array des plus hauts.
        lows: Array des plus bas.
        period: Période de calcul (26 par défaut).

    Retourne:
        La valeur du Kijun Sen, ou NaN si pas assez de données.
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")

    highest_high = np.max(highs[-period:])
    lowest_low = np.min(lows[-period:])
    return (highest_high + lowest_low) / 2.0


def compute_tenkan_sen(highs: np.ndarray, lows: np.ndarray,
                       period: int = 9) -> float:
    """Calcule la valeur actuelle du Tenkan Sen (Conversion Line).

    Tenkan Sen = (Plus Haut(9) + Plus Bas(9)) / 2
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")
    return (np.max(highs[-period:]) + np.min(lows[-period:])) / 2.0


def compute_senkou_span_a(highs: np.ndarray, lows: np.ndarray,
                          tenkan_period: int = 9,
                          kijun_period: int = 26,
                      shift: int = 26) -> float:
    """Calcule le Senkou Span A (Leading Span A) décalé.

    Senkou A = (Tenkan + Kijun) / 2, décalé de 26 périodes.
    Note: ici on retourne la valeur au point actuel (avant décalage).
    """
    tenkan = compute_tenkan_sen(highs, lows, tenkan_period)
    kijun = compute_kijun_sen(highs, lows, kijun_period)
    if np.isnan(tenkan) or np.isnan(kijun):
        return float("nan")
    return (tenkan + kijun) / 2.0


def compute_senkou_span_b(highs: np.ndarray, lows: np.ndarray,
                          period: int = 52, shift: int = 26) -> float:
    """Calcule le Senkou Span B (Leading Span B) décalé.

    Senkou B = (Plus Haut(52) + Plus Bas(52)) / 2, décalé de 26.
    Note: ici on retourne la valeur au point actuel (avant décalage).
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")
    return (np.max(highs[-period:]) + np.min(lows[-period:])) / 2.0


def analyze_kijun_proximity(
    symbol: str,
    timeframe_label: str,
    close_price: float,
    highs: np.ndarray,
    lows: np.ndarray,
    kijun_period: int = 26,
) -> Optional[IchimokuResult]:
    """Analyse complète de la proximité du Kijun Sen pour un symbole.

    Args:
        symbol: Nom du symbole.
        timeframe_label: Label du timeframe utilisé.
        close_price: Prix de clôture actuel (ou dernier tick).
        highs: Array des plus hauts.
        lows: Array des plus bas.
        kijun_period: Période du Kijun (26 par défaut).

    Retourne:
        IchimokuResult ou None si pas assez de données.
    """
    if len(highs) < kijun_period:
        return None

    kijun = compute_kijun_sen(highs, lows, kijun_period)
    if np.isnan(kijun):
        return None

    tenkan = compute_tenkan_sen(highs, lows, 9)
    senkou_a = compute_senkou_span_a(highs, lows, 9, kijun_period, 26)
    senkou_b = compute_senkou_span_b(highs, lows, 52, 26)

    # Distance du prix par rapport au Kijun Sen
    if kijun != 0:
        distance_pct = abs(close_price - kijun) / kijun * 100.0
    else:
        distance_pct = abs(close_price - kijun) * 100.0 if kijun == 0 else 0.0

    above_kijun = close_price > kijun

    return IchimokuResult(
        symbol=symbol,
        timeframe_label=timeframe_label,
        current_price=close_price,
        kijun_sen=kijun,
        tenkan_sen=None if np.isnan(tenkan) else tenkan,
        senkou_span_a=None if np.isnan(senkou_a) else senkou_a,
        senkou_span_b=None if np.isnan(senkou_b) else senkou_b,
        distance_pct=round(distance_pct, 4),
        above_kijun=above_kijun,
        bars_count=len(highs),
    )
