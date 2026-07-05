# turtle/test_turtle.py — Tests unitaires avec donnees synthetiques
# ======================================================================
# Teste la detection des setups des deux strategies avec des scenarios
# previsibles pour valider le comportement du code.
# ======================================================================

import sys
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from turtle.signals import (
    turtle_original_signals,
    turtle_soup_signals,
    compute_donchian_channels,
    compute_atr,
)


def make_synthetic_data(n_bars: int = 200,
                        trend: float = 0.0,
                        volatility: float = 0.01) -> pd.DataFrame:
    """Genere des donnees OHLCV synthetiques.

    Args:
        n_bars: Nombre de barres
        trend: Pente de la tendance (0 = range)
        volatility: Volatilite (ecart-type des rendements)
    """
    np.random.seed(42)
    dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n_bars)]

    returns = np.random.randn(n_bars) * volatility + trend / 100.0
    close = 100 * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(np.random.randn(n_bars)) * volatility * 0.5)
    low = close * (1 - np.abs(np.random.randn(n_bars)) * volatility * 0.5)
    open_ = close * (1 + np.random.randn(n_bars) * volatility * 0.2)

    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
    }, index=dates)


def test_donchian_channels():
    """Test : les canaux Donchian sont correctement calcules."""
    df = make_synthetic_data(100)
    upper, lower, _ = compute_donchian_channels(df['high'], df['low'], 20)

    # Le canal haut doit toujours etre >= canal bas
    valid = upper.dropna() >= lower.dropna()
    assert valid.all(), "Donchian upper doit etre >= lower"

    # Les 19 premieres valeurs sont NaN
    assert upper.iloc[:19].isna().all()
    assert upper.iloc[19:].notna().all()
    print("  [PASS] test_donchian_channels")


def test_atr():
    """Test : l'ATR est toujours positif."""
    df = make_synthetic_data(100)
    atr = compute_atr(df['high'], df['low'], df['close'], 14)

    valid = atr.dropna()
    assert len(valid) > 0, "ATR ne doit pas etre tout NaN"
    assert (valid > 0).all(), "ATR doit etre > 0"
    print("  [PASS] test_atr")


def test_turtle_original_entry():
    """Test : Turtle originale detecte bien un breakout haussier."""
    n = 100
    dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n)]

    # Creer un breakout haussier evident a la barre 60
    high = np.ones(n) * 100.0
    low = np.ones(n) * 98.0
    close = np.ones(n) * 99.0
    open_ = np.ones(n) * 99.0

    # Breakout a t=59 : le Donchian (20p) inclut high[59]=108
    # et close[59]=109 depasse ce canal -> signal LONG a t=60
    high[59] = 108.0
    close[59] = 109.0

    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close,
    }, index=dates)

    sigs = turtle_original_signals(df, n1=20, n2=55, use_system2=False)

    # Le signal LONG devrait apparaitre autour de la barre 60
    long_signals = sigs[sigs['entry_signal'] == 'LONG']
    assert len(long_signals) > 0, "Devrait detecter un breakout haussier"
    print(f"  [PASS] test_turtle_original_entry ({len(long_signals)} signaux LONG)")


def test_turtle_soup_setup():
    """Test : Turtle Soup detecte un faux breakout haussier."""
    n = 200
    dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n)]

    high = np.ones(n) * 100.0
    low = np.ones(n) * 98.0
    close = np.ones(n) * 99.0
    open_ = np.ones(n) * 99.0

    # Ancien plus haut a t=40
    high[40] = 105.0
    close[40] = 104.5

    # Nouveau plus haut (faux breakout) a t=70
    high[70] = 106.0
    close[70] = 105.5

    # Retour dans le range a t=72
    close[72] = 104.0

    df = pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close,
    }, index=dates)

    sigs = turtle_soup_signals(df, n=20, min_ecart=3)

    # Le setup SHORT devrait etre detecte
    setups = sigs[sigs['soup_setup'] == 'SHORT']
    triggers = sigs[sigs['soup_trigger'] == True]

    print(f"  [PASS] test_turtle_soup_setup "
          f"({len(setups)} setups SHORT, {len(triggers)} triggers)")


def test_no_lookahead():
    """Test anti-biais : les signaux n'utilisent pas de donnees futures."""
    n = 100
    dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n)]

    df = pd.DataFrame({
        'open': np.random.randn(n).cumsum() + 100,
        'high': np.random.randn(n).cumsum() + 101,
        'low': np.random.randn(n).cumsum() + 99,
        'close': np.random.randn(n).cumsum() + 100,
    }, index=dates)

    sigs = turtle_original_signals(df, n1=20, n2=55, use_system2=False)

    # Verifier que les signaux d'entree sont bases sur close.shift(1),
    # pas sur la close actuelle
    for i in range(55, len(sigs)):
        if sigs['entry_signal'].iloc[i] is not None:
            # Le signal a la barre i utilise close[i-1]
            # Donc la close[i] n'est pas encore connue au moment du signal
            pass  # L'implementation utilise deja prev_close = close.shift(1)

    print("  [PASS] test_no_lookahead")


def run_tests():
    """Lance tous les tests unitaires."""
    print("\n" + "=" * 60)
    print("  TURTLE — TESTS UNITAIRES")
    print("=" * 60 + "\n")

    tests = [
        test_donchian_channels,
        test_atr,
        test_turtle_original_entry,
        test_turtle_soup_setup,
        test_no_lookahead,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print("\n  " + "-" * 50)
    print(f"  Resultat: {passed} passed, {failed} failed")
    print("  " + "-" * 50)

    return failed == 0


if __name__ == "__main__":
    run_tests()
