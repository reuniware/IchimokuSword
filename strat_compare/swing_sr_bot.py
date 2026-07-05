# strat_compare/swing_sr_bot.py — Live Trading Bot Swing_SR (MetaTrader 5)
# =============================================================================
# Robot de trading automatise pour la strategie Swing_SR.
# Compatible avec TOUS les brokers MetaTrader 5 (quel que soit le serveur).
#
# Usage:
#   python swing_sr_bot.py                           # Mode reel
#   python swing_sr_bot.py --dry-run                 # Simulation (pas d'ordres)
#   python swing_sr_bot.py --symbols EURUSD,GBPUSD   # Symboles specifiques
#   python swing_sr_bot.py --tf H4 --risk 1.5        # H4, risque 1.5%
#
# =============================================================================

import os
import sys
import time
import logging
from datetime import datetime, timezone
from argparse import ArgumentParser
from typing import Dict, List, Optional, Tuple

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Ajouter le projet parent au path pour charger .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import load_env

UTC = timezone.utc

# Parametres par defaut (identiques a ceux du backtest gagnant)
DEFAULT_CONFIG = {
    "symbols": ["EURUSD", "GBPUSD", "XAUUSD"],
    "timeframe": "H1",
    "swing_window": 20,
    "proximity_atr": 0.8,
    "sl_atr": 1.5,
    "tp_atr": 2.0,
    "atr_period": 14,
    "risk_pct": 2.0,            # % du capital risque par trade
    "magic_number": 250706,     # identifiant unique pour nos ordres
    "max_spread_pct": 0.05,     # spread max autorise (rejette si superieur)
    "deviation_pts": 50,        # deviation acceptee (en points)
    "min_bars": 300,            # barres minimum pour swing_window*6+50
    "max_positions": 3,         # max positions simultanees (tous symboles)
    "cooldown_bars": 5,         # barres minimum entre 2 entrees sur meme symbole
    "fill_policy": "IOC",       # IOC ou RETURN (IOC prioritaire, fallback RETURN)
    "daily_loss_limit": 485.0,  # FTMO: perte max par jour en $ (marge 3% vs $500)
}


# =============================================================================
# Indicateurs (meme logique que signals.py, adaptee pour usage temps reel)
# =============================================================================

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> pd.Series:
    """ATR avec lissage Wilder."""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def find_swing_points(high: pd.Series, low: pd.Series, window: int = 20
                      ) -> Tuple[pd.Series, pd.Series]:
    """Detecte les swing highs et swing lows."""
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


def detect_signal(df: pd.DataFrame, config: dict) -> Optional[dict]:
    """Detecte un signal Swing_SR sur la derniere barre.
    
    Retourne un dict: {direction, entry_price, sl_price, tp_price, support/resistance}
    ou None si pas de signal.
    """
    swing_window = config["swing_window"]
    proximity_atr = config["proximity_atr"]
    sl_atr = config["sl_atr"]
    tp_atr = config["tp_atr"]
    atr_period = config["atr_period"]

    close = df['close']
    high = df['high']
    low = df['low']
    opens = df['open']
    n = len(df)

    atr = compute_atr(high, low, close, atr_period)
    is_swing_high, is_swing_low = find_swing_points(high, low, swing_window)

    # Avant-derniere barre (derniere barre COMPLETEE — pas la barre en cours)
    # n-1 = barre en cours (incomplete), n-2 = derniere bougie fermee
    i = n - 2
    a = atr.iloc[i]
    if pd.isna(a) or a == 0:
        return None

    prox = proximity_atr * a
    curr_close = close.iloc[i]
    curr_high = high.iloc[i]
    curr_low = low.iloc[i]
    curr_open = opens.iloc[i]

    # Chercher le swing low le plus recent (support)
    lb = max(0, i - swing_window * 4)
    past_lows = low.iloc[lb:i]
    swing_low_mask = is_swing_low.iloc[lb:i]
    recent_swing_lows = past_lows[swing_low_mask]

    # Chercher le swing high le plus recent (resistance)
    past_highs = high.iloc[lb:i]
    swing_high_mask = is_swing_high.iloc[lb:i]
    recent_swing_highs = past_highs[swing_high_mask]

    # Signal LONG
    if len(recent_swing_lows) > 0:
        support = recent_swing_lows.iloc[-1]
        dist_to_support = curr_low - support
        if 0 < dist_to_support < prox:
            if curr_close > curr_open:  # bougie haussiere
                return {
                    "direction": "LONG",
                    "entry_price": curr_close,
                    "sl_price": support - sl_atr * a,
                    "tp_price": curr_close + tp_atr * a,
                    "level": support,
                    "level_type": "support",
                    "atr": a,
                }

    # Signal SHORT (seulement si pas deja LONG)
    if len(recent_swing_highs) > 0:
        resistance = recent_swing_highs.iloc[-1]
        dist_to_res = resistance - curr_high
        if 0 < dist_to_res < prox:
            if curr_close < curr_open:  # bougie baissiere
                return {
                    "direction": "SHORT",
                    "entry_price": curr_close,
                    "sl_price": resistance + sl_atr * a,
                    "tp_price": curr_close - tp_atr * a,
                    "level": resistance,
                    "level_type": "resistance",
                    "atr": a,
                }

    return None


# =============================================================================
# Bot principal
# =============================================================================

class SwingSRBot:
    """Robot de trading Swing_SR pour MetaTrader 5."""

    def __init__(self, config: dict, dry_run: bool = False):
        self.cfg = config
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        self.tf_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
        }
        self.tf_mt5 = self.tf_map.get(self.cfg["timeframe"])
        if self.tf_mt5 is None:
            raise ValueError(f"Timeframe inconnu: {self.cfg['timeframe']}")

        # Tracking (timestamp-based pour eviter les problemes d'index)
        self.last_entry_time: Dict[str, pd.Timestamp] = {}
        self.last_signal_dir: Dict[str, str] = {}
        self.total_trades = 0
        self.running = True
        # FTMO daily loss tracking
        self._daily_pnl_date = datetime.now(UTC).date()
        self._start_of_day_balance = 0.0  # sera initialise par _reset_daily_if_new_day
        self._daily_closed_pnl = 0.0  # legacy
        self._daily_loss_hit = False  # True si la limite est atteinte aujourd'hui

    def _setup_logger(self) -> logging.Logger:
        """Configure le logger."""
        logger = logging.getLogger("SwingSRBot")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            logger.addHandler(h)
        return logger

    # ------------------------------------------------------------------
    # Connexion MT5
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Etablit la connexion MT5."""
        load_env()
        if not mt5.initialize():
            self.logger.error("Echec mt5.initialize()")
            return False

        account = mt5.account_info()
        if account is None:
            self.logger.error("Impossible d'obtenir les infos du compte")
            mt5.shutdown()
            return False

        self.logger.info(
            "MT5 connecte | Broker: %s | Login: %s | Balance: %.2f %s | "
            "Levier: 1:%s",
            account.company, account.login, account.balance,
            account.currency, account.leverage
        )
        return True

    def disconnect(self):
        """Ferme la connexion MT5."""
        mt5.shutdown()
        self.logger.info("MT5 deconnecte")

    # ------------------------------------------------------------------
    # Donnees
    # ------------------------------------------------------------------

    def fetch_bars(self, symbol: str) -> Optional[pd.DataFrame]:
        """Recupere les dernieres barres pour un symbole."""
        if not mt5.symbol_select(symbol, True):
            self.logger.warning("%s : impossible de selectionner le symbole", symbol)
            return None

        rates = mt5.copy_rates_from_pos(
            symbol, self.tf_mt5, 0, self.cfg["min_bars"]
        )
        if rates is None or len(rates) == 0:
            self.logger.warning("%s : pas de donnees (copy_rates_from_pos)", symbol)
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df.set_index('time', inplace=True)
        df.sort_index(inplace=True)
        return df

    def get_spread_pct(self, symbol: str) -> float:
        """Calcule le spread actuel en % du prix."""
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None:
            return 999
        if tick.ask <= 0:
            return 999
        return (tick.ask - tick.bid) / tick.ask * 100

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self, symbol: Optional[str] = None) -> List[dict]:
        """Retourne les positions ouvertes par ce bot (filtre magic number)."""
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return []
        return [
            {
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT",
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
                "comment": p.comment,
            }
            for p in positions
            if p.magic == self.cfg["magic_number"]
        ]

    def close_position(self, ticket: int, symbol: str, volume: float,
                       position_type: str) -> bool:
        """Ferme une position par son ticket."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False

        if self.dry_run:
            self.logger.info("[DRY-RUN] Fermeture #%d %s (%s)", ticket, symbol, position_type)
            return True

        close_type = (mt5.ORDER_TYPE_SELL if position_type == "LONG"
                      else mt5.ORDER_TYPE_BUY)
        close_price = tick.bid if position_type == "LONG" else tick.ask

        def _close_order(fill_policy):
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": close_type,
                "position": ticket,
                "price": close_price,
                "deviation": self.cfg["deviation_pts"],
                "magic": self.cfg["magic_number"],
                "comment": "SwingSR close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_policy,
            }
            return mt5.order_send(req)

        fill_ioc = getattr(mt5, 'ORDER_FILLING_IOC', 1)
        fill_return = getattr(mt5, 'ORDER_FILLING_RETURN', 2)

        result = _close_order(fill_ioc)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            if "FILLING" in str(result.comment).upper() or "INVALID" in str(result.comment).upper():
                result = _close_order(fill_return)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error("Fermeture #%d echouee: %s", ticket, result.comment)
            return False

        self.logger.info("Position #%d fermee | %s | Profit=%.2f",
                         ticket, symbol, result.profit if hasattr(result, 'profit') else 0)
        return True

    # ------------------------------------------------------------------
    # Calcul de lot size
    # ------------------------------------------------------------------

    def calculate_lot_size(self, symbol: str, sl_distance_pct: float) -> float:
        """Calcule la taille du lot en fonction du risque.

        Args:
            symbol: Symbole MT5
            sl_distance_pct: Distance du SL en % du prix

        Returns:
            Volume en lots (arrondi au step de lot du symbole)
        """
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)
        if account is None or info is None:
            return 0.01

        # Capital et risque
        balance = account.balance
        risk_amount = balance * self.cfg["risk_pct"] / 100.0

        # Distance SL en points
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or tick.ask <= 0:
            return 0.01
        price = tick.ask
        sl_points = sl_distance_pct / 100.0 * price / info.point

        if sl_points <= 0:
            sl_points = 1

        # Valeur du point par lot
        point_value = info.trade_tick_value
        if point_value <= 0:
            # Fallback: utiliser trade_contract_size (universel, tous actifs)
            contract_size = info.trade_contract_size
            if contract_size <= 0:
                contract_size = 100000  # forex standard
            point_value = price * info.point * contract_size / price

        # Lot size
        lot_size = risk_amount / (sl_points * point_value)
        lot_size = max(info.volume_min, min(lot_size, info.volume_max))

        # Arrondir au step
        step = info.volume_step
        lot_size = round(lot_size / step) * step
        lot_size = max(info.volume_min, min(lot_size, info.volume_max))

        return lot_size

    # ------------------------------------------------------------------
    # Placement d'ordre
    # ------------------------------------------------------------------

    def place_order(self, symbol: str, signal: dict) -> Optional[int]:
        """Place un ordre market avec SL et TP.
        
        Retourne le ticket si succes, None sinon.
        """
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if tick is None or info is None:
            self.logger.error("%s : pas d'info tick/symbol", symbol)
            return None

        # Verifier le spread
        spread_pct = self.get_spread_pct(symbol)
        if spread_pct > self.cfg["max_spread_pct"]:
            self.logger.warning(
                "%s : spread %.4f%% > max %.4f%% — trade ignore",
                symbol, spread_pct, self.cfg["max_spread_pct"]
            )
            return None

        direction = signal["direction"]
        entry_price = signal["entry_price"]
        sl_price = signal["sl_price"]
        tp_price = signal["tp_price"]

        # Distance SL en %
        sl_dist_pct = abs(entry_price - sl_price) / entry_price * 100

        # Lot size
        lot_size = self.calculate_lot_size(symbol, sl_dist_pct)

        # Prix d'execution
        if direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            exec_price = tick.ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            exec_price = tick.bid

        if self.dry_run:
            self.logger.info(
                "[DRY-RUN] %s %s | Lots=%.2f | Entry=%.5f | SL=%.5f | TP=%.5f | "
                "SLdist=%.2f%% | Risk=%.2f",
                symbol, direction, lot_size, exec_price, sl_price, tp_price,
                sl_dist_pct, self.cfg["risk_pct"]
            )
            return 999999  # fake ticket

        # Arrondir les prix selon les digits
        digits = info.digits
        sl_price = round(sl_price, digits)
        tp_price = round(tp_price, digits)

        # --- Fonction helper pour envoyer avec fallback fill policy ---
        def _send_order(fill_policy):
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": exec_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": self.cfg["deviation_pts"],
                "magic": self.cfg["magic_number"],
                "comment": "SwingSR",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_policy,
            }
            return mt5.order_send(req)

        # Essayer IOC d'abord, puis RETURN si IOC non supporte
        fill_ioc = getattr(mt5, 'ORDER_FILLING_IOC', 1)
        fill_return = getattr(mt5, 'ORDER_FILLING_RETURN', 2)

        result = _send_order(fill_ioc)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            # Fallback: ORDER_FILLING_RETURN
            if "FILLING" in str(result.comment).upper() or "INVALID" in str(result.comment).upper():
                self.logger.debug("%s : IOC non supporte, essai RETURN...", symbol)
                result = _send_order(fill_return)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(
                "%s : ordre %s echoue [retcode=%s] — %s",
                symbol, direction, result.retcode, result.comment
            )
            return None

        self.total_trades += 1
        self.logger.info(
            "#%d %s %s | Ticket=%s | Lots=%.2f | Entry=%.5f | "
            "SL=%.5f(%.2f%%) | TP=%.5f",
            self.total_trades, symbol, direction,
            result.order, lot_size, exec_price,
            sl_price, sl_dist_pct, tp_price
        )
        return result.order

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    def _reset_daily_if_new_day(self):
        """Reset le tracking quotidien si on change de jour."""
        today = datetime.now(UTC).date()
        if today != self._daily_pnl_date:
            self._daily_pnl_date = today
            self._daily_loss_hit = False
            account = mt5.account_info()
            self._start_of_day_balance = account.balance if account else 10000.0
            self._daily_closed_pnl = 0.0  # legacy, plus vraiment utilise
            self.logger.info("Nouveau jour FTMO — P&L quotidien reinitialise (balance: %.2f)",
                             self._start_of_day_balance)

    def _get_daily_pnl(self) -> float:
        """Calcule le P&L du jour via la balance (capture TOUT : SL/TP server-side)."""
        account = mt5.account_info()
        if account is None:
            return 0.0
        return account.balance - self._start_of_day_balance

    def run_once(self) -> Dict[str, Optional[dict]]:
        """Execute UNE iteration : scanne tous les symboles, detecte,
        et place les ordres si signal.

        Retourne: {symbol: signal_dict or None}
        """
        # Reset quotidien
        self._reset_daily_if_new_day()

        results = {}
        all_positions = self.get_positions()
        n_positions = len(all_positions)
        daily_limit = self.cfg["daily_loss_limit"]

        # --- Check FTMO daily loss limit ---
        daily_pnl = self._get_daily_pnl()
        if not self._daily_loss_hit and daily_pnl <= -daily_limit:
            self._daily_loss_hit = True
            self.logger.warning(
                "FTMO: LIMITE QUOTIDIENNE ATTEINTE (-$%.0f/$%.0f) — "
                "plus aucun trade aujourd'hui",
                -daily_pnl, daily_limit
            )

        if self._daily_loss_hit:
            self.logger.debug("FTMO: trading bloque (limite quotidienne deja atteinte)")
            return results

        for symbol in self.cfg["symbols"]:
            results[symbol] = None

            # --- Verifier positions existantes pour ce symbole ---
            sym_positions = [p for p in all_positions if p["symbol"] == symbol]

            # --- Verifier si position opposee -> fermer ---
            # (on ne peut pas encore savoir le signal, on verifie apres)

            # --- Fetch data ---
            df = self.fetch_bars(symbol)
            if df is None or len(df) < self.cfg["min_bars"]:
                continue

            # --- Detect signal ---
            signal = detect_signal(df, self.cfg)
            if signal is None:
                continue

            results[symbol] = signal

            # --- Verifier cooldown (base sur les timestamps) ---
            last_entry_ts = self.last_entry_time.get(symbol)
            if last_entry_ts is not None:
                bars_since = len(df.loc[last_entry_ts:]) - 1
                if bars_since < self.cfg["cooldown_bars"]:
                    self.logger.debug("%s : cooldown (dernier trade il y a %d barres)",
                                      symbol, bars_since)
                    continue

            # --- Anti-doublon: pas de signal identique consecutif ---
            last_dir = self.last_signal_dir.get(symbol)
            if last_dir == signal["direction"]:
                self.logger.debug("%s : signal %s ignore (identique au precedent)",
                                  symbol, signal["direction"])
                continue

            # --- Positions existantes ---
            if len(sym_positions) > 0:
                pos = sym_positions[0]
                # Meme direction : on skip
                if pos["type"] == signal["direction"]:
                    self.logger.debug("%s : deja en position %s", symbol, pos["type"])
                    continue
                # Direction opposee : on ferme d'abord
                else:
                    self.logger.info("%s : signal oppose (%s->%s) — fermeture #%d",
                                     symbol, pos["type"], signal["direction"],
                                     pos["ticket"])
                    closed = self.close_position(
                        pos["ticket"], symbol, pos["volume"], pos["type"]
                    )
                    if closed:
                        daily_pnl = self._get_daily_pnl()  # recalcule via balance
                    # Recalculer le nombre de positions
                    all_positions = self.get_positions()
                    n_positions = len(all_positions)

            # --- Max positions ---
            if n_positions >= self.cfg["max_positions"]:
                self.logger.debug("Max positions atteint (%d)", n_positions)
                continue

            # --- FTMO: verifier que l'ordre ne risque pas de depasser la limite ---
            remaining = daily_limit + daily_pnl  # marge restante avant limite
            original_risk = self.cfg["risk_pct"]
            account = mt5.account_info()
            balance = account.balance if account else 10000
            max_risk_abs = original_risk / 100.0 * balance
            if remaining <= 0:
                self.logger.debug("%s : FTMO limite depassee — trade ignore", symbol)
                continue
            if max_risk_abs > remaining:
                safe_risk_pct = remaining / balance * 100
                safe_risk_pct = max(safe_risk_pct, 0.1)
                self.cfg["risk_pct"] = safe_risk_pct
                self.logger.debug("%s : risque reduit %.2f%% -> %.2f%% (limite FTMO)",
                                  symbol, original_risk, self.cfg["risk_pct"])

            try:
                ticket = self.place_order(symbol, signal)
            finally:
                self.cfg["risk_pct"] = original_risk

            if ticket is not None:
                self.last_entry_time[symbol] = df.index[-2]  # timestamp barre signalee
                self.last_signal_dir[symbol] = signal["direction"]

        return results

    def run(self, interval_seconds: int = 60):
        """Boucle principale infinie.

        Args:
            interval_seconds: delai entre chaque scan (defaut: 60s pour H1)
        """
        if not self.connect():
            return

        mode = "DRY-RUN" if self.dry_run else "LIVE"
        self.logger.info(
            "=" * 70 + "\n"
            "  Swing_SR Bot DEMARRE | Mode: %s | %s\n"
            "  Symboles: %s | Timeframe: %s\n"
            "  Swing window: %d | Proximity: %.1f ATR | SL: %.1f ATR | TP: %.1f ATR\n"
            "  Risque: %.1f%% | Max positions: %d | Magic: %d\n"
            "  Intervalle: %ds\n"
            + "=" * 70,
            mode,
            datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            ", ".join(self.cfg["symbols"]),
            self.cfg["timeframe"],
            self.cfg["swing_window"], self.cfg["proximity_atr"],
            self.cfg["sl_atr"], self.cfg["tp_atr"],
            self.cfg["risk_pct"], self.cfg["max_positions"],
            self.cfg["magic_number"],
            interval_seconds
        )

        try:
            while self.running:
                cycle_start = time.time()

                try:
                    results = self.run_once()
                    signals_found = sum(1 for s in results.values() if s is not None)
                    if signals_found > 0:
                        for sym, sig in results.items():
                            if sig:
                                self.logger.info(
                                    "  >> %s %s | Level=%.5f(%s) | Entry=%.5f | "
                                    "SL=%.5f | TP=%.5f | ATR=%.5f",
                                    sym, sig["direction"], sig["level"],
                                    sig["level_type"], sig["entry_price"],
                                    sig["sl_price"], sig["tp_price"], sig["atr"]
                                )
                except Exception as e:
                    self.logger.error("Erreur dans run_once: %s", e)

                # Reconnexion automatique si MT5 deconnecte
                if mt5.terminal_info() is None:
                    self.logger.warning("MT5 deconnecte — tentative reconnexion...")
                    mt5.shutdown()
                    time.sleep(5)
                    if not self.connect():
                        self.logger.error("Reconnexion echouee — arret du bot")
                        break

                elapsed = time.time() - cycle_start
                sleep_time = max(1, interval_seconds - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info("Arret demande par l'utilisateur (Ctrl+C)")
        finally:
            self._print_summary()
            self.disconnect()

    def _print_summary(self):
        """Affiche le resume de la session."""
        positions = self.get_positions()
        balance = mt5.account_info().balance if mt5.account_info() else 0
        self.logger.info(
            "=" * 70 + "\n"
            "  Session terminee\n"
            "  Ordres envoyes: %d | Positions ouvertes: %d | Balance: %.2f\n"
            + "=" * 70,
            self.total_trades, len(positions), balance
        )


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = ArgumentParser(
        description="Swing_SR Live Trading Bot - MetaTrader 5 (tous brokers)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulation : pas d'ordres reels")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Symboles separes par virgule (defaut: EURUSD,GBPUSD,XAUUSD)")
    parser.add_argument("--tf", type=str, default="H1",
                        help="Timeframe (defaut: H1)")
    parser.add_argument("--risk", type=float, default=2.0,
                        help="%% risque par trade (defaut: 2.0)")
    parser.add_argument("--max-positions", type=int, default=3,
                        help="Max positions simultanees (defaut: 3)")
    parser.add_argument("--interval", type=int, default=60,
                        help="Intervalle entre scans en secondes (defaut: 60)")
    parser.add_argument("--swing-window", type=int, default=20,
                        help="Fenetre swing points (defaut: 20)")
    parser.add_argument("--proximity", type=float, default=0.8,
                        help="Proximite S/R en ATR (defaut: 0.8)")
    parser.add_argument("--sl-atr", type=float, default=1.5,
                        help="Stop-loss en ATR (defaut: 1.5)")
    parser.add_argument("--tp-atr", type=float, default=2.0,
                        help="Take-profit en ATR (defaut: 2.0)")
    parser.add_argument("--magic", type=int, default=250706,
                        help="Magic number MT5 (defaut: 250706)")

    args = parser.parse_args()

    # Construire la config
    config = DEFAULT_CONFIG.copy()
    config["timeframe"] = args.tf
    config["risk_pct"] = args.risk
    config["max_positions"] = args.max_positions
    config["swing_window"] = args.swing_window
    config["proximity_atr"] = args.proximity
    config["sl_atr"] = args.sl_atr
    config["tp_atr"] = args.tp_atr
    config["magic_number"] = args.magic

    if args.symbols:
        config["symbols"] = [s.strip() for s in args.symbols.split(",")]

    # Creer et lancer le bot
    bot = SwingSRBot(config, dry_run=args.dry_run)
    bot.run(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
