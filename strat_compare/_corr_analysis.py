# strat_compare/_corr_analysis.py — XAUUSD vs DXY.cash correlation
# Period: 01/01/2026 -> 03/07/2026

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

import numpy as np
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timezone

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END   = datetime(2026, 7, 3, tzinfo=UTC)

load_env()
mt5.initialize()

TIMEFRAMES = {
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

def fetch(symbol, tf_name, tf_val):
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_range(symbol, tf_val, START, END)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df.set_index('time', inplace=True)
    df.sort_index(inplace=True)
    df.rename(columns={c: f"{c}_{symbol}" for c in ['open','high','low','close','tick_volume']}, inplace=True)
    return df

print("=" * 100)
print("  XAUUSD vs DXY.cash CORRELATION -- 2026-01-01 to 2026-07-03")
print("=" * 100)

for tf_name, tf_val in TIMEFRAMES.items():
    print(f"\n{'=' * 100}")
    print(f"  TIMEFRAME: {tf_name}")
    print(f"{'=' * 100}")

    xau = fetch("XAUUSD", tf_name, tf_val)
    dxy = fetch("DXY.cash", tf_name, tf_val)

    if len(xau) < 10 or len(dxy) < 10:
        print(f"  WARN: not enough data: XAUUSD={len(xau)} bars, DXY={len(dxy)} bars")
        continue

    common_idx = xau.index.intersection(dxy.index)
    xau = xau.loc[common_idx]
    dxy = dxy.loc[common_idx]

    xau_close = xau['close_XAUUSD']
    dxy_close = dxy['close_DXY.cash']
    xau_ret = xau_close.pct_change().dropna() * 100
    dxy_ret = dxy_close.pct_change().dropna() * 100

    print(f"  Aligned bars: {len(common_idx)}")
    print(f"  XAUUSD close: {xau_close.min():.2f} - {xau_close.max():.2f}")
    print(f"  DXY    close: {dxy_close.min():.4f} - {dxy_close.max():.4f}")

    # -- Static correlations --
    pearson_close  = xau_close.corr(dxy_close)
    pearson_ret    = xau_ret.corr(dxy_ret)
    # Spearman = Pearson on ranks (no scipy needed)
    spearman_close = xau_close.rank().corr(dxy_close.rank())
    spearman_ret   = xau_ret.rank().corr(dxy_ret.rank())

    print(f"\n  --- STATIC CORRELATIONS ---")
    print(f"  Pearson  (close) : {pearson_close:>+8.4f}")
    print(f"  Pearson  (ret %) : {pearson_ret:>+8.4f}")
    print(f"  Spearman (close) : {spearman_close:>+8.4f}")
    print(f"  Spearman (ret %) : {spearman_ret:>+8.4f}")

    # -- Rolling correlation --
    print(f"\n  --- ROLLING CORRELATION ---")
    for window in [20, 50]:
        roll_corr = xau_close.rolling(window).corr(dxy_close)
        valid = roll_corr.dropna()
        if len(valid) == 0:
            print(f"  Window {window}: not enough data")
            continue
        neg_pct = (valid < 0).sum() / len(valid) * 100
        pos_pct = (valid >= 0).sum() / len(valid) * 100
        print(f"  Window {window:>3}b: mean={valid.mean():>+7.4f}  min={valid.min():>+7.4f}  "
              f"max={valid.max():>+7.4f}  std={valid.std():.4f}")
        print(f"            Negative: {neg_pct:5.1f}%  |  Positive: {pos_pct:5.1f}%")

    # -- Cross-correlation (lag analysis) --
    print(f"\n  --- CROSS-CORRELATION (who leads?) ---")
    max_lag = min(20, len(xau_ret) // 10)
    lags, corrs_list = [], []

    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            c = dxy_ret.iloc[:lag].corr(xau_ret.iloc[-lag:])
            label = f"DXY lead {-lag:>2d}b"
        elif lag > 0:
            c = xau_ret.iloc[:-lag].corr(dxy_ret.iloc[lag:])
            label = f"XAU lead {lag:>2d}b"
        else:
            c = xau_ret.corr(dxy_ret)
            label = f"simultaneous"

        lags.append(lag)
        corrs_list.append(c)
        bar_len = int(abs(c) * 50) if not np.isnan(c) else 0
        print(f"  {label:>20s} : {c:>+8.4f}  {'#' * bar_len}")

    # Best lag
    best_idx = np.argmax(np.abs(corrs_list))
    best_lag = lags[best_idx]
    best_corr = corrs_list[best_idx]
    if best_lag < 0:
        best_desc = f"DXY leads by {-best_lag} bars"
    elif best_lag > 0:
        best_desc = f"XAU leads by {best_lag} bars"
    else:
        best_desc = "simultaneous"

    print(f"\n  >>> BEST LAG: {best_desc} -- r = {best_corr:+.4f}")

    # -- Regression --
    print(f"\n  --- REGRESSION ---")
    from numpy import polyfit
    slope, intercept = polyfit(dxy_close, xau_close, 1)
    residuals = xau_close - (slope * dxy_close + intercept)
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((xau_close - xau_close.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    print(f"  XAUUSD = {slope:.2f} * DXY + {intercept:+.2f}")
    print(f"  R2 = {r2:.4f}")
    print(f"  If DXY moves +1 point, XAUUSD moves {slope:+.2f}$")

    # -- Volatility --
    print(f"\n  --- VOLATILITY ---")
    xau_vol = xau_ret.std()
    dxy_vol = dxy_ret.std()
    print(f"  XAUUSD vol (std ret %): {xau_vol:.3f}%")
    print(f"  DXY    vol (std ret %): {dxy_vol:.3f}%")
    print(f"  Ratio XAU/DXY: {xau_vol/dxy_vol:.1f}x")

    # -- Directional analysis --
    print(f"\n  --- DIRECTIONAL ---")
    dxy_up   = dxy_close.diff() > 0
    dxy_down = dxy_close.diff() < 0

    xau_when_dxy_up   = xau_ret[dxy_up.shift(1).fillna(False)]
    xau_when_dxy_down = xau_ret[dxy_down.shift(1).fillna(False)]

    n_up   = len(xau_when_dxy_up)
    n_down = len(xau_when_dxy_down)

    print(f"  Prev bar DXY UP   -> XAUUSD next bar ret: {xau_when_dxy_up.mean():>+8.3f}%  "
          f"(n={n_up}, std={xau_when_dxy_up.std():.3f}%)")
    print(f"  Prev bar DXY DOWN -> XAUUSD next bar ret: {xau_when_dxy_down.mean():>+8.3f}%  "
          f"(n={n_down}, std={xau_when_dxy_down.std():.3f}%)")

    if n_up > 0:
        xau_up_dxy_up = (xau_when_dxy_up > 0).sum() / n_up * 100
        print(f"  DXY UP   -> XAU UP   : {xau_up_dxy_up:5.1f}% of cases")
    if n_down > 0:
        xau_down_dxy_down = (xau_when_dxy_down < 0).sum() / n_down * 100
        print(f"  DXY DOWN -> XAU DOWN : {xau_down_dxy_down:5.1f}% of cases (anti-corr if <50%)")

    # -- Distribution of XAU return when DXY moves --
    print(f"\n  --- RETURNS CONDITIONAL ON DXY MOVEMENT ---")
    # When DXY has a significant move (> 1 std)
    dxy_std = dxy_ret.std()
    dxy_big_up   = dxy_ret > dxy_std
    dxy_big_down = dxy_ret < -dxy_std

    xau_on_dxy_big_up   = xau_ret[dxy_big_up]
    xau_on_dxy_big_down = xau_ret[dxy_big_down]

    print(f"  DXY strong UP   (> {dxy_std:.3f}%) -> XAU ret: {xau_on_dxy_big_up.mean():>+8.3f}%  "
          f"(n={len(xau_on_dxy_big_up)})")
    print(f"  DXY strong DOWN (< -{dxy_std:.3f}%) -> XAU ret: {xau_on_dxy_big_down.mean():>+8.3f}%  "
          f"(n={len(xau_on_dxy_big_down)})")

print(f"\n{'=' * 100}")
print("  GLOBAL SUMMARY")
print(f"{'=' * 100}")
print("""
  CLASSIC RELATIONSHIP: DXY UP -> XAUUSD DOWN (negative correlation)
  Gold is priced in USD. Stronger dollar = cheaper gold in USD.

  If correlation near -1: strong, reliable inverse relationship.
  If correlation near 0: assets move independently on this period.
  If correlation positive: unusual -- gold rising with dollar.
""")

mt5.shutdown()
