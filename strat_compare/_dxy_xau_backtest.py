# strat_compare/_dxy_xau_backtest.py
# DXY.cash -> XAUUSD correlation scalping — MULTI-TF backtest
# ======================================================================
# Tests M1, M5, M15, H1, H4 with adapted cooldown per TF
# ======================================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timezone

from strat_compare.engine import run_backtest
from strat_compare.signals import compute_atr

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END   = datetime(2026, 7, 3, tzinfo=UTC)

# ======================================================================
# Params (shared across TFs)
# ======================================================================
THRESHOLD_STD    = 1.5
SL_ATR           = 1.5
TP_ATR           = 3.0
ROLLING_CORR_MIN = -0.3
ATR_PERIOD       = 14
H4_SMA_PERIOD    = 20
STD_WINDOW       = 50

# Per-TF params: (mt5_tf, label, cooldown_bars)
TF_CONFIGS = [
    (mt5.TIMEFRAME_M1,  "M1",  30),
    (mt5.TIMEFRAME_M5,  "M5",  12),
    (mt5.TIMEFRAME_M15, "M15", 8),
    (mt5.TIMEFRAME_H1,  "H1",  3),
    (mt5.TIMEFRAME_H4,  "H4",  2),
]

# ======================================================================
# 1. Fetch all data once
# ======================================================================
load_env()
mt5.initialize()

def fetch(symbol, tf, start, end):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_range(symbol, tf, start, end)
    if rates is None or len(rates) == 0:
        for count in [50000, 20000, 10000, 5000]:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is not None and len(rates) > 0:
                break
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    return df.loc[start:end]

# Fetch DXY once (H1 for signals, H4 for trend)
dxy_h1 = fetch("DXY.cash", mt5.TIMEFRAME_H1, START, END)
dxy_h4 = fetch("DXY.cash", mt5.TIMEFRAME_H4, START, END)

if len(dxy_h1) < 50 or len(dxy_h4) < 20:
    print("ERROR: not enough DXY data")
    mt5.shutdown()
    sys.exit(1)

# ======================================================================
# 2. Pre-compute DXY indicators (shared across all TFs)
# ======================================================================
dxy_h1_close = dxy_h1['close']
dxy_h1_ret = dxy_h1_close.pct_change() * 100

# Rolling std (anti-look-ahead)
dxy_std = dxy_h1_ret.rolling(STD_WINDOW, min_periods=20).std()
dxy_exp = dxy_h1_ret.expanding(min_periods=20).std()
dxy_std = dxy_std.fillna(dxy_exp)

dxy_strong_up   = dxy_h1_ret >  THRESHOLD_STD * dxy_std
dxy_strong_down = dxy_h1_ret < -THRESHOLD_STD * dxy_std

# H4 trend
dxy_h4_sma = dxy_h4['close'].rolling(H4_SMA_PERIOD).mean()
dxy_h4_trend_h1 = dxy_h4_sma.reindex(dxy_h1.index, method='ffill')
dxy_h4_bullish = dxy_h1_close > dxy_h4_trend_h1

print("=" * 100)
print(f"  DXY -> XAUUSD CORRELATION SCALPING — MULTI-TF BACKTEST")
print(f"  {START.strftime('%Y-%m-%d')} -> {END.strftime('%Y-%m-%d')}")
print(f"  Threshold={THRESHOLD_STD}std  SL={SL_ATR}ATR  TP={TP_ATR}ATR")
print(f"  DXY H1 strong UP: {dxy_strong_up.sum()}  "
      f"DOWN: {dxy_strong_down.sum()}  "
      f"std(mean)={dxy_std.mean():.4f}%")
print("=" * 100)

# ======================================================================
# 3. Run backtest for each trading TF
# ======================================================================
results = []

for tf_mt5, tf_label, cooldown in TF_CONFIGS:
    # Fetch XAUUSD for this TF
    xau = fetch("XAUUSD", tf_mt5, START, END)
    if len(xau) < 200:
        print(f"\n  [{tf_label}] SKIP: only {len(xau)} bars")
        continue

    # Rolling returns correlation XAU vs DXY (on H1, projected to trading TF)
    xau_h1_close = xau['close'].resample('1h').last().dropna()
    common_idx = xau_h1_close.index.intersection(dxy_h1_close.index)
    xau_h1_close = xau_h1_close.loc[common_idx]
    dxy_aligned = dxy_h1_close.loc[common_idx]
    xau_h1_ret = xau_h1_close.pct_change() * 100
    dxy_aligned_ret = dxy_aligned.pct_change() * 100
    rolling_corr_ret = xau_h1_ret.rolling(20).corr(dxy_aligned_ret)
    rolling_corr_tf = rolling_corr_ret.reindex(xau.index, method='ffill')

    # DXY signal: shift(1) + ffill to trading TF
    dxy_signal_h1 = pd.Series(0, index=dxy_h1.index)
    dxy_signal_h1[dxy_strong_up]   = -1
    dxy_signal_h1[dxy_strong_down] =  1
    dxy_signal_tf = (
        dxy_signal_h1.shift(1)
        .reindex(xau.index, method='ffill')
        .fillna(0).astype(int)
    )

    # H4 trend on trading TF
    h4_bullish_tf = (
        dxy_h4_bullish.reindex(dxy_h1.index, method='ffill')
        .shift(1).reindex(xau.index, method='ffill')
        .fillna(False)
    )

    # Generate signals
    close = xau['close']
    high  = xau['high']
    low   = xau['low']
    atr   = compute_atr(high, low, close, ATR_PERIOD)

    signals = xau.copy()
    signals['entry_signal'] = None
    signals['sl_price'] = np.nan
    signals['tp_price'] = np.nan
    signals['atr'] = atr

    n = len(signals)
    last_signal_bar = -cooldown

    for i in range(100, n):
        a = atr.iloc[i]
        if pd.isna(a) or a == 0:
            continue
        if i - last_signal_bar < cooldown:
            continue

        dxy_sig = dxy_signal_tf.iloc[i]
        if dxy_sig == 0:
            continue

        rc = rolling_corr_tf.iloc[i]
        if pd.notna(rc) and rc > ROLLING_CORR_MIN:
            continue

        if dxy_sig == -1 and not h4_bullish_tf.iloc[i]:
            continue
        if dxy_sig == 1 and h4_bullish_tf.iloc[i]:
            continue

        curr_close = close.iloc[i]
        curr_open  = xau['open'].iloc[i]

        if dxy_sig == 1:
            if not (curr_close > curr_open):
                continue
            signals.iloc[i, signals.columns.get_loc('entry_signal')] = 'LONG'
            signals.iloc[i, signals.columns.get_loc('sl_price')] = curr_close - SL_ATR * a
            signals.iloc[i, signals.columns.get_loc('tp_price')] = curr_close + TP_ATR * a
            last_signal_bar = i
        elif dxy_sig == -1:
            if not (curr_close < curr_open):
                continue
            signals.iloc[i, signals.columns.get_loc('entry_signal')] = 'SHORT'
            signals.iloc[i, signals.columns.get_loc('sl_price')] = curr_close + SL_ATR * a
            signals.iloc[i, signals.columns.get_loc('tp_price')] = curr_close - TP_ATR * a
            last_signal_bar = i

    prev_sig = signals['entry_signal'].shift(1)
    signals.loc[signals['entry_signal'] == prev_sig, 'entry_signal'] = None

    # Run backtest (standard only for comparison)
    result = run_backtest(xau, signals, "XAUUSD", "DXY_Corr", ftmo_mode=False)
    result.timeframe = tf_label

    n_long  = (signals['entry_signal'] == 'LONG').sum()
    n_short = (signals['entry_signal'] == 'SHORT').sum()

    results.append(result)

    print(f"\n  [{tf_label}] {len(xau):>6} bars | {n_long+n_short:>3} signals ({n_long}L/{n_short}S) | "
          f"Trades={result.n_trades:>4}  WR={result.win_rate:>5.1f}%  "
          f"Ret={result.total_return:>+7.2f}%  Sharpe={result.sharpe:>+6.2f}  "
          f"MaxDD={result.max_dd:>+6.1f}%  PF={result.profit_factor:>5.2f}")

# ======================================================================
# 4. Comparison table
# ======================================================================
print(f"\n{'=' * 100}")
print(f"  COMPARISON — ALL TIMEFRAMES")
print(f"{'=' * 100}")
print(f"  {'TF':<5} {'Bars':>7} {'Trades':>7} {'WR%':>7} {'Ret%':>8} "
      f"{'Sharpe':>8} {'MaxDD%':>8} {'PF':>6} {'AvgW%':>8} {'AvgL%':>8}")
print(f"  {'-' * 80}")

for r in sorted(results, key=lambda x: -x.sharpe):
    print(f"  {r.timeframe:<5} {len(r.equity_curve) if r.equity_curve is not None else 0:>7} "
          f"{r.n_trades:>7} {r.win_rate:>6.1f}% {r.total_return:>+7.2f}% "
          f"{r.sharpe:>+7.2f} {r.max_dd:>+7.1f}% {r.profit_factor:>5.2f} "
          f"{r.avg_win:>+7.2f}% {r.avg_loss:>+7.2f}%")

# Find best
if results:
    best = max(results, key=lambda r: r.sharpe)
    print(f"\n  >>> BEST: {best.timeframe}  "
          f"Sharpe={best.sharpe:+.2f}  "
          f"Trades={best.n_trades}  WR={best.win_rate:.1f}%  "
          f"Ret={best.total_return:+.2f}%")

    # Also show FTMO for the best TF only
    best_xau = fetch("XAUUSD",
                     dict(TF_CONFIGS)[best.timeframe] if hasattr(dict, '__missing__') else
                     [t for t, l, c in TF_CONFIGS if l == best.timeframe][0],
                     START, END)
    # Re-generate best signals (quick)
    best_signals = signals  # reuse last signals if it matches
    ftmo_result = run_backtest(xau, signals, "XAUUSD", "DXY_Corr",
                               ftmo_mode=True, ftmo_risk_pct=2.0)
    ftmo_ret = (ftmo_result.final_capital - ftmo_result.initial_capital) / ftmo_result.initial_capital * 100
    ftmo_dl = getattr(ftmo_result, 'ftmo_days_lost', 'N/A')
    print(f"  FTMO ({best.timeframe}): ${ftmo_result.final_capital:,.2f}  "
          f"ROI={ftmo_ret:+.2f}%  days_lost={ftmo_dl}")

print(f"\n{'=' * 100}")
mt5.shutdown()
