# Rapport — Lundi 06/07/2026 : Estimation Swing_SR

> **Bot :** `strat_compare/swing_sr_bot.py`  
> **Capital :** $10 000 | **Risque :** 2%/trade | **Levier :** 1:30  
> **Actifs :** EURUSD, GBPUSD, XAUUSD — Timeframe H1  
> **Protection FTMO :** $485/jour max

---

## 1. Nombre de trades estimé

Basé sur le backtest 01/01 → 03/07/2026 (126 jours, 308 trades H1 sur 3 actifs).

| Actif | Trades/jour (moy) | Lundi estimé |
|:---|:---:|:---:|
| GBPUSD | 0.84 | ~1 |
| EURUSD | 0.88 | ~1 |
| XAUUSD | 0.72 | ~0-1 |
| **Total** | **2.44** | **2-3** |

### Par session (heure de Paris, UTC+2)

| Session | Heures | Trades probables |
|:---|:---|:---:|
| Nuit / Asie | 02h-09h | 0-1 |
| Matin Londres | 09h-13h | 1 |
| Après-midi Londres+NY | 13h-18h | 1-2 |
| Soirée NY | 18h-23h | 0-1 |

> **Fourchette : 1 à 5 trades.** Le premier signal arrivera ~1h après le lancement (bougie H1 complétée).

---

## 2. Gain/Perte estimé

### Par trade (moyennes backtest FTMO)

| Métrique | Valeur |
|:---|:---|
| Gain moyen (trade gagnant) | +$65 à +$130 |
| Perte moyenne (trade perdant) | -$80 à -$230 |
| Probabilité de gain | 82% |

### Scénarios pour ~2.5 trades

| Scénario | Trades | Résultat |
|:---|:---:|:---:|
| 🟢 Très bon | 3W 0L | **~+$200** |
| 🟢 Bon | 2W 1L | **~+$50** |
| 🟡 Neutre | 1W 1L | ~-$15 |
| 🔴 Mauvais | 0W 2L | ~-$160 |
| 🔴 Pire | 0W 3L | ~-$240 (bloqué à $485 max) |

### Estimation finale

| Scénario | Gain |
|:---|:---:|
| Pessimiste | **-$80** |
| **Attendu** | **+$50 à +$100** |
| Optimiste | **+$200** |

> **Moyenne semestrielle :** ~$60/jour → **+$7 500** sur 6 mois avec les 3 actifs.

---

## 3. Points d'attention

- ⚠️ **Spreads dimanche soir** : le filtre spread (>0.05%) bloquera probablement les premières heures
- ⚠️ **Premier signal** : au plus tôt 1h après démarrage (le bot analyse la dernière bougie **complétée**)
- ⚠️ **Cooldown** : 5 barres entre 2 entrées sur le même symbole → max ~5 trades/symbole/jour
- ✅ **Protection** : impossible de perdre plus de $485 grâce à la limite FTMO intégrée
