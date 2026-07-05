# turtle/signals.py — Generation de signaux Donchian
# ======================================================================
# Implemente les regles des deux strategies :
#   1. Turtle originale (trend-following) — entrees, sorties, pyramidage
#   2. Turtle Soup (contrarian) — faux breakouts haussiers/baissiers
#
# Anti-biais : AUCUNE donnee future n'est utilisee. Chaque signal est
# calcule uniquement a partir des donnees disponibles au moment T (barre
# close ou en cours, selon le mode choisi).
# ======================================================================

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


# ======================================================================
# Indicateurs communs
# ======================================================================

def compute_donchian_channels(high: pd.Series, low: pd.Series, period: int
                              ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calcule les canaux de Donchian (plus haut, plus bas, milieu).

    Args:
        high: Serie des plus hauts
        low: Serie des plus bas
        period: Periode du canal (ex: 20, 55)

    Returns:
        (upper, lower, middle) — chaque element est une Series indexee
        comme high/low. Les premieres period-1 valeurs sont NaN.
    """
    upper = high.rolling(window=period).max()
    lower = low.rolling(window=period).min()
    middle = (upper + lower) / 2.0
    return upper, lower, middle


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 20) -> pd.Series:
    """Calcule l'Average True Range (ATR).

    Utilise la methode de Wilder (lissage exponentiel) pour rester
    fidele au systeme Turtle original.

    Args:
        high, low, close: Series OHLC
        period: Periode ATR (20 par defaut)
    """
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder smoothing: ATR = (ATR_prev * (period-1) + TR) / period
    atr = tr.copy()
    atr.iloc[:period] = np.nan
    # Initialisation : moyenne simple des 'period' premieres valeurs
    first_valid = tr.iloc[:period].mean()
    atr.iloc[period - 1] = first_valid
    # Lissage Wilder
    for i in range(period, len(atr)):
        atr.iloc[i] = (atr.iloc[i - 1] * (period - 1) + tr.iloc[i]) / period
    return atr


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    """Calcule l'ADX (Average Directional Index).

    Filtre de regime de marche : ADX > 25 = tendance, ADX < 25 = range.
    """
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    # +DM / -DM
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    # Wilder smoothing
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 0.0001)
    adx = dx.rolling(window=period).mean()
    return adx


# ======================================================================
# Stratégie 1 : Turtle originale (trend-following)
# ======================================================================

def turtle_original_signals(
    df: pd.DataFrame,
    n1: int = 20,
    n2: int = 55,
    n_exit: int = 10,
    atr_period: int = 20,
    use_system2: bool = True,
) -> pd.DataFrame:
    """Genere les signaux de la strategie Turtle originale.

    Systeme 1 (n1) : breakout du canal a 20 periodes
    Systeme 2 (n2) : breakout du canal a 55 periodes (filtre optionnel)
    Sortie : breakout du canal oppose a n_exit periodes

    Args:
        df: DataFrame OHLCV avec index datetime
        n1: Periode canal Systeme 1 (defaut 20)
        n2: Periode canal Systeme 2 (defaut 55)
        n_exit: Periode canal de sortie (defaut 10)
        atr_period: Periode ATR (defaut 20)
        use_system2: Si True, filtre les signaux Systeme 1 avec Systeme 2

    Returns:
        DataFrame avec colonnes supplementaires :
        - dc_n1_upper, dc_n1_lower : canal Systeme 1
        - dc_n2_upper, dc_n2_lower : canal Systeme 2
        - dc_exit_upper, dc_exit_lower : canal de sortie
        - atr : ATR
        - entry_signal : 'LONG', 'SHORT', ou None
        - exit_signal : True si sortie
        - in_position : True si en position
        - unit_add : nombre d'unites a ajouter (pyramidage, gere ailleurs)
    """
    result = df.copy()
    high = df['high']
    low = df['low']
    close = df['close']

    # -- Canaux Donchian --
    dc1_up, dc1_lo, _ = compute_donchian_channels(high, low, n1)
    dc2_up, dc2_lo, _ = compute_donchian_channels(high, low, n2)
    dc_ex_up, dc_ex_lo, _ = compute_donchian_channels(high, low, n_exit)

    result['dc_n1_upper'] = dc1_up
    result['dc_n1_lower'] = dc1_lo
    result['dc_n2_upper'] = dc2_up
    result['dc_n2_lower'] = dc2_lo
    result['dc_exit_upper'] = dc_ex_up
    result['dc_exit_lower'] = dc_ex_lo

    # -- ATR --
    result['atr'] = compute_atr(high, low, close, atr_period)

    # -- Signaux d'entree (look-ahead proof : utilise close.shift(1)) --
    # On utilise la CLOTURE de la barre precedente pour eviter tout look-ahead
    prev_close = close.shift(1)

    # Systeme 1 : close > plus haut N1 (LONG), close < plus bas N1 (SHORT)
    s1_long = prev_close > dc1_up.shift(1)
    s1_short = prev_close < dc1_lo.shift(1)

    # Systeme 2 : filtre optionnel
    if use_system2:
        s2_long = prev_close > dc2_up.shift(1)
        s2_short = prev_close < dc2_lo.shift(1)
        entry_long = s1_long & s2_long
        entry_short = s1_short & s2_short
    else:
        entry_long = s1_long
        entry_short = s1_short

    # -- Signaux de sortie --
    exit_long_signal = prev_close < dc_ex_lo.shift(1)
    exit_short_signal = prev_close > dc_ex_up.shift(1)

    # -- Construction du signal --
    result['entry_signal'] = None
    result.loc[entry_long, 'entry_signal'] = 'LONG'
    result.loc[entry_short, 'entry_signal'] = 'SHORT'

    result['exit_signal'] = False
    result.loc[exit_long_signal | exit_short_signal, 'exit_signal'] = True

    return result


# ======================================================================
# Stratégie 2 : Turtle Soup (contrarian / faux breakout)
# ======================================================================

def turtle_soup_signals(
    df: pd.DataFrame,
    n: int = 20,
    min_ecart: int = 3,
    atr_period: int = 20,
    stop_buffer: float = 1.0,
    take_profit_mode: str = "milieu_range",
    rr_ratio: float = 2.0,
) -> pd.DataFrame:
    """Genere les signaux de la strategie Turtle Soup.

    Setup SHORT (faux breakout haussier) :
    1. Le prix fait un nouveau plus haut sur n periodes
    2. Un plus haut similaire ou superieur existait deja >= min_ecart
       barres plus tot
    3. Le nouveau plus haut est confirme par une cloture au-dessus
       de l'ancien plus haut
    4. Entree : quand le prix repasse SOUS l'ancien plus haut
    5. Stop : au-dessus du nouveau plus haut + stop_buffer * ATR
    6. TP selon take_profit_mode

    Args:
        df: DataFrame OHLCV
        n: Periode du canal Donchian
        min_ecart: Barres minimum entre ancien et nouveau extreme
        atr_period: Periode ATR
        stop_buffer: Multiple d'ATR pour le stop
        take_profit_mode: "milieu_range", "swing_oppose", ou "rr_fixe"
        rr_ratio: Ratio risque/rendement si take_profit_mode="rr_fixe"

    Returns:
        DataFrame avec colonnes supplementaires.
    """
    result = df.copy()
    high = df['high']
    low = df['low']
    close = df['close']
    n_bars = len(df)

    # -- Canal Donchian --
    dc_up, dc_lo, dc_mid = compute_donchian_channels(high, low, n)
    result['dc_n_upper'] = dc_up
    result['dc_n_lower'] = dc_lo

    # -- ATR --
    result['atr'] = compute_atr(high, low, close, atr_period)

    # -- Init colonnes --
    result['soup_setup'] = None
    result['soup_trigger'] = False
    result['soup_stop'] = np.nan
    result['soup_tp'] = np.nan
    result['soup_old_extreme'] = np.nan
    result['soup_new_extreme'] = np.nan

    # ==================================================================
    # Setup detection (vectorise) : trouver les faux breakouts
    # ==================================================================
    # Nouveau plus haut/bas sur n periodes
    is_new_high = high >= dc_up.shift(1)
    is_new_low = low <= dc_lo.shift(1)

    lookback_win = n * 3
    setup_col = result.columns.get_loc('soup_setup')
    old_ext_col = result.columns.get_loc('soup_old_extreme')
    new_ext_col = result.columns.get_loc('soup_new_extreme')
    atr_col = result.columns.get_loc('atr')
    trigger_col = result.columns.get_loc('soup_trigger')
    stop_col = result.columns.get_loc('soup_stop')
    tp_col = result.columns.get_loc('soup_tp')

    for i in range(n + lookback_win, n_bars):
        # -- SHORT setup --
        if is_new_high.iloc[i]:
            new_high = high.iloc[i]
            # Chercher ancien plus haut dans [i-lookback_win, i-min_ecart]
            lb_start = max(0, i - lookback_win)
            lb_end = i - min_ecart
            window_highs = high.iloc[lb_start:lb_end + 1]
            if len(window_highs) > 0:
                max_old = window_highs.max()
                if max_old >= new_high * 0.998 and close.iloc[i] > max_old:
                    old_idx = window_highs.idxmax()
                    result.iloc[i, setup_col] = 'SHORT'
                    result.iloc[i, old_ext_col] = max_old
                    result.iloc[i, new_ext_col] = new_high

        # -- LONG setup --
        if is_new_low.iloc[i]:
            new_low = low.iloc[i]
            lb_start = max(0, i - lookback_win)
            lb_end = i - min_ecart
            window_lows = low.iloc[lb_start:lb_end + 1]
            if len(window_lows) > 0:
                min_old = window_lows.min()
                if min_old <= new_low * 1.002 and close.iloc[i] < min_old:
                    result.iloc[i, setup_col] = 'LONG'
                    result.iloc[i, old_ext_col] = min_old
                    result.iloc[i, new_ext_col] = new_low

    # ==================================================================
    # Triggers (boucle contrainte a 40 barres max par setup)
    # ==================================================================
    for i in range(n + lookback_win, n_bars - 1):
        setup = result.iloc[i, setup_col]
        if pd.isna(setup):
            continue

        old_ext = result.iloc[i, old_ext_col]
        new_ext = result.iloc[i, new_ext_col]
        atr_val = result.iloc[i, atr_col]

        if pd.isna(old_ext) or pd.isna(atr_val) or atr_val == 0:
            continue

        buffer = stop_buffer * atr_val
        max_look = min(40, n_bars - i - 1)

        for k in range(i + 1, i + max_look + 1):
            already_triggered = result.iloc[k, trigger_col]
            if already_triggered:
                continue

            if setup == 'SHORT' and close.iloc[k] < old_ext:
                result.iloc[k, trigger_col] = True
                result.iloc[k, setup_col] = 'SHORT'
                result.iloc[k, old_ext_col] = old_ext
                result.iloc[k, stop_col] = new_ext + buffer
                result.iloc[k, tp_col] = _compute_soup_tp(
                    'SHORT', old_ext, new_ext, buffer,
                    low.iloc[i - min_ecart:i].min(),
                    high.iloc[i - min_ecart:i].max(),
                    take_profit_mode, rr_ratio
                )
                break

            elif setup == 'LONG' and close.iloc[k] > old_ext:
                result.iloc[k, trigger_col] = True
                result.iloc[k, setup_col] = 'LONG'
                result.iloc[k, old_ext_col] = old_ext
                result.iloc[k, stop_col] = new_ext - buffer
                result.iloc[k, tp_col] = _compute_soup_tp(
                    'LONG', old_ext, new_ext, buffer,
                    low.iloc[i - min_ecart:i].min(),
                    high.iloc[i - min_ecart:i].max(),
                    take_profit_mode, rr_ratio
                )
                break

    return result


def _compute_soup_tp(direction: str, old_ext: float, new_ext: float,
                     stop_dist: float, range_low: float, range_high: float,
                     tp_mode: str, rr_ratio: float) -> float:
    """Calcule le take-profit pour un setup Turtle Soup.

    - milieu_range : (old_ext + opposite_swing) / 2
    - swing_oppose : le swing oppose du range
    - rr_fixe : stop +/- rr_ratio * stop_distance
    """
    if tp_mode == "milieu_range":
        if direction == 'SHORT':
            return (old_ext + range_low) / 2.0
        else:
            return (old_ext + range_high) / 2.0

    elif tp_mode == "swing_oppose":
        if direction == 'SHORT':
            return range_low
        else:
            return range_high

    elif tp_mode == "rr_fixe":
        if direction == 'SHORT':
            return old_ext - rr_ratio * stop_dist
        else:
            return old_ext + rr_ratio * stop_dist

    # Fallback: milieu du range
    return (old_ext + range_low) / 2.0 if direction == 'SHORT' else (old_ext + range_high) / 2.0
