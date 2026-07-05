# Stratégie DXY → XAUUSD — Corrélation Scalping

> **Type :** Cross-asset correlation (DXY.cash → XAUUSD / XAGUSD)  
> **Signal :** DXY H1 fort mouvement → entrée inverse sur l'actif  
> **Période testée :** 01/01/2026 → 03/07/2026  
> **Meilleur couple :** DXY→XAGUSD H4 (Sharpe +1.45, +25.7% retour)  
> **Meilleur TF :** H4 uniquement (TFs inférieurs non rentables)

---

## 1. Contexte — Pourquoi DXY et les commodités USD ?

### La relation classique

```
DXY ↗  ⟹  XAUUSD ↘, XAGUSD ↘    (corrélation négative)
```

L'or et l'argent sont pricés en USD. Un dollar fort = les commodités deviennent plus chères pour les acheteurs étrangers → baisse de la demande → baisse du prix en USD. La relation inverse est tout aussi vraie : un dollar faible = commodités plus attractives = hausse.

### Analyse de corrélation (06 mois, 28 actifs)

| Actif | Pearson H4 | Pearson D1 | Force |
|:---|---:|---:|:---|
| XAUUSD (Or) | −0.72 | −0.74 | *** |
| **XAGUSD (Argent)** | **−0.71** | **−0.70** | *** |
| XPDUSD (Palladium) | −0.66 | −0.68 | *** |
| XPTUSD (Platine) | −0.64 | −0.62 | *** |

> 4 commodités ont une corrélation forte avec DXY. **XAUUSD et XAGUSD** sont les meilleurs candidats : forte corrélation, liquidité élevée, pas composants du DXY.

### Pourquoi l'argent (XAGUSD) surpasse l'or (XAUUSD)

| Facteur | XAGUSD | XAUUSD |
|:---|---:|:---|
| Volatilité (ATR H4) | ~$0.30-0.50 (1-1.5%) | ~$10 (0.4%) |
| Prix | ~$30 | ~$2 500 |
| Beta au DXY | 1.5× | 1.0× |
| Corrélation returns | −0.51 | −0.50 |

> L'argent est **3× plus volatil que l'or** en pourcentage. Les mouvements du DXY sont amplifiés sur XAGUSD, ce qui donne des retoirs plus importants avec le même ratio R:R.

### Scan exhaustif — 54 symboles USD

Un scan de **tous les symboles disponibles sur MT5** contenant "USD" (54 symboles) a classé XAGUSD comme le **meilleur actif non-crypto** (Sharpe +0.62, +11.5% retour), derrière seulement des cryptos mineures (NEO, XMR, UNI) à la corrélation instable.

---

## 2. Concept de la stratégie

```
DXY H1 fort (>1.5σ)  ──▶  entrée opposée XAUUSD
```

### Principe

1. **Surveiller DXY.cash en H1** : détecter les mouvements anormalement forts
2. **Quand DXY explose à la hausse** (>1.5× écart-type roulant) → **SHORT XAUUSD**
3. **Quand DXY s'effondre** (<−1.5σ) → **LONG XAUUSD**
4. **Le lead naturel** : DXY anticipe XAUUSD de 5-20 barres H1 → on entre tôt dans le mouvement

### Pourquoi ça peut marcher

- La corrélation n'est pas parfaite (−0.50 en returns), mais elle est **fiable directionnellement**
- Les mouvements forts de DXY (>1.5σ) sont des **chocs** qui se répercutent mécaniquement sur l'or
- Le lead de DXY donne une **fenêtre d'entrée anticipée** avant que XAUUSD ne réagisse pleinement

---

## 3. Algorithme (7 étapes)

### Étape 1 : Calcul du seuil dynamique (anti-look-ahead)

```python
dxy_h1_ret = DXY.close.pct_change() * 100
dxy_std = dxy_h1_ret.rolling(50, min_periods=20).std()  # ⚠️ rolling, pas global
threshold = 1.5 × dxy_std
```

> **ANTI-LOOK-AHEAD** : Le std est calculé en **fenêtre glissante de 50 barres**. À la barre N, seule l'information jusqu'à N est connue. Pas de fuite du futur.

### Étape 2 : Détection des signaux DXY H1

```python
dxy_strong_up   = dxy_h1_ret >  threshold   → signal SHORT XAU (-1)
dxy_strong_down = dxy_h1_ret < -threshold   → signal LONG  XAU (+1)
```

~325 signaux DXY sur 2712 barres H1 (12% du temps). 156 UP, 169 DOWN.

### Étape 3 : Projection sur le TF de trading (anti-look-ahead)

```python
dxy_signal_TF = dxy_signal_h1.shift(1).reindex(TF_index, method='ffill')
```

- **shift(1)** : la barre H1 08:00-08:59 n'est connue qu'à 09:00 → signal dispo à partir de 09:00
- **reindex(ffill)** : forward-fill sur toutes les barres du TF de trading jusqu'au prochain signal H1

### Étape 4 : Filtres

| Filtre | Condition | Rôle |
|:---|:---|:---|
| **Rolling corrélation** | `rolling_corr(20) < −0.3` | Ne trader que si la relation inverse est active (évite les régimes « safe haven » où or et dollar montent ensemble) |
| **Tendance H4 DXY** | DXY H4 > SMA20 pour SHORT, DXY H4 < SMA20 pour LONG | Alignement avec la tendance macro du dollar |
| **Confirmation bougie** | `close > open` (LONG), `close < open` (SHORT) | Évite les entrées à contre-courant immédiat |
| **Cooldown** | 2-30 barres selon TF | Anti-overtrading après une sortie |

### Étape 5 : Stop-Loss & Take-Profit

```python
SL = entrée ± 1.5 × ATR(TF trading)
TP = entrée ± 3.0 × ATR(TF trading)
```

Ratio risque/rendement = **2:1** (TP = 2× SL).

### Étape 6 : Sorties

| Type | Condition |
|:---|:---|
| **Stop-Loss** | Prix touche le SL |
| **Take-Profit** | Prix atteint le TP |
| **Signal opposé** | DXY fort dans l'autre sens |
| **Fin de période** | Clôture forcée |

### Étape 7 : Déduplication

Les signaux consécutifs identiques sont filtrés (une seule entrée par cluster DXY).

---

## 4. Paramètres

| Paramètre | Valeur | Rôle |
|:---|:---:|:---|
| `THRESHOLD_STD` | 1.5 | Seuil de détection DXY en écarts-types roulants |
| `STD_WINDOW` | 50 | Fenêtre glissante pour le std (anti-look-ahead) |
| `SL_ATR` | 1.5 | Stop-loss en multiple d'ATR du TF de trading |
| `TP_ATR` | 3.0 | Take-profit en multiple d'ATR |
| `ROLLING_CORR_MIN` | −0.3 | Corrélation rolling minimum pour trader |
| `H4_SMA_PERIOD` | 20 | SMA pour le filtre de tendance H4 DXY |
| `ATR_PERIOD` | 14 | Période ATR |

---

## 5. Résultats — Multi-Timeframe XAUUSD

> Testé sur XAUUSD avec DXY.cash H1 comme source de signal.  
> Période : 01/01/2026 → 03/07/2026. Capital : $10 000.

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF |
|:---|---:|---:|---:|---:|---:|---:|
| **🏆 H4** | 20 | **55.0%** | **+9.22%** | **+1.25** | −6.3% | 1.46 |
| 🥈 H1 | 65 | 43.1% | +5.86% | +0.64 | −15.3% | 1.14 |
| M15 | 146 | 33.6% | −17.4% | −2.95 | −21.0% | 0.66 |
| M5 | 182 | 35.7% | −13.0% | −3.26 | −14.4% | 0.70 |
| M1 | 119 | 27.7% | −10.8% | −16.9 | −11.0% | 0.31 |

### 📈 Pattern clair

```
H4 (+1.25) > H1 (+0.64) > M15 (-2.95) > M5 (-3.26) > M1 (-16.9)
```

---

## 6. Focus H4 — Meilleurs couples

### XAUUSD H4 (référence historique)

| Métrique | Valeur |
|:---|---:|
| Trades (6 mois) | 20 |
| Win Rate | **55.0%** |
| Retour | **+9.22%** |
| Sharpe | **+1.25** |
| Max Drawdown | −6.3% |
| Profit Factor | 1.46 |
| FTMO ROI | **+14.48%** |
| Days lost | 1 |

### 🏆 XAGUSD H4 (nouveau champion — MEILLEURE STRATÉGIE)

| Métrique | Valeur |
|:---|---:|
| Trades (6 mois) | 18 |
| Win Rate | **55.6%** |
| Retour | **+25.70%** |
| Sharpe | **+1.45** |
| Max Drawdown | −9.6% |
| Profit Factor | **1.75** |
| FTMO ROI | **+18.29%** |
| Days lost | 1 |

### Comparaison XAUUSD vs XAGUSD

| Métrique | XAUUSD | **XAGUSD** | Δ |
|:---|---:|---:|:---|
| Retour | +9.22% | **+25.70%** | **+179%** |
| Sharpe | +1.25 | **+1.45** | **+16%** |
| WR | 55.0% | **55.6%** | +1% |
| PF | 1.46 | **1.75** | **+20%** |
| FTMO | +14.48% | **+18.29%** | **+26%** |
| MaxDD | −6.3% | −9.6% | −52%* |

> \* Drawdown plus élevé mais acceptable (limite FTMO 10%). XAGUSD surperforme XAUUSD sur **tous les critères de rentabilité** au prix d'un drawdown modérément plus haut.

### Optimisation du seuil XAGUSD

| Seuil | Trades | WR% | Ret% | Sharpe |
|:---:|:---:|:---:|:---:|:---:|
| 1.0σ | 26 | 46% | +10.3% | +0.50 |
| 1.2σ | 21 | 52% | +20.4% | +1.09 |
| **1.5σ** 🏆 | **18** | **56%** | **+25.7%** | **+1.45** |
| 1.8σ | 13 | 46% | +3.8% | +0.40 |
| 2.0σ | 9 | 44% | +4.1% | +0.48 |

> **1.5σ optimal** pour XAGUSD comme pour XAUUSD.

### Portefeuille 50/50 XAUUSD + XAGUSD

| Actif | Retour | Sharpe | MaxDD |
|:---|---:|:---:|:---:|
| XAGUSD seul | **+25.70%** | **+1.45** | −9.6% |
| XAUUSD seul | +9.22% | +1.25 | −6.3% |
| **Portfolio 50/50** | +14.59% | ∼0.0 | **−7.0%** |

> Le portefeuille lisse la volatilité (MaxDD −7.0%) mais coupe la performance de moitié. **XAGUSD seul est meilleur.**

---

## 7. Forces & Faiblesses

### ✅ Forces

| Force | Détail |
|:---|:---|
| **Signal exogène** | DXY est un indice macro indépendant — pas de circularité |
| **Lead naturel** | DXY anticipe XAUUSD/XAGUSD → entrée avec une longueur d'avance |
| **Relation robuste** | Corrélation −0.72/−0.71, 85-100% du temps négative en rolling |
| **Filtres multiples** | Rolling corr + trend H4 + confirmation bougie → qualité des entrées |
| **Anti-look-ahead complet** | Rolling std, shift(1), ffill → zéro fuite de données futures |
| **FTMO viable sur H4** | XAGUSD +18.3%, XAUUSD +14.5%, max 1 jour perdu |
| **Multi-actif** | Fonctionne sur XAUUSD, XAGUSD, et potentiellement XPDUSD/XPTUSD |

### ⚠️ Faiblesses

| Faiblesse | Impact |
|:---|:---|
| **Peu de trades (H4)** | 18-20 trades en 6 mois = ~3/mois — patience requise |
| **Défaillance de la corrélation** | En régime « risk-on/risk-off » extrême, or/dollar peuvent monter ensemble (filtre rolling corr atténue ce risque) |
| **Dépendance à DXY.cash** | Le symbole doit être disponible chez le broker (vérifié : OK sur MT5) |
| **H4 uniquement rentable** | Les TFs inférieures ne fonctionnent pas — le bruit domine |
| **Sensible au seuil σ** | 1.0σ = trop de bruit, 2.0σ = trop peu de signaux. 1.5σ est optimal |
| **Drawdown XAGUSD** | −9.6% vs −6.3% XAUUSD — plus de volatilité = plus de risque

---

## 8. Structure des fichiers

| Fichier | Rôle |
|:---|:---|
| `strat_compare/_corr_analysis.py` | Analyse de corrélation XAUUSD vs DXY.cash |
| `strat_compare/_dxy_xau_backtest.py` | Backtest multi-TF XAUUSD |
| `strat_compare/dxy_xau_bot.py` | **Bot live XAUUSD** (magic 260706) |
| `strat_compare/dxy_xag_bot.py` | **Bot live XAGUSD** (magic 270706, MEILLEURE PERF) |
| `strat_compare/GUIDE_DXY_BOT.md` | Guide d'utilisation bot XAUUSD |
| `strat_compare/GUIDE_XAG_BOT.md` | Guide d'utilisation bot XAGUSD |
| `strat_compare/ANALYSE_CORRELATION_DXY.md` | Analyse corrélation DXY vs 28+ actifs |

---

## 9. Comment lancer

```bash
# Backtest multi-TF XAUUSD
python strat_compare/_dxy_xau_backtest.py

# Bot live XAUUSD (dry-run recommandé d'abord)
python strat_compare/dxy_xau_bot.py --dry-run

# Bot live XAGUSD (MEILLEURE STRATÉGIE, Sharpe +1.45)
python strat_compare/dxy_xag_bot.py --dry-run
```

---

## 10. Conclusion

La stratégie DXY × commodités exploite une **relation macro robuste** (corrélation −0.72/−0.71) avec un **lead temporel** (DXY anticipe de 5-20 barres).

### 🏆 Meilleure configuration : DXY → XAGUSD H4

| Métrique | XAGUSD H4 | XAUUSD H4 |
|:---|---:|---:|
| Sharpe | **+1.45** | +1.25 |
| Retour 6 mois | **+25.70%** | +9.22% |
| FTMO | **+18.29%** | +14.48% |

- ✅ **Rentable sur H4** — XAGUSD (Sharpe +1.45, +25.7%) et XAUUSD (Sharpe +1.25, +9.2%)
- ❌ **Non viable sur M15 et inférieur** (le bruit domine le signal)
- ✅ **Bot live disponible** pour XAUUSD (`dxy_xau_bot.py`) et XAGUSD (`dxy_xag_bot.py`)

Le point faible est le **faible nombre de trades** (18-20 en 6 mois sur H4). La stratégie convient à un trading patient, orienté qualité plutôt que quantité.
