"""
Scan multi-timeframe des rejets du Kijun Sen + confluences.

Analyse H1, H4, D1, W1 pour chaque symbole et détecte :
  - Rejets haussiers/baissiers (avec ou sans mèche)
  - Éloignements après contact
  - Confluences : même actif signalé sur plusieurs timeframes
"""
import sys
from datetime import datetime, timezone
from collections import defaultdict

import MetaTrader5 as mt5
import numpy as np

# Timeframes MT5
TIMEFRAMES = {
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
}

NB_CANDLES = {
    "H1": 96,    # ~4 jours
    "H4": 80,    # ~13 jours
    "D1": 55,    # ~55 jours
    "W1": 52,    # ~1 an
}


def compute_kijun(highs, lows, idx=-1, period=26):
    """Calcule le Kijun Sen sur `period` bougies finissant à `idx`."""
    start = idx - period + 1
    if start < 0:
        return None
    hh = np.max(highs[start:idx + 1])
    ll = np.min(lows[start:idx + 1])
    return float((hh + ll) / 2.0)


def detect_rejets_multi(highs, lows, closes, opens, lookback=10, contact_pct=0.5):
    """
    Détecte les rejets du Kijun sur les `lookback` dernières bougies.

    Retourne le meilleur rejet trouvé (dict) ou None.
    """
    n = len(highs)
    if n < 35:
        return None

    best = None

    for i in range(2, lookback + 2):
        idx = n - i
        if idx < 26:
            continue

        kijun_then = compute_kijun(highs, lows, idx, 26)
        if kijun_then is None:
            continue

        close_then = float(closes[idx])
        high_then = float(highs[idx])
        low_then = float(lows[idx])
        open_then = float(opens[idx])
        dist_then = abs(close_then - kijun_then) / kijun_then * 100
        above_then = close_then > kijun_then

        # Seuil d'approche du Kijun
        if dist_then >= contact_pct:
            continue

        # Bougie suivante
        idx_next = idx + 1
        if idx_next >= n:
            continue

        kijun_next = compute_kijun(highs, lows, idx_next, 26)
        if kijun_next is None:
            continue

        close_next = float(closes[idx_next])
        dist_next = abs(close_next - kijun_next) / kijun_next * 100
        above_next = close_next > kijun_next

        is_rejet = False
        rejet_type = ""

        if above_then and not above_next:
            is_rejet = True
            rejet_type = "REJET_BAISSIER"
            body = abs(close_then - open_then)
            if body > 0:
                upper_wick = high_then - max(close_then, open_then)
                if upper_wick > body * 0.5:
                    rejet_type = "REJET_BAISSIER_MECHE"

        elif not above_then and above_next:
            is_rejet = True
            rejet_type = "REJET_HAUSSIER"
            body = abs(close_then - open_then)
            if body > 0:
                lower_wick = min(close_then, open_then) - low_then
                if lower_wick > body * 0.5:
                    rejet_type = "REJET_HAUSSIER_MECHE"

        elif dist_next > dist_then * 2 and dist_next > 0.3:
            is_rejet = True
            rejet_type = "ELOIGNEMENT_HAUSSIER" if above_then and above_next else "ELOIGNEMENT_BAISSIER"

        if not is_rejet:
            continue

        # Kijun actuel
        kijun_now = compute_kijun(highs, lows, n - 1, 26)
        if kijun_now is None:
            continue
        price_now = float(closes[-1])
        dist_now = abs(price_now - kijun_now) / kijun_now * 100
        above_now = price_now > kijun_now

        result = {
            'bougie_idx': i,
            'kijun_then': kijun_then,
            'price_then': close_then,
            'dist_then': dist_then,
            'dist_next': dist_next,
            'dist_now': dist_now,
            'rejet_type': rejet_type,
            'above_then': above_then,
            'above_now': above_now,
        }

        if best is None or dist_then < best['dist_then']:
            best = result

    return best


def format_rejet_type(t):
    """Formate lisiblement le type de rejet."""
    labels = {
        "REJET_HAUSSIER": "Rejet haussier",
        "REJET_HAUSSIER_MECHE": "Rejet haussier (meche)",
        "REJET_BAISSIER": "Rejet baissier",
        "REJET_BAISSIER_MECHE": "Rejet baissier (meche)",
        "ELOIGNEMENT_HAUSSIER": "Eloignement haussier",
        "ELOIGNEMENT_BAISSIER": "Eloignement baissier",
    }
    return labels.get(t, t)


def main():
    if not mt5.initialize():
        print("ERREUR: echec mt5.initialize()")
        sys.exit(1)

    # Récupérer tous les symboles
    all_symbols = mt5.symbols_get()
    total = len(all_symbols)
    print(f"Total symboles MT5: {total}")
    print()

    # Structure : { tf_label: { sym: rejet_dict } }
    rejets_par_tf = defaultdict(dict)
    symboles_par_tf = defaultdict(list)

    for tf_label, tf_value in TIMEFRAMES.items():
        nb = NB_CANDLES[tf_label]
        print(f"[{tf_label}] Scan de {total} symboles ({nb} bougies)...")

        count = 0
        for s in all_symbols:
            sym = s.name
            mt5.symbol_select(sym, True)
            rates = mt5.copy_rates_from_pos(sym, tf_value, 0, nb)
            if rates is None or len(rates) < 30:
                continue

            highs = rates["high"]
            lows = rates["low"]
            closes = rates["close"]
            opens = rates["open"]

            rejet = detect_rejets_multi(highs, lows, closes, opens,
                                        lookback=12 if tf_label in ("H1", "H4") else 8,
                                        contact_pct=0.5)
            if rejet:
                rejets_par_tf[tf_label][sym] = rejet
                symboles_par_tf[tf_label].append(sym)
                count += 1

        print(f"  -> {count} rejets detectes")
        mt5.shutdown()
        if not mt5.initialize():
            print("ERREUR: reconnexion MT5")
            sys.exit(1)

    mt5.shutdown()

    # -----------------------------------------------------------------------
    # CONFLUENCES : symboles presents sur plusieurs timeframes
    # -----------------------------------------------------------------------
    all_sym_set = set()
    for syms in symboles_par_tf.values():
        all_sym_set.update(syms)

    confluence_scores = {}
    for sym in all_sym_set:
        tfs_presents = [tf for tf in TIMEFRAMES if sym in symboles_par_tf[tf]]
        if len(tfs_presents) >= 2:
            # Score : 1 point par timeframe + bonus si types complementaires
            score = len(tfs_presents)
            types_tf = {}
            for tf in tfs_presents:
                r = rejets_par_tf[tf][sym]
                t = r['rejet_type']
                types_tf[tf] = t
                if 'MECHE' in t:
                    score += 1  # Bonus meche
            confluence_scores[sym] = {
                'timeframes': tfs_presents,
                'types': types_tf,
                'score': score,
            }

    # -----------------------------------------------------------------------
    # AFFICHAGE
    # -----------------------------------------------------------------------
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print()
    print("=" * 100)
    print(f"  SCAN MULTI-TIMEFRAME : REJETS KIJUN + CONFLUENCES")
    print(f"  {now_str}")
    print("=" * 100)

    for tf_label in TIMEFRAMES:
        print()
        print(f"─── {tf_label} : {len(symboles_par_tf[tf_label])} rejets ───")
        print(f"  {'Symbole':<12} {'Type':<28} {'Dist@contact':<14} {'Dist@actuelle':<14} {'Dir':<6}")
        print(f"  {'-'*12} {'-'*28} {'-'*14} {'-'*14} {'-'*6}")

        rejets_tf = sorted(rejets_par_tf[tf_label].items(), key=lambda x: x[1]['dist_then'])
        for sym, r in rejets_tf[:20]:
            dir_sym = "HAUT" if r['above_now'] else "BAS"
            print(f"  {sym:<12} {format_rejet_type(r['rejet_type']):<28} {r['dist_then']:.3f}%         {r['dist_now']:.3f}%         {dir_sym:<6}")
        if len(rejets_tf) > 20:
            print(f"  ... et {len(rejets_tf) - 20} autres")

    # Confluences
    print()
    print("=" * 100)
    print("  CONFLUENCES MULTI-TIMEFRAMES")
    print("  (meme actif rejete sur 2+ timeframes simultanement)")
    print("=" * 100)

    sorted_conf = sorted(confluence_scores.items(), key=lambda x: -x[1]['score'])

    if not sorted_conf:
        print("\n  Aucune confluence detectee.")
    else:
        print(f"\n  {'Symbole':<12} {'TF':<18} {'Types':<55} {'Score':<6}")
        print(f"  {'-'*12} {'-'*18} {'-'*55} {'-'*6}")
        for sym, info in sorted_conf:
            tfs_str = ", ".join(info['timeframes'])
            types_str = " | ".join(f"{tf}={format_rejet_type(t)}" for tf, t in info['types'].items())
            print(f"  {sym:<12} {tfs_str:<18} {types_str:<55} {info['score']:<6}")

        # Top confluences
        print()
        print("  ─── TOP 10 CONFLUENCES ───")
        print()
        for rank, (sym, info) in enumerate(sorted_conf[:10], 1):
            tfs_list = info['timeframes']
            types_detail = " / ".join(f"{tf}:{format_rejet_type(info['types'][tf])}" for tf in tfs_list)
            dirs = set()
            for tf in tfs_list:
                r = rejets_par_tf[tf][sym]
                dirs.add("HAUSSIER" if r['above_now'] else "BAISSIER")
            dir_consistency = "CONSISTANT" if len(dirs) == 1 else "MIXTE"
            print(f"  #{rank:<2} {sym:<12} [{', '.join(tfs_list):<14}] {types_detail}")
            print(f"      Direction: {' / '.join(dirs)} ({dir_consistency})")

    # Résumé stats
    print()
    print("─" * 100)
    print("  STATISTIQUES")
    print("─" * 100)
    total_rejets = sum(len(v) for v in symboles_par_tf.values())
    print(f"  Total rejets: {total_rejets}")
    for tf_label in TIMEFRAMES:
        print(f"    {tf_label}: {len(symboles_par_tf[tf_label])}")
    print(f"  Confluences (2+ TF): {len(confluence_scores)}")
    print(f"  Top confluence: {sorted_conf[0][0]} ({sorted_conf[0][1]['score']} pts)" if sorted_conf else "  Aucune")

    # Résumé par type
    print()
    print("  Rejets par type :")
    type_counts = defaultdict(int)
    for tf, rejets in rejets_par_tf.items():
        for sym, r in rejets.items():
            type_counts[r['rejet_type']] += 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {format_rejet_type(t):<30}: {c}")

    print()


if __name__ == "__main__":
    main()
