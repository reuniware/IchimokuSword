"""
Analyse scoring : Quel actif trader aujourd'hui ?

Criteres :
  - Proximite du Kijun (mieux = score eleve)
  - Direction consistante sur H1, H4, D1, W1 (bonus si aligne)
  - Rejet recent (meche, eloignement) (bonus)
  - Liquidite (forex majeur > indices > crosses > metaux)
"""
import MetaTrader5 as mt5
from datetime import datetime, timezone
import numpy as np
from dataclasses import asdict

# Importer la detection SSB depuis le module central
from src.ichimoku import detect_ssb_flat_levels

TIMEFRAMES = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
              "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1}
NB = {"H1": 96, "H4": 80, "D1": 60, "W1": 52}

LIQUIDITY = {
    "EURUSD": 10, "GBPUSD": 9, "USDJPY": 9, "USDCAD": 8, "AUDUSD": 8,
    "NZDUSD": 7, "USDCHF": 7, "XAUUSD": 9, "XAGUSD": 7,
}
DEFAULT_LIQ = 5

CATEGORIES = {
    "METAUX": ["XAUUSD", "XAGUSD", "XPDUSD", "XPTUSD", "XAUEUR", "XAUAUD"],
    "FOREX_MAJORS": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF"],
    "FOREX_CROSSES": [
        "EURJPY", "GBPJPY", "EURGBP", "EURAUD", "EURCHF",
        "GBPCHF", "AUDJPY", "CHFJPY", "CADJPY",
        "AUDCAD", "NZDCAD", "GBPCAD", "AUDCHF", "AUDNZD",
        "EURNZD", "GBPNZD", "EURNOK", "EURSEK",
        "EURCZK", "USDSEK", "USDPLN", "EURPLN",
        "USDHUF", "EURHUF", "USDSGD", "USDCNH",
        "USDZAR", "USDMXN",
    ],
    "INDICES": [
        "US30", "SP500", "NAS100", "US100.cash", "US500.cash", "US30.cash",
        "GER40", "UK100", "FRA40", "JPN225", "AUS200.cash",
        "N25.cash", "HK50",
    ],
}


def kijun(highs, lows, idx=-1, p=26):
    s = idx - p + 1
    if s < 0:
        return None
    return float((np.max(highs[s:idx + 1]) + np.min(lows[s:idx + 1])) / 2.0)


def tenkan(highs, lows, idx=-1):
    s = idx - 9 + 1
    if s < 0:
        return None
    return float((np.max(highs[s:idx + 1]) + np.min(lows[s:idx + 1])) / 2.0)


def detect_rejet(highs, lows, closes, opens, lookback=8, contact_pct=0.5):
    """Detecte le meilleur rejet recent."""
    n = len(highs)
    best = None
    for i in range(2, lookback + 2):
        idx = n - i
        if idx < 26:
            continue
        k_then = kijun(highs, lows, idx, 26)
        if k_then is None:
            continue
        ct = float(closes[idx])
        ht = float(highs[idx])
        lt = float(lows[idx])
        ot = float(opens[idx])
        dt = abs(ct - k_then) / k_then * 100
        abv_then = ct > k_then
        if dt >= contact_pct:
            continue
        idx_n = idx + 1
        if idx_n >= n:
            continue
        k_n = kijun(highs, lows, idx_n, 26)
        if k_n is None:
            continue
        cn = float(closes[idx_n])
        dn = abs(cn - k_n) / k_n * 100
        abv_n = cn > k_n
        rtype = None
        if abv_then and not abv_n:
            body = abs(ct - ot)
            uw = ht - max(ct, ot)
            rtype = "REJET_BAISSIER_MECHE" if (body > 0 and uw > body * 0.5) else "REJET_BAISSIER"
        elif not abv_then and abv_n:
            body = abs(ct - ot)
            lw = min(ct, ot) - lt
            rtype = "REJET_HAUSSIER_MECHE" if (body > 0 and lw > body * 0.5) else "REJET_HAUSSIER"
        elif dn > dt * 2 and dn > 0.3:
            rtype = "ELOIGNEMENT_HAUSSIER" if abv_n else "ELOIGNEMENT_BAISSIER"
        if rtype:
            score = 0
            if "MECHE" in rtype:
                score += 3
            elif "REJET" in rtype:
                score += 2
            else:
                score += 1
            score += max(0, 5 - dt * 10)  # plus proche = mieux
            if best is None or score > best["score"]:
                best = {"type": rtype, "dist_then": dt, "dist_next": dn, "score": score}
    return best


def analyze_tk_cross(highs, lows):
    """Analyse le croisement Tenkan/Kijun."""
    n = len(highs)
    tk_now = tenkan(highs, lows, n - 1)
    kj_now = kijun(highs, lows, n - 1, 26)
    if tk_now is None or kj_now is None:
        return None
    
    tk_prev = tenkan(highs, lows, n - 2) if n >= 2 else None
    kj_prev = kijun(highs, lows, n - 2, 26) if n >= 2 else None
    
    status = "TK>K" if tk_now > kj_now else ("K>TK" if kj_now > tk_now else "EGAL")
    cross = None
    if tk_prev and kj_prev:
        if tk_prev <= kj_prev and tk_now > kj_now:
            cross = "TK_CROSS_HAUSSIER"
        elif tk_prev >= kj_prev and tk_now < kj_now:
            cross = "TK_CROSS_BAISSIER"
    
    return {"status": status, "cross": cross, "tk": tk_now, "kj": kj_now}


def analyze_cloud_position(senkou_a, senkou_b, price):
    """Analyse la position du prix par rapport au nuage."""
    if not senkou_a or not senkou_b:
        return None
    above = price > max(senkou_a, senkou_b)
    below = price < min(senkou_a, senkou_b)
    inside = not above and not below
    color = "VERT" if senkou_a > senkou_b else "ROUGE"
    return {"above": above, "below": below, "inside": inside, "color": color}


def analyze_chikou(closes, above_kijun):
    """Analyse le Chikou Span.

    Chikou = close actuel projete 26 periodes en arriere.
    Signal haussier: Chikou (close actuel) > close d'il y a 26 periodes.
    """
    n = len(closes)
    if n < 27:
        return None
    chikou_val = float(closes[-1])  # close actuel = valeur du Chikou
    price_26_ago = float(closes[-27])  # close il y a 26 periodes
    above = chikou_val > price_26_ago
    align = above and above_kijun
    return {"value": chikou_val, "above_price": above, "aligned": align}


def detect_flat_line(values, lookback=5, tolerance_pct=0.05):
    """Detecte si une ligne est plate."""
    if len(values) < lookback + 1:
        return False
    seg = values[-(lookback + 1):]
    base = abs(seg[0]) if seg[0] != 0 else 1
    variation = (max(seg) - min(seg)) / base * 100.0
    return variation <= tolerance_pct


def detect_flat_bars(values, tolerance_pct=0.05, max_lookback=20):
    """Depuis combien de bougies une ligne est plate."""
    if len(values) < 3:
        return 0
    count = 0
    for i in range(min(max_lookback, len(values) - 1)):
        seg = values[-(i + 3):]
        base = abs(seg[0]) if seg[0] != 0 else 1
        var = (max(seg) - min(seg)) / base * 100.0
        if var <= tolerance_pct:
            count += 1
        else:
            break
    return count


def compute_flat_analysis_recommend(highs, lows, closes, senkou_a, senkou_b, kijun_val, tenkan_val, close_price):
    """Analyse des lignes plates pour le scoring."""
    n = len(highs)
    
    # Kijun plat ?
    kijun_vals = []
    tenkan_vals = []
    for i in range(1, 22):
        idx = n - i - 1
        if idx < 26:
            break
        k = (max(highs[idx-25:idx+1]) + min(lows[idx-25:idx+1])) / 2.0
        kijun_vals.append(k)
        t = (max(highs[idx-8:idx+1]) + min(lows[idx-8:idx+1])) / 2.0
        tenkan_vals.append(t)
    
    kijun_flat = detect_flat_line(np.array(kijun_vals), 5, 0.05) if len(kijun_vals) >= 6 else False
    tenkan_flat = detect_flat_line(np.array(tenkan_vals), 5, 0.05) if len(tenkan_vals) >= 6 else False
    kijun_flat_bars = detect_flat_bars(np.array(kijun_vals), 0.05, 20) if len(kijun_vals) >= 3 else 0
    
    # Chikou passe plat ?
    past_chikou = float(closes[-27]) if len(closes) >= 27 else 0
    chikou_vals = []
    for i in range(1, 8):
        idx = -(27 + i)
        if abs(idx) <= len(closes):
            chikou_vals.append(float(closes[idx]))
    past_chikou_flat = detect_flat_line(np.array(chikou_vals), 5, 0.05) if len(chikou_vals) >= 5 else False
    
    # Nuage futur plat ?
    future_thickness = abs(senkou_a - senkou_b) if senkou_a and senkou_b else 0
    future_cloud_flat = (future_thickness / close_price * 100) < 0.05 if close_price > 0 and future_thickness > 0 else False
    
    # Epaisseur nuage
    cloud_thickness = abs(senkou_a - senkou_b) if senkou_a and senkou_b else 0
    cloud_thin = (cloud_thickness / close_price * 100) < 0.1 if close_price > 0 and cloud_thickness > 0 else False
    
    # SSB plates historiques
    ssb_result = detect_ssb_flat_levels(highs, lows, close_price, 100, 3, 0.02)
    ssb_history = asdict(ssb_result) if ssb_result else None

    return {
        "kijun_flat": kijun_flat,
        "tenkan_flat": tenkan_flat,
        "kijun_flat_bars": kijun_flat_bars,
        "past_chikou": past_chikou,
        "past_chikou_flat": past_chikou_flat,
        "future_cloud_flat": future_cloud_flat,
        "cloud_thickness": cloud_thickness,
        "cloud_thin": cloud_thin,
        "ssb_history": ssb_history,
    }


def compute_three_rules_recommend(cloud, chikou, tk_cross, above_kijun):
    """Calcule les 3 regles d'or pour le scoring."""
    r1 = False
    r2 = False
    r3 = False
    
    if cloud:
        r1 = cloud["above"] or cloud["below"]
    
    if chikou:
        r2 = chikou["aligned"]
    
    if tk_cross:
        r3 = tk_cross["cross"] is not None
    
    return {"r1": r1, "r2": r2, "r3": r3, "validated": sum([r1, r2, r3])}


def compute_twist_recommend(highs, lows, senkou_a, senkou_b):
    """Detecte le twist (croisement Senkou A/B) pour le scoring."""
    if not senkou_a or not senkou_b:
        return None
    n = len(highs)
    cur = "VERT" if senkou_a > senkou_b else "ROUGE"
    if n >= 27:
        tk_p = tenkan(highs, lows, n - 2) if n >= 2 else None
        kj_p = kijun(highs, lows, n - 2, 26) if n >= 2 else None
        if tk_p and kj_p and n >= 53:
            sa_p = (tk_p + kj_p) / 2.0
            sb_p = (np.max(highs[-53:-1]) + np.min(lows[-53:-1])) / 2.0
            if sb_p is not None:
                prev = "VERT" if sa_p > sb_p else "ROUGE"
            else:
                prev = cur
        else:
            prev = cur
    else:
        prev = cur
    active = cur != prev
    twist_type = f"{prev}->{cur}" if active else None
    return {"active": active, "type": twist_type, "current": cur}


def compute_lagging_recommend(closes, senkou_a, senkou_b, above_kijun):
    """Analyse la confirmation Lagging Span pour le scoring."""
    n = len(closes)
    if n < 27:
        return None
    chikou_val = float(closes[-1])
    if n >= 53:
        # Chikou compare avec le nuage d'il y a 26 periodes
        price_26 = float(closes[-27])
        above_cloud = chikou_val > max(senkou_a, senkou_b) if senkou_a and senkou_b else False
        below_cloud = chikou_val < min(senkou_a, senkou_b) if senkou_a and senkou_b else False
        bullish = above_kijun and above_cloud
        bearish = not above_kijun and below_cloud
        return {"confirmed": bullish or bearish, "bullish": bullish, "bearish": bearish,
                "above_cloud": above_cloud, "below_cloud": below_cloud}
    return None


def compute_ichimoku_data(highs, lows, closes, opens, n, price):
    """Calcule tous les elements Ichimoku pour le scoring."""
    k = kijun(highs, lows, n - 1, 26)
    tk = tenkan(highs, lows, n - 1)
    c = price
    
    if k is None:
        return None
    
    d = abs(c - k) / k * 100
    a = c > k
    rejet = detect_rejet(highs, lows, closes, opens, 8, 0.5)
    tk_cross = analyze_tk_cross(highs, lows)
    
    # Senkou A = (Tenkan + Kijun) / 2
    sa = (tk + k) / 2.0 if tk is not None else None
    # Senkou B = (HH52 + LL52) / 2
    if n >= 52:
        sb = (np.max(highs[-52:]) + np.min(lows[-52:])) / 2.0
    else:
        sb = None
    
    cloud = analyze_cloud_position(sa, sb, c) if sa and sb else None
    chikou = analyze_chikou(closes, a)
    flat = compute_flat_analysis_recommend(highs, lows, closes, sa, sb, k, tk, c)
    
    # Nouveaux concepts
    three_rules = compute_three_rules_recommend(cloud, chikou, tk_cross, a)
    twist = compute_twist_recommend(highs, lows, sa, sb)
    lagging = compute_lagging_recommend(closes, sa, sb, a)
    
    return {
        "kijun": k, "tenkan": tk, "close": c, "dist": d, "above": a,
        "rejet": rejet, "tk_cross": tk_cross,
        "senkou_a": sa, "senkou_b": sb, "cloud": cloud, "chikou": chikou,
        "flat": flat,
        "three_rules": three_rules,
        "twist": twist,
        "lagging": lagging,
    }


def main():
    if not mt5.initialize():
        print("ERREUR: connexion MT5")
        return

    now = datetime.now(timezone.utc)
    all_symbols = {s.name: s for s in mt5.symbols_get()}

    print("=" * 130)
    print("  RECHERCHE DU MEILLEUR ACTIF A TRADER AUJOURD'HUI")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 130)

    all_scores = []

    for cat_name, cat_symbols in CATEGORIES.items():
        for sym in cat_symbols:
            if sym not in all_symbols:
                continue
            mt5.symbol_select(sym, True)

            tf_data = {}
            has_data = 0
            for tf_label, tf_val in TIMEFRAMES.items():
                r = mt5.copy_rates_from_pos(sym, tf_val, 0, NB[tf_label])
                if r is None or len(r) < 26:
                    tf_data[tf_label] = None
                    continue
                highs, lows, closes, opens_arr = r["high"], r["low"], r["close"], r["open"]
                n = len(highs)
                c = float(closes[-1])
                ichi = compute_ichimoku_data(highs, lows, closes, opens_arr, n, c)
                if ichi is None:
                    tf_data[tf_label] = None
                    continue
                tf_data[tf_label] = ichi
                has_data += 1

            if has_data < 3:
                continue

            # --- SCORING (Ichimoku complet) ---
            liq = LIQUIDITY.get(sym, DEFAULT_LIQ)

            score_prox = 0
            score_dir = 0
            score_rejet = 0
            score_cloud = 0
            score_tk = 0
            score_chikou = 0

            for tf in TIMEFRAMES:
                d = tf_data[tf]
                if not d:
                    continue

                # Proximite Kijun
                if d["dist"] < 0.1:
                    score_prox += 10
                elif d["dist"] < 0.3:
                    score_prox += 8
                elif d["dist"] < 0.5:
                    score_prox += 5
                elif d["dist"] < 1.0:
                    score_prox += 2

                # Nuage Senkou
                if d["cloud"]:
                    if d["cloud"]["above"]:
                        score_cloud += 6
                    elif d["cloud"]["inside"]:
                        score_cloud += 1  # Dans le nuage = indecision
                    # Bonus couleur: vert en haussier, rouge en baissier
                    if d["above"] and d["cloud"]["color"] == "VERT":
                        score_cloud += 3
                    elif not d["above"] and d["cloud"]["color"] == "ROUGE":
                        score_cloud += 3

                # TK Cross
                if d["tk_cross"]:
                    if d["tk_cross"]["cross"] == "TK_CROSS_HAUSSIER":
                        score_tk += 8
                    elif d["tk_cross"]["cross"] == "TK_CROSS_BAISSIER":
                        score_tk += 8
                    if d["tk_cross"]["status"] == "TK>K":
                        score_tk += 3
                    elif d["tk_cross"]["status"] == "K>TK":
                        score_tk += 1

                # Chikou
                if d["chikou"]:
                    if d["chikou"]["aligned"]:
                        score_chikou += 8
                    elif d["chikou"]["above_price"]:
                        score_chikou += 3

                # Rejet
                if d["rejet"]:
                    score_rejet += d["rejet"]["score"]

            # Direction
            dirs = [v["above"] for v in tf_data.values() if v]
            nb_haut = sum(1 for a in dirs if a)
            nb_bas = sum(1 for a in dirs if not a)
            dir_score = 0
            if nb_haut == 4 or nb_bas == 4:
                dir_score = 15
            elif nb_haut == 3 or nb_bas == 3:
                dir_score = 8
            elif nb_haut == 2 or nb_bas == 2:
                dir_score = 2

            # Score 3 regles d'or
            score_rules = 0
            for tf in TIMEFRAMES:
                d = tf_data[tf]
                if not d or not d.get("three_rules"):
                    continue
                rules = d["three_rules"]
                if rules["validated"] == 3:
                    score_rules += 12  # 3/3 = signal fort
                elif rules["validated"] == 2:
                    score_rules += 5   # 2/3 = signal modere
                elif rules["validated"] == 1:
                    score_rules += 1   # 1/3 = faible

            # Score twist (changement de nuage = zone de retournement)
            score_twist = 0
            for tf in TIMEFRAMES:
                d = tf_data[tf]
                if not d or not d.get("twist") or not d["twist"]["active"]:
                    continue
                # Twist recent = signal fort (changement de tendance potentiel)
                score_twist += 6
                if d["twist"]["type"] and "ROUGE->VERT" in d["twist"]["type"]:
                    score_twist += 3  # Twist haussier bonus
                elif d["twist"]["type"] and "VERT->ROUGE" in d["twist"]["type"]:
                    score_twist += 3  # Twist baissier bonus

            # Score Lagging confirmation
            score_lagging = 0
            for tf in TIMEFRAMES:
                d = tf_data[tf]
                if not d or not d.get("lagging") or not d["lagging"]["confirmed"]:
                    continue
                score_lagging += 8
                if d["lagging"]["bullish"]:
                    score_lagging += 2
                elif d["lagging"]["bearish"]:
                    score_lagging += 2

    # Score lignes plates (bonus si pas plat = tendance claire)
    score_flat = 0
    for tf in TIMEFRAMES:
        d = tf_data[tf]
        if not d or not d.get("flat"):
            continue
        fl = d["flat"]
        # Kijun plat = range = penalite (-3)
        if fl["kijun_flat"]:
            score_flat -= 3
        # Tenkan plat = consolidation court terme
        if fl["tenkan_flat"]:
            score_flat -= 2
        # Nuage futur plat = consolidation projete
        if fl["future_cloud_flat"]:
            score_flat -= 2
        # Chikou passe plat = range historique
        if fl["past_chikou_flat"]:
            score_flat -= 1
        # Nuage fin = support/resistance faible
        if fl["cloud_thin"]:
            score_flat -= 1
        
        # SSB plates historiques
        # Plus il y a de niveaux SSB, plus la zone est technique
        # Plus ils sont proches, plus ils sont actifs
        if fl.get("ssb_history"):
            sh = fl["ssb_history"]
            for lvl in sh.get("levels", []):
                if lvl["position"] == "AU-DESSUS" and lvl["price_distance_pct"] < 1.0:
                    score_flat -= 1  # Resistance proche = penalite
                elif lvl["position"] == "EN-DESSOUS" and lvl["price_distance_pct"] < 1.0:
                    score_flat += 1  # Support proche = bonus (prix sur support)

    total = (score_prox + dir_score + score_rejet + score_cloud + score_tk
             + score_chikou + score_rules + score_twist + score_lagging
             + score_flat + liq * 0.5)

    direction = "HAUSSIER" if nb_haut > nb_bas else "BAISSIER"
    dir_align = f"{nb_haut}/{nb_bas}"

    all_scores.append({
        "sym": sym, "cat": cat_name,
        "total": total,
        "prox": score_prox, "dir_score": dir_score,
        "rejet_score": score_rejet,
        "cloud_score": score_cloud,
        "tk_score": score_tk,
        "chikou_score": score_chikou,
        "rules_score": score_rules,
        "twist_score": score_twist,
        "lagging_score": score_lagging,
        "flat_score": score_flat,
        "liq": liq,
        "direction": direction, "dir_detail": dir_align,
        "tf_data": tf_data,
    })

    all_scores.sort(key=lambda x: -x["total"])

    # --- AFFICHAGE TOP 10 ---
    print(f"\n  {'':>3} {'Symbole':<14} {'Categorie':<18} {'Score':<8} {'Prox':<6} {'Dir':<6} {'Nuage':<6} {'TK':<6} {'Chikou':<6} {'3R':<5} {'Twist':<6} {'Lag':<5} {'Plat':<5} {'Rejet':<6} {'Liq':<4} {'Signal':<12}")
    print(f"  {'-'*3} {'-'*14} {'-'*18} {'-'*8} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*5} {'-'*6} {'-'*5} {'-'*5} {'-'*6} {'-'*4} {'-'*12}")
    for rank, s in enumerate(all_scores[:15], 1):
        print(f"  {rank:<3} {s['sym']:<14} {s['cat']:<18} {s['total']:<8.1f} {s['prox']:<6} {s['dir_score']:<6} {s['cloud_score']:<6} {s['tk_score']:<6} {s['chikou_score']:<6} {s['rules_score']:<5} {s['twist_score']:<6} {s['lagging_score']:<5} {s['flat_score']:<5} {s['rejet_score']:<6} {s['liq']:<4} {s['direction']:<12}")

    # --- DETAIL TOP 3 ---
    print(f"\n{'=' * 130}")
    print(f"  TOP 3 RECOMMANDATIONS")
    print(f"{'=' * 130}")

    for rank, s in enumerate(all_scores[:3], 1):
        print(f"\n  #{rank} - {s['sym']} ({s['cat']})")
        print(f"  {'-' * 90}")
        print(f"  Score total: {s['total']:.1f} (prox={s['prox']}, dir={s['dir_score']}, "
              f"nuage={s['cloud_score']}, tk={s['tk_score']}, chikou={s['chikou_score']}, "
              f"3regles={s['rules_score']}, twist={s['twist_score']}, lagging={s['lagging_score']}, "
              f"plat={s['flat_score']}, rejet={s['rejet_score']}, liq={s['liq']})")
        print(f"  Direction: {s['direction']} ({s['dir_detail']} timeframes)")
        for tf in TIMEFRAMES:
            d = s["tf_data"][tf]
            if d:
                dir_sym = "HAUT" if d["above"] else "BAS "
                extras = []
                # 3 regles
                if d.get("three_rules"):
                    rules = d["three_rules"]
                    extras.append(f"3R:{rules['validated']}/3")
                # Twist
                if d.get("twist") and d["twist"]["active"]:
                    extras.append(f"TWIST:{d['twist']['type']}")
                # Lagging
                if d.get("lagging") and d["lagging"]["confirmed"]:
                    extras.append("LAG_CONFIRME")
                # TK Cross
                if d["tk_cross"] and d["tk_cross"]["cross"]:
                    extras.append(f"TK:{d['tk_cross']['cross']}")
                if d["cloud"]:
                    pos = "NUAGE" if d["cloud"]["inside"] else ("A-DESSUS" if d["cloud"]["above"] else "DESSOUS")
                    extras.append(f"{pos}({d['cloud']['color']})")
                if d["chikou"] and d["chikou"]["aligned"]:
                    extras.append("CHIKOU_OK")
                if d["rejet"]:
                    extras.append(f"REJET:{d['rejet']['type']}")
                if d.get("flat"):
                    fl = d["flat"]
                    if fl["kijun_flat"]:
                        extras.append(f"KJ_PLAT({fl['kijun_flat_bars']}B)")
                    if fl["tenkan_flat"]:
                        extras.append("TK_PLAT")
                    if fl["future_cloud_flat"]:
                        extras.append("NUAGE_FUTUR_PLAT")
                    if fl["past_chikou_flat"]:
                        extras.append("CHIKOU_PASSE_PLAT")
                extra_str = " | ".join(extras) if extras else ""
                print(f"    {tf}: T={d['tenkan']:.5f} K={d['kijun']:.5f}  Prix={d['close']:.5f}  "
                      f"Dist={d['dist']:.3f}%  {dir_sym}  {extra_str}")

    # --- MEILLEURE RECOMMANDATION ---
    best = all_scores[0] if all_scores else None
    if best:
        dir_dir = "↑ (LONG)" if best["direction"] == "HAUSSIER" else "↓ (SHORT)"
        print(f"\n{'=' * 130}")
        print(f"  >>> RECOMMANDATION #1 : {best['sym']} en {dir_dir}")
        print(f"{'=' * 130}")
        print(f"")
        print(f"  Pourquoi {best['sym']} ?")
        print(f"  - Score {best['total']:.1f}/100 — meilleur score du scan")
        print(f"  - Proximite Kijun: {best['prox']} pts")
        print(f"  - Direction consistante: {best['dir_detail']} timeframes {best['direction']}")
        print(f"  - Nuage Senkou: {best['cloud_score']} pts")
        print(f"  - TK Cross: {best['tk_score']} pts")
        print(f"  - Chikou aligne: {best['chikou_score']} pts")
        print(f"  - 3 regles d'or: {best['rules_score']} pts")
        print(f"  - Twist: {best['twist_score']} pts")
        print(f"  - Lagging confirmation: {best['lagging_score']} pts")
        print(f"  - Lignes plates: {best['flat_score']} pts")
        print(f"  - Rejets detectes: {best['rejet_score']} pts")
        print(f"  - Liquidite: {best['liq']}/10")
        print(f"")

        # Itineraire de trade avec Ichimoku complet
        tf_data = best["tf_data"]
        print(f"  Itineraire de trade conseille (Ichimoku complet):")
        for tf in ["H1", "H4", "D1", "W1"]:
            d = tf_data[tf]
            if d:
                parts = []
                parts.append(f"K={d['kijun']:.5f}")
                parts.append(f"T={d['tenkan']:.5f}")
                if d['cloud']:
                    pos = "DANS" if d['cloud']['inside'] else ("A-DESSUS" if d['cloud']['above'] else "DESSOUS")
                    parts.append(f"{pos} ({d['cloud']['color']})")
                if d['tk_cross'] and d['tk_cross']['cross']:
                    parts.append(f"{d['tk_cross']['cross']}")
                if d['chikou'] and d['chikou']['aligned']:
                    parts.append("CHIKOU HAUSSIER")
                if d['dist'] < 0.3:
                    parts.append("*** CONTACT ***")
                print(f"    {tf}: {' | '.join(parts)}  Dist={d['dist']:.3f}%")

        # Signaux Ichimoku avances (approche descendante)
        bullish_tf = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf]['tk_cross'] and tf_data[tf]['tk_cross']['cross'] == 'TK_CROSS_HAUSSIER')
        bearish_tf = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf]['tk_cross'] and tf_data[tf]['tk_cross']['cross'] == 'TK_CROSS_BAISSIER')
        above_cloud = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf]['cloud'] and tf_data[tf]['cloud']['above'])
        chikou_ok = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf]['chikou'] and tf_data[tf]['chikou']['aligned'])
        rules_3 = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf].get('three_rules') and tf_data[tf]['three_rules']['validated'] >= 2)
        twist_count = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf].get('twist') and tf_data[tf]['twist']['active'])
        lagging_ok = sum(1 for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf].get('lagging') and tf_data[tf]['lagging']['confirmed'])
        
        print(f"\n  Approche descendante (biais D1 -> confirmation H4 -> execution H1):")
        print(f"    - Biais D1: {best['direction']} (3R:{best['tf_data'].get('D1', {}).get('three_rules', {}).get('validated', 'N/A')}/3")
        print(f"    - Confirmation H4: {best['tf_data'].get('H4', {}).get('three_rules', {}).get('validated', 'N/A')}/3")
        print(f"    - Execution H1: {best['tf_data'].get('H1', {}).get('three_rules', {}).get('validated', 'N/A')}/3")
        
        print(f"\n  Resume signaux ({len(TIMEFRAMES)} timeframes):")
        print(f"    - 3 regles >= 2/3: {rules_3}/4")
        print(f"    - TK Cross: {bullish_tf} haussier / {bearish_tf} baissier")
        print(f"    - Nuage au-dessus: {above_cloud}/4")
        print(f"    - Chikou aligne: {chikou_ok}/4")
        print(f"    - Twist actif: {twist_count}/4")
        print(f"    - Lagging confirme: {lagging_ok}/4")
        
        if best["direction"] == "HAUSSIER":
            print(f"\n  Plan de trade (Karen Peeloille method):")
            print(f"  -> Entree: au-dessus Tenkan H1 ({tf_data.get('H1', {}).get('tenkan', 0):.5f})")
            print(f"  -> Stop: sous Kijun H1 ({tf_data.get('H1', {}).get('kijun', 0):.5f})")
            print(f"  -> Objectif: nuage superieur")
        else:
            print(f"\n  Plan de trade (Karen Peeloille method):")
            print(f"  -> Entree: sous Tenkan H1 ({tf_data.get('H1', {}).get('tenkan', 0):.5f})")
            print(f"  -> Stop: au-dessus Tenkan H1")
            print(f"  -> Objectif: nuage inferieur")        # Tableau complet
    print(f"\n{'=' * 130}")
    print(f"  CLASSEMENT COMPLET ({len(all_scores)} actifs analyses)")
    print(f"{'=' * 130}")
    for rank, s in enumerate(all_scores, 1):
        dir_sym = "LONG" if s["direction"] == "HAUSSIER" else "SHORT"
        print(f"  {rank:<3} {s['sym']:<14} Score={s['total']:<6.1f} {dir_sym:<7} ({s['dir_detail']} TF) 3R={s['rules_score']} Twist={s['twist_score']} Lag={s['lagging_score']} {s['cat']}")

    mt5.shutdown()


if __name__ == "__main__":
    main()
