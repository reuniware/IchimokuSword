# strat_compare/_trace_verify.py — Trace manuel pas a pas
# Verification qu'un trade Swing_SR est calcule correctement
import MetaTrader5 as mt5
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

load_env()
mt5.initialize()

# XAUUSD H4
rates = mt5.copy_rates_from_pos('XAUUSD', mt5.TIMEFRAME_H4, 0, 2000)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
df.set_index('time', inplace=True)
df.sort_index(inplace=True)

start = pd.Timestamp('2026-01-01', tz='UTC')
end = pd.Timestamp('2026-07-03', tz='UTC')
df = df.loc[start:end].copy()

from strat_compare.config import COSTS
from strat_compare.signals import swing_sr_signals
from strat_compare.engine import run_backtest, result_summary

signals = swing_sr_signals(df)
print(f"Data: {len(df)} bars, {df.index[0]} -> {df.index[-1]}")
print(f"Signals: {(signals['entry_signal'].notna()).sum()} signals")

# First 5 signals
sig_mask = signals['entry_signal'].notna()
sig_df = signals.loc[sig_mask, ['entry_signal', 'sl_price', 'tp_price', 'atr']].head(10)
print("\n--- First 10 signals ---")
for idx, row in sig_df.iterrows():
    bar = df.loc[idx]
    print(f"  {idx}: {row['entry_signal']:6s} C={bar['close']:.2f} O={bar['open']:.2f} "
          f"H={bar['high']:.2f} L={bar['low']:.2f} "
          f"SL={row['sl_price']:.2f} TP={row['tp_price']:.2f} ATR={row['atr']:.2f}")

# Backtest
print("\n--- BACKTEST ---")
result = run_backtest(df, signals, 'XAUUSD', 'Swing_SR')
result.timeframe = 'H4'
print(result_summary(result))

# Trace first 3 trades in detail
print("\n--- TRACE DETAILED: First 3 trades ---")
for i, t in enumerate(result.trades[:3]):
    print(f"\nTrade #{i+1}: {t.direction}")
    print(f"  Entry: {t.entry_time} @ {t.entry_price:.2f} (cost-adjusted)")
    print(f"  Exit:  {t.exit_time} @ {t.exit_price:.2f} (cost-adjusted)")
    print(f"  PnL:   {t.pnl_pct:.4f}% = ${t.pnl_abs:.2f}")
    print(f"  Reason: {t.exit_reason} | Costs: {t.costs_pct:.4f}%")

    # Find the raw bar at entry
    entry_bar = df.loc[t.entry_time]
    print(f"  Entry bar: O={entry_bar['open']:.2f} H={entry_bar['high']:.2f} "
          f"L={entry_bar['low']:.2f} C={entry_bar['close']:.2f}")

    # Find signal at entry
    if t.entry_time in signals.index:
        sig_row = signals.loc[t.entry_time]
        print(f"  Signal: SL={sig_row['sl_price']:.2f} TP={sig_row['tp_price']:.2f} "
              f"ATR={sig_row['atr']:.2f}")

    exit_bar = df.loc[t.exit_time]
    print(f"  Exit bar:  O={exit_bar['open']:.2f} H={exit_bar['high']:.2f} "
          f"L={exit_bar['low']:.2f} C={exit_bar['close']:.2f}")

    # Manual PnL verification
    # Le exit_price du trade est DEJA cost-adjusted. On reverse-engineer le raw exit.
    costs = COSTS.get('XAUUSD', {"spread_pct": 0.02, "slippage_pct": 0.02})
    total_pct = (costs["spread_pct"] + costs["slippage_pct"]) / 100.0

    # entry_price est cost-adjusted, entry_price_raw est le close brut
    raw_entry = entry_bar['close']
    exit_price_cost = t.exit_price  # deja cost-adjusted

    if t.direction == 'LONG':
        # entry: raw * (1+costs), exit: raw * (1-costs)
        # reverse: raw_exit = exit_price_cost / (1 - costs)
        raw_exit_used = exit_price_cost / (1 - total_pct)
        raw_entry_cost = raw_entry * (1 + total_pct)
        manual_pnl = (exit_price_cost / raw_entry_cost - 1) * 100
    else:
        # SHORT: entry: raw * (1-costs), exit: raw * (1+costs)
        raw_exit_used = exit_price_cost / (1 + total_pct)
        raw_entry_cost = raw_entry * (1 - total_pct)
        manual_pnl = -(exit_price_cost / raw_entry_cost - 1) * 100

    # Verifier si exit etait au close ou SL/TP
    close_at_exit = exit_bar['close']
    low_at_exit = exit_bar['low']
    high_at_exit = exit_bar['high']
    used_close = abs(raw_exit_used - close_at_exit) < 0.01
    used_low = abs(raw_exit_used - low_at_exit) < 0.01
    used_high = abs(raw_exit_used - high_at_exit) < 0.01
    price_source = "CLOSE" if used_close else ("LOW(SL)" if used_low else ("HIGH(TP)" if used_high else f"OTHER({raw_exit_used:.2f})"))

    print(f"  Engine exit_price_cost={exit_price_cost:.2f} -> raw_exit_used={raw_exit_used:.2f} (source: {price_source})")
    print(f"  Exit bar: C={close_at_exit:.2f} L={low_at_exit:.2f} H={high_at_exit:.2f} Reason={t.exit_reason}")
    print(f"  MANUAL verify: entry_cost={raw_entry_cost:.2f} exit_cost={exit_price_cost:.2f} manual_pnl={manual_pnl:.4f}%")
    print(f"  Engine pnl:    {t.pnl_pct:.4f}%  ->  {'MATCH' if abs(manual_pnl - t.pnl_pct) < 0.001 else 'MISMATCH!'}")

mt5.shutdown()
print("\nDone.")
