"""
Module de scan Kijun Sen pour tous les symboles MT5.
"""

import logging
import time
from typing import Callable, List, Optional

import MetaTrader5 as mt5

from src.config import TIMEFRAME_LABELS, ScanConfig
from src.display import print_kijun_results
from src.ichimoku import IchimokuResult, compute_full_ichimoku
from src.mt5_connector import MT5Connector

logger = logging.getLogger("ichimoku.scanner")


class KijunScanner:
    """Scanner qui analyse la proximité du Kijun Sen pour tous les symboles."""

    def __init__(self, connector: MT5Connector, config: ScanConfig):
        self.connector = connector
        self.config = config

    # ------------------------------------------------------------------
    # Scan unique
    # ------------------------------------------------------------------

    def scan_symbol(self, symbol: str, timeframe: int) -> Optional[IchimokuResult]:
        """Analyse un symbole sur un timeframe donné.

        Args:
            symbol: Nom du symbole.
            timeframe: Constante MT5 (mt5.TIMEFRAME_*).

        Retourne:
            IchimokuResult ou None si données insuffisantes.
        """
        # S'assurer que le symbole est sélectionné
        if not self.connector.select_symbol(symbol, True):
            logger.debug("Impossible de sélectionner %s", symbol)
            return None

        # Récupérer les données (besoin de plus de bougies pour Chikou/Senkou)
        needed_bars = max(self.config.min_bars, self.config.kijun_period + 30)
        rates = self.connector.get_rates(symbol, timeframe, count=needed_bars)
        if rates is None or len(rates) < self.config.kijun_period + 5:
            return None

        # Extraire les colonnes
        highs = rates["high"]
        lows = rates["low"]
        closes = rates["close"]
        opens = rates["open"]

        # Prix actuel via tick
        current_price = float(closes[-1])
        tick = self.connector.get_symbol_tick(symbol)
        if tick is not None:
            current_price = (tick.bid + tick.ask) / 2.0

        # Analyse Ichimoku complete (5 elements)
        timeframe_label = TIMEFRAME_LABELS.get(timeframe, str(timeframe))
        result = compute_full_ichimoku(
            symbol=symbol,
            timeframe_label=timeframe_label,
            close_price=current_price,
            highs=highs,
            lows=lows,
            closes=closes,
            opens=opens,
            kijun_period=self.config.kijun_period,
        )
        return result

    def scan_all(self, symbols: Optional[List[str]] = None,
                 progress_callback: Optional[Callable] = None,
                 filter_fn: Optional[Callable] = None) -> List[IchimokuResult]:
        """Scanne tous les symboles sur tous les timeframes configurés.

        Args:
            symbols: Liste de symboles à scanner. Si None, tous les symboles.
            progress_callback: Fonction appelée après chaque symbole.
            filter_fn: Fonction de filtrage des résultats (ex: seuil de distance).

        Retourne:
            Liste des IchimokuResult pour les symboles/timeframes analysés.
        """
        # Résoudre la liste des symboles
        if symbols is None:
            symbols = self.connector.list_all_symbols()
            if not symbols:
                logger.error("Aucun symbole disponible dans MT5.")
                return []
            logger.info("%d symboles disponibles dans MT5.", len(symbols))

        all_results: List[IchimokuResult] = []
        total = len(symbols) * len(self.config.timeframes)
        processed = 0

        for symbol in symbols:
            for tf in self.config.timeframes:
                result = self.scan_symbol(symbol, tf)
                processed += 1

                if result is not None:
                    if filter_fn is None or filter_fn(result):
                        all_results.append(result)

                if progress_callback is not None:
                    progress_callback(processed, total, symbol, tf)

        # Trier par distance au Kijun (les plus proches en premier)
        all_results.sort(key=lambda r: r.distance_pct)

        return all_results

    # ------------------------------------------------------------------
    # Mode Watch (continu)
    # ------------------------------------------------------------------

    def watch(self, symbols: Optional[List[str]] = None,
              threshold: float = 1.0,
              display_fn: Optional[Callable] = None,
              stop_event=None):
        """Boucle de scan en continu.

        Args:
            symbols: Liste de symboles. Si None, tous les symboles.
            threshold: Seuil de distance au Kijun pour l'alerte (%).
            display_fn: Fonction d'affichage appelée à chaque cycle.
            stop_event: threading.Event pour arrêter la boucle.
        """
        logger.info("Démarrage du mode WATCH (intervalle: %.1fs, seuil: %.2f%%)",
                    self.config.watch_interval_sec, threshold)

        def proximity_filter(r: IchimokuResult) -> bool:
            return r.distance_pct <= threshold

        while True:
            if stop_event is not None and stop_event.is_set():
                logger.info("Watch arrêté par signal.")
                break

            try:
                results = self.scan_all(
                    symbols=symbols,
                    filter_fn=proximity_filter,
                )

                if display_fn is not None:
                    display_fn(results)
                else:
                    self._default_display(results)

            except Exception as exc:
                logger.error("Erreur durant le scan : %s", exc)

            # Pause avant le prochain cycle
            time.sleep(self.config.watch_interval_sec)

    @staticmethod
    def _default_display(results: List[IchimokuResult]) -> None:
        """Affichage console par défaut."""
        print_kijun_results(results)
