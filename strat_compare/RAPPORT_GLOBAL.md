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

## 4. Groupe C — Stratégie cross-asset DXY → XAUUSD

### Analyse de corrélation préalable

| Métrique | H1 | H4 | D1 |
|:---|---:|---:|---:|
| Pearson close | **−0.72** | **−0.72** | **−0.74** |
| Pearson returns | −0.50 | −0.50 | −0.48 |
| DXY lead XAUUSD | 20 barres | 20 barres | 5 barres |
| Rolling 50b % négatif | 89% | 82% | **100%** |
| Régression : 1 pt DXY = | −$206 XAU | −$206 XAU | −$208 XAU |

### Stratégie

| ★ | Paramètre | Valeur |
|:--:|:---|:---|
| ★ | **Signal** | DXY.cash H1 mouvement fort (>1.5σ roulant sur 50 barres) |
| ★ | **Entrée** | Inverse sur XAUUSD : DXY↑ → SHORT, DXY↓ → LONG |
| ★ | **SL** | 1.5 × ATR du TF de trading |
| ★ | **TP** | 3.0 × ATR du TF de trading |
| ★ | **Filtre 1** | Rolling corrélation 20 barres < −0.3 (évite régimes "safe haven") |
| ★ | **Filtre 2** | Tendance DXY H4 vs SMA20 (alignement macro) |
| ★ | **Filtre 3** | Confirmation bougie (bullish pour LONG, bearish pour SHORT) |
| ★ | **Cooldown** | 2 à 30 barres selon TF |
| ★ | **Anti-look-ahead** | Rolling std (pas global), shift(1) + ffill, H4 trend shift(1) |

### Résultats multi-TF (XAUUSD seul)

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF | FTMO |
|:---|---:|---:|---:|---:|---:|---:|:---|
| **🏆 H4** | 20 | **55.0%** | **+9.22%** | **+1.25** | −6.3% | 1.46 | **+14.5%** |
| 🥈 H1 | 65 | 43.1% | +5.86% | +0.64 | −15.3% | 1.14 | — |
| M15 | 146 | 33.6% | −17.4% | −2.95 | −21.0% | 0.66 | −44.6% |
| M5 | 182 | 35.7% | −13.0% | −3.26 | −14.4% | 0.70 | — |
| M1 | 119 | 27.7% | −10.8% | −16.9 | −11.0% | 0.31 | — |

### Pattern

```
H4 (+1.25) > H1 (+0.64) > M15 (−2.95) > M5 (−3.26) > M1 (−16.9)
```

Le bruit tue le signal sur les TFs basses. Plus le TF monte, plus la stratégie s'améliore.

---

## 5. Classement final

| Rang | Stratégie | Actif | TF | Trades | WR | Ret% | Sharpe | FTMO |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 🥇 | **DXY→XAUUSD** | XAUUSD | **H4** | 20 | 55% | **+9.2%** | **+1.25** | **+14.5%** |
| 🥈 | Stochastic | GBPUSD | H4 | 53 | 60% | +4.6% | +1.78 | — |
| 🥉 | Swing_SR | GBPUSD | H4 | 17 | 71% | +2.4% | +1.56 | — |
| 4 | Stochastic | XAGUSD | D1 | 11 | 73% | +137% | +3.00 | — |
| 5 | Parabolic SAR | XRPUSD | D1 | 12 | 58% | +86% | +2.73 | — |

---

## 6. Conclusion

### 🎯 Meilleure stratégie : DXY → XAUUSD H4

| Critère | Valeur |
|:---|---:|
| Trades (6 mois) | 20 (~3/mois) |
| Win Rate | **55%** |
| Retour | **+9.2%** |
| Sharpe | **+1.25** |
| FTMO ROI | **+14.5%** |
| Days lost | 1 |
| Forces | Signal exogène, lead naturel, corrélation robuste, filtres multiples, anti-look-ahead complet |
| Faiblesse | Peu de trades, dépendance à DXY.cash, sensible au choix du seuil σ |

### Constats généraux

- ✅ **1 seule stratégie rentable** : DXY→XAUUSD H4
- ⚠️ **Stratégies classiques** : toutes perdantes ou au mieux flat sur la période
- 📉 **TFs basses (M1–M15)** : le bruit domine systématiquement
- 📈 **TFs hautes (H4, D1)** : seuls timeframes où des stratégies deviennent rentables
- 🔄 **Marché rangeant** : janvier–juillet 2026 sans tendance claire, défavorable aux stratégies testées

---

## 7. Fichiers du projet

```
strat_compare/
├── signals.py              # 9 générateurs de signaux + indicateurs (Ichimoku inclus)
├── engine.py               # Moteur de backtesting standard + FTMO
├── config.py               # 32 symboles FTMO, 6 TFs, coûts, paramètres stratégies
├── main.py                 # CLI multi-TF : python -m strat_compare.main compare
├── swing_sr_bot.py         # Bot live Swing_SR (tous brokers MT5)
├── _corr_analysis.py       # Analyse corrélation XAUUSD vs DXY.cash
├── _dxy_xau_backtest.py    # Backtest multi-TF DXY → XAUUSD (M1→H4)
├── _verify_indicators.py   # Tests de validation indicateurs (30/30 PASS)
├── _trace_verify.py        # Trace PnL pas à pas
├── AUDIT.md                # Rapport d'audit : bugs, corrections, validation
├── STRATEGIE_DXY.md        # Documentation détaillée stratégie DXY → XAUUSD
├── RAPPORT_FTMO.md         # Backtest 32 symboles FTMO
├── RAPPORT_GLOBAL.md       # Ce fichier — synthèse complète
├── GUIDE.md                # Guide du bot live
└── README.md               # Documentation générale
```
