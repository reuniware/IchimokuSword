# Stratégie DXY → XAUUSD — Corrélation Scalping

> **Type :** Cross-asset correlation (DXY.cash → XAUUSD)  
> **Signal :** DXY H1 fort mouvement → entrée inverse XAUUSD  
> **Période testée :** 01/01/2026 → 03/07/2026  
> **Meilleur TF :** H4 (Sharpe +1.25, +9.2% retour)

---

## 1. Contexte — Pourquoi DXY et XAUUSD ?

### La relation classique

```
DXY ↗  ⟹  XAUUSD ↘    (corrélation négative)
```

L'or est pricé en USD. Un dollar fort = l'or devient plus cher pour les acheteurs étrangers → baisse de la demande → baisse du prix en USD. La relation inverse est tout aussi vraie : un dollar faible = or plus attractif = hausse.

### Analyse de corrélation (06 mois)

| Métrique | H1 | H4 | D1 |
|:---|---:|---:|---:|
| **Pearson close** | **−0.72** | **−0.72** | **−0.74** |
| **Pearson returns** | −0.50 | −0.50 | −0.48 |
| **Spearman close** | −0.67 | −0.67 | −0.70 |
| **DXY lead** | 20 barres | 20 barres | 5 barres |
| **Rolling corr (50b) % négatif** | 89% | 82% | **100%** |

> La corrélation est **forte, négative et persistante** : 85-100% des fenêtres glissantes sont négatives. DXY mène systématiquement XAUUSD de 5 à 20 barres selon le timeframe.

### Régression

```
XAUUSD = −206 $ × DXY + intercept  (R² = 0.52-0.55)
```

Chaque point de DXY gagné = ~$206 perdus sur XAUUSD. La relation explique 52-55% de la variance du prix de l'or.

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

## 5. Résultats — Multi-Timeframe

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
TF haut ← Meilleur — Pire → TF bas

H4 (+1.25) > H1 (+0.64) > M15 (-2.95) > M5 (-3.26) > M1 (-16.9)
```

**Le bruit tue le signal.** Sur M1/M5, le mouvement DXY n'a pas le temps de se transmettre à XAUUSD avant que le SL ne soit touché. Sur H4, le lead de 20 barres H1 = 5 barres H4 laisse le temps au mouvement de se développer.

---

## 6. Focus H4 — Meilleure configuration

| Métrique | Valeur |
|:---|---:|
| Trades (6 mois) | 20 |
| Win Rate | **55.0%** |
| Retour | **+9.22%** |
| Sharpe | **+1.25** |
| Max Drawdown | −6.3% |
| Profit Factor | 1.46 |
| Avg Win | +2.53% |
| Avg Loss | −1.89% |

### Sorties

| Type | # | % |
|:---|---:|---:|
| Take-Profit | 11 | 55% |
| Stop-Loss | 9 | 45% |

### FTMO H4

| Métrique | Valeur |
|:---|---:|
| Capital final | $11 448 |
| ROI | **+14.48%** |
| Days lost | 1 |

> Avec 2% de risque par trade et levier 1:30, la stratégie H4 est **rentable en FTMO** sur la période. Seulement 1 jour de limite daily loss atteinte.

---

## 7. Forces & Faiblesses

### ✅ Forces

| Force | Détail |
|:---|:---|
| **Signal exogène** | DXY est un indice macro indépendant — pas de circularité |
| **Lead naturel** | DXY anticipe XAUUSD → entrée avec une longueur d'avance |
| **Relation robuste** | Corrélation −0.72, 85-100% du temps négative en rolling |
| **Filtres multiples** | Rolling corr + trend H4 + confirmation bougie → qualité des entrées |
| **Anti-look-ahead complet** | Rolling std, shift(1), ffill → zéro fuite de données futures |
| **FTMO viable sur H4** | +14.5% ROI, 1 seul jour perdu |

### ⚠️ Faiblesses

| Faiblesse | Impact |
|:---|:---|
| **Peu de trades (H4)** | 20 trades en 6 mois = ~3/mois — patience requise |
| **Défaillance de la corrélation** | En régime « risk-on/risk-off » extrême, or et dollar peuvent monter ensemble (filtre rolling corr atténue ce risque) |
| **Dépendance à DXY.cash** | Le symbole doit être disponible chez le broker (vérifié : OK sur MT5) |
| **H1 et H4 uniquement** | Les TFs inférieures ne fonctionnent pas — le bruit domine |
| **Sensible au seuil σ** | 1.0σ = trop de bruit, 2.0σ = trop peu de signaux. 1.5σ est optimal |

---

## 8. Structure des fichiers

| Fichier | Rôle |
|:---|:---|
| `strat_compare/_corr_analysis.py` | Analyse de corrélation XAUUSD vs DXY.cash (H1, H4, D1) |
| `strat_compare/_dxy_xau_backtest.py` | Backtest multi-TF de la stratégie (M1→H4) |
| `strat_compare/_m1_diag.py` | Diagnostic de disponibilité des données M1/M5 |

---

## 9. Comment lancer

```bash
# Analyse de corrélation (une fois)
python strat_compare/_corr_analysis.py

# Backtest multi-TF complet
python strat_compare/_dxy_xau_backtest.py
```

---

## 10. Conclusion

La stratégie DXY → XAUUSD exploite une **relation macro robuste** (corrélation −0.72) avec un **lead temporel** (DXY anticipe XAUUSD de 5-20 barres).

- ✅ **Rentable sur H4** (Sharpe +1.25, +9.2%, FTMO +14.5%)
- ✅ **Rentable sur H1** (Sharpe +0.64, +5.9%)
- ❌ **Non viable sur M15 et inférieur** (le bruit domine le signal)

Le point faible est le **faible nombre de trades** (20 en 6 mois sur H4). La stratégie convient à un trading patient, orienté qualité plutôt que quantité.
