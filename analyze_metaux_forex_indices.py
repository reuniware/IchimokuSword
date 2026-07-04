"""
Analyse multi-classes : Métaux, Forex, Indices
Kijun Sen sur H1, H4, D1, W1 pour chaque actif
"""
import MetaTrader5 as mt5
from datetime import datetime, timezone
import numpy as np

CATEGORIES = {
    "METAUX": [
        "XAUUSD", "XAGUSD", "XPDUSD", "XPTUSD",
        "XAUEUR", "XAUAUD", "XAUXAG", "COPPER",
    ],
    "FOREX_MAJORS": [
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
        "AUDUSD", "NZDUSD", "USDCHF",
    ],
    "FOREX_CROSSES": [
        "EURJPY", "GBPJPY", "EURGBP", "EURAUD", "EURCHF",
        "GBPCHF", "AUDJPY", "CHFJPY", "CADJPY",
        "AUDCAD", "NZDCAD", "GBPCAD", "AUDCHF", "AUDNZD",
        "EURNZD", "GBPNZD", "EURNOK", "EURSEK", "NOKSEK",
        "EURCZK", "USDSEK", "USDNOK", "USDPLN", "EURPLN",
        "USDHUF", "EURHUF", "USDCZK", "USDSGD", "USDCNH",
        "USDZAR", "USDMXN", "USDINR",
    ],
    "INDICES": [
        "US30", "SP500", "NAS100", "US100.cash", "US500.cash", "US30.cash",
        "GER40", "UK100", "FRA40", "JPN225", "AUS200", "AUS200.cash",
        "N25.cash", "HK50", "CHN50", "INDIA50", "SPN35", "SWI20",
    ],
}

TIMEFRAMES = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
              "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1}
NB = {"H1": 96, "H4": 80, "D1": 60, "W1": 52}


def kijun(highs, lows, idx=-1, p=26):
    s = idx - p + 1
    if s < 0:
        return None
    return float((np.max(highs[s:idx + 1]) + np.min(lows[s:idx + 1])) / 2.0)


def main():
    if not mt5.initialize():
        print("ERREUR: echec connexion MT5")
        return

    now = datetime.now(timezone.utc)
    print("=" * 120)
    print("  ANALYSE MULTI-CLASSES : METAUX | FOREX | INDICES")
    print("  Kijun Sen sur H1 - H4 - D1 - W1")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 120)

    all_symbols = {s.name: s for s in mt5.symbols_get()}
    print(f"  Symboles MT5 disponibles: {len(all_symbols)}")
    print()

    for cat_name, cat_symbols in CATEGORIES.items():
        print("#" * 120)
        print(f"  # {cat_name}")
        print("#" * 120)

        results = []
        for sym in cat_symbols:
            if sym not in all_symbols:
                continue
            mt5.symbol_select(sym, True)

            tf_data = {}
            for tf_label, tf_val in TIMEFRAMES.items():
                r = mt5.copy_rates_from_pos(sym, tf_val, 0, NB[tf_label])
                if r is None or len(r) < 26:
                    tf_data[tf_label] = None
                    continue

                highs, lows, closes = r["high"], r["low"], r["close"]
                n = len(highs)
                k = kijun(highs, lows, n - 1, 26)
                if k is None:
                    tf_data[tf_label] = None
                    continue

                c = float(closes[-1])
                d = abs(c - k) / k * 100
                a = c > k

                # Contact dans les 10 dernieres bougies
                contact = None
                for i in range(max(0, n - 10), n):
                    kk = kijun(highs, lows, i, 26)
                    if kk is not None:
                        cc = float(closes[i])
                        dd = abs(cc - kk) / kk * 100
                        if dd < 0.3:
                            contact = True
                            break

                tf_data[tf_label] = {
                    "kijun": k,
                    "close": c,
                    "dist": d,
                    "above": a,
                    "contact": contact,
                }

            contacts_tf = [tf for tf in TIMEFRAMES if tf_data[tf] and tf_data[tf]["contact"]]
            dirs = {v["above"] for v in tf_data.values() if v}
            results.append({
                "sym": sym,
                "tf_data": tf_data,
                "consistent": len(dirs) == 1,
                "contacts_tf": contacts_tf,
            })

        # Tri par score : proximite + contacts
        def sort_key(r):
            score = 0
            for v in r["tf_data"].values():
                if v:
                    score += 1
                    if v["dist"] < 0.3:
                        score += 2
                    if v["contact"]:
                        score += 1
            return -score

        results.sort(key=sort_key)

        # Affichage
        for r in results:
            sym = r["sym"]
            dir_lbl = "CONSISTANT" if r["consistent"] else "MIXTE"
            contacts_info = f" [{len(r['contacts_tf'])} contacts]"

            print(f"\n  {sym:<12} | Dir: {dir_lbl:<12} | {contacts_info}")
            for tf in TIMEFRAMES:
                d = r["tf_data"][tf]
                if d is None:
                    print(f"    {tf}: N/A")
                else:
                    dir_sym = "HAUT" if d["above"] else "BAS "
                    ctc = " ***" if d["contact"] else ""
                    print(f"    {tf}: Kijun={d['kijun']:.5f}  Prix={d['close']:.5f}  "
                          f"Dist={d['dist']:.3f}%  {dir_sym}{ctc}")

        # Resume categorie
        confluences = [c for c in results if len(c["contacts_tf"]) >= 2]
        contacts_total = sum(1 for r in results if r["contacts_tf"])
        print(f"\n  --- RESUME {cat_name} ---")
        print(f"  Analyses: {len(results)} | Avec contacts: {contacts_total} | Confluences multi-TF: {len(confluences)}")
        if confluences:
            print(f"\n  Confluences (2+ timeframes):")
            for c in confluences:
                tfs_str = "+".join(c["contacts_tf"])
                dir_str = "CONSISTANT" if c["consistent"] else "MIXTE"
                print(f"    {c['sym']:<12} TFs: {tfs_str:<12} {dir_str}")
        print()

    mt5.shutdown()
    print("Termine.")


if __name__ == "__main__":
    main()
