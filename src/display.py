"""
Affichage console coloré des résultats du scan Kijun Sen.
S'inspire du style du projet InelidaMarketScan.
"""

from datetime import datetime
from typing import List, Optional

from src.config import TIMEFRAME_LABELS
from src.ichimoku import IchimokuResult

# ---------------------------------------------------------------------------
# Codes ANSI pour les couleurs
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_DARK_GRAY = "\033[100m"

# ---------------------------------------------------------------------------
# Symboles ASCII-safe (compatibles cp1252)
# ---------------------------------------------------------------------------
ARROW_UP = "^"
ARROW_DN = "v"
BULLET = ">"
DOT = "."
BLOCK = "#"
BAR_EMPTY = "-"

# ---------------------------------------------------------------------------
# Seuils de proximité
# ---------------------------------------------------------------------------
PROXIMITY_TIGHT = 0.3    # Très proche (%)
PROXIMITY_MODERATE = 1.0 # Proche (%)
PROXIMITY_WIDE = 2.0     # Modérément proche (%)


def _proximity_color(dist_pct: float) -> str:
    """Retourne la couleur ANSI selon la distance au Kijun."""
    if dist_pct <= PROXIMITY_TIGHT:
        return RED       # Très proche
    if dist_pct <= PROXIMITY_MODERATE:
        return YELLOW    # Proche
    if dist_pct <= PROXIMITY_WIDE:
        return CYAN      # Modéré
    return GREEN         # Éloigné


def _proximity_label(dist_pct: float) -> str:
    """Retourne un label pour la distance."""
    if dist_pct <= PROXIMITY_TIGHT:
        return "[!] TRES PROCHE"
    if dist_pct <= PROXIMITY_MODERATE:
        return "[-] PROCHE"
    if dist_pct <= PROXIMITY_WIDE:
        return "[~] MODERE"
    return "[ ] LOINTAIN"


def _direction_arrow(above: bool) -> str:
    """Indique si le prix est au-dessus ou en-dessous du Kijun."""
    return f"{GREEN}^{RESET}" if above else f"{RED}v{RESET}"


def format_px(value: float, decimals: int = 5) -> str:
    """Formate un prix avec le nombre de décimales approprié."""
    if value >= 1000:
        return f"{value:.2f}"
    if value >= 100:
        return f"{value:.3f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.{decimals}f}"


def print_header(title: str = "ICHIMOKU SWORD - SCAN KIJUN SEN") -> None:
    """Affiche l'en-tête du scanner."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(f"{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}{title:^65}{RESET}")
    print(f"{DIM}{CYAN}{'='*65}{RESET}")
    print(f"{DIM}  {now}{RESET}")
    print(f"{CYAN}{'-'*65}{RESET}")
    print()


def print_kijun_results(results: List[IchimokuResult],
                        threshold: Optional[float] = None) -> None:
    """Affiche les résultats du scan Kijun Sen dans un tableau coloré.

    Args:
        results: Liste des résultats Ichimoku.
        threshold: Seuil optionnel pour le filtre.
    """
    if not results:
        print(f"{DIM}Aucun résultat à afficher.{RESET}")
        return

    # Affichage compact : un symbole par ligne, tous timeframes confondus
    print(f"{BOLD}{'Symbole':<10} {'TF':<4} {'Prix':<12} {'Kijun':<12} "
          f"{'Dist%':<8} {'Dir':<4} {'Signal'}{RESET}")
    print(f"{DIM}{'-'*65}{RESET}")

    for r in results:
        color = _proximity_color(r.distance_pct)
        label = _proximity_label(r.distance_pct)
        arrow = _direction_arrow(r.above_kijun)

        # Distance formatée
        dist_str = f"{color}{r.distance_pct:.2f}%{RESET}"

        print(f"{r.symbol:<10} {r.timeframe_label:<4} "
              f"{format_px(r.current_price):<12} "
              f"{format_px(r.kijun_sen):<12} "
              f"{dist_str:<20} {arrow:<4} {label}")

    # Résumé
    print(f"{DIM}{'-'*65}{RESET}")
    print(f"{DIM}Total: {len(results)} signaux{RESET}")
    tight = sum(1 for r in results if r.distance_pct <= PROXIMITY_TIGHT)
    moderate = sum(1 for r in results
                   if PROXIMITY_TIGHT < r.distance_pct <= PROXIMITY_MODERATE)
    wide = sum(1 for r in results
               if PROXIMITY_MODERATE < r.distance_pct <= PROXIMITY_WIDE)
    if tight:
        print(f"  {RED}[!] Tres proche : {tight}{RESET}")
    if moderate:
        print(f"  {YELLOW}[-] Proche      : {moderate}{RESET}")
    if wide:
        print(f"  {CYAN}[~] Modere      : {wide}{RESET}")
    print()


def print_detailed_result(r: IchimokuResult) -> None:
    """Affiche les détails complets d'un résultat Ichimoku."""
    print(f"{BOLD}{r.symbol}{RESET} ({r.timeframe_label})")
    print(f"  Prix actuel    : {format_px(r.current_price)}")
    print(f"  Kijun Sen      : {format_px(r.kijun_sen)}")
    print(f"  Distance       : {r.distance_pct:.2f}% "
          f"({'au-dessus' if r.above_kijun else 'en-dessous'})")
    if r.tenkan_sen is not None:
        print(f"  Tenkan Sen     : {format_px(r.tenkan_sen)}")
    if r.senkou_span_a is not None:
        print(f"  Senkou Span A  : {format_px(r.senkou_span_a)}")
    if r.senkou_span_b is not None:
        print(f"  Senkou Span B  : {format_px(r.senkou_span_b)}")
    print(f"  Bougies        : {r.bars_count}")
    print()


def print_progress(current: int, total: int, symbol: str, tf: int) -> None:
    """Affiche la progression du scan (callback)."""
    tf_label = TIMEFRAME_LABELS.get(tf, str(tf))
    pct = current / total * 100 if total > 0 else 0
    bar_len = 30
    filled = int(bar_len * current / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_len - filled)
    print(f"\r{DIM}Scan {symbol} ({tf_label}) ... "
          f"[{bar}] {current}/{total} ({pct:.0f}%){RESET}", end="", flush=True)
