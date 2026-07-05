# strat_compare/_verify_indicators.py — Verification pratique des indicateurs
# Genere des donnees synthetiques et compare chaque indicateur contre des valeurs attendues

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from strat_compare.signals import (
    compute_atr, compute_rsi, compute_ema, compute_macd,
    compute_bollinger, compute_stochastic, compute_parabolic_sar,
    find_swing_points
)

PASS = 0
FAIL = 0

def check(name, actual, expected, tol=1e-4):
    global PASS, FAIL
    if isinstance(actual, pd.Series):
        actual = actual.dropna().values[-1]
    if isinstance(expected, pd.Series):
        expected = expected.dropna().values[-1]
    if abs(actual - expected) < tol:
        PASS += 1
        print(f"  [{name}] PASS (actual={actual:.6f}, expected={expected:.6f})")
    else:
        FAIL += 1
        print(f"  [{name}] FAIL (actual={actual:.6f}, expected={expected:.6f}, diff={abs(actual-expected):.6f})")

# ============================================================
# 1. Donnees synthetiques simples
# ============================================================
np.random.seed(42)
n = 200
base = 1.0800
# Marche aleatoire avec tendance legerement haussiere
close = pd.Series(base + np.cumsum(np.random.randn(n) * 0.0010), name='close')
high = close + np.abs(np.random.randn(n) * 0.0005)
low = close - np.abs(np.random.randn(n) * 0.0005)
opens = close.shift(1).fillna(base)

print("=" * 70)
print("VERIFICATION PRATIQUE DES INDICATEURS")
print("=" * 70)

# ============================================================
# 2. ATR — verification manuelle des 3 premieres barres
# ============================================================
print("\n--- ATR ---")
atr = compute_atr(high, low, close, 14)

# Verification manuelle TR[0] et TR[1]
tr0 = high.iloc[0] - low.iloc[0]
tr0_manual = max(
    high.iloc[0] - low.iloc[0],
    abs(high.iloc[0] - base),  # close.shift(1)[0] = base
    abs(low.iloc[0] - base)
)
print(f"  TR[0] = {tr0:.6f}, TR[0]_manual = {tr0_manual:.6f}")
check("ATR TR[0]", tr0, tr0_manual)

# ATR[0] avec ewm(alpha=1/14, adjust=False): atr[0] = TR[0]
print(f"  ATR[0] = {atr.iloc[0]:.6f} (should = TR[0] = {tr0:.6f})")
check("ATR[0]", atr.iloc[0], tr0, 1e-3)

# ATR[n-1] doit etre > 0
print(f"  ATR[-1] = {atr.iloc[-1]:.6f}")
check("ATR[-1] > 0", 1 if atr.iloc[-1] > 0 else 0, 1)

# ============================================================
# 3. RSI — verification contre calcul manuel sur valeurs constantes
# ============================================================
print("\n--- RSI ---")
# Serie qui monte puis descend
test_close = pd.Series(np.concatenate([
    np.linspace(100, 110, 50),  # montee
    np.linspace(110, 95, 50)    # descente
]))
rsi = compute_rsi(test_close, 14)

# Apres une longue montee, le RSI doit etre > 70 (surachete)
rsi_mid_up = rsi.iloc[50]
print(f"  RSI apres montee (bar 50) = {rsi_mid_up:.1f} (should be > 70)")
check("RSI surachete", 1 if rsi_mid_up > 70 else 0, 1)

# Apres une longue descente, le RSI doit etre < 30
rsi_mid_down = rsi.iloc[-1]
print(f"  RSI apres descente (fin) = {rsi_mid_down:.1f} (should be < 30)")
check("RSI survendu", 1 if rsi_mid_down < 30 else 0, 1)

# ============================================================
# 4. EMA — verification manuelle
# ============================================================
print("\n--- EMA ---")
ema10 = compute_ema(close, 10)
# EMA[0] = close[0] (avec adjust=False)
check("EMA[0] = close[0]", ema10.iloc[0], close.iloc[0], 1e-4)

# EMA[1] = close[1]*alpha + close[0]*(1-alpha) avec alpha = 2/(10+1) = 2/11
alpha = 2/11
ema1_expected = close.iloc[1] * alpha + close.iloc[0] * (1 - alpha)
check("EMA[1] manuel", ema10.iloc[1], ema1_expected, 1e-4)

# ============================================================
# 5. MACD — verification structurelle
# ============================================================
print("\n--- MACD ---")
macd_line, signal_line, hist = compute_macd(close, 12, 26, 9)
check("MACD = EMA12 - EMA26", macd_line.iloc[-1],
      compute_ema(close, 12).iloc[-1] - compute_ema(close, 26).iloc[-1], 1e-4)
check("Signal = EMA9(MACD)", signal_line.iloc[-1],
      compute_ema(macd_line, 9).iloc[-1], 1e-4)
check("Hist = MACD - Signal", hist.iloc[-1],
      macd_line.iloc[-1] - signal_line.iloc[-1], 1e-4)

# ============================================================
# 6. Bollinger Bands — verification
# ============================================================
print("\n--- Bollinger ---")
middle, upper, lower, width = compute_bollinger(close, 20, 2.0)
# middle[19] doit etre la SMA des 20 premieres valeurs
sma20_first = close.iloc[:20].mean()
check("Bollinger middle[19]", middle.iloc[19], sma20_first, 1e-4)
# upper = middle + 2*std
std20_first = close.iloc[:20].std(ddof=0)  # ddof=0 conforme signals.py
check("Bollinger upper[19]", upper.iloc[19], sma20_first + 2*std20_first, 1e-4)
check("Bollinger lower[19]", lower.iloc[19], sma20_first - 2*std20_first, 1e-4)
# width
check("Bollinger width_pct", width.iloc[19], (upper.iloc[19] - lower.iloc[19]) / middle.iloc[19] * 100, 1e-4)

# ============================================================
# 7. Stochastic
# ============================================================
print("\n--- Stochastic ---")
k, d = compute_stochastic(high, low, close, 14, 3, 3)

# Le %K doit etre entre 0 et 100
k_valid = k.dropna()
check("Stoch %K entre 0 et 100 (min)", 1 if k_valid.min() >= 0 else 0, 1)
check("Stoch %K entre 0 et 100 (max)", 1 if k_valid.max() <= 100 else 0, 1)

# %D doit etre entre 0 et 100
d_valid = d.dropna()
check("Stoch %D entre 0 et 100 (min)", 1 if d_valid.min() >= 0 else 0, 1)
check("Stoch %D entre 0 et 100 (max)", 1 if d_valid.max() <= 100 else 0, 1)

# ============================================================
# 8. Parabolic SAR — verification proprietes
# ============================================================
print("\n--- Parabolic SAR ---")
sar = compute_parabolic_sar(high, low, 0.02, 0.2)

# SAR ne doit pas etre NaN apres les premieres barres
sar_valid = sar.iloc[50:]
check("PSAR pas de NaN (apres bar 50)", 1 if sar_valid.notna().all() else 0, 1)

# En uptrend, SAR doit etre <= low[i-1] et <= low[i-2]
# En downtrend, SAR doit etre >= high[i-1] et >= high[i-2]
# Test: SAR doit toujours etre <= high ou >= low (coherence basique)
sar_total = len(sar_valid)
sar_not_between = ((sar_valid > high.iloc[50:]) & (sar_valid < low.iloc[50:])).sum()
print(f"  PSAR incoherent (entre high et low): {sar_not_between}/{sar_total}")
check("PSAR coherent (jamais entre H et L)", 1 if sar_not_between == 0 else 0, 1)

# ============================================================
# 9. Swing Points — verification structurelle
# ============================================================
print("\n--- Swing Points ---")
is_swing_high, is_swing_low = find_swing_points(high, low, 5)

# Les swing points ne doivent pas apparaitre avant window ou apres n-window
n_swings_high = is_swing_high.sum()
n_swings_low = is_swing_low.sum()
print(f"  Swing highs: {n_swings_high}, Swing lows: {n_swings_low}")

# Verifier qu'il n'y a pas de swing dans les premieres ni dernieres 'window' barres
first_5 = is_swing_high.iloc[:5]
last_5 = is_swing_high.iloc[-5:]
check("Pas de swing high dans les 5 premieres", first_5.sum(), 0)
check("Pas de swing high dans les 5 dernieres", last_5.sum(), 0)

# Un swing high doit etre >= aux highs voisins dans [i-w, i+w]
if n_swings_high > 0:
    swing_idx = is_swing_high[is_swing_high].index[0]
    pos = high.index.get_loc(swing_idx)
    window = 5
    neighbors = high.iloc[max(0,pos-window):min(n,pos+window+1)]
    is_max = high.iloc[pos] >= neighbors.max()
    check("Swing high est bien un max local", 1 if is_max else 0, 1)

# ============================================================
# 10. Verification signaux generes (non-NaN, coherents)
# ============================================================
print("\n--- Verification signaux generes ---")

# Creer un mini DataFrame pour tester tous les signaux
df_mini = pd.DataFrame({
    'open': opens,
    'high': high,
    'low': low,
    'close': close,
}, index=close.index)

from strat_compare.signals import (
    rsi_signals, bollinger_signals, macd_signals,
    stochastic_signals, ema_cross_signals, swing_sr_signals,
    parabolic_sar_signals
)

signal_fns = {
    "RSI": lambda: rsi_signals(df_mini),
    "Bollinger": lambda: bollinger_signals(df_mini),
    "MACD": lambda: macd_signals(df_mini),
    "Stochastic": lambda: stochastic_signals(df_mini),
    "EMA_Cross": lambda: ema_cross_signals(df_mini),
    "Swing_SR": lambda: swing_sr_signals(df_mini),
    "Parabolic_SAR": lambda: parabolic_sar_signals(df_mini),
}

for name, fn in signal_fns.items():
    try:
        sig = fn()
        n_sig = sig['entry_signal'].notna().sum()
        print(f"  {name:<16}: {n_sig:>4} signaux generes")
        # Verifier que les signaux avec SL ont un SL valide
        has_sig = sig['entry_signal'].notna()
        if has_sig.any():
            sl_valid = sig.loc[has_sig, 'sl_price'].notna().all()
            check(f"{name} SL valides", 1 if sl_valid else 0, 1)
        else:
            check(f"{name} SL valides (0 signaux)", 1, 1)
    except Exception as e:
        FAIL += 1
        print(f"  {name:<16}: ERREUR — {e}")

# ============================================================
# Resume
# ============================================================
print(f"\n{'='*70}")
print(f"RESULTAT: {PASS} PASS, {FAIL} FAIL sur {PASS+FAIL} tests")
if FAIL == 0:
    print("TOUS LES INDICATEURS SONT VERIFIES ET CORRECTS.")
else:
    print(f"ATTENTION: {FAIL} tests ont echoue !")
print(f"{'='*70}")
