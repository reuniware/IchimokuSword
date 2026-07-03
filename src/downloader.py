"""
downloader.py - Telechargement historique de donnees MT5
========================================================
Inspire de download_historical.py du projet InelidaMarketScan.

Utilise MT5Connector pour la connexion et copy_rates_from_pos
(compatible FTMO, pas de bug timezone serveur).

Sauvegarde en JSON dans le dossier reports/.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.display import BOLD, CYAN, DIM, GREEN, RESET, YELLOW, format_px
from src.mt5_connector import MT5Connector

logger = logging.getLogger("ichimoku.downloader")

UTC = timezone.utc

# Timeframes supportes avec leurs constantes MT5
HISTORICAL_TIMEFRAMES = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M6": 6,
    "M10": 10,
    "M12": 12,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}


@dataclass
class DownloadResult:
    """Resultat du telechargement."""
    symbol: str
    timeframe: str
    total_bars: int
    start_date: str
    end_date: str
    broker: str = ""
    output_path: str = ""
    file_size_kb: float = 0.0
    price_high: float = 0.0
    price_low: float = 0.0
    first_bar_time: str = ""
    last_bar_time: str = ""


class HistoricalDownloader:
    """Telecharge l'historique des donnees depuis MetaTrader 5."""

    def __init__(self, connector: MT5Connector):
        self.connector = connector

    def download(
        self,
        symbol: str,
        timeframe_str: str = "M3",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_bars: int = 80000,
        output_dir: str = "reports",
    ) -> Optional[DownloadResult]:
        """Telecharge les donnees historiques pour un symbole.

        Args:
            symbol: Nom du symbole MT5 (ex: XAUUSD, EURUSD).
            timeframe_str: Timeframe (M1, M5, M15, M30, H1, H4, D1).
            start_date: Date de debut (incluse). Defaut: 2026-01-01.
            end_date: Date de fin (excluse). Defaut: aujourd'hui UTC.
            max_bars: Nombre max de barres a telecharger (defaut: 80000).
            output_dir: Dossier de sortie pour le fichier JSON.

        Retourne:
            DownloadResult ou None si erreur.
        """
        timeframe_str = timeframe_str.upper()
        if timeframe_str not in HISTORICAL_TIMEFRAMES:
            logger.error("Timeframe inconnu: %s. Options: %s",
                         timeframe_str, list(HISTORICAL_TIMEFRAMES))
            return None

        tf = HISTORICAL_TIMEFRAMES[timeframe_str]

        # Dates par defaut
        if start_date is None:
            start_date = datetime(2026, 1, 1, tzinfo=UTC)
        if end_date is None:
            end_date = datetime.now(UTC)

        # S'assurer que les dates sont timezone-aware
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=UTC)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=UTC)

        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())

        # --- Verifier le symbole ---
        logger.info("Verification du symbole %s...", symbol)
        if not self.connector.select_symbol(symbol, True):
            logger.error("Impossible de selectionner %s", symbol)
            return None

        info = self.connector.get_symbol_info(symbol)
        if info is None:
            logger.error("Symbole %s indisponible.", symbol)
            return None

        logger.info("Symbole: %s (digits=%d, spread=%d)",
                     symbol, info.digits, info.spread)

        # --- Telechargement ---
        logger.info("Telechargement de %d barres %s...", max_bars, timeframe_str)
        rates = self.connector.get_rates(symbol, tf, count=max_bars)

        if rates is None or len(rates) == 0:
            logger.error("Aucune donnee retournee par MT5 pour %s", symbol)
            return None

        # --- Filtrer par date ---
        all_bars: List[Dict] = []
        for r in rates:
            t = int(r[0])
            if t < start_ts or t >= end_ts:
                continue
            all_bars.append({
                "time": t,
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "tick_volume": int(r[5]),
                "spread": int(r[6]) if len(r) > 6 else 0,
                "real_volume": int(r[7]) if len(r) > 7 else 0,
            })

        all_bars.sort(key=lambda b: b["time"])
        total_bars = len(all_bars)

        logger.info("%d barres brutes MT5 -> %d barres dans la periode",
                     len(rates), total_bars)

        if total_bars == 0:
            logger.warning("Aucune barre dans la periode specifiee.")
            return DownloadResult(
                symbol=symbol,
                timeframe=timeframe_str,
                total_bars=0,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )

        # --- Statistiques ---
        first_bar = all_bars[0]
        last_bar = all_bars[-1]
        first_dt = datetime.fromtimestamp(first_bar["time"], tz=UTC)
        last_dt = datetime.fromtimestamp(last_bar["time"], tz=UTC)
        price_high = max(b["high"] for b in all_bars)
        price_low = min(b["low"] for b in all_bars)

        # --- Sauvegarde JSON ---
        os.makedirs(output_dir, exist_ok=True)

        fname = (
            f"{symbol.lower()}_{timeframe_str.lower()}_"
            f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.json"
        )
        output_path = os.path.join(output_dir, fname)

        # Infos compte pour le broker
        account = self.connector.get_account_info()
        broker = account.server if account else "unknown"

        data = {
            "symbol": symbol,
            "timeframe": timeframe_str,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "total_bars": total_bars,
            "broker": broker,
            "downloaded_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "bars": all_bars,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        file_size_kb = os.path.getsize(output_path) / 1024
        logger.info("Sauvegarde: %s (%.0f Ko, %d barres)",
                     output_path, file_size_kb, total_bars)

        return DownloadResult(
            symbol=symbol,
            timeframe=timeframe_str,
            total_bars=total_bars,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            broker=broker,
            output_path=output_path,
            file_size_kb=file_size_kb,
            price_high=price_high,
            price_low=price_low,
            first_bar_time=first_dt.strftime("%Y-%m-%d %H:%M"),
            last_bar_time=last_dt.strftime("%Y-%m-%d %H:%M"),
        )

    def download_multiple(
        self,
        symbols: List[str],
        timeframe_str: str = "M3",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_bars: int = 80000,
        output_dir: str = "reports",
    ) -> List[DownloadResult]:
        """Telecharge l'historique pour plusieurs symboles.

        Args:
            symbols: Liste des symboles a telecharger.
            timeframe_str: Timeframe.
            start_date: Date de debut.
            end_date: Date de fin.
            max_bars: Nombre max de barres.
            output_dir: Dossier de sortie.

        Retourne:
            Liste des DownloadResult (reussites uniquement).
        """
        results: List[DownloadResult] = []
        for symbol in symbols:
            logger.info("--- %s ---", symbol)
            result = self.download(
                symbol=symbol,
                timeframe_str=timeframe_str,
                start_date=start_date,
                end_date=end_date,
                max_bars=max_bars,
                output_dir=output_dir,
            )
            if result is not None and result.total_bars > 0:
                results.append(result)
        return results


def print_download_result(result: DownloadResult) -> None:
    """Affiche les resultats du telechargement dans la console."""
    print()
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}{result.symbol} - {result.timeframe}{RESET}")
    print(f"{DIM}{'='*60}{RESET}")

    if result.total_bars == 0:
        print(f"  {YELLOW}Aucune donnee dans la periode.{RESET}")
        print()
        return

    print(f"  Barres     : {result.total_bars}")
    print(f"  Periode    : {result.first_bar_time} -> {result.last_bar_time} UTC")
    print(f"  Range      : {format_px(result.price_low)} -> "
          f"{format_px(result.price_high)}")
    print(f"  Broker     : {result.broker}")
    print(f"  Fichier    : {result.output_path}")
    print(f"  Taille     : {result.file_size_kb:.0f} Ko")
