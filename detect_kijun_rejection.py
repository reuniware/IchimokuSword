"""
Détection des rejets du Kijun Sen sur timeframe D1.

Un rejet = le prix s'approche du Kijun (contact < 0.4%) puis rebondit
en sens inverse (distance double ou inversion de direction).
"""
import MetaTrader5 as mt5
import numpy as np

D1 = 16408


def compute_kijun(highs, lows, idx):
    hh = np.max(highs[idx-25:idx+1])
    ll = np.min(lows[idx-25:idx+1])
    return (hh + ll) / 2.0


def detect_rejet(highs, lows, closes, lookback=7):
    n = len(highs)
    if n < 35:
        return None

    best_rejet = None
    for i in range(2, lookback + 2):
        idx = n - i
        if idx < 26:
            continue

        kijun_then = compute_kijun(highs, lows, idx)
        close_then = float(closes[idx])
        high_then = float(highs[idx])
        low_then = float(lows[idx])
        dist_then = abs(close_then - kijun_then) / kijun_then * 100
        above_then = close_then > kijun_then

        # Approche proche du Kijun (< 0.4%)
        if dist_then >= 0.4:
            continue

        # Vérifier la bougie suivante
        if i <= 1:
            continue
        idx_next = idx + 1
        if idx_next >= n:
            continue

        kijun_next = compute_kijun(highs, lows, idx_next)
        close_next = float(closes[idx_next])
        dist_next = abs(close_next - kijun_next) / kijun_next * 100
        above_next = close_next > kijun_next

        # Critères de rejet : distance augmente significativement
        # ou inversion de direction
        is_rejet = False
        rejet_type = ""

        if above_then and not above_next:
            # Était au-dessus, passe en-dessous = rejet baissier
            is_rejet = True
            rejet_type = "REJET BAISSIER"
            # Vérifier la mèche haute
            upper_wick = high_then - close_then
            body = abs(close_then - float(open_then)) if idx > 0 else 0
            if upper_wick > body * 0.5:
                rejet_type = "REJET BAISSIER (meche)"

        elif not above_then and above_next:
            # Était en-dessous, passe au-dessus = rejet haussier
            is_rejet = True
            rejet_type = "REJET HAUSSIER"
            # Vérifier la mèche basse
            lower_wick = close_then - low_then
            body = abs(close_then - float(open_then)) if idx > 0 else 0
            if lower_wick > body * 0.5:
                rejet_type = "REJET HAUSSIER (meche)"

        elif dist_next > dist_then * 2 and dist_next > 0.3:
            # Éloignement fort sans inversion
            is_rejet = True
            if above_then and above_next:
                rejet_type = "ELOIGNEMENT HAUSSIER"
            else:
                rejet_type = "ELOIGNEMENT BAISSIER"

        if not is_rejet:
            continue

        candles_since = i - 1
        result = {
            'candle_index': i,
            'kijun_then': float(kijun_then),
            'close_then': close_then,
            'dist_then': dist_then,
            'dist_next': dist_next,
            'rejet_type': rejet_type,
            'above_then': above_then,
            'above_now': float(closes[-1]) > (np.max(highs[-26:]) + np.min(lows[-26:])) / 2.0,
            'candles_since': candles_since,
            'dist_now': abs(float(closes[-1]) - (np.max(highs[-26:]) + np.min(lows[-26:])) / 2.0) / ((np.max(highs[-26:]) + np.min(lows[-26:])) / 2.0) * 100,
        }

        if best_rejet is None or dist_then < best_rejet['dist_then']:
            best_rejet = result

    return best_rejet


def main():
    if not mt5.initialize():
        print("FAIL: mt5.initialize()")
        return

    symbols = [s.name for s in mt5.symbols_get()]
    print(f"Total symboles: {len(symbols)}")
    print()

    # Récupérer les opens pour chaque symbole
    rejets = []
    for sym in symbols[:200]:
        mt5.symbol_select(sym, True)
        rates = mt5.copy_rates_from_pos(sym, D1, 0, 55)
        if rates is None or len(rates) < 30:
            continue

        highs = rates["high"]
        lows = rates["low"]
        closes = rates["close"]

        # On a besoin de `open_then`, donc on passe les opens
        # On définit globalement opens
        global open_then
        opens = rates["open"]

        # Modifier detect_rejet pour recevoir opens
        # Réimplémentons localement
        n = len(highs)
        best_rejet = None
        lookback = 7

        for i in range(2, lookback + 2):
            idx = n - i
            if idx < 26:
                continue

            kijun_then = compute_kijun(highs, lows, idx)
            close_then = float(closes[idx])
            high_then = float(highs[idx])
            low_then = float(lows[idx])
            open_then_val = float(opens[idx])
            dist_then = abs(close_then - kijun_then) / kijun_then * 100
            above_then = close_then > kijun_then

            if dist_then >= 0.4:
                continue

            if i <= 1:
                continue
            idx_next = idx + 1
            if idx_next >= n:
                continue

            kijun_next = compute_kijun(highs, lows, idx_next)
            close_next = float(closes[idx_next])
            dist_next = abs(close_next - kijun_next) / kijun_next * 100
            above_next = close_next > kijun_next

            is_rejet = False
            rejet_type = ""

            if above_then and not above_next:
                is_rejet = True
                rejet_type = "REJET BAISSIER"
                upper_wick = high_then - close_then
                body = abs(close_then - open_then_val)
                if body > 0 and upper_wick > body * 0.5:
                    rejet_type = "REJET BAISSIER (meche)"

            elif not above_then and above_next:
                is_rejet = True
                rejet_type = "REJET HAUSSIER"
                lower_wick = close_then - low_then
                body = abs(close_then - open_then_val)
                if body > 0 and lower_wick > body * 0.5:
                    rejet_type = "REJET HAUSSIER (meche)"

            elif dist_next > dist_then * 2 and dist_next > 0.3:
                is_rejet = True
                if above_then and above_next:
                    rejet_type = "ELOIGNEMENT HAUSSIER"
                else:
                    rejet_type = "ELOIGNEMENT BAISSIER"

            if not is_rejet:
                continue

            kijun_now = (np.max(highs[-26:]) + np.min(lows[-26:])) / 2.0
            price_now = float(closes[-1])
            dist_now = abs(price_now - kijun_now) / kijun_now * 100
            above_now = price_now > kijun_now

            candles_since_val = i - 1
            result = {
                'candle_index': i,
                'kijun_then': float(kijun_then),
                'close_then': close_then,
                'dist_then': dist_then,
                'dist_next': dist_next,
                'dist_now': dist_now,
                'rejet_type': rejet_type,
                'above_then': above_then,
                'above_now': above_now,
                'candles_since': candles_since_val,
            }

            if best_rejet is None or dist_then < best_rejet['dist_then']:
                best_rejet = result

        if best_rejet:
            rejets.append((sym.name if hasattr(sym, 'name') else sym, best_rejet))

    mt5.shutdown()

    rejets.sort(key=lambda x: x[1]['dist_then'])

    print("=" * 80)
    print("DETECTION DE REJET DU KIJUN SEN (D1)")
    print("=" * 80)
    print()
    print(f"Analyse des {lookback} dernieres bougies D1")
    print(f"Seuil d'approche: < 0.40% du Kijun")
    print()

    if not rejets:
        print("Aucun rejet detecte sur D1.")
    else:
        print(f"{'Symbole':<10} {'Type':<28} {'Dist@contact':<15} {'Dist@apres':<15} {'Dist@maintenant':<18} {'Jours':<6}")
        print("-" * 92)
        for sym, r in rejets[:30]:
            print(f"{sym:<10} {r['rejet_type']:<28} {r['dist_then']:.3f}%          {r['dist_next']:.3f}%          {r['dist_now']:.3f}%              {r['candles_since']}")

        if len(rejets) > 30:
            print(f"... et {len(rejets) - 30} autres")

        # Résumé par type
        print()
        print("--- Résumé par type ---")
        types = {}
        for _, r in rejets:
            t = r['rejet_type']
            types[t] = types.get(t, 0) + 1
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            print(f"  {t:<30}: {c}")

    print()


if __name__ == "__main__":
    main()
