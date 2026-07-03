"""
Affichage console coloré des résultats du scan Ichimoku.
Affiche les 5 elements : Tenkan, Kijun, Senkou A, Senkou B, Chikou.
"""

from datetime import datetime
from typing import List, Optional

from src.config import TIMEFRAME_LABELS
from src.ichimoku import (IchimokuResult, IchimokuCloud, IchimokuTKCross,
    IchimokuChikou, IchimokuFlatLines, IchimokuThreeRules,
    IchimokuTwist, IchimokuLaggingConfirmation)

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
        return RED       # Tres proche
    if dist_pct <= PROXIMITY_MODERATE:
        return YELLOW    # Proche
    if dist_pct <= PROXIMITY_WIDE:
        return CYAN      # Modere
    return GREEN         # Eloigne


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


def _cloud_color_ansi(cloud: 'IchimokuCloud') -> str:
    """Couleur ANSI pour le nuage."""
    if cloud.above_cloud:
        return f"{GREEN}AU-DESSUS{RESET}"
    if cloud.below_cloud:
        return f"{RED}EN-DESSOUS{RESET}"
    if cloud.inside_cloud:
        return f"{YELLOW}DANS NUAGE{RESET}"
    return f"{DIM}N/A{RESET}"


def _tk_cross_str(tk: 'IchimokuTKCross') -> str:
    """Texte du croisement TK."""
    if tk.cross_type == "TK_CROSS_HAUSSIER":
        return f"{GREEN}TK HAUSSIER{RESET}"
    if tk.cross_type == "TK_CROSS_BAISSIER":
        return f"{RED}TK BAISSIER{RESET}"
    if tk.current_position == "TENKAN_HAUT":
        return f"{GREEN}TK>K{RESET}"
    if tk.current_position == "KIJUN_HAUT":
        return f"{RED}K>TK{RESET}"
    return f"{DIM}TK=K{RESET}"


def _chikou_str(chikou: 'IchimokuChikou') -> str:
    """Texte du Chikou."""
    if chikou.bullish_alignment:
        return f"{GREEN}ALIGNE HAUT{RESET}"
    if chikou.above_price_26:
        return f"{CYAN}CHIKOU>P26{RESET}"
    return f"{RED}CHIKOU<P26{RESET}"


def _flat_str(flat: Optional['IchimokuFlatLines']) -> str:
    """Indicateurs des lignes plates et SSB historiques."""
    if not flat:
        return f"{DIM}N/A{RESET}"
    parts = []
    if flat.kijun_flat:
        parts.append(f"{YELLOW}KJ PLAT{RESET}")
    if flat.tenkan_flat:
        parts.append(f"{YELLOW}TK PLAT{RESET}")
    if flat.future_cloud_flat:
        parts.append(f"{CYAN}NUAGE FUTUR FIN{RESET}")
    if flat.past_chikou_flat:
        parts.append(f"{DIM}CHIKOU PLAT{RESET}")
    if flat.cloud_thin:
        parts.append(f"{DIM}NUAGE FIN{RESET}")
    if flat.kijun_flat_bars >= 10:
        parts.append(f"{YELLOW}KJ PLAT {flat.kijun_flat_bars}B{RESET}")
    
    # SSB plates historiques
    if flat.ssb_history and flat.ssb_history.levels:
        nb_levels = len(flat.ssb_history.levels)
        parts.append(f"{BLUE}SSBx{nb_levels}{RESET}")
        if flat.ssb_history.nearest_above:
            parts.append(f"{RED}R:{flat.ssb_history.nearest_above:.5f}{RESET}")
        if flat.ssb_history.nearest_below:
            parts.append(f"{GREEN}S:{flat.ssb_history.nearest_below:.5f}{RESET}")
    
    return " ".join(parts) if parts else ""


def _three_rules_str(rules: Optional['IchimokuThreeRules']) -> str:
    """Affichage des 3 regles d'or."""
    if not rules:
        return f"{DIM}N/A{RESET}"
    if rules.all_valid:
        return f"{GREEN}3/3 VALIDE{RESET}"
    return f"{YELLOW}{rules.rules_validated}/3{RESET}"


def _twist_str(twist: Optional['IchimokuTwist']) -> str:
    """Affichage du twist."""
    if not twist:
        return ""
    if twist.twist_active:
        if "ROUGE->VERT" in (twist.twist_type or ""):
            return f"{GREEN}TWIST HAUSSIER{RESET}"
        elif "VERT->ROUGE" in (twist.twist_type or ""):
            return f"{RED}TWIST BAISSIER{RESET}"
        return f"{YELLOW}TWIST{RESET}"
    return ""


def _lagging_str(lag: Optional['IchimokuLaggingConfirmation']) -> str:
    """Affichage de la confirmation Lagging Span."""
    if not lag:
        return f"{DIM}N/A{RESET}"
    if lag.power_confirmed:
        if lag.confirmation_bullish:
            return f"{GREEN}CONFIRME HAUT{RESET}"
        return f"{RED}CONFIRME BAS{RESET}"
    if lag.chikou_françit_kijun:
        return f"{YELLOW}FRANCHIT KIJUN{RESET}"
    if lag.chikou_françit_nuage:
        return f"{YELLOW}FRANCHIT NUAGE{RESET}"
    return f"{DIM}PAS CONFIRME{RESET}"


def format_px(value: float, decimals: int = 5) -> str:
    """Formate un prix avec le nombre de decimales approprie."""
    if value >= 1000:
        return f"{value:.2f}"
    if value >= 100:
        return f"{value:.3f}"
    if value >= 1:
        return f"{value:.4f}"
    return f"{value:.{decimals}f}"


def print_header(title: str = "ICHIMOKU SWORD - SCAN ICHIMOKU") -> None:
    """Affiche l'en-tete du scanner."""
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
    """Affiche les resultats du scan Ichimoku dans un tableau compact.

    Montre Kijun + indicateurs cles (nuage, TK, Chikou).
    """
    if not results:
        print(f"{DIM}Aucun resultat a afficher.{RESET}")
        return

    # En-tete
    print(f"{BOLD}{'Symbole':<10} {'TF':<4} {'Prix':<11} {'Kijun':<11} "
          f"{'Dist%':<7} {'Kumo':<12} {'TK':<10} {'Chikou':<12} {'Lignes':<18}{RESET}")
    print(f"{DIM}{'-'*88}{RESET}")

    for r in results:
        color = _proximity_color(r.distance_pct)
        label = _proximity_label(r.distance_pct)
        arrow = _direction_arrow(r.above_kijun)
        dist_str = f"{color}{r.distance_pct:.2f}%{RESET}"

        # Nuage
        cloud_str = ""
        if r.cloud:
            cloud_str = _cloud_color_ansi(r.cloud)

        # TK Cross
        tk_str = ""
        if r.tk_cross:
            tk_str = _tk_cross_str(r.tk_cross)

        # Chikou
        chikou_str = ""
        if r.chikou:
            chikou_str = _chikou_str(r.chikou)

        # Lignes plates
        flat_str = _flat_str(r.flat)

        # 3 Regles
        rules_str = _three_rules_str(r.three_rules)

        # Twist
        twist_str = _twist_str(r.twist)

        # Lagging confirmation
        lag_str = _lagging_str(r.lagging_confirmation)

        all_extra = " ".join(filter(None, [twist_str, lag_str, flat_str]))
        print(f"{r.symbol:<10} {r.timeframe_label:<4} "
              f"{format_px(r.current_price):<11} "
              f"{format_px(r.kijun_sen):<11} "
              f"{dist_str:<14} {cloud_str:<12} {tk_str:<10} {chikou_str:<22} {rules_str:<10} {all_extra}")

    # Resume
    print(f"{DIM}{'-'*88}{RESET}")
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

    # Resume elements
    above_cloud = sum(1 for r in results if r.cloud and r.cloud.above_cloud)
    inside_cloud = sum(1 for r in results if r.cloud and r.cloud.inside_cloud)
    tk_up = sum(1 for r in results if r.tk_cross and r.tk_cross.current_position == "TENKAN_HAUT")
    chikou_align = sum(1 for r in results if r.chikou and r.chikou.bullish_alignment)
    kijun_flat = sum(1 for r in results if r.flat and r.flat.kijun_flat)
    cloud_thin = sum(1 for r in results if r.flat and r.flat.cloud_thin)
    rules_3_3 = sum(1 for r in results if r.three_rules and r.three_rules.all_valid)
    twist_count = sum(1 for r in results if r.twist and r.twist.twist_active)
    lag_confirm = sum(1 for r in results if r.lagging_confirmation and r.lagging_confirmation.power_confirmed)
    print(f"{DIM}  Nuage: {above_cloud} au-dessus / {inside_cloud} dans nuage | TK>K: {tk_up} | Chikou aligne: {chikou_align}{RESET}")
    print(f"{DIM}  3 regles: {rules_3_3} valides | Twist: {twist_count} | Lagging confirme: {lag_confirm}{RESET}")
    print(f"{DIM}  Kijun plat: {kijun_flat} | Nuage fin: {cloud_thin}{RESET}")
    print()


def print_detailed_result(r: IchimokuResult) -> None:
    """Affiche les details complets d'un resultat Ichimoku (5 elements + structure)."""
    print(f"{BOLD}{r.symbol}{RESET} ({r.timeframe_label})")
    print(f"  {'='*45}")
    print(f"  {BOLD}LES 5 LIGNES{RESET}")
    print(f"  {'='*45}")
    print(f"  Tenkan Sen (9)     : {format_px(r.tenkan_sen)}")
    print(f"  Kijun Sen (26)     : {format_px(r.kijun_sen)}")
    print(f"  Senkou Span A (26) : {format_px(r.senkou_span_a)}")
    print(f"  Senkou Span B (52) : {format_px(r.senkou_span_b)}")
    print(f"  Chikou Span (26)   : {format_px(r.chikou_span)}")
    print()
    print(f"  {BOLD}POSITION PRIX{RESET}")
    print(f"  Prix actuel        : {format_px(r.current_price)}")
    print(f"  Distance Kijun     : {r.distance_pct:.3f}% ({'au-dessus' if r.above_kijun else 'en-dessous'})")
    if r.cloud:
        print(f"  Nuage Senkou       : {_cloud_color_ansi(r.cloud)}")
        print(f"    Senkou A         : {format_px(r.cloud.senkou_a)}")
        print(f"    Senkou B         : {format_px(r.cloud.senkou_b)}")
        print(f"    Couleur nuage    : {r.cloud.cloud_color}")
    if r.tk_cross:
        print(f"  TK Cross           : {_tk_cross_str(r.tk_cross)}")
        if r.tk_cross.cross_type:
            print(f"    Type             : {r.tk_cross.cross_type}")
            print(f"    Bougies depuis   : {r.tk_cross.bars_since_cross}")
    if r.chikou:
        print(f"  Chikou             : {_chikou_str(r.chikou)}")
        print(f"    Valeur           : {format_px(r.chikou.value)}")
        print(f"    > Prix 26         : {'Oui' if r.chikou.above_price_26 else 'Non'}")
    if r.three_rules:
        print(f"  {'='*45}")
        print(f"  {BOLD}LES 3 REGLES D'OR{RESET}")
        print(f"  {'='*45}")
        print(f"  Regle 1 (Nuage)   : {r.three_rules.rule1_detail} {'OK' if r.three_rules.rule1_cloud else 'KO'}")
        print(f"  Regle 2 (Chikou)  : {r.three_rules.rule2_detail} {'OK' if r.three_rules.rule2_chikou else 'KO'}")
        print(f"  Regle 3 (TK)      : {r.three_rules.rule3_detail} {'OK' if r.three_rules.rule3_tk else 'KO'}")
        print(f"  Score             : {r.three_rules.rules_validated}/3")
        print(f"  Signal            : {r.three_rules.signal_type}")
    if r.twist and r.twist.twist_active:
        print(f"  Twist              : {_twist_str(r.twist)}")
        print(f"    Couleur         : {r.twist.previous_color} -> {r.twist.current_color}")
    if r.lagging_confirmation:
        print(f"  Lagging Span       : {_lagging_str(r.lagging_confirmation)}")
        print(f"    Detail          : {r.lagging_confirmation.detail}")
    if r.flat:
        print(f"  {'='*45}")
        print(f"  {BOLD}LIGNES PASSÉES / FUTURES / PLATES / SSB{RESET}")
        print(f"  {'='*45}")
        print(f"  Ligne passee (Chikou affiche): {format_px(r.flat.past_chikou)}")
        print(f"    Chikou plat                : {'Oui' if r.flat.past_chikou_flat else 'Non'}")
        print(f"  Nuage futur (Senkou A/B): A={format_px(r.flat.future_senkou_a)} B={format_px(r.flat.future_senkou_b)}")
        print(f"    Epaisseur                 : {format_px(r.flat.future_cloud_thickness)}")
        print(f"    Nuage futur plat          : {'Oui' if r.flat.future_cloud_flat else 'Non'}")
        print(f"    Couleur nuage futur       : {r.flat.future_cloud_color}")
        print(f"  Kijun plat                  : {'Oui' if r.flat.kijun_flat else 'Non'}")
        if r.flat.kijun_flat_bars:
            print(f"    Depuis {r.flat.kijun_flat_bars} bougies")
        print(f"  Tenkan plat                 : {'Oui' if r.flat.tenkan_flat else 'Non'}")
        print(f"  Epaisseur nuage             : {format_px(r.flat.cloud_thickness)}")
        print(f"  Nuage fin                   : {'Oui' if r.flat.cloud_thin else 'Non'}")
        
        # SSB plates historiques
        if r.flat.ssb_history and r.flat.ssb_history.levels:
            print(f"  {'='*45}")
            print(f"  {BOLD}SSB PLATES HISTORIQUES (supports/resistances){RESET}")
            print(f"  {'='*45}")
            print(f"  {len(r.flat.ssb_history.levels)} niveaux detectes")
            if r.flat.ssb_history.nearest_above:
                print(f"  Resistance la plus proche : {r.flat.ssb_history.nearest_above:.6f}")
            if r.flat.ssb_history.nearest_below:
                print(f"  Support le plus proche    : {r.flat.ssb_history.nearest_below:.6f}")
            print()
            print(f"  {'Niveau':<14} {'Bars':<6} {'Dist%':<8} {'Position':<12} {'Age':<6}")
            print(f"  {'-'*46}")
            for lvl in r.flat.ssb_history.levels[:8]:
                dist_color = GREEN if lvl.position == "EN-DESSOUS" else RED
                arrow = "v" if lvl.position == "AU-DESSUS" else "^"
                print(f"  {lvl.level:<14.6f} {lvl.bars_count:<6} "
                      f"{dist_color}{lvl.price_distance_pct:<7.3f}%{RESET} "
                      f"{arrow} {lvl.position:<10} {lvl.age_bars:<6}")
    print(f"  Bougies analysees  : {r.bars_count}")
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
