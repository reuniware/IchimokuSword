"""
Module de connexion MetaTrader 5.
Pattern Singleton inspiré du projet InelidaMarketScan (mt5_connector.py).
"""

import logging
import time
from typing import List, Optional, Tuple

import MetaTrader5 as mt5

from src.config import MT5Config

logger = logging.getLogger("ichimoku.mt5")


class MT5Connector:
    """Singleton gérant la connexion à MetaTrader 5."""

    _instance: Optional["MT5Connector"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[MT5Config] = None):
        if self._initialized:
            return
        self.config = config or MT5Config()
        self._initialized = True

    # ------------------------------------------------------------------
    # Initialisation / Shutdown
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """Initialise la connexion MT5.

        Stratégie :
        1. D'abord tenter mt5.initialize() sans argument (terminal déjà lancé).
        2. Si échec, utiliser le path et/ou les identifiants configurés.

        Retourne True si la connexion est établie.
        """
        # Étape 1 : tentative simple (terminal déjà en cours d'exécution)
        if mt5.initialize():
            logger.info("Connexion MT5 établie (terminal déjà lancé).")
            return True

        mt5.shutdown()

        # Étape 2 : construire les kwargs avec path et/ou identifiants
        kwargs = {}
        if self.config.path:
            kwargs["path"] = self.config.path
        if self.config.login and self.config.password and self.config.server:
            kwargs["login"] = self.config.login
            kwargs["password"] = self.config.password
            kwargs["server"] = self.config.server

        if not kwargs:
            logger.error("Aucun paramètre de connexion (path ou identifiants).")
            return False

        for attempt in range(1, self.config.max_retries + 1):
            logger.info(
                "Tentative MT5 #%d/%d avec paramètres...",
                attempt, self.config.max_retries
            )
            if mt5.initialize(**kwargs):
                logger.info("Connexion MT5 établie avec paramètres.")
                return True

            error = mt5.last_error()
            logger.warning("Échec tentative #%d : %s", attempt, error)
            mt5.shutdown()
            time.sleep(self.config.retry_delay)

        logger.error("Impossible de se connecter à MT5 après %d tentatives.",
                      self.config.max_retries)
        return False

    def shutdown(self) -> None:
        """Ferme proprement la connexion MT5."""
        mt5.shutdown()
        logger.info("Connexion MT5 fermée.")

    def is_connected(self) -> bool:
        """Vérifie si la connexion MT5 est active."""
        return mt5.terminal_info() is not None

    def ensure_connected(self) -> bool:
        """S'assure que la connexion est active ; tente une reconnexion si nécessaire."""
        if self.is_connected():
            return True
        logger.warning("Connexion perdue, reconnexion...")
        return self.initialize()

    # ------------------------------------------------------------------
    # Symboles
    # ------------------------------------------------------------------

    def select_symbol(self, symbol: str, enable: bool = True) -> bool:
        """Active / désactive un symbole dans le Market Watch."""
        return mt5.symbol_select(symbol, enable)

    def list_all_symbols(self) -> List[str]:
        """Retourne tous les symboles disponibles dans MT5.

        Retourne une liste triée des noms de symboles.
        """
        symbols = mt5.symbols_get()
        if symbols is None:
            logger.warning("Aucun symbole trouvé : MT5 retourne None.")
            return []
        return sorted([s.name for s in symbols])

    def list_market_watch_symbols(self) -> List[str]:
        """Retourne les symboles visibles dans le Market Watch."""
        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return sorted([s.name for s in symbols if s.visible])

    def get_symbol_info(self, symbol: str):
        """Retourne les informations d'un symbole."""
        return mt5.symbol_info(symbol)

    # ------------------------------------------------------------------
    # Données de marché
    # ------------------------------------------------------------------

    def get_rates(self, symbol: str, timeframe: int, count: int = 100,
                  start_pos: int = 0):
        """Récupère les bougies d'un symbole.

        Args:
            symbol: Nom du symbole.
            timeframe: Constante MT5 (ex: mt5.TIMEFRAME_D1).
            count: Nombre de bougies.
            start_pos: Position de départ (0 = plus récente).

        Retourne:
            Un numpy structured array avec time, open, high, low, close,
            tick_volume, spread, real_volume. None si erreur.
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)
        if rates is None:
            error = mt5.last_error()
            logger.debug("Impossible de récupérer les rates pour %s : %s",
                         symbol, error)
        return rates

    def get_symbol_tick(self, symbol: str):
        """Récupère le dernier tick d'un symbole."""
        return mt5.symbol_info_tick(symbol)

    # ------------------------------------------------------------------
    # Compte & Terminal
    # ------------------------------------------------------------------

    def get_account_info(self):
        """Retourne les informations du compte MT5."""
        return mt5.account_info()

    def get_terminal_info(self):
        """Retourne les informations du terminal MT5."""
        return mt5.terminal_info()

    # ------------------------------------------------------------------
    # Context Manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
