"""
Calculs des indicateurs Ichimoku Kinko Hyo.
Couvre les 5 elements : Tenkan, Kijun, Senkou A, Senkou B, Chikou.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class IchimokuCloud:
    """Etat du nuage Senkou (Kumo)."""
    senkou_a: float          # Senkou Span A (valeur projetee)
    senkou_b: float          # Senkou Span B (valeur projetee)
    cloud_color: str         # "VERT" si A>B, "ROUGE" si B>A
    above_cloud: bool        # True si price > les deux
    below_cloud: bool        # True si price < les deux
    inside_cloud: bool       # True si price entre A et B


@dataclass
class IchimokuTKCross:
    """Croisement Tenkan / Kijun."""
    current_position: str    # "TENKAN_HAUT", "KIJUN_HAUT", "EGAL"
    previous_position: str   # Position a la bougie precedente
    cross_type: Optional[str]  # "TK_CROSS_HAUSSIER", "TK_CROSS_BAISSIER", None
    bars_since_cross: int = 99  # Bougies depuis le dernier croisement


@dataclass
class IchimokuChikou:
    """Position du Chikou Span (Lagging Span)."""
    value: float             # Close actuel (projete 26 periodes en arriere)
    above_price_26: bool     # True si > prix d'il y a 26 periodes
    bullish_alignment: bool  # True si au-dessus ET price actuelle au-dessus Kijun


@dataclass
class SsbFlatLevel:
    """Niveau SSB plat historique (support/resistance potentiel)."""
    level: float             # Valeur du niveau
    bars_count: int          # Nombre de bougies plates consecutives
    price_distance_pct: float  # Distance du prix actuel a ce niveau (%)
    position: str            # "AU-DESSUS" ou "EN-DESSOUS"
    age_bars: int            # Depuis combien de bougies ce niveau a ete forme


@dataclass
class IchimokuSsbHistory:
    """Analyse historique de la SSB (Senkou Span B) pour detecter
    les zones de support/resistance issues d'anciennes SSB plates.
    Une SSB plate sur plusieurs bougies forme un niveau horizontal
    qui agit comme support ou resistance plus tard.
    """
    levels: List[SsbFlatLevel]       # Niveaux SSB plats detectes
    strongest_level: Optional[SsbFlatLevel]  # Le niveau le plus fort
    above_levels: List[SsbFlatLevel]  # Niveaux au-dessus du prix (resistances)
    below_levels: List[SsbFlatLevel]  # Niveaux en-dessous du prix (supports)
    nearest_above: Optional[float]    # Resistance la plus proche
    nearest_below: Optional[float]    # Support le plus proche


@dataclass
class IchimokuFlatLines:
    """Analyse des lignes plates et projections passe/futur."""
    # Lignes passees (ce qui est affiche decale en arriere)
    past_chikou: float           # Chikou tel qu'affiche sur le graphique (close[-26])
    past_chikou_flat: bool       # Le Chikou est-il plat sur les 5 dernieres periodes ?
    
    # Lignes futures (ce qui sera projete en avant)
    future_senkou_a: float       # Senkou A qui sera affiche dans 26 periodes
    future_senkou_b: float       # Senkou B qui sera affiche dans 26 periodes
    future_cloud_thickness: float  # Epaisseur du nuage futur (|A-B|)
    future_cloud_flat: bool      # Le nuage futur est-il plat/fin ?
    future_cloud_color: str      # "VERT" ou "ROUGE"
    
    # Lignes actuelles plates
    kijun_flat: bool             # Kijun est-il plat ?
    tenkan_flat: bool            # Tenkan est-il plat ?
    kijun_flat_bars: int         # Depuis combien de bougies le Kijun est plat
    
    # Epaisseur nuage actuel
    cloud_thickness: float       # Epaisseur du nuage = |Senkou A - Senkou B|
    cloud_thin: bool             # Nuage fin (< 0.1% du prix)
    
    # SSB plates historiques
    ssb_history: Optional[IchimokuSsbHistory] = None


@dataclass
class IchimokuThreeRules:
    """Les 3 regles d'or Ichimoku (Karen Péloille)."""
    # Regle 1: Prix au-dessus du nuage (haussier) ou en-dessous (baissier)
    rule1_cloud: bool               # True si prix du bon cote du nuage
    rule1_detail: str               # "AU-DESSUS", "EN-DESSOUS", "DANS-NUAGE"
    
    # Regle 2: Chikou aligne (au-dessus du prix 26 + dans la bonne direction)
    rule2_chikou: bool              # True si Chikou aligne
    rule2_detail: str               # "ALIGNE", "NON-ALIGNE", "N/A"
    
    # Regle 3: TK Cross dans la direction du trade
    rule3_tk: bool                  # True si TK confirme
    rule3_detail: str               # "TK>K", "K>TK", "TK_CROSS_HAUSSIER", etc.
    
    # Score global (0-3)
    rules_validated: int            # Nombre de regles validees (0-3)
    all_valid: bool                 # True si les 3 regles sont validees
    signal_type: str                # "HAUSSIER", "BAISSIER", ou "NEUTRE"


@dataclass
class IchimokuTwist:
    """Detection du 'twist' (croisement Senkou A / Senkou B).
    Le twist est le point ou le nuage change de couleur.
    """
    current_color: str              # "VERT", "ROUGE", "N/A"
    previous_color: str             # Couleur a la bougie precedente
    twist_active: bool              # True si twist en cours (changement de couleur)
    twist_type: Optional[str]       # "VERT->ROUGE" (baissier) ou "ROUGE->VERT" (haussier)
    bars_since_twist: int           # Bougies depuis le dernier twist
    twist_distance_pct: float       # Distance du prix au point de twist (%)


@dataclass
class IchimokuLaggingConfirmation:
    """Confirmation du Chikou Span (Lagging Span).
    Le Chikou doit franchir le nuage ET la Kijun pour valider.
    """
    chikou_above_kijun_past: bool   # Chikou > Kijun d'il y a 26 periodes ?
    chikou_above_cloud_past: bool   # Chikou au-dessus du nuage d'il y a 26p ?
    chikou_below_cloud_past: bool   # Chikou en-dessous du nuage d'il y a 26p ?
    chikou_françit_nuage: bool      # Le Chikou vient-il de franchir le nuage ?
    chikou_françit_kijun: bool      # Le Chikou vient-il de franchir la Kijun ?
    confirmation_bullish: bool      # Toutes les conditions haussieres reunies ?
    confirmation_bearish: bool      # Toutes les conditions baissieres reunies ?
    power_confirmed: bool           # True si mouvement confirme par le Chikou
    detail: str                     # Description textuelle


@dataclass
class IchimokuResult:
    """Resultat complet du calcul Ichimoku pour un symbole/timeframe."""
    symbol: str
    timeframe_label: str
    current_price: float
    
    # Les 5 lignes
    tenkan_sen: float
    kijun_sen: float
    senkou_span_a: float
    senkou_span_b: float
    chikou_span: float
    
    # Metriques Kijun
    distance_pct: float = 0.0       # Distance price -> Kijun (%)
    above_kijun: bool = True
    
    # Analyse avancee
    cloud: Optional[IchimokuCloud] = None
    tk_cross: Optional[IchimokuTKCross] = None
    chikou: Optional[IchimokuChikou] = None
    flat: Optional[IchimokuFlatLines] = None
    three_rules: Optional[IchimokuThreeRules] = None
    twist: Optional[IchimokuTwist] = None
    lagging_confirmation: Optional[IchimokuLaggingConfirmation] = None
    
    # Raw data
    bars_count: int = 0
    all_highs: List[float] = field(default_factory=list)
    all_lows: List[float] = field(default_factory=list)
    all_closes: List[float] = field(default_factory=list)
    all_opens: List[float] = field(default_factory=list)


def compute_chikou_span(closes: np.ndarray, shift: int = 26) -> float:
    """Calcule la valeur actuelle du Chikou Span (Lagging Span).

    Le Chikou Span est le close actuel, projete 26 periodes en arriere.
    Pour le signal haussier: Chikou (close actuel) > close d'il y a 26 periodes.

    Donc ici on retourne le close actuel qui sera affiche decale.
    """
    if len(closes) < 1:
        return float("nan")
    return float(closes[-1])


def compute_kijun_sen(highs: np.ndarray, lows: np.ndarray,
                      period: int = 26) -> float:
    """Calcule la valeur actuelle du Kijun Sen.

    Kijun Sen = (Plus Haut(26) + Plus Bas(26)) / 2

    Args:
        highs: Array des plus hauts.
        lows: Array des plus bas.
        period: Période de calcul (26 par défaut).

    Retourne:
        La valeur du Kijun Sen, ou NaN si pas assez de données.
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")

    highest_high = np.max(highs[-period:])
    lowest_low = np.min(lows[-period:])
    return (highest_high + lowest_low) / 2.0


def compute_tenkan_sen(highs: np.ndarray, lows: np.ndarray,
                       period: int = 9) -> float:
    """Calcule la valeur actuelle du Tenkan Sen (Conversion Line).

    Tenkan Sen = (Plus Haut(9) + Plus Bas(9)) / 2
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")
    return (np.max(highs[-period:]) + np.min(lows[-period:])) / 2.0


def compute_senkou_span_a(highs: np.ndarray, lows: np.ndarray,
                          tenkan_period: int = 9,
                          kijun_period: int = 26,
                      shift: int = 26) -> float:
    """Calcule le Senkou Span A (Leading Span A) décalé.

    Senkou A = (Tenkan + Kijun) / 2, décalé de 26 périodes.
    Note: ici on retourne la valeur au point actuel (avant décalage).
    """
    tenkan = compute_tenkan_sen(highs, lows, tenkan_period)
    kijun = compute_kijun_sen(highs, lows, kijun_period)
    if np.isnan(tenkan) or np.isnan(kijun):
        return float("nan")
    return (tenkan + kijun) / 2.0


def compute_senkou_span_b(highs: np.ndarray, lows: np.ndarray,
                          period: int = 52, shift: int = 26) -> float:
    """Calcule le Senkou Span B (Leading Span B) décalé.

    Senkou B = (Plus Haut(52) + Plus Bas(52)) / 2, décalé de 26.
    Note: ici on retourne la valeur au point actuel (avant décalage).
    """
    if len(highs) < period or len(lows) < period:
        return float("nan")
    return (np.max(highs[-period:]) + np.min(lows[-period:])) / 2.0


def detect_flat_line(values: np.ndarray, lookback: int = 5,
                      tolerance_pct: float = 0.05) -> bool:
    """Detecte si une ligne est plate (horizontale) sur les N dernieres periodes.

    Une ligne est "plate" si la variation relative sur `lookback` periodes
    est inferieure a `tolerance_pct` pourcent.

    Args:
        values: Array des valeurs de la ligne.
        lookback: Nombre de periodes a analyser.
        tolerance_pct: Tolerance en % (0.05 = 0.05% de variation max).

    Retourne:
        True si la ligne est plate.
    """
    if len(values) < lookback + 1:
        return False
    segment = values[-(lookback + 1):]
    base = abs(float(segment[0]))
    if base < 1e-10:
        return False
    variation = (float(np.max(segment)) - float(np.min(segment))) / base * 100.0
    return variation <= tolerance_pct


def detect_flat_bars(values: np.ndarray, tolerance_pct: float = 0.05,
                      max_lookback: int = 20) -> int:
    """Compte depuis combien de bougies une ligne est plate.

    Retourne le nombre de bougies consecutives ou la ligne est restee plate.
    """
    if len(values) < 3:
        return 0
    count = 0
    for i in range(min(max_lookback, len(values) - 1)):
        seg = values[-(i + 3):]
        base = abs(float(seg[0]))
        if base < 1e-10:
            break
        var = (float(np.max(seg)) - float(np.min(seg))) / base * 100.0
        if var <= tolerance_pct:
            count += 1
        else:
            break
    return count


def compute_past_chikou(closes: np.ndarray) -> float:
    """Calcule la valeur du Chikou Span "passe" affichee sur le graphique.

    Le Chikou Span est le close actuel projete 26 periodes en arriere.
    Donc ce qui est AFFICHE sur le graphique a la bougie actuelle
    = le close d'il y a 26 periodes.
    """
    if len(closes) < 27:
        return float("nan")
    return float(closes[-27])


def detect_ssb_flat_levels(highs: np.ndarray, lows: np.ndarray,
                            close_price: float,
                            lookback_bars: int = 100,
                            min_flat_bars: int = 3,
                            tolerance_pct: float = 0.02) -> IchimokuSsbHistory:
    """Detecte les niveaux SSB plats historiques.

    Parcourt l'historique de la SSB et identifie les segments ou
    la SSB est restee plate (horizontale) pendant au moins N bougies.
    Ces niveaux agissent comme supports/resistances.

    Args:
        highs: Array des plus hauts.
        lows: Array des plus bas.
        close_price: Prix actuel.
        lookback_bars: Nombre de bougies a analyser.
        min_flat_bars: Nombre minimum de bougies plates pour etre un niveau.
        tolerance_pct: Tolerance de variation pour considerer "plat" (%).

    Retourne:
        IchimokuSsbHistory avec les niveaux detectes.
    """
    n = len(highs)
    start_idx = max(0, n - lookback_bars)
    
    # Calculer la SSB pour chaque barre
    ssb_values = []
    for i in range(start_idx, n):
        if i >= 52:
            hh = np.max(highs[i-52:i])
            ll = np.min(lows[i-52:i])
            ssb = (hh + ll) / 2.0
            ssb_values.append((i, float(ssb)))
        else:
            ssb_values.append((i, None))
    
    # Detecter les segments plats
    levels = []
    i = 0
    while i < len(ssb_values):
        idx_i, val_i = ssb_values[i]
        if val_i is None:
            i += 1
            continue
        # Commencer un segment plat
        seg_start = i
        j = i + 1
        while j < len(ssb_values):
            idx_j, val_j = ssb_values[j]
            if val_j is None:
                break
            seg = [ssb_values[k][1] for k in range(seg_start, j + 1) if ssb_values[k][1] is not None]
            if len(seg) < 2:
                j += 1
                continue
            variation = (float(np.max(seg)) - float(np.min(seg))) / abs(float(min(seg))) * 100.0 if min(seg) != 0 else 999
            if variation > tolerance_pct:
                break
            j += 1
        seg_len = j - seg_start
        if seg_len >= min_flat_bars:
            seg_vals = [ssb_values[k][1] for k in range(seg_start, j) if ssb_values[k][1] is not None]
            avg_val = sum(seg_vals) / len(seg_vals)
            # Distance au prix actuel
            dist_pct = abs(close_price - avg_val) / avg_val * 100.0 if avg_val != 0 else 999
            position = "AU-DESSUS" if avg_val > close_price else "EN-DESSOUS"
            # Age: depuis combien de bougies ce niveau a ete forme
            last_idx = ssb_values[j - 1][0] if j - 1 >= 0 else 0
            age = n - 1 - last_idx
            
            levels.append(SsbFlatLevel(
                level=round(avg_val, 6),
                bars_count=seg_len,
                price_distance_pct=round(dist_pct, 4),
                position=position,
                age_bars=age,
            ))
        i = j
    
    # Classer: le plus fort = plus de bougies plates
    levels.sort(key=lambda x: (-x.bars_count, x.price_distance_pct))
    strongest = levels[0] if levels else None
    above = [l for l in levels if l.position == "AU-DESSUS"]
    below = [l for l in levels if l.position == "EN-DESSOUS"]
    
    # Niveaux les plus proches
    nearest_above = min((l.level for l in above), default=None)
    nearest_below = max((l.level for l in below), default=None)
    
    # Garder les plus significatifs (max 10)
    levels = levels[:10]
    above = above[:5]
    below = below[:5]
    
    return IchimokuSsbHistory(
        levels=levels,
        strongest_level=strongest,
        above_levels=above,
        below_levels=below,
        nearest_above=nearest_above,
        nearest_below=nearest_below,
    )


def compute_flat_analysis(highs: np.ndarray, lows: np.ndarray,
                           closes: np.ndarray, senkou_a: float,
                           senkou_b: float, kijun: float,
                           tenkan: float, close_price: float) -> Optional[IchimokuFlatLines]:
    """Analyse complete des lignes plates, passees et futures."""
    # Lignes futures (Senkou projete 26 periodes en avant)
    # Ce sont deja les valeurs calculees par compute_senkou_span_a/b
    future_a = senkou_a if not np.isnan(senkou_a) else 0.0
    future_b = senkou_b if not np.isnan(senkou_b) else 0.0
    future_thickness = abs(future_a - future_b)
    future_flat = False
    if close_price > 0:
        future_flat = (future_thickness / close_price * 100) < 0.05
    future_color = "VERT" if future_a > future_b else "ROUGE"

    # Ligne passee (Chikou affiche sur le graphique)
    past_chikou = compute_past_chikou(closes)
    past_chikou_flat = False
    if not np.isnan(past_chikou):
        # Construire une array du Chikou passe sur les dernieres periodes
        chikou_values = []
        for i in range(1, 8):
            idx = -(27 + i)
            if abs(idx) <= len(closes):
                chikou_values.append(float(closes[idx]))
        if len(chikou_values) >= 5:
            past_chikou_flat = detect_flat_line(np.array(chikou_values), 5, 0.05)

    # Lignes actuelles plates
    kijun_vals = []
    tenkan_vals = []
    for i in range(1, 22):
        idx = -(i + 1)
        if abs(idx) <= len(highs):
            k = (np.max(highs[-(i + 26):-i or None]) + np.min(lows[-(i + 26):-i or None])) / 2.0
            kijun_vals.append(k)
            t = (np.max(highs[-(i + 9):-i or None]) + np.min(lows[-(i + 9):-i or None])) / 2.0
            tenkan_vals.append(t)

    kijun_flat = detect_flat_line(np.array(kijun_vals), 5, 0.05) if len(kijun_vals) >= 6 else False
    tenkan_flat = detect_flat_line(np.array(tenkan_vals), 5, 0.05) if len(tenkan_vals) >= 6 else False
    kijun_flat_bars = detect_flat_bars(np.array(kijun_vals), 0.05, 20) if len(kijun_vals) >= 3 else 0

    # Epaisseur nuage
    cloud_thickness = abs(senkou_a - senkou_b) if not np.isnan(senkou_a) and not np.isnan(senkou_b) else 0.0
    cloud_thin = False
    if close_price > 0 and cloud_thickness > 0:
        cloud_thin = (cloud_thickness / close_price * 100) < 0.1

    # SSB plates historiques
    ssb_history = detect_ssb_flat_levels(highs, lows, close_price, 100, 3, 0.02)

    return IchimokuFlatLines(
        past_chikou=past_chikou if not np.isnan(past_chikou) else 0.0,
        past_chikou_flat=past_chikou_flat,
        future_senkou_a=future_a,
        future_senkou_b=future_b,
        future_cloud_thickness=future_thickness,
        future_cloud_flat=future_flat,
        future_cloud_color=future_color,
        kijun_flat=kijun_flat,
        tenkan_flat=tenkan_flat,
        kijun_flat_bars=kijun_flat_bars,
        cloud_thickness=cloud_thickness,
        cloud_thin=cloud_thin,
        ssb_history=ssb_history,
    )


def _compute_cloud(senkou_a: float, senkou_b: float, close_price: float) -> IchimokuCloud:
    """Analyse le nuage Senkou."""
    if np.isnan(senkou_a) or np.isnan(senkou_b):
        return IchimokuCloud(senkou_a=0, senkou_b=0, cloud_color="N/A",
                              above_cloud=False, below_cloud=False, inside_cloud=False)
    color = "VERT" if senkou_a > senkou_b else "ROUGE"
    above = close_price > max(senkou_a, senkou_b)
    below = close_price < min(senkou_a, senkou_b)
    inside = not above and not below
    return IchimokuCloud(senkou_a=senkou_a, senkou_b=senkou_b,
                          cloud_color=color, above_cloud=above,
                          below_cloud=below, inside_cloud=inside)


def _compute_tk_cross(highs: np.ndarray, lows: np.ndarray,
                       closes: np.ndarray) -> IchimokuTKCross:
    """Detecte le croisement Tenkan/Kijun."""
    n = len(highs)
    tenkan_now = compute_tenkan_sen(highs, lows, 9)
    kijun_now = compute_kijun_sen(highs, lows, 26)
    if np.isnan(tenkan_now) or np.isnan(kijun_now):
        return IchimokuTKCross(current_position="N/A", previous_position="N/A")

    # Position actuelle
    if tenkan_now > kijun_now:
        cur = "TENKAN_HAUT"
    elif kijun_now > tenkan_now:
        cur = "KIJUN_HAUT"
    else:
        cur = "EGAL"

    # Position precedente (1 bougie avant)
    if n >= 27:
        tenkan_prev = compute_tenkan_sen(highs[:-1], lows[:-1], 9)
        kijun_prev = compute_kijun_sen(highs[:-1], lows[:-1], 26)
        if not np.isnan(tenkan_prev) and not np.isnan(kijun_prev):
            if tenkan_prev > kijun_prev:
                prev = "TENKAN_HAUT"
            elif kijun_prev > tenkan_prev:
                prev = "KIJUN_HAUT"
            else:
                prev = "EGAL"
        else:
            prev = cur
    else:
        prev = cur

    # Detection du croisement
    cross = None
    bars_since = 99
    if prev == "KIJUN_HAUT" and cur == "TENKAN_HAUT":
        cross = "TK_CROSS_HAUSSIER"
        bars_since = 0
    elif prev == "TENKAN_HAUT" and cur == "KIJUN_HAUT":
        cross = "TK_CROSS_BAISSIER"
        bars_since = 0
    elif cur != "EGAL":
        # Chercher depuis combien de bougies
        for i in range(1, min(50, n - 26)):
            t = compute_tenkan_sen(highs[:-i], lows[:-i], 9) if n > i else float("nan")
            k = compute_kijun_sen(highs[:-i], lows[:-i], 26) if n > i else float("nan")
            if np.isnan(t) or np.isnan(k):
                break
            if (cur == "TENKAN_HAUT" and t <= k) or (cur == "KIJUN_HAUT" and k <= t):
                cross = "TK_CROSS_HAUSSIER" if cur == "TENKAN_HAUT" else "TK_CROSS_BAISSIER"
                bars_since = i - 1
                break

    return IchimokuTKCross(
        current_position=cur,
        previous_position=prev,
        cross_type=cross,
        bars_since_cross=bars_since,
    )


def _compute_chikou_analysis(closes: np.ndarray, kijun: float,
                              above_kijun: bool) -> IchimokuChikou:
    """Analyse la position du Chikou Span.

    Chikou = close actuel (projete 26 periodes en arriere).
    Signal haussier si Chikou > close d'il y a 26 periodes ET price > Kijun.
    """
    if len(closes) < 27:
        return IchimokuChikou(value=0, above_price_26=False, bullish_alignment=False)

    chikou_value = float(closes[-1])  # close actuel (valeur du Chikou)
    price_26_ago = float(closes[-27])  # prix il y a 26 periodes
    above = chikou_value > price_26_ago
    align = above and above_kijun
    return IchimokuChikou(value=chikou_value, above_price_26=above, bullish_alignment=align)


def compute_three_rules(cloud: Optional[IchimokuCloud], chikou: Optional[IchimokuChikou],
                          tk: Optional[IchimokuTKCross], above_kijun: bool) -> IchimokuThreeRules:
    """Les 3 regles d'or d'Ichimoku (Karen Péloille).

    Regle 1: Prix du bon cote du nuage
    Regle 2: Chikou aligne
    Regle 3: TK Cross dans la direction
    """
    # Regle 1: Position par rapport au nuage
    if cloud and cloud.above_cloud:
        r1 = True
        r1d = "AU-DESSUS"
        bias = "HAUSSIER"
    elif cloud and cloud.below_cloud:
        r1 = True
        r1d = "EN-DESSOUS"
        bias = "BAISSIER"
    elif cloud and cloud.inside_cloud:
        r1 = False
        r1d = "DANS-NUAGE"
        bias = "NEUTRE"
    else:
        r1 = False
        r1d = "N/A"
        bias = "NEUTRE"

    # Regle 2: Chikou aligne
    if chikou and chikou.bullish_alignment:
        r2 = True
        r2d = "ALIGNE"
        if bias == "NEUTRE":
            bias = "HAUSSIER"
    elif chikou and not chikou.above_price_26:
        r2 = False
        r2d = "NON-ALIGNE"
        bias = "BAISSIER" if bias == "NEUTRE" else bias
    elif chikou:
        r2 = False
        r2d = "NON-ALIGNE"
    else:
        r2 = False
        r2d = "N/A"

    # Regle 3: TK Cross
    if tk and tk.cross_type == "TK_CROSS_HAUSSIER":
        r3 = True
        r3d = "TK_CROSS_HAUSSIER"
        bias = "HAUSSIER"
    elif tk and tk.cross_type == "TK_CROSS_BAISSIER":
        r3 = True
        r3d = "TK_CROSS_BAISSIER"
        bias = "BAISSIER"
    elif tk and tk.current_position == "TENKAN_HAUT":
        r3 = False
        r3d = "TK>K"
    elif tk and tk.current_position == "KIJUN_HAUT":
        r3 = False
        r3d = "K>TK"
    else:
        r3 = False
        r3d = "N/A"

    validated = sum([r1, r2, r3])
    signal_type = bias
    if bias == "NEUTRE" or (r1 and r2 and r3):
        signal_type = "HAUSSIER" if (r1 and r2 and r3) else bias

    return IchimokuThreeRules(
        rule1_cloud=r1, rule1_detail=r1d,
        rule2_chikou=r2, rule2_detail=r2d,
        rule3_tk=r3, rule3_detail=r3d,
        rules_validated=validated,
        all_valid=(validated == 3),
        signal_type=signal_type,
    )


def compute_twist(highs: np.ndarray, lows: np.ndarray,
                  senkou_a: float, senkou_b: float,
                  close_price: float) -> Optional[IchimokuTwist]:
    """Detecte le 'twist' (croisement Senkou A / Senkou B).

    Le twist est le point ou le nuage change de couleur (Vert <-> Rouge).
    C'est une zone de retournement potentiel.
    """
    if np.isnan(senkou_a) or np.isnan(senkou_b):
        return None

    current_color = "VERT" if senkou_a > senkou_b else "ROUGE"

    # Couleur precedente (26 bougies avant pour le Senkou projete)
    n = len(highs)
    prev_a = float("nan")
    prev_b = float("nan")
    if n >= 27:
        tk_p = compute_tenkan_sen(highs[:-1], lows[:-1], 9)
        kj_p = compute_kijun_sen(highs[:-1], lows[:-1], 26)
        if not np.isnan(tk_p) and not np.isnan(kj_p):
            prev_a = (tk_p + kj_p) / 2.0
            prev_b = (np.max(highs[-53:-1]) + np.min(lows[-53:-1])) / 2.0 if n >= 53 else float("nan")
    else:
        prev_a = senkou_a
        prev_b = senkou_b

    if np.isnan(prev_a) or np.isnan(prev_b):
        previous_color = current_color
    else:
        previous_color = "VERT" if prev_a > prev_b else "ROUGE"

    twist_active = current_color != previous_color
    twist_type = None
    if twist_active:
        twist_type = f"{previous_color}->{current_color}"

    # Distance au twist (approximation: point ou A = B)
    twist_price = abs(senkou_a + senkou_b) / 2.0
    twist_dist = abs(close_price - twist_price) / twist_price * 100 if twist_price > 0 else 999

    # Bougies depuis le dernier twist
    bars_since = 99
    if twist_active:
        bars_since = 0
    else:
        for i in range(1, min(50, n - 26)):
            hh = highs[:n - i]
            ll = lows[:n - i]
            if len(hh) < 52:
                break
            ta = compute_tenkan_sen(hh, ll, 9)
            ka = compute_kijun_sen(hh, ll, 26)
            if np.isnan(ta) or np.isnan(ka):
                break
            sa_i = (ta + ka) / 2.0
            sb_i = (np.max(hh[-52:]) + np.min(ll[-52:])) / 2.0
            if np.isnan(sa_i) or np.isnan(sb_i):
                break
            col_i = "VERT" if sa_i > sb_i else "ROUGE"
            if col_i != current_color:
                bars_since = i - 1
                break

    return IchimokuTwist(
        current_color=current_color,
        previous_color=previous_color,
        twist_active=twist_active,
        twist_type=twist_type,
        bars_since_twist=bars_since,
        twist_distance_pct=round(twist_dist, 4),
    )


def compute_lagging_confirmation(highs: np.ndarray, lows: np.ndarray,
                                   closes: np.ndarray, kijun: float,
                                   senkou_a: float, senkou_b: float,
                                   above_kijun: bool) -> Optional[IchimokuLaggingConfirmation]:
    """Confirmation Lagging Span (Chikou).

    Le Chikou doit franchir le nuage ET la Kijun pour valider un mouvement.
    Si le Chikou echoue a traverser = manque de puissance.
    """
    n = len(highs)
    if n < 53:
        return None

    chikou_val = float(closes[-1])  # Chikou = close actuel

    # Kijun d'il y a 26 periodes
    kijun_26_ago = compute_kijun_sen(highs[:-26], lows[:-26], 26) if n >= 52 else float("nan")

    # Nuage d'il y a 26 periodes = Senkou A/B calcules 26 bougies avant
    if n >= 52:
        ta_26 = compute_tenkan_sen(highs[:-26], lows[:-26], 9) if n >= 35 else float("nan")
        ka_26 = compute_kijun_sen(highs[:-26], lows[:-26], 26) if n >= 52 else float("nan")
        if not np.isnan(ta_26) and not np.isnan(ka_26):
            sa_26 = (ta_26 + ka_26) / 2.0
            sb_26 = (np.max(highs[-78:-26]) + np.min(lows[-78:-26])) / 2.0 if n >= 78 else float("nan")
        else:
            sa_26 = float("nan")
            sb_26 = float("nan")
    else:
        sa_26 = float("nan")
        sb_26 = float("nan")

    # Analyses
    above_kijun_26 = chikou_val > kijun_26_ago if not np.isnan(kijun_26_ago) else False
    above_cloud_26 = False
    below_cloud_26 = False
    if not np.isnan(sa_26) and not np.isnan(sb_26):
        above_cloud_26 = chikou_val > max(sa_26, sb_26)
        below_cloud_26 = chikou_val < min(sa_26, sb_26)

    # Detection franchissement Kijun
    if n >= 54 and not np.isnan(kijun_26_ago):
        chikou_prev = float(closes[-2])
        above_kijun_prev = chikou_prev > kijun_26_ago
        franchit_kijun = not above_kijun_prev and above_kijun_26
    else:
        franchit_kijun = False

    # Detection franchissement nuage
    franchit_nuage = False
    if n >= 54 and not np.isnan(sa_26):
        chikou_prev = float(closes[-2])
        above_cloud_prev = chikou_prev > max(sa_26, sb_26) if not np.isnan(sa_26) else above_cloud_26
        franchit_nuage = not above_cloud_prev and above_cloud_26

    confirmation_h = above_kijun_26 and above_cloud_26 and above_kijun
    confirmation_b = not above_kijun_26 and below_cloud_26 and not above_kijun
    power = confirmation_h or confirmation_b

    parts = []
    if confirmation_h:
        parts.append("HAUSSIER CONFIRME")
    elif confirmation_b:
        parts.append("BAISSIER CONFIRME")
    if franchit_kijun:
        parts.append("FRANCHIT KIJUN")
    if franchit_nuage:
        parts.append("FRANCHIT NUAGE")
    if not power:
        if above_kijun_26:
            parts.append("CHIKOU>K26 MAIS PAS NUAGE")
        else:
            parts.append("CHIKOU PAS CONFIRME")

    return IchimokuLaggingConfirmation(
        chikou_above_kijun_past=above_kijun_26,
        chikou_above_cloud_past=above_cloud_26,
        chikou_below_cloud_past=below_cloud_26,
        chikou_françit_nuage=franchit_nuage,
        chikou_françit_kijun=franchit_kijun,
        confirmation_bullish=confirmation_h,
        confirmation_bearish=confirmation_b,
        power_confirmed=power,
        detail=" | ".join(parts) if parts else "PAS DE SIGNAL",
    )


def compute_full_ichimoku(
    symbol: str,
    timeframe_label: str,
    close_price: float,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    opens: Optional[np.ndarray] = None,
    kijun_period: int = 26,
) -> Optional[IchimokuResult]:
    """Analyse Ichimoku complete (5 elements + structure + 3 regles + twist + lagging).

    Args:
        symbol: Nom du symbole.
        timeframe_label: Label du timeframe.
        close_price: Prix de cloture actuel (ou tick).
        highs: Array des plus hauts.
        lows: Array des plus bas.
        closes: Array des closes (necessaire pour Chikou).
        opens: Array des opens (optionnel).
        kijun_period: Periode du Kijun (26).

    Retourne:
        IchimokuResult complet ou None.
    """
    if len(highs) < kijun_period + 5:
        return None

    kijun = compute_kijun_sen(highs, lows, kijun_period)
    tenkan = compute_tenkan_sen(highs, lows, 9)
    senkou_a = compute_senkou_span_a(highs, lows, 9, kijun_period, 26)
    senkou_b = compute_senkou_span_b(highs, lows, 52, 26)
    chikou = compute_chikou_span(closes, 26)

    if np.isnan(kijun):
        return None

    # Distance
    if kijun != 0:
        distance_pct = abs(close_price - kijun) / kijun * 100.0
    else:
        distance_pct = 0.0
    above_kijun = close_price > kijun

    # Analyses avancees
    sa = None if np.isnan(senkou_a) else senkou_a
    sb = None if np.isnan(senkou_b) else senkou_b
    cloud = _compute_cloud(
        sa if sa is not None else 0,
        sb if sb is not None else 0,
        close_price,
    ) if sa is not None and sb is not None else None

    tk = _compute_tk_cross(highs, lows, closes) if not np.isnan(tenkan) and not np.isnan(kijun) else None
    chikou_analysis = _compute_chikou_analysis(closes, kijun, above_kijun) if not np.isnan(chikou) else None

    # Analyse des lignes plates
    flat_analysis = compute_flat_analysis(
        highs, lows, closes,
        senkou_a, senkou_b, kijun, tenkan, close_price,
    ) if not np.isnan(kijun) else None

    # Les 3 regles d'or
    three_rules = compute_three_rules(cloud, chikou_analysis, tk, above_kijun)

    # Detection du twist
    twist = compute_twist(highs, lows, senkou_a, senkou_b, close_price)

    # Confirmation Lagging Span
    lagging = compute_lagging_confirmation(highs, lows, closes, kijun, senkou_a, senkou_b, above_kijun)

    return IchimokuResult(
        symbol=symbol,
        timeframe_label=timeframe_label,
        current_price=close_price,
        tenkan_sen=tenkan if not np.isnan(tenkan) else 0.0,
        kijun_sen=kijun,
        senkou_span_a=sa if sa is not None else 0.0,
        senkou_span_b=sb if sb is not None else 0.0,
        chikou_span=chikou if not np.isnan(chikou) else 0.0,
        distance_pct=round(distance_pct, 4),
        above_kijun=above_kijun,
        cloud=cloud,
        tk_cross=tk,
        chikou=chikou_analysis,
        flat=flat_analysis,
        three_rules=three_rules,
        twist=twist,
        lagging_confirmation=lagging,
        bars_count=len(highs),
        all_highs=[float(h) for h in highs],
        all_lows=[float(l) for l in lows],
        all_closes=[float(c) for c in closes],
        all_opens=[float(o) for o in opens] if opens is not None else [],
    )
