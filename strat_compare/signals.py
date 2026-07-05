# strat_compare/signals.py — Generateurs de signaux pour 7 strategies
# ======================================================================
# Chaque fonction prend un DataFrame OHLCV + parametres et retourne un
# DataFrame avec colonnes : entry_signal, sl_price, tp_price, + indicateurs
#
# Anti-biais : toutes les fonctions utilisent shift(1) pour eviter le
# look-ahead bias.
# ======================================================================

from typing import List, Tuple

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


# ======================================================================
# Ichimoku Kinko Hyo
# ======================================================================

def compute_ichimoku(df: pd.DataFrame, tenkan_p: int = 9, kijun_p: int = 26,
                     senkou_b_p: int = 52, displacement: int = 26
                     ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Composants Ichimoku Kinko Hyo.

    Retourne (tenkan_sen, kijun_sen, senkou_a_active, senkou_b_active).
    
    Les Senkou spans sont projetees 26 barres dans le futur dans
    l'Ichimoku classique. On applique shift(displacement) pour aligner
    le nuage "actif" avec la barre courante :
      senkou_active[i] = senkou_raw[i - displacement]
    """
    high, low = df['high'], df['low']

    tenkan_sen = (high.rolling(tenkan_p).max() + low.rolling(tenkan_p).min()) / 2
    kijun_sen = (high.rolling(kijun_p).max() + low.rolling(kijun_p).min()) / 2

    # Senkou bruts (projetes dans le futur)
    senkou_a_raw = (tenkan_sen + kijun_sen) / 2
    senkou_b_raw = (high.rolling(senkou_b_p).max() + low.rolling(senkou_b_p).min()) / 2

    # Alignement avec la barre courante
    senkou_a_active = senkou_a_raw.shift(displacement)
    senkou_b_active = senkou_b_raw.shift(displacement)

    return tenkan_sen, kijun_sen, senkou_a_active, senkou_b_active


# ======================================================================
# Swing Points (API commune)
# ======================================================================

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


def ichimoku_scalp_signals(df: pd.DataFrame, flat_window: int = 7,
                           flat_threshold_atr: float = 0.01,
                           sl_atr: float = 0.6, tp_atr: float = 1.5,
                           atr_period: int = 14,
                           tenkan_p: int = 9, kijun_p: int = 26,
                           senkou_b_p: int = 52, displacement: int = 26
                           ) -> pd.DataFrame:
    """Ichimoku flat-line scalping.

    Principe :
    1. Identifier les lignes Ichimoku parfaitement plates (Kijun-sen,
       Senkou B). Ces plats sont des niveaux d'equilibre solides.
    2. Entrer des que le prix franchit une ligne plate :
       - LONG  : close passe au-dessus + bougie haussiere
       - SHORT : close passe en dessous + bougie baissiere
    3. SL juste de l'autre cote de la ligne franchie
    4. TP = prochaine ligne plate dans la direction du trade,
       ou fallback ATR

    Anti-look-ahead : toutes les valeurs sont calculees sur [0, i].
    Les Senkou spans sont shiftees de 26 barres (nuage actif = calcule
    il y a 26 barres).
    """
    result = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    tenkan, kijun, senkou_a, senkou_b = compute_ichimoku(
        df, tenkan_p, kijun_p, senkou_b_p, displacement)
    atr = compute_atr(high, low, close, atr_period)

    result['ichimoku_tenkan'] = tenkan
    result['ichimoku_kijun'] = kijun
    result['ichimoku_senkou_a'] = senkou_a
    result['ichimoku_senkou_b'] = senkou_b
    result['atr'] = atr
    result['entry_signal'] = None
    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    # Lignes utilisees pour les entrees (Kijun + Senkou B uniquement —
    # les plus solides ; Tenkan trop reactif, Senkou A est intermediaire)
    entry_lines = {'kijun': kijun, 'senkou_b': senkou_b}
    # Toutes les lignes pour les TP (cibles potentielles)
    all_lines = {
        'tenkan': tenkan, 'kijun': kijun,
        'senkou_a': senkou_a, 'senkou_b': senkou_b,
    }

    # --- Helper: meilleure ligne d'entree parmi les candidates plates ---
    def _pick_best_entry(flat_dict, prev_c, curr_c, side):
        """Retourne (name, value) du meilleur signal d'entree.
        Priorite Senkou B > Kijun."""
        candidates = {}
        for name, val in flat_dict.items():
            if side == 'LONG' and prev_c < val and curr_c > val:
                candidates[name] = val
            elif side == 'SHORT' and prev_c > val and curr_c < val:
                candidates[name] = val
        if not candidates:
            return None, None
        if 'senkou_b' in candidates:
            return 'senkou_b', candidates['senkou_b']
        return list(candidates.items())[0]

    # Besoin minimum:
    #   senkou_b_p barres pour rolling (52) + displacement shift (26)
    #   + flat_window-1 (6) = 84. On arrondit a 90 pour marge.
    start_bar = max(senkou_b_p + displacement + flat_window, 90)
    n = len(df)

    for i in range(start_bar, n):
        a = atr.iloc[i]
        if pd.isna(a) or a == 0:
            continue

        curr_close = close.iloc[i]
        prev_close = close.iloc[i - 1]
        curr_open = df['open'].iloc[i]

        # Detecter les lignes plates (boucle sur all_lines seulement)
        flat_all = {}
        for name, line in all_lines.items():
            line_val = line.iloc[i]
            if pd.isna(line_val):
                continue
            win_start = max(0, i - flat_window + 1)
            window_vals = line.iloc[win_start:i + 1]
            line_range = window_vals.max() - window_vals.min()
            if line_range < flat_threshold_atr * a:
                flat_all[name] = line_val

        # Filtrer les entrees : seules Kijun et Senkou B comptent
        flat_entries = {n: v for n, v in flat_all.items() if n in entry_lines}
        if not flat_entries:
            continue

        # --- LONG ---
        long_name, long_val = _pick_best_entry(flat_entries, prev_close, curr_close, 'LONG')
        if long_name is not None and curr_close > curr_open:
            sl = long_val - sl_atr * a

            higher = [v for n, v in flat_all.items()
                      if v > long_val + 0.15 * a]
            if higher:
                tp = min(higher)
            else:
                tp = curr_close + tp_atr * a

            if tp - curr_close < 0.5 * a:
                tp = curr_close + tp_atr * a

            result.iloc[i, result.columns.get_loc('entry_signal')] = 'LONG'
            result.iloc[i, result.columns.get_loc('sl_price')] = sl
            result.iloc[i, result.columns.get_loc('tp_price')] = tp
            continue

        # --- SHORT ---
        short_name, short_val = _pick_best_entry(flat_entries, prev_close, curr_close, 'SHORT')
        if short_name is not None and curr_close < curr_open:
            sl = short_val + sl_atr * a

            lower = [v for n, v in flat_all.items()
                     if v < short_val - 0.15 * a]
            if lower:
                tp = max(lower)
            else:
                tp = curr_close - tp_atr * a

            if curr_close - tp < 0.5 * a:
                tp = curr_close - tp_atr * a

            result.iloc[i, result.columns.get_loc('entry_signal')] = 'SHORT'
            result.iloc[i, result.columns.get_loc('sl_price')] = sl
            result.iloc[i, result.columns.get_loc('tp_price')] = tp

    # Pas de signaux consecutifs identiques
    prev_sig = result['entry_signal'].shift(1)
    result.loc[result['entry_signal'] == prev_sig, 'entry_signal'] = None

    return result


def ichimoku_mtf_scalp_signals(df: pd.DataFrame,
                               higher_tfs: str = '4h,D',
                               flat_window: int = 5,
                               flat_threshold_atr: float = 0.01,
                               sl_atr: float = 0.6, tp_atr: float = 1.5,
                               atr_period: int = 14,
                               tenkan_p: int = 9, kijun_p: int = 26,
                               senkou_b_p: int = 52, displacement: int = 26
                               ) -> pd.DataFrame:
    """Ichimoku multi-timeframe flat-line scalping.

    **Concept** :
    - Flat lines detectees sur TF hautes (W1, D1, H4) → niveaux majeurs
    - Trading sur la TF basse (celle du DataFrame passe) → scalping

    **Pipeline anti-look-ahead** :
    1. Resample le DF bas vers chaque TF haute
    2. compute_ichimoku() sur chaque TF haute
    3. Detection des lignes plates sur TF haute
    4. shift(1) → les lignes de la barre N sont disponibles a N+1
    5. reindex(method='ffill') → projection sur TF basse
       → a chaque barre basse, seules les lignes des periodes hautes
         COMPLETEES sont visibles
    6. Cross detection sur TF basse + bougie confirmative

    **SL/TP** : ATR calcule sur la TF basse (pertinent pour le scalping).
    """
    # Mapping TF string → nombre de barres a sauter pour laisser
    # le temps au resample + Ichimoku de se stabiliser
    _TF_SKIP = {'W': 300, 'D': 200, '4h': 100, '1h': 50, '12h': 150}

    result = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    atr = compute_atr(high, low, close, atr_period)
    result['atr'] = atr
    result['entry_signal'] = None
    result['sl_price'] = np.nan
    result['tp_price'] = np.nan

    # Parser les TFs hautes (string → liste)
    if isinstance(higher_tfs, str):
        tf_list: List[str] = [t.strip() for t in higher_tfs.split(',')]
    else:
        tf_list = list(higher_tfs)

    # Pour chaque TF haute, calculer les flat lines et les projeter
    # sur la TF basse. On merge toutes les flat lines (toutes TFs hautes)
    # dans un seul dictionnaire de Series (index = TF basse).
    projected_flat: dict = {}  # line_name → Series sur index bas (NaN si pas flat)

    # Trier les TFs de la plus haute a la plus basse (D > 4h > 1h)
    # pour que les TFs superieures soient listees en premier dans projected_flat
    _TF_ORDER = {'W': 4, 'D': 3, '12h': 2, '4h': 1, '1h': 0}
    tf_list_sorted = sorted(tf_list, key=lambda t: _TF_ORDER.get(t, 0), reverse=True)

    for tf_str in tf_list_sorted:
        try:
            # 1. Resample vers TF haute
            df_h = df.resample(tf_str).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
            }).dropna()

            if len(df_h) < 30:
                continue

            # 2. Ichimoku sur TF haute
            tenkan_h, kijun_h, senkou_a_h, senkou_b_h = compute_ichimoku(
                df_h, tenkan_p, kijun_p, senkou_b_p, displacement)
            atr_h = compute_atr(df_h['high'], df_h['low'], df_h['close'],
                                atr_period)

            # 3. Detection des lignes plates sur TF haute
            all_lines_h = {
                'tenkan': tenkan_h, 'kijun': kijun_h,
                'senkou_a': senkou_a_h, 'senkou_b': senkou_b_h,
            }

            for line_name, line_h in all_lines_h.items():
                # Range sur flat_window barres de TF haute
                line_range = line_h.rolling(flat_window).max() - line_h.rolling(flat_window).min()
                is_flat = line_range < (flat_threshold_atr * atr_h)
                # Serie: valeur de la ligne si flat, NaN sinon
                flat_series_h = line_h.where(is_flat)

                # 4 & 5. shift(1) + reindex ffill → projection anti-look-ahead
                # shift(1): la flat line de la barre N devient visible a N+1
                # reindex(ffill): forward-fill sur chaque barre de TF basse
                flat_projected = (
                    flat_series_h
                    .shift(1)
                    .reindex(df.index, method='ffill')
                )

                # Nom unique par TF (ex: "kijun_4h", "senkou_b_D")
                key = f"{line_name}_{tf_str}"
                projected_flat[key] = flat_projected

        except (ValueError, KeyError):
            # TF string non supportee par pandas resample
            continue

    if not projected_flat:
        return result

    # --- Helper: meilleure entree parmi les lignes plates projetees ---
    # Les cles sont de la forme "senkou_b_D", "kijun_4h"
    # Priorite : Senkou B > Kijun > Senkou A > Tenkan
    # Au sein du meme type de ligne, TF superieure prioritaire (D > 4h > 1h)
    # projected_flat est deja trie (TFs hautes d'abord)
    def _pick_best_mtf(flat_dict, prev_c, curr_c, side):
        priority = ['senkou_b', 'kijun', 'senkou_a', 'tenkan']
        for pfx in priority:
            for key, val in flat_dict.items():
                if not key.startswith(pfx):
                    continue
                if side == 'LONG' and prev_c < val and curr_c > val:
                    return key, val
                elif side == 'SHORT' and prev_c > val and curr_c < val:
                    return key, val
        return None, None

    # --- Boucle principale sur TF basse ---
    n = len(df)
    # Calculer le start_bar base sur les TFs hautes demandees
    min_skip = max(_TF_SKIP.get(tf, 100) for tf in tf_list)
    start_bar = max(senkou_b_p + displacement + flat_window + 10, min_skip)

    for i in range(start_bar, n):
        a = atr.iloc[i]
        if pd.isna(a) or a == 0:
            continue

        curr_close = close.iloc[i]
        prev_close = close.iloc[i - 1]
        curr_open = df['open'].iloc[i]

        # Recuperer les flat lines actives a cette barre (valeur non-NaN = plate)
        active_flat = {}
        for key, series in projected_flat.items():
            val = series.iloc[i]
            if pd.notna(val):
                active_flat[key] = val

        if not active_flat:
            continue

        # Filtrer: seules Kijun et Senkou B pour les entrees
        entry_candidates = {
            k: v for k, v in active_flat.items()
            if k.startswith('kijun') or k.startswith('senkou_b')
        }
        if not entry_candidates:
            continue

        # --- LONG ---
        long_name, long_val = _pick_best_mtf(entry_candidates, prev_close, curr_close, 'LONG')
        if long_name is not None and curr_close > curr_open:
            sl = long_val - sl_atr * a

            # TP: prochaine ligne plate au-dessus (toute ligne, toutes TFs)
            higher = [v for v in active_flat.values()
                      if v > long_val + 0.15 * a]
            if higher:
                tp = min(higher)
            else:
                tp = curr_close + tp_atr * a

            if tp - curr_close < 0.5 * a:
                tp = curr_close + tp_atr * a

            result.iloc[i, result.columns.get_loc('entry_signal')] = 'LONG'
            result.iloc[i, result.columns.get_loc('sl_price')] = sl
            result.iloc[i, result.columns.get_loc('tp_price')] = tp
            continue

        # --- SHORT ---
        short_name, short_val = _pick_best_mtf(entry_candidates, prev_close, curr_close, 'SHORT')
        if short_name is not None and curr_close < curr_open:
            sl = short_val + sl_atr * a

            lower = [v for v in active_flat.values()
                     if v < short_val - 0.15 * a]
            if lower:
                tp = max(lower)
            else:
                tp = curr_close - tp_atr * a

            if curr_close - tp < 0.5 * a:
                tp = curr_close - tp_atr * a

            result.iloc[i, result.columns.get_loc('entry_signal')] = 'SHORT'
            result.iloc[i, result.columns.get_loc('sl_price')] = sl
            result.iloc[i, result.columns.get_loc('tp_price')] = tp

    # Pas de signaux consecutifs identiques
    prev_sig = result['entry_signal'].shift(1)
    result.loc[result['entry_signal'] == prev_sig, 'entry_signal'] = None

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
    "Ichimoku_Scalp": ichimoku_scalp_signals,
    "Ichimoku_MTF": ichimoku_mtf_scalp_signals,
}
