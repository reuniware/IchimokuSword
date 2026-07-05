# strat_compare/signals.py — Generateurs de signaux pour 7 strategies
# ======================================================================
# Chaque fonction prend un DataFrame OHLCV + parametres et retourne un
# DataFrame avec colonnes : entry_signal, sl_price, tp_price, + indicateurs
#
# Anti-biais : toutes les fonctions utilisent shift(1) pour eviter le
# look-ahead bias.
# ======================================================================

from typing import Tuple

import numpy as np
import pandas as pd


# ======================================================================
# Indicateurs communs
# ======================================================================

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    """ATR avec lissage Wilder."""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """EMA standard."""
    return series.ewm(span=period, adjust=False).mean()


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26,
                 signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(close: pd.Series, period: int = 20, std: float = 2.0
                      ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bollinger Bands. Retourne (middle, upper, lower, width_pct)."""
    middle = close.rolling(period).mean()
    std_dev = close.rolling(period).std(ddof=0)  # ddof=0 conforme TA-Lib
    upper = middle + std * std_dev
    lower = middle - std * std_dev
    width_pct = (upper - lower) / middle * 100
    return middle, upper, lower, width_pct


def compute_stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                       k_period: int = 14, d_period: int = 3,
                       smooth: int = 3
                       ) -> Tuple[pd.Series, pd.Series]:
    """Stochastic %K (fast) et %D (slow)."""
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    fast_k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
    k = fast_k.rolling(smooth).mean()
    d = k.rolling(d_period).mean()
    return k, d


def compute_parabolic_sar(high: pd.Series, low: pd.Series,
                          step: float = 0.02, maximum: float = 0.2
                          ) -> pd.Series:
    """Parabolic SAR (simplifie, proche de Wilder)."""
    n = len(high)
    sar = pd.Series(np.nan, index=high.index)
    ep = pd.Series(np.nan, index=high.index)  # extreme point
    af = pd.Series(np.nan, index=high.index)   # acceleration factor
    trend = pd.Series(0, index=high.index)      # 1 = uptrend, -1 = downtrend

    # Initialisation
    trend.iloc[0] = 1
    sar.iloc[0] = low.iloc[0]
    ep.iloc[0] = high.iloc[0]
    af.iloc[0] = step

    for i in range(1, n):
        prev_sar = sar.iloc[i - 1]
        prev_ep = ep.iloc[i - 1]
        prev_af = af.iloc[i - 1]
        prev_trend = trend.iloc[i - 1]

        # Calcul SAR
        new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

        if prev_trend == 1:  # uptrend
            new_sar = min(new_sar, low.iloc[i - 1])
            if i >= 2:
                new_sar = min(new_sar, low.iloc[i - 2])

            if high.iloc[i] > prev_ep:
                new_ep = high.iloc[i]
                new_af = min(prev_af + step, maximum)
            else:
                new_ep = prev_ep
                new_af = prev_af

            # Reversal
            if low.iloc[i] < new_sar:
                new_trend = -1
                new_sar = prev_ep
                new_ep = low.iloc[i]
                new_af = step
            else:
                new_trend = 1
        else:  # downtrend
            new_sar = max(new_sar, high.iloc[i - 1])
            if i >= 2:
                new_sar = max(new_sar, high.iloc[i - 2])

            if low.iloc[i] < prev_ep:
                new_ep = low.iloc[i]
                new_af = min(prev_af + step, maximum)
            else:
                new_ep = prev_ep
                new_af = prev_af

            if high.iloc[i] > new_sar:
                new_trend = 1
                new_sar = prev_ep
                new_ep = high.iloc[i]
                new_af = step
            else:
                new_trend = -1

        sar.iloc[i] = new_sar
        ep.iloc[i] = new_ep
        af.iloc[i] = new_af
        trend.iloc[i] = new_trend

    return sar


def find_swing_points(high: pd.Series, low: pd.Series, window: int = 20
                      ) -> Tuple[pd.Series, pd.Series]:
    """Detecte les swing highs et swing lows.

    Un swing high est un high qui est le max de [i-window, i+window].
    Un swing low est un low qui est le min de [i-window, i+window].
    """
    n = len(high)
    is_swing_high = pd.Series(False, index=high.index)
    is_swing_low = pd.Series(False, index=low.index)

    for i in range(window, n - window):
        h_window = high.iloc[i - window:i + window + 1]
        l_window = low.iloc[i - window:i + window + 1]
        if high.iloc[i] == h_window.max():
            is_swing_high.iloc[i] = True
        if low.iloc[i] == l_window.min():
            is_swing_low.iloc[i] = True

    return is_swing_high, is_swing_low


# ======================================================================
# Generateurs de signaux
# ======================================================================

def rsi_signals(df: pd.DataFrame, rsi_period: int = 14,
                oversold: int = 30, overbought: int = 70,
                sl_atr: float = 1.5, tp_atr: float = 2.0,
                atr_period: int = 14) -> pd.DataFrame:
    """RSI mean reversion : achat quand RSI sort de la zone survendue,
    vente quand RSI sort de la zone surachetee.

    Regle :
    - LONG : RSI passe au-dessus de oversold (cross above 30)
    - SHORT : RSI passe en dessous de overbought (cross below 70)
    - Exit : signal oppose
    """
    result = df.copy()
    close = df['close']

    rsi = compute_rsi(close, rsi_period)
    atr = compute_atr(df['high'], df['low'], close, atr_period)

    result['rsi'] = rsi
    result['atr'] = atr

    # Cross detection (look-ahead proof: utilise shift(1))
    rsi_prev = rsi.shift(1)

    long_sig = (rsi_prev <= oversold) & (rsi > oversold)
    short_sig = (rsi_prev >= overbought) & (rsi < overbought)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = price + tp_atr * a if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = price - tp_atr * a if tp_atr > 0 else 0

    return result


def bollinger_signals(df: pd.DataFrame, bb_period: int = 20,
                      bb_std: float = 2.0,
                      sl_atr: float = 1.5, tp_atr: float = 1.5,
                      atr_period: int = 14) -> pd.DataFrame:
    """Bollinger Bands mean reversion.

    - LONG : close touche ou passe sous la bande inferieure
    - SHORT : close touche ou passe au-dessus de la bande superieure
    - Exit : signal oppose OU close repasse de l'autre cote du middle
    """
    result = df.copy()
    close = df['close']

    middle, upper, lower, width = compute_bollinger(close, bb_period, bb_std)
    atr = compute_atr(df['high'], df['low'], close, atr_period)

    result['bb_middle'] = middle
    result['bb_upper'] = upper
    result['bb_lower'] = lower
    result['atr'] = atr

    # Look-ahead proof : utilise shift(1)
    prev_close = close.shift(1)
    prev_lower = lower.shift(1)
    prev_upper = upper.shift(1)

    long_sig = (prev_close <= prev_lower)
    short_sig = (prev_close >= prev_upper)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    # Pas de signaux consecutifs identiques
    prev_sig = result['entry_signal'].shift(1)
    result.loc[result['entry_signal'] == prev_sig, 'entry_signal'] = None

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        mid = middle.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = mid if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = mid if tp_atr > 0 else 0

    return result


def macd_signals(df: pd.DataFrame, fast: int = 12, slow: int = 26,
                 signal: int = 9, sl_atr: float = 1.5,
                 tp_atr: float = 2.0, atr_period: int = 14) -> pd.DataFrame:
    """MACD crossover trend following.

    - LONG : MACD line croise au-dessus de la signal line
    - SHORT : MACD line croise en dessous de la signal line
    - Exit : crossover oppose
    """
    result = df.copy()
    close = df['close']

    macd_line, signal_line, histogram = compute_macd(close, fast, slow, signal)
    atr = compute_atr(df['high'], df['low'], close, atr_period)

    result['macd_line'] = macd_line
    result['macd_signal'] = signal_line
    result['macd_hist'] = histogram
    result['atr'] = atr

    # Cross detection
    macd_prev = macd_line.shift(1)
    sig_prev = signal_line.shift(1)

    long_sig = (macd_prev <= sig_prev) & (macd_line > signal_line)
    short_sig = (macd_prev >= sig_prev) & (macd_line < signal_line)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = price + tp_atr * a if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = price - tp_atr * a if tp_atr > 0 else 0

    return result


def stochastic_signals(df: pd.DataFrame, stoch_k: int = 14,
                       stoch_d: int = 3, stoch_smooth: int = 3,
                       oversold: int = 20, overbought: int = 80,
                       sl_atr: float = 1.5, tp_atr: float = 2.0,
                       atr_period: int = 14) -> pd.DataFrame:
    """Stochastic oversold/overbought crossover.

    - LONG : %K croise au-dessus de %D dans la zone survendue (< oversold)
    - SHORT : %K croise en dessous de %D dans la zone surachetee (> overbought)
    - Exit : signal oppose
    """
    result = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    k, d = compute_stochastic(high, low, close, stoch_k, stoch_d, stoch_smooth)
    atr = compute_atr(high, low, close, atr_period)

    result['stoch_k'] = k
    result['stoch_d'] = d
    result['atr'] = atr

    k_prev = k.shift(1)
    d_prev = d.shift(1)

    long_sig = (k_prev < oversold) & (k > d) & (k <= oversold + 10)
    short_sig = (k_prev > overbought) & (k < d) & (k >= overbought - 10)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = price + tp_atr * a if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = price - tp_atr * a if tp_atr > 0 else 0

    return result


def ema_cross_signals(df: pd.DataFrame, fast: int = 9, slow: int = 21,
                      sl_atr: float = 1.5, tp_atr: float = 2.0,
                      atr_period: int = 14) -> pd.DataFrame:
    """EMA crossover trend following.

    - LONG : EMA rapide croise au-dessus de EMA lente
    - SHORT : EMA rapide croise en dessous de EMA lente
    - Exit : crossover oppose
    """
    result = df.copy()
    close = df['close']

    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    atr = compute_atr(df['high'], df['low'], close, atr_period)

    result['ema_fast'] = ema_fast
    result['ema_slow'] = ema_slow
    result['atr'] = atr

    ema_f_prev = ema_fast.shift(1)
    ema_s_prev = ema_slow.shift(1)

    long_sig = (ema_f_prev <= ema_s_prev) & (ema_fast > ema_slow)
    short_sig = (ema_f_prev >= ema_s_prev) & (ema_fast < ema_slow)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = price + tp_atr * a if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = price - tp_atr * a if tp_atr > 0 else 0

    return result


def swing_sr_signals(df: pd.DataFrame, swing_window: int = 20,
                     proximity_atr: float = 0.8,
                     sl_atr: float = 1.5, tp_atr: float = 2.0,
                     atr_period: int = 14) -> pd.DataFrame:
    """Swing High/Low support-resistance bounces.

    Detecte les swing highs (resistances) et swing lows (supports).
    - LONG : prix proche d'un support (swing low recent) et hausse
    - SHORT : prix proche d'une resistance (swing high recent) et baisse
    """
    result = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    atr = compute_atr(high, low, close, atr_period)
    is_swing_high, is_swing_low = find_swing_points(high, low, swing_window)

    result['atr'] = atr
    result['entry_signal'] = None
    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    n = len(df)
    # Pour chaque barre, trouver le support/resistance le plus proche.
    # ANTI-LOOK-AHEAD : find_swing_points confirme un swing a l'index j
    # seulement apres avoir vu les barres [j-window, j+window].
    # Donc a la barre i, seuls les swings indexes <= i - window sont confirmes.
    for i in range(swing_window * 2, n):
        a = atr.iloc[i]
        if pd.isna(a) or a == 0:
            continue

        prox = proximity_atr * a
        curr_close = close.iloc[i]
        curr_high = high.iloc[i]
        curr_low = low.iloc[i]

        # Derniere barre dont les swings sont confirmes (inclus car slice exclusif)
        confirmed_end = i - swing_window + 1
        if confirmed_end <= 0:
            continue
        search_start = max(0, confirmed_end - swing_window * 4)

        # Chercher le swing low le plus recent (support) — confirme uniquement
        past_lows = low.iloc[search_start:confirmed_end]
        swing_low_mask = is_swing_low.iloc[search_start:confirmed_end]
        recent_swing_lows = past_lows[swing_low_mask]

        # Chercher le swing high le plus recent (resistance) — confirme uniquement
        past_highs = high.iloc[search_start:confirmed_end]
        swing_high_mask = is_swing_high.iloc[search_start:confirmed_end]
        recent_swing_highs = past_highs[swing_high_mask]

        # Signal LONG : prix proche du support et la barre montre un rebond
        if len(recent_swing_lows) > 0:
            support = recent_swing_lows.iloc[-1]
            dist_to_support = curr_low - support
            if 0 < dist_to_support < prox:
                # Confirmation: la barre est haussiere (close > open)
                if close.iloc[i] > df['open'].iloc[i]:
                    result.iloc[i, result.columns.get_loc('entry_signal')] = 'LONG'
                    result.iloc[i, result.columns.get_loc('sl_price')] = support - sl_atr * a
                    result.iloc[i, result.columns.get_loc('tp_price')] = curr_close + tp_atr * a

        # Signal SHORT : prix proche de la resistance et la barre montre une rejection
        if result.iloc[i, result.columns.get_loc('entry_signal')] is None:
            if len(recent_swing_highs) > 0:
                resistance = recent_swing_highs.iloc[-1]
                dist_to_res = resistance - curr_high
                if 0 < dist_to_res < prox:
                    if close.iloc[i] < df['open'].iloc[i]:
                        result.iloc[i, result.columns.get_loc('entry_signal')] = 'SHORT'
                        result.iloc[i, result.columns.get_loc('sl_price')] = resistance + sl_atr * a
                        result.iloc[i, result.columns.get_loc('tp_price')] = curr_close - tp_atr * a

    # Pas de signaux consecutifs identiques
    prev_sig = result['entry_signal'].shift(1)
    result.loc[result['entry_signal'] == prev_sig, 'entry_signal'] = None

    return result


def parabolic_sar_signals(df: pd.DataFrame, step: float = 0.02,
                          maximum: float = 0.2,
                          sl_atr: float = 1.5, tp_atr: float = 2.0,
                          atr_period: int = 14) -> pd.DataFrame:
    """Parabolic SAR trend following.

    - LONG : SAR passe de au-dessus a en dessous du prix (trend haussier)
    - SHORT : SAR passe de en dessous a au-dessus du prix (trend baissier)
    - Exit : SAR flip oppose
    """
    result = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    sar = compute_parabolic_sar(high, low, step, maximum)
    atr = compute_atr(high, low, close, atr_period)

    result['psar'] = sar
    result['atr'] = atr

    # Trend detection: SAR position relative to close
    # Sar en dessous du prix = trend haussier
    # Sar au dessus du prix = trend baissier
    sar_above = sar.shift(1) > close.shift(1)
    sar_below = sar.shift(1) < close.shift(1)

    # Flip : SAR traverse le prix
    long_sig = sar_above & (sar < close)
    short_sig = sar_below & (sar > close)

    result['entry_signal'] = None
    result.loc[long_sig, 'entry_signal'] = 'LONG'
    result.loc[short_sig, 'entry_signal'] = 'SHORT'

    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    for i in result.index[result['entry_signal'].notna()]:
        sig = result.at[i, 'entry_signal']
        price = close.loc[i]
        a = atr.loc[i]
        if sig == 'LONG':
            result.at[i, 'sl_price'] = price - sl_atr * a
            result.at[i, 'tp_price'] = price + tp_atr * a if tp_atr > 0 else 0
        else:
            result.at[i, 'sl_price'] = price + sl_atr * a
            result.at[i, 'tp_price'] = price - tp_atr * a if tp_atr > 0 else 0

    return result


# ======================================================================
# Mapping strategy name -> signal function
# ======================================================================

SIGNAL_FUNCTIONS = {
    "RSI": rsi_signals,
    "Bollinger": bollinger_signals,
    "MACD": macd_signals,
    "Stochastic": stochastic_signals,
    "EMA_Cross": ema_cross_signals,
    "Swing_SR": swing_sr_signals,
    "Parabolic_SAR": parabolic_sar_signals,
}
