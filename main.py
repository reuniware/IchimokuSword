#!/usr/bin/env python3
"""
IchimokuSword 🗡️ - Scanner Kijun Sen pour MetaTrader 5

Usage:
    python main.py snapshot           # Scan unique de tous les symboles
    python main.py snapshot --symbols EURUSD,GBPUSD,XAUUSD
    python main.py snapshot --timeframe H1,H4,D1 --threshold 0.5

    python main.py watch              # Mode continu
    python main.py watch --interval 30 --threshold 1.0

Options:
    -h, --help              Affiche ce message
    -s, --symbols LIST      Symboles à scanner (séparés par des virgules)
    -t, --timeframe TF      Timeframes (H1,H4,D1 par défaut)
    -T, --threshold PCT     Seuil de distance au Kijun en % (défaut: 1.0)
    -i, --interval SEC      Intervalle en secondes pour le mode watch (défaut: 60)
    --all                   Scanner tous les symboles MT5 (par défaut)
    --no-color              Désactiver les couleurs ANSI
    --debug                 Activer les logs de debug
"""

import argparse
import logging
import signal
import sys
import threading
import time
from typing import List, Optional

import MetaTrader5 as mt5

from src.config import (
    TIMEFRAME_MAP,
    TIMEFRAME_LABELS,
    ScanConfig,
    load_env,
    make_mt5_config,
    resolve_watchlist,
)
from src.display import (
    BOLD,
    RESET,
    print_header,
    print_kijun_results,
    print_detailed_result,
    print_progress,
)
from src.downloader import HISTORICAL_TIMEFRAMES, HistoricalDownloader, print_download_result
from src.mt5_connector import MT5Connector
from src.scanner import KijunScanner


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(debug: bool = False) -> None:
    """Configure le logging."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%H:%M:%S",
    )
    # Réduire le bruit des bibliothèques tierces
    logging.getLogger("MetaTrader5").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Parsing des arguments
# ---------------------------------------------------------------------------

def parse_timeframes(tf_str: str) -> List[int]:
    """Convertit une chaîne de timeframes en liste de constantes MT5.

    Exemple: "H1,H4,D1" -> [16385, 16388, 16408]
    """
    tf_list = []
    for part in tf_str.split(","):
        part = part.strip().upper()
        if part in TIMEFRAME_MAP:
            tf_list.append(TIMEFRAME_MAP[part])
        else:
            print(f"⚠ Timeframe inconnu : {part}. Ignoré.")
    if not tf_list:
        tf_list = [16408]  # D1 par défaut
    return tf_list


def parse_symbols(symbols_str: Optional[str]) -> Optional[List[str]]:
    """Convertit une chaîne de symboles en liste."""
    if not symbols_str:
        return None
    return [s.strip().upper() for s in symbols_str.split(",") if s.strip()]


def build_parser() -> argparse.ArgumentParser:
    """Construit le parser CLI."""
    parser = argparse.ArgumentParser(
        prog="ichimokusword",
        description="⚔️ IchimokuSword - Scanner Kijun Sen pour MetaTrader 5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python main.py snapshot
  python main.py snapshot --symbols EURUSD,GBPUSD,XAUUSD --timeframe H1 --threshold 0.5
  python main.py snapshot --timeframe D1,H4 --threshold 1.5
  python main.py watch --interval 30 --threshold 0.8 --timeframe H1
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commande à exécuter")

    # ---- Commande snapshot ----
    snap = subparsers.add_parser("snapshot", help="Scan unique des symboles")
    snap.add_argument("-s", "--symbols", type=str, default=None,
                      help="Symboles à scanner (ex: EURUSD,GBPUSD)")
    snap.add_argument("-t", "--timeframe", type=str, default="D1",
                      help="Timeframes (ex: H1,H4,D1)")
    snap.add_argument("-T", "--threshold", type=float, default=1.0,
                      help="Seuil de distance au Kijun (%%%, défaut: 1.0)")
    snap.add_argument("--detail", action="store_true",
                      help="Afficher les détails complets pour chaque signal")
    snap.add_argument("--all", action="store_true",
                      help="Scanner tous les symboles MT5")
    snap.add_argument("--no-color", action="store_true",
                      help="Désactiver les couleurs")

    # ---- Commande watch ----
    watch = subparsers.add_parser("watch", help="Scan en continu")
    watch.add_argument("-s", "--symbols", type=str, default=None,
                       help="Symboles à surveiller (ex: EURUSD,GBPUSD)")
    watch.add_argument("-t", "--timeframe", type=str, default="D1",
                       help="Timeframes (ex: H1,H4,D1)")
    watch.add_argument("-T", "--threshold", type=float, default=1.0,
                       help="Seuil de distance au Kijun (%%%, défaut: 1.0)")
    watch.add_argument("-i", "--interval", type=float, default=60.0,
                       help="Intervalle entre les scans (secondes, défaut: 60)")
    watch.add_argument("--all", action="store_true",
                       help="Scanner tous les symboles MT5")
    watch.add_argument("--no-color", action="store_true",
                       help="Désactiver les couleurs")

    # ---- Commande info ----
    info = subparsers.add_parser("info", help="Afficher les infos du compte MT5")

    # ---- Commande download ----
    dload = subparsers.add_parser("download",
                                  help="Telecharger l'historique des donnees")
    dload.add_argument("symbol", type=str,
                       help="Symbole a telecharger (ex: XAUUSD)")
    dload.add_argument("--tf", type=str, default="M3",
                       help="Timeframe: M1, M5, M15, M30, H1, H4, D1 (defaut: M3)")
    dload.add_argument("--start", type=str, default=None,
                       help="Date debut YYYY-MM-DD (defaut: 2026-01-01)")
    dload.add_argument("--end", type=str, default=None,
                       help="Date fin YYYY-MM-DD (defaut: aujourd'hui)")
    dload.add_argument("--max-bars", type=int, default=80000,
                       help="Nombre max de barres a telecharger (defaut: 80000)")
    dload.add_argument("--output", type=str, default="reports",
                       help="Dossier de sortie (defaut: reports)")

    # Options globales
    parser.add_argument("--debug", action="store_true",
                        help="Activer les logs de debug")
    parser.add_argument("--no-color", action="store_true",
                        help="Désactiver les couleurs")

    return parser


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def cmd_snapshot(args: argparse.Namespace, connector: MT5Connector,
                 scan_config: ScanConfig) -> None:
    """Exécute un scan unique."""
    timeframes = parse_timeframes(args.timeframe)
    threshold = args.threshold
    scan_config.timeframes = timeframes
    symbols = parse_symbols(args.symbols) if not args.all else None

    scanner = KijunScanner(connector, scan_config)

    print_header("⚔️ ICHIMOKU SWORD - SNAPSHOT")
    tf_labels = ", ".join(TIMEFRAME_LABELS.get(t, str(t)) for t in timeframes)
    print(f"  Timeframes   : {tf_labels}")
    print(f"  Seuil        : {threshold:.1f}%")
    if symbols:
        print(f"  Symboles     : {len(symbols)} (spécifiés)")
    else:
        print(f"  Symboles     : Tous (scan complet)")
    print()

    # Scan
    results = scanner.scan_all(
        symbols=symbols,
        progress_callback=print_progress,
        filter_fn=lambda r: r.distance_pct <= threshold,
    )

    # Affichage
    print("\n" + " " * 80)  # Efface la ligne de progression
    if args.detail:
        for r in results:
            print_detailed_result(r)
    else:
        print_kijun_results(results, threshold=threshold)


def cmd_watch(args: argparse.Namespace, connector: MT5Connector,
              scan_config: ScanConfig) -> None:
    """Exécute le mode watch (scan continu)."""
    timeframes = parse_timeframes(args.timeframe)
    threshold = args.threshold
    scan_config.timeframes = timeframes
    scan_config.watch_interval_sec = args.interval
    symbols = parse_symbols(args.symbols) if not args.all else None

    scanner = KijunScanner(connector, scan_config)

    # Gestion de l'arrêt via Ctrl+C
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("\n\n⏹ Arrêt demandé...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)  # non-Windows

    print_header("⚔️ ICHIMOKU SWORD - MODE WATCH")
    tf_labels = ", ".join(TIMEFRAME_LABELS.get(t, str(t)) for t in timeframes)
    print(f"  Timeframes   : {tf_labels}")
    print(f"  Seuil        : {threshold:.1f}%")
    print(f"  Intervalle   : {args.interval}s")
    if symbols:
        print(f"  Symboles     : {len(symbols)} (spécifiés)")
    else:
        print(f"  Symboles     : Tous (scan complet)")
    print(f"  Appuyez sur Ctrl+C pour arrêter.")
    print()

    try:
        scanner.watch(
            symbols=symbols,
            threshold=threshold,
            display_fn=lambda results: _watch_display(
                results, threshold=threshold
            ),
            stop_event=stop_event,
        )
    except KeyboardInterrupt:
        print("\n⏹ Watch arrêté.")
    finally:
        connector.shutdown()


def _watch_display(results: List, threshold: float) -> None:
    """Affiche les résultats du watch avec la date/heure."""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\033[2J\033[H")  # Clear screen
    print_header(f"⚔️ ICHIMOKU SWORD - WATCH ({now})")
    print(f"  Appuyez sur Ctrl+C pour arrêter.\n")
    if results:
        print_kijun_results(results, threshold=threshold)
    else:
        print(f"{' Aucun signal pour le moment.':^65}")
        print()


def cmd_download(args: argparse.Namespace, connector: MT5Connector) -> None:
    """Execute le telechargement historique."""
    from datetime import datetime, timezone

    tf = args.tf.upper()
    if tf not in HISTORICAL_TIMEFRAMES:
        print(f"Timeframe inconnu: {tf}. Options: {list(HISTORICAL_TIMEFRAMES)}")
        return

    # Parser les dates
    start_date = None
    end_date = None
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if args.end:
        end_date = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    downloader = HistoricalDownloader(connector)

    print_header("ICHIMOKU SWORD - DOWNLOAD")
    print(f"  Symbole    : {args.symbol}")
    print(f"  Timeframe  : {tf}")
    print(f"  Max barres : {args.max_bars}")
    print(f"  Output     : {args.output}")
    print()

    result = downloader.download(
        symbol=args.symbol,
        timeframe_str=tf,
        start_date=start_date,
        end_date=end_date,
        max_bars=args.max_bars,
        output_dir=args.output,
    )

    if result is None:
        print(f"Echec du telechargement pour {args.symbol}.")
        return

    print_download_result(result)


def cmd_info(args: argparse.Namespace, connector: MT5Connector) -> None:
    """Affiche les informations du compte MT5."""
    if not connector.ensure_connected():
        print("❌ Impossible de se connecter à MT5.")
        return

    # Terminal info
    terminal = connector.get_terminal_info()
    if terminal:
        print(f"\n{BOLD}Terminal:{RESET}")
        print(f"  Nom         : {terminal.name}")
        print(f"  Build       : {terminal.build}")
        print(f"  Data path   : {terminal.data_path}")
        print(f"  Version     : {terminal.community}")

    # Account info
    account = connector.get_account_info()
    if account:
        print(f"\n{BOLD}Compte:{RESET}")
        print(f"  Login       : {account.login}")
        print(f"  Serveur     : {account.server}")
        print(f"  Balance     : {account.balance:.2f} {account.currency}")
        print(f"  Equity      : {account.equity:.2f} {account.currency}")
        print(f"  Margin level: {account.margin_level:.2f}%")

    # Symbols count
    symbols = connector.list_all_symbols()
    print(f"\n{BOLD}Symboles:{RESET}")
    print(f"  Disponibles : {len(symbols)}")
    print()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main() -> None:
    """Point d'entrée principal."""
    parser = build_parser()
    args = parser.parse_args()

    # Chargement du .env
    load_env()

    # Logging
    setup_logging(debug=getattr(args, "debug", False) or args.debug)

    # Configuration
    mt5_config = make_mt5_config()
    scan_config = ScanConfig()

    # Connexion MT5
    connector = MT5Connector(mt5_config)
    if not connector.initialize():
        print("❌ Échec de connexion à MetaTrader 5.")
        print()
        print("  Vérifiez que :")
        print("  1. MetaTrader 5 est installé et lancé")
        print("  2. Le fichier .env contient les bons paramètres")
        print("  3. Le compte est connecté dans MT5")
        print()
        print(f"  Exemple .env :")
        print(f"    MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe")
        print(f"    MT5_LOGIN=12345678")
        print(f"    MT5_PASSWORD=votre_mot_de_passe")
        print(f"    MT5_SERVER=YourBrokerServer")
        print()
        sys.exit(1)

    try:
        # Routage des commandes
        if args.command == "snapshot":
            cmd_snapshot(args, connector, scan_config)
        elif args.command == "watch":
            cmd_watch(args, connector, scan_config)
        elif args.command == "info":
            cmd_info(args, connector)
        elif args.command == "download":
            cmd_download(args, connector)
        else:
            parser.print_help()
    finally:
        if args.command != "watch":
            connector.shutdown()


if __name__ == "__main__":
    main()
