# strat_compare/dxy_xau_bot.py — Live Trading Bot DXY→XAUUSD H4
# =============================================================================
# Bot cross-asset: DXY.cash H1 fort mouvement → XAUUSD H4 inverse.
# Compatible avec TOUS les brokers MetaTrader 5.
#
# Usage:
#   python dxy_xau_bot.py                          # Mode reel
#   python dxy_xau_bot.py --dry-run                # Simulation
#   python dxy_xau_bot.py --risk 1.5 --cooldown 3  # Risque 1.5%
# =============================================================================

import os, sys, time, logging
from datetime import datetime, timezone
from argparse import ArgumentParser
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

UTC = timezone.utc

DEFAULT_CONFIG = {
    # Actifs
    "dxy_symbol": "DXY.cash",        # Source du signal
    "trade_symbol": "XAUUSD",        # Actif trade
    "dxy_tf": "H1",                  # TF detection DXY
    "trade_tf": "H4",                # TF trading XAUUSD
    "corr_tf": "M15",                # TF pour calcul correlation (resample -> H1)

    # Parametres strategie
    "threshold_std": 1.5,            # Seuil DXY (ecarts-types roulants)
    "std_window": 50,                # Fenetre rolling std DXY
    "sl_atr": 1.5,                   # SL en ATR du TF trading
    "tp_atr": 3.0,                   # TP en ATR du TF trading
    "atr_period": 14,
    "rolling_corr_min": -0.3,       # Corr rolling minimum (< -0.3)
    "h4_sma_period": 20,            # SMA H4 pour filtre tendance DXY
    "cooldown_bars": 2,             # Barres H4 entre signaux

    # Risk management
    "risk_pct": 2.0,
    "magic_number": 260706,
    "max_spread_pct": 0.05,
    "deviation_pts": 50,
    "max_positions": 1,
    "daily_loss_limit": 485.0,

    # Data
    "min_bars_dxy_h1": 300,
    "min_bars_dxy_h4": 100,
    "min_bars_xau_h4": 300,
    "min_bars_xau_corr": 5000,       # XAUUSD M15 pour correlation
}

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
}


# =============================================================================
# Indicateurs
# =============================================================================

def compute_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


# =============================================================================
# Detection de signal
# =============================================================================

def detect_dxy_signal(df_dxy_h1, df_dxy_h4, df_xau_h4, df_xau_corr, config):
    """Detecte un signal DXY fort -> trade XAUUSD inverse.

    df_xau_corr: XAUUSD en TF basse (M15) pour correlation H1.
    Retourne dict signal ou None.
    """
    threshold = config["threshold_std"]
    std_win = config["std_window"]
    sl_atr = config["sl_atr"]
    tp_atr = config["tp_atr"]
    atr_period = config["atr_period"]
    corr_min = config["rolling_corr_min"]
    h4_sma_period = config["h4_sma_period"]

    # --- DXY H1: retour et rolling std (anti-look-ahead) ---
    dxy_close = df_dxy_h1['close']
    dxy_ret = dxy_close.pct_change() * 100
    dxy_std = dxy_ret.rolling(std_win, min_periods=20).std()
    dxy_exp_std = dxy_ret.expanding(min_periods=20).std()
    dxy_std = dxy_std.fillna(dxy_exp_std)

    i_h1 = len(df_dxy_h1) - 2  # derniere barre H1 completee
    if i_h1 < std_win:
        return None
    ret_i = dxy_ret.iloc[i_h1]
    std_i = dxy_std.iloc[i_h1]
    if pd.isna(ret_i) or pd.isna(std_i) or std_i == 0:
        return None

    thresh_i = threshold * std_i

    # Signal
    if ret_i > thresh_i:
        dxy_dir = "UP"
        trade_dir = "SHORT"
    elif ret_i < -thresh_i:
        dxy_dir = "DOWN"
        trade_dir = "LONG"
    else:
        return None

    # --- Filtre 1: Rolling correlation (XAUUSD M15 resample -> H1) ---
    # On utilise df_xau_corr (M15) qu'on resample en H1 pour de vrais returns H1
    xau_h1 = df_xau_corr['close'].resample('1h').last().dropna()
    common = xau_h1.index.intersection(dxy_close.index)
    if len(common) < 21:
        return None
    xau_ret_h1 = xau_h1.loc[common].pct_change() * 100
    dxy_ret_h1 = dxy_close.loc[common].pct_change() * 100
    roll_corr = xau_ret_h1.rolling(20).corr(dxy_ret_h1)
    corr_val = roll_corr.iloc[-1]
    if pd.notna(corr_val) and corr_val > corr_min:
        return None

    # --- Filtre 2: Tendance DXY H4 ---
    dxy_h4_close = df_dxy_h4['close']
    dxy_h4_sma = dxy_h4_close.rolling(h4_sma_period).mean()
    i_h4 = len(df_dxy_h4) - 2
    if i_h4 >= h4_sma_period:
        h4_bullish = dxy_h4_close.iloc[i_h4] > dxy_h4_sma.iloc[i_h4]
        if trade_dir == "SHORT" and not h4_bullish:
            return None
        if trade_dir == "LONG" and h4_bullish:
            return None

    # --- XAUUSD H4: ATR, prix, confirmation bougie ---
    xau_close = df_xau_h4['close']
    xau_high = df_xau_h4['high']
    xau_low = df_xau_h4['low']
    atr = compute_atr(xau_high, xau_low, xau_close, atr_period)

    i_xau = len(df_xau_h4) - 2
    if i_xau < 20:
        return None
    a = atr.iloc[i_xau]
    if pd.isna(a) or a == 0:
        return None

    curr_close = xau_close.iloc[i_xau]
    curr_open = df_xau_h4['open'].iloc[i_xau]

    if trade_dir == "LONG" and not (curr_close > curr_open):
        return None
    if trade_dir == "SHORT" and not (curr_close < curr_open):
        return None

    # SL/TP
    if trade_dir == "LONG":
        sl = curr_close - sl_atr * a
        tp = curr_close + tp_atr * a
    else:
        sl = curr_close + sl_atr * a
        tp = curr_close - tp_atr * a

    return {
        "direction": trade_dir,
        "entry_price": curr_close,
        "sl_price": sl,
        "tp_price": tp,
        "atr": a,
        "dxy_direction": dxy_dir,
        "dxy_ret": ret_i,
        "dxy_threshold": thresh_i,
        "correlation": corr_val,
    }


# =============================================================================
# Bot
# =============================================================================

class DxyXauBot:
    """Robot cross-asset DXY -> XAUUSD H4."""

    def __init__(self, config, dry_run=False):
        self.cfg = config
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        self.tf_dxy = TF_MAP.get(self.cfg["dxy_tf"])
        self.tf_trade = TF_MAP.get(self.cfg["trade_tf"])
        self.tf_corr = TF_MAP.get(self.cfg["corr_tf"], mt5.TIMEFRAME_M15)
        if self.tf_dxy is None or self.tf_trade is None:
            raise ValueError("Timeframe invalide")

        self.total_trades = 0
        self.running = True
        self.last_signal_bar_time = None
        self.last_signal_dir = None

        # FTMO
        self._daily_pnl_date = datetime.now(UTC).date()
        self._start_of_day_balance = 0.0
        self._daily_loss_hit = False

    def _setup_logger(self):
        logger = logging.getLogger("DxyXauBot")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"))
            logger.addHandler(h)
        return logger

    # ---------- Connexion ----------
    def connect(self):
        load_env()
        if not mt5.initialize():
            self.logger.error("Echec mt5.initialize()")
            return False
        account = mt5.account_info()
        if account is None:
            self.logger.error("Pas d'info compte")
            mt5.shutdown()
            return False
        self.logger.info("MT5 connecte | Broker: %s | Login: %s | Balance: %.2f %s | Levier: 1:%s",
                         account.company, account.login, account.balance,
                         account.currency, account.leverage)
        return True

    def disconnect(self):
        mt5.shutdown()
        self.logger.info("MT5 deconnecte")

    # ---------- Data ----------
    def fetch_bars(self, symbol, tf, min_bars):
        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, min_bars)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)
        df.sort_index(inplace=True)
        return df

    def get_spread_pct(self, symbol):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask <= 0:
            return 999
        return (tick.ask - tick.bid) / tick.ask * 100

    # ---------- Positions ----------
    def get_positions(self):
        positions = mt5.positions_get(symbol=self.cfg["trade_symbol"])
        if positions is None:
            return []
        return [{"ticket": p.ticket, "symbol": p.symbol,
                 "type": "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT",
                 "volume": p.volume, "price_open": p.price_open,
                 "sl": p.sl, "tp": p.tp, "profit": p.profit}
                for p in positions if p.magic == self.cfg["magic_number"]]

    def close_position(self, ticket, volume, pos_type):
        symbol = self.cfg["trade_symbol"]
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
        if self.dry_run:
            self.logger.info("[DRY-RUN] Fermeture #%d %s", ticket, pos_type)
            return True

        close_type = mt5.ORDER_TYPE_SELL if pos_type == "LONG" else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos_type == "LONG" else tick.ask

        def _send(fill):
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                   "volume": volume, "type": close_type, "position": ticket,
                   "price": price, "deviation": self.cfg["deviation_pts"],
                   "magic": self.cfg["magic_number"], "comment": "DXY_XAU close",
                   "type_time": mt5.ORDER_TIME_GTC, "type_filling": fill}
            return mt5.order_send(req)

        ioc = getattr(mt5, 'ORDER_FILLING_IOC', 1)
        ret = getattr(mt5, 'ORDER_FILLING_RETURN', 2)

        result = _send(ioc)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            if "FILLING" in str(result.comment).upper():
                result = _send(ret)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error("Fermeture #%d echouee: %s", ticket, result.comment)
            return False
        self.logger.info("#%d ferme | Profit=%.2f", ticket,
                         result.profit if hasattr(result, 'profit') else 0)
        return True

    # ---------- Lot size ----------
    def calculate_lot_size(self, sl_distance_pct):
        symbol = self.cfg["trade_symbol"]
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)
        if account is None or info is None:
            return 0.01
        balance = account.balance
        risk_amount = balance * self.cfg["risk_pct"] / 100.0
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask <= 0:
            return 0.01
        price = tick.ask
        sl_points = sl_distance_pct / 100.0 * price / info.point
        if sl_points <= 0:
            sl_points = 1
        point_value = info.trade_tick_value
        if point_value <= 0:
            contract_size = info.trade_contract_size
            if contract_size <= 0:
                contract_size = 100000
            point_value = price * info.point * contract_size / price
        lot_size = risk_amount / (sl_points * point_value)
        lot_size = max(info.volume_min, min(lot_size, info.volume_max))
        step = info.volume_step
        lot_size = round(lot_size / step) * step
        return max(info.volume_min, min(lot_size, info.volume_max))

    # ---------- Ordre ----------
    def place_order(self, signal):
        symbol = self.cfg["trade_symbol"]
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None:
            self.logger.error("%s: pas d'info tick/symbol", symbol)
            return None

        spread_pct = self.get_spread_pct(symbol)
        if spread_pct > self.cfg["max_spread_pct"]:
            self.logger.warning("%s: spread %.4f%% > max — trade ignore", symbol, spread_pct)
            return None

        direction = signal["direction"]
        sl_price = signal["sl_price"]
        tp_price = signal["tp_price"]

        if direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            exec_price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            exec_price = tick.bid

        # Calculer le risque base sur le prix d'execution REEL (pas le close historique)
        sl_dist_pct = abs(exec_price - sl_price) / exec_price * 100
        lot_size = self.calculate_lot_size(sl_dist_pct)

        if self.dry_run:
            corr_str = f"Corr={signal['correlation']:.3f}" if pd.notna(signal.get('correlation')) else "Corr=N/A"
            self.logger.info("[DRY-RUN] %s %s | Lots=%.2f | Entry=%.2f | SL=%.2f | TP=%.2f "
                             "| SLdist=%.2f%% | DXY=%s(%.3f%%) | %s",
                             symbol, direction, lot_size, exec_price, sl_price, tp_price,
                             sl_dist_pct, signal["dxy_direction"], signal["dxy_ret"], corr_str)
            return 999999

        digits = info.digits
        sl_price = round(sl_price, digits)
        tp_price = round(tp_price, digits)

        def _send(fill):
            req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": symbol,
                   "volume": lot_size, "type": order_type, "price": exec_price,
                   "sl": sl_price, "tp": tp_price,
                   "deviation": self.cfg["deviation_pts"],
                   "magic": self.cfg["magic_number"], "comment": "DXY_XAU",
                   "type_time": mt5.ORDER_TIME_GTC, "type_filling": fill}
            return mt5.order_send(req)

        ioc = getattr(mt5, 'ORDER_FILLING_IOC', 1)
        ret = getattr(mt5, 'ORDER_FILLING_RETURN', 2)

        result = _send(ioc)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            if "FILLING" in str(result.comment).upper():
                result = _send(ret)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error("%s: ordre %s echoue [retcode=%s] — %s",
                              symbol, direction, result.retcode, result.comment)
            return None

        self.total_trades += 1
        self.logger.info("#%d %s %s | Ticket=%s | Lots=%.2f | Entry=%.2f | "
                         "SL=%.2f(%.2f%%) | TP=%.2f | DXY=%s",
                         self.total_trades, symbol, direction, result.order,
                         lot_size, exec_price, sl_price, sl_dist_pct, tp_price,
                         signal["dxy_direction"])
        return result.order

    # ---------- FTMO daily ----------
    def _reset_daily(self):
        today = datetime.now(UTC).date()
        if today != self._daily_pnl_date:
            self._daily_pnl_date = today
            self._daily_loss_hit = False
            account = mt5.account_info()
            self._start_of_day_balance = account.balance if account else 10000.0
            self.logger.info("Nouveau jour FTMO — balance: %.2f", self._start_of_day_balance)

    def _daily_pnl(self):
        account = mt5.account_info()
        if account is None:
            return 0.0
        return account.balance - self._start_of_day_balance

    # ---------- Boucle ----------
    def run_once(self):
        self._reset_daily()
        daily_limit = self.cfg["daily_loss_limit"]
        daily_pnl = self._daily_pnl()

        if not self._daily_loss_hit and daily_pnl <= -daily_limit:
            self._daily_loss_hit = True
            self.logger.warning("FTMO: LIMITE QUOTIDIENNE ATTEINTE (-$%.0f/$%.0f)",
                                -daily_pnl, daily_limit)
        if self._daily_loss_hit:
            self.logger.debug("FTMO: trading bloque (limite atteinte)")
            return None

        # Fetch toutes les donnees (DXY H1, DXY H4, XAUUSD H4, XAUUSD M15 pour corr)
        dxy_h1 = self.fetch_bars(self.cfg["dxy_symbol"], self.tf_dxy,
                                 self.cfg["min_bars_dxy_h1"])
        dxy_h4 = self.fetch_bars(self.cfg["dxy_symbol"], mt5.TIMEFRAME_H4,
                                 self.cfg["min_bars_dxy_h4"])
        xau_h4 = self.fetch_bars(self.cfg["trade_symbol"], self.tf_trade,
                                 self.cfg["min_bars_xau_h4"])
        xau_corr = self.fetch_bars(self.cfg["trade_symbol"], self.tf_corr,
                                   self.cfg["min_bars_xau_corr"])

        if dxy_h1 is None or dxy_h4 is None or xau_h4 is None or xau_corr is None:
            self.logger.debug("Donnees insuffisantes (fetch None)")
            return None
        if len(dxy_h1) < 100 or len(dxy_h4) < 30 or len(xau_h4) < 100 or len(xau_corr) < 500:
            self.logger.debug("Barres insuffisantes: DXY_H1=%d DXY_H4=%d XAU_H4=%d XAU_M15=%d",
                              len(dxy_h1), len(dxy_h4), len(xau_h4), len(xau_corr))
            return None

        # Detect signal
        signal = detect_dxy_signal(dxy_h1, dxy_h4, xau_h4, xau_corr, self.cfg)
        if signal is None:
            return None

        # Cooldown
        if self.last_signal_bar_time is not None:
            bars_since = len(xau_h4.loc[self.last_signal_bar_time:]) - 1
            if bars_since < self.cfg["cooldown_bars"]:
                self.logger.debug("Cooldown: %d/%d barres", bars_since, self.cfg["cooldown_bars"])
                return signal

        # Anti-doublon
        if self.last_signal_dir == signal["direction"]:
            self.logger.debug("Signal %s ignore (identique au precedent)", signal["direction"])
            return signal

        # Positions existantes
        positions = self.get_positions()
        if positions:
            pos = positions[0]
            if pos["type"] == signal["direction"]:
                self.logger.debug("Deja en position %s", pos["type"])
                return signal
            else:
                self.logger.info("Signal oppose (%s -> %s) — fermeture #%d",
                                 pos["type"], signal["direction"], pos["ticket"])
                self.close_position(pos["ticket"], pos["volume"], pos["type"])
                positions = self.get_positions()

        if positions:
            self.logger.debug("Position encore ouverte, skip")
            return signal

        # FTMO: marge restante
        remaining = daily_limit + daily_pnl
        original_risk = self.cfg["risk_pct"]
        account = mt5.account_info()
        balance = account.balance if account else 10000
        max_risk = original_risk / 100.0 * balance
        if remaining <= 0:
            return signal
        if max_risk > remaining:
            self.cfg["risk_pct"] = max(remaining / balance * 100, 0.1)

        try:
            ticket = self.place_order(signal)
        finally:
            self.cfg["risk_pct"] = original_risk

        if ticket is not None:
            self.last_signal_bar_time = xau_h4.index[-2]
            self.last_signal_dir = signal["direction"]

        return signal

    # ---------- Main loop ----------
    def run(self, interval_seconds=300):
        if not self.connect():
            return

        mode = "DRY-RUN" if self.dry_run else "LIVE"
        self.logger.info("=" * 70)
        self.logger.info("  DXY->XAUUSD Bot DEMARRE | Mode: %s | %s", mode,
                         datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
        self.logger.info("  Signal: %s %s | Trading: %s %s | Corr: %s %s",
                         self.cfg["dxy_symbol"], self.cfg["dxy_tf"],
                         self.cfg["trade_symbol"], self.cfg["trade_tf"],
                         self.cfg["trade_symbol"], self.cfg["corr_tf"])
        self.logger.info("  Threshold: %.1fσ | SL: %.1f ATR | TP: %.1f ATR | Risque: %.1f%%",
                         self.cfg["threshold_std"], self.cfg["sl_atr"],
                         self.cfg["tp_atr"], self.cfg["risk_pct"])
        self.logger.info("  Filtres: corr < %.1f | trend H4 DXY SMA%d | Cooldown: %d barres",
                         self.cfg["rolling_corr_min"], self.cfg["h4_sma_period"],
                         self.cfg["cooldown_bars"])
        self.logger.info("=" * 70)

        try:
            while self.running:
                cycle_start = time.time()
                try:
                    signal = self.run_once()
                    if signal:
                        corr_str = f"Corr={signal['correlation']:.3f}" if pd.notna(signal.get('correlation')) else "Corr=N/A"
                        self.logger.info("  >> %s %s | Entry=%.2f | SL=%.2f | TP=%.2f | "
                                         "ATR=%.2f | DXY=%s(%.3f%%) | %s",
                                         self.cfg["trade_symbol"], signal["direction"],
                                         signal["entry_price"], signal["sl_price"],
                                         signal["tp_price"], signal["atr"],
                                         signal["dxy_direction"], signal["dxy_ret"],
                                         corr_str)
                except Exception as e:
                    self.logger.error("Erreur run_once: %s", e)

                if mt5.terminal_info() is None:
                    self.logger.warning("MT5 deconnecte — reconnexion...")
                    mt5.shutdown()
                    time.sleep(5)
                    if not self.connect():
                        self.logger.error("Reconnexion echouee")
                        break

                elapsed = time.time() - cycle_start
                time.sleep(max(1, interval_seconds - elapsed))

        except KeyboardInterrupt:
            self.logger.info("Arret (Ctrl+C)")
        finally:
            positions = self.get_positions()
            balance = mt5.account_info().balance if mt5.account_info() else 0
            self.logger.info("=" * 70)
            self.logger.info("  Session terminee | Trades: %d | Positions: %d | Balance: %.2f",
                             self.total_trades, len(positions), balance)
            self.logger.info("=" * 70)
            self.disconnect()


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = ArgumentParser(description="DXY->XAUUSD H4 Live Trading Bot - MT5")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans ordres reels")
    parser.add_argument("--risk", type=float, default=2.0, help="%% risque par trade (defaut: 2.0)")
    parser.add_argument("--threshold", type=float, default=1.5, help="Seuil DXY en ecarts-types (defaut: 1.5)")
    parser.add_argument("--sl-atr", type=float, default=1.5, help="SL en ATR (defaut: 1.5)")
    parser.add_argument("--tp-atr", type=float, default=3.0, help="TP en ATR (defaut: 3.0)")
    parser.add_argument("--cooldown", type=int, default=2, help="Cooldown en barres H4 (defaut: 2)")
    parser.add_argument("--interval", type=int, default=300, help="Intervalle scan secondes (defaut: 300)")
    parser.add_argument("--magic", type=int, default=260706, help="Magic number MT5 (defaut: 260706)")

    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    config["risk_pct"] = args.risk
    config["threshold_std"] = args.threshold
    config["sl_atr"] = args.sl_atr
    config["tp_atr"] = args.tp_atr
    config["cooldown_bars"] = args.cooldown
    config["magic_number"] = args.magic

    bot = DxyXauBot(config, dry_run=args.dry_run)
    bot.run(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
