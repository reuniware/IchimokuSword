# Rapport Global — Toutes les Stratégies Testées

> **Période :** 01/01/2026 → 03/07/2026 (6 mois)  
> **Capital initial :** $10 000  
> **Données :** MetaTrader5  
> **Date du rapport :** 06/07/2026

---

## 1. Contexte

Ce rapport synthétise l'ensemble des stratégies de trading testées sur la période janvier–juillet 2026. Trois grandes familles ont été évaluées :

| Groupe | Stratégies | Approche |
|:---|:---|:---|
| **A — Classiques** | 7 stratégies (RSI, Bollinger, MACD, Stochastic, EMA Cross, Swing_SR, Parabolic SAR) | Single-asset, même TF |
| **B — Ichimoku** | 2 stratégies (Scalp, MTF) | Flat-line breakout, single + multi-TF |
| **C — Cross-asset** | 1 stratégie (DXY → XAUUSD) | Signal DXY.cash → trade XAUUSD |

---

## 2. Groupe A — Stratégies classiques

### Paramètres communs

| Paramètre | Valeur |
|:---|:---|
| SL | 1.5 × ATR(14) |
| TP | 2.0 × ATR(14) |
| Sortie | Signal opposé |
| Coûts | Spread + slippage réalistes par catégorie |

### Détail par stratégie

| # | Stratégie | Type | Signal d'entrée |
|:--:|:---|:---|:---|
| 1 | **RSI** | Mean reversion | RSI(14) sort de zone survendue (>30) / surachatée (<70) |
| 2 | **Bollinger** | Mean reversion | Close touche bande inférieure (LONG) / supérieure (SHORT), TP = middle band |
| 3 | **MACD** | Trend following | MACD(12,26,9) line croise signal line |
| 4 | **Stochastic** | Mean reversion | %K(14,3,3) croise %D en zone survendue (<20) / surachatée (>80) |
| 5 | **EMA Cross** | Trend following | EMA(9) croise EMA(21) |
| 6 | **Swing_SR** | S/R bounces | Rebond sur swing high/low ±20 barres + bougie confirmative, SL au-delà du niveau |
| 7 | **Parabolic SAR** | Trend following | SAR(0.02, 0.2) flip au-dessus → en dessous du prix |

### Actifs & Timeframes testés

- **Restreint** : EURUSD, GBPUSD, XAUUSD × H1, H4 (48 backtests)
- **Étendu** : 32 symboles FTMO (forex, indices, commodities, crypto) × D1, H4, H1, M15 (1127 backtests)

### Résultats moyens (EURUSD, GBPUSD, XAUUSD × H1, H4)

| Rang | Stratégie | Sharpe | WR% | Ret% | Trades moy. | Meilleur couple |
|:---:|:---|---:|---:|---:|---:|:---|
| 🥇 | Stochastic | −1.08 | 48.3% | −6.0% | 43 | **GBPUSD H4** (Sharpe 1.78, +4.6%) |
| 🥈 | RSI | −0.25 | 43.4% | −0.1% | 29 | XAUUSD H4 (Sharpe 0.72) |
| 🥉 | Swing_SR | +0.01 | 63.6% | −1.3% | 37 | GBPUSD H4 (Sharpe 1.56, +2.4%) |
| 4 | MACD | −1.03 | 39.8% | −0.4% | 62 | — |
| 5 | Bollinger | −1.30 | 42.7% | −5.7% | 44 | — |
| 6 | EMA Cross | −1.53 | 41.2% | −3.2% | 38 | — |
| 7 | Parabolic SAR | −1.68 | 39.4% | −4.4% | 58 | — |

### Résultats FTMO (2% risque, levier 1:30, limite $485/j)

| Rang | Stratégie | Sharpe | WR% | Ret% | Meilleur couple |
|:---:|:---|---:|---:|---:|:---|
| 1 | Swing_SR | +0.23 | 63.6% | −0.3% | — |
| 2 | RSI | −0.90 | 43.6% | −10.7% | — |
| 3 | MACD | −1.20 | 39.6% | −19.1% | — |

> ⚠️ **Aucune stratégie classique n'est viable en FTMO** sur la période. Le position sizing FTMO amplifie les pertes.

### Backtest étendu (32 symboles, 1127 tests)

- **D1 est le seul TF rentable** — H4 marginal, H1 négatif, M15 catastrophique
- **Meilleur résultat absolu** : Stochastic XAGUSD D1 (Sharpe 3.00, +137% — mais seulement 11 trades)
- **XAGUSD, XRPUSD, GBPJPY** : meilleurs actifs isolés sur D1

---

## 3. Groupe B — Stratégies Ichimoku

| # | Stratégie | Concept | SL | TP |
|:--:|:---|:---|:---|:---|
| 8 | **Ichimoku Scalp** | Flat-line breakout même TF (Kijun/Senkou B plates) | Ligne plate ± 0.6 ATR | Prochaine ligne plate / 1.5 ATR |
| 9 | **Ichimoku MTF** | Flat lines H4/D1 → trading M15 (pipeline shift+ffill) | Ligne plate ± 0.6 ATR | Prochaine ligne plate / 1.5 ATR |

### Composants Ichimoku utilisés

| Ligne | Formule | Rôle |
|:---|:---|:---|
| Tenkan-sen | (highest(9) + lowest(9)) / 2 | Ligne rapide (non utilisée pour l'entrée) |
| Kijun-sen | (highest(26) + lowest(26)) / 2 | **Ligne d'entrée principale** (équilibre 26 périodes) |
| Senkou A | (Tenkan + Kijun) / 2, shifté 26 | Cible TP |
| Senkou B | (highest(52) + lowest(52)) / 2, shifté 26 | **Ligne d'entrée forte** (équilibre 52 périodes) |

### Flat line detection

```
Une ligne est "plate" si range sur 5-7 barres < 0.01 × ATR
```

Les lignes Ichimoku forment des segments **parfaitement plats** quand le plus haut/plus bas de la période n'évolue pas. Détection quasi-instantanée.

### Anti-look-ahead MTF

```
TF haute (H4) : compute_ichimoku() → flat lines → shift(1) → reindex(ffill) → TF basse (M15)
```

- `shift(1)` : la flat line de la période H4 N n'est visible qu'à N+1
- `reindex(ffill)` : forward-fill sur chaque barre M15 jusqu'au prochain signal H4

### Résultats (EURUSD, GBPUSD, XAUUSD M15)

| Stratégie | Sharpe | WR% | Ret% | Trades moy. |
|:---|---:|---:|---:|---:|
| Ichimoku MTF (H4+D1→M15) | **−4.42** | 26.2% | −9.4% | 195 |
| Ichimoku Scalp (M15 seule) | −9.56 | 33.2% | −19.5% | 432 |

> L'approche MTF filtre mieux le bruit (2× moins de trades, Sharpe 2× meilleur), mais reste perdante sur M15. Trop peu de lignes plates détectables en 6 mois.

---

## 4. Groupe C — Stratégie cross-asset DXY → Commodités (XAUUSD / XAGUSD)

### Analyse de corrélation préalable (28 actifs + 54 symboles USD)

| Actif | Pearson H4 | Pearson D1 | Lead DXY |
|:---|---:|---:|:---|
| **XAUUSD** (Or) | **−0.72** | **−0.74** | 5-20 barres |
| **XAGUSD** (Argent) 🥇 | **−0.71** | **−0.70** | 5-20 barres |
| XPDUSD (Palladium) | −0.66 | −0.68 | 10-15 barres |
| XPTUSD (Platine) | −0.64 | −0.62 | 10-15 barres |

> Scan exhaustif de **54 symboles USD** : XAGUSD est le meilleur actif non-crypto, les cryptos mineures (NEO, XMR) ayant une corrélation instable.

### Stratégie (identique pour XAUUSD et XAGUSD)

| ★ | Paramètre | Valeur |
|:--:|:---|:---|
| ★ | **Signal** | DXY.cash H1 mouvement fort (>1.5σ roulant sur 50 barres) |
| ★ | **Entrée** | Inverse : DXY↑ → SHORT, DXY↓ → LONG |
| ★ | **SL** | 1.5 × ATR du TF de trading |
| ★ | **TP** | 3.0 × ATR du TF de trading |
| ★ | **Filtre 1** | Rolling corrélation 20 barres < −0.3 |
| ★ | **Filtre 2** | Tendance DXY H4 vs SMA20 |
| ★ | **Filtre 3** | Confirmation bougie |
| ★ | **Cooldown** | 2 barres H4 |

### Résultats XAUUSD H4 (référence historique)

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF | FTMO |
|:---|---:|---:|---:|---:|---:|---:|:---|
| **H4** 🏆 | 20 | **55.0%** | **+9.22%** | **+1.25** | −6.3% | 1.46 | **+14.48%** |

### 🏆 Résultats XAGUSD H4 (MEILLEURE STRATÉGIE GLOBALE)

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF | FTMO |
|:---|---:|---:|---:|---:|---:|---:|:---|
| **H4** 🏆 | **18** | **55.6%** | **+25.70%** | **+1.45** | −9.6% | **1.75** | **+18.29%** |

### Comparaison XAUUSD vs XAGUSD

| Métrique | XAUUSD H4 | **XAGUSD H4** | Δ |
|:---|---:|---:|:---|
| Retour | +9.22% | **+25.70%** | **+179%** |
| Sharpe | +1.25 | **+1.45** | +16% |
| WR | 55.0% | **55.6%** | +1% |
| PF | 1.46 | **1.75** | +20% |
| FTMO | +14.48% | **+18.29%** | +26% |
| MaxDD | −6.3% | −9.6% | plus élevé* |

> \* Drawdown plus élevé mais sous la limite FTMO (10%). XAGUSD surperforme XAUUSD sur tous les critères de rentabilité.

### Multi-TF XAGUSD confirmé : seul H4 est rentable

| TF | Trades | WR% | Ret% | Sharpe | Verdict |
|:---:|:---:|:---:|:---:|:---:|:---|
| **H4** | 18 | 55.6% | **+25.70%** | **+1.45** | ✅ Recommandé |
| M15 | 139 | 40.3% | +3.77% | +0.39 | ⚠️ Trop de trades |
| H1 | 68 | 32.4% | −15.57% | −0.49 | ❌ Perdant |
| M5 | 179 | 34.1% | −19.56% | −2.54 | ❌ Perdant |
| M1 | 119 | 27.7% | −18.14% | −13.18 | ❌ Perdant |

### Optimisation seuil XAGUSD

| Seuil | Trades | WR% | Ret% | Sharpe |
|:---:|:---:|:---:|:---:|:---:|
| 1.0σ | 26 | 46% | +10.3% | +0.50 |
| 1.2σ | 21 | 52% | +20.4% | +1.09 |
| **1.5σ** 🏆 | **18** | **56%** | **+25.7%** | **+1.45** |
| 1.8σ | 13 | 46% | +3.8% | +0.40 |
| 2.0σ | 9 | 44% | +4.1% | +0.48 |

> **1.5σ optimal** pour les deux actifs.

### Portefeuille 50/50 XAUUSD + XAGUSD

| Actif | Retour | Sharpe | MaxDD |
|:---|---:|:---:|:---:|
| XAGUSD seul | **+25.70%** | **+1.45** | −9.6% |
| XAUUSD seul | +9.22% | +1.25 | −6.3% |
| **Portfolio 50/50** | +14.59% | ∼0.0 | **−7.0%** |

> Le portefeuille coupe la performance. **XAGUSD seul reste meilleur.**

---

## 5. Classement final

| Rang | Stratégie | Actif | TF | Trades | WR | Ret% | Sharpe | FTMO |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 🥇 | **DXY→XAGUSD** 🆕 | **XAGUSD** | **H4** | **18** | **56%** | **+25.70%** | **+1.45** | **+18.29%** |
| 🥇 | **DXY→XAUUSD** | XAUUSD | H4 | 20 | 55% | +9.22% | +1.25 | +14.48% |
| 3 | Stochastic | GBPUSD | H4 | 53 | 60% | +4.6% | +1.78* | — |
| 4 | Swing_SR | GBPUSD | H4 | 17 | 71% | +2.4% | +1.56* | — |
| 5 | Stochastic | XAGUSD | D1 | 11 | 73% | +137% | +3.00** | — |

> \* Meilleur Sharpe ponctuel sur un couple spécifique — la moyenne est négative.  
> ** \*\* Peu de trades (11) → non statistiquement significatif.

---

## 6. Conclusion

### 🏆 Meilleure stratégie : DXY → XAGUSD H4

| Critère | **XAGUSD H4** 🥇 | XAUUSD H4 |
|:---|---:|---:|
| Trades (6 mois) | 18 (~3/mois) | 20 |
| Win Rate | **55.6%** | 55.0% |
| Retour | **+25.70%** | +9.22% |
| Sharpe | **+1.45** | +1.25 |
| FTMO ROI | **+18.29%** | +14.48% |
| Days lost | 1 | 1 |
| Forces | Signal exogène, lead naturel, corrélation robuste, filtres multiples, anti-look-ahead complet, **meilleur sur XAGUSD** |

### Constats généraux

- ✅ **2 configurations rentables** : DXY→XAGUSD H4 (+25.7%, Sharpe +1.45) et DXY→XAUUSD H4 (+9.2%, Sharpe +1.25)
- ✅ **XAGUSD surpasse XAUUSD** de **+179%** sur le retour et **+26%** sur le FTMO
- ⚠️ **Stratégies classiques** : toutes perdantes ou au mieux flat sur la période
- 📉 **TFs basses (M1–M15)** : le bruit domine systématiquement
- 📈 **TFs hautes (H4, D1)** : seuls timeframes où des stratégies deviennent rentables
- 🔄 **Marché rangeant** : janvier–juillet 2026 sans tendance claire, défavorable aux stratégies testées

---

## 7. Fichiers du projet

```
strat_compare/
├── signals.py              # 9 générateurs de signaux
├── engine.py               # Moteur de backtesting standard + FTMO
├── config.py               # 32 symboles FTMO, coûts, paramètres
├── main.py                 # CLI multi-TF
├── swing_sr_bot.py         # Bot live Swing_SR
├── dxy_xau_bot.py          # Bot live DXY→XAUUSD H4 (magic 260706)
├── dxy_xag_bot.py          # Bot live DXY→XAGUSD H4 (magic 270706) 🏆
├── _corr_analysis.py       # Analyse corrélation DXY vs actifs
├── _dxy_xau_backtest.py    # Backtest multi-TF DXY → XAUUSD
├── _verify_indicators.py   # Tests indicateurs
├── _trace_verify.py        # Trace PnL
├── AUDIT.md                # Rapport d'audit bugs
├── STRATEGIE_DXY.md        # Doc stratégie DXY → XAU/XAG
├── GUIDE_DXY_BOT.md        # Guide bot XAUUSD
├── GUIDE_XAG_BOT.md        # Guide bot XAGUSD 🆕
├── ANALYSE_CORRELATION_DXY.md # Corrélation DXY vs 28+ actifs
├── RAPPORT_FTMO.md         # Backtest 32 symboles FTMO
├── RAPPORT_GLOBAL.md       # Ce fichier
├── TODO-RESEARCH.md        # Plan test 4 phases
└── README.md               # Documentation générale
```
