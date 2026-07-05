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

### Résultats 18 mois (Jan 2025 → Juil 2026)

#### XAUUSD H4

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF | FTMO |
|:---|---:|---:|---:|---:|---:|---:|:---|
| **H4** | 34 | **47.1%** | **+7.35%** | **+0.50** | −8.4% | 1.24 | **+13.35%** |

#### 🏆 XAGUSD H4 (MEILLEURE STRATÉGIE GLOBALE)

| TF | Trades | WR% | Ret% | Sharpe | MaxDD | PF | FTMO |
|:---|---:|---:|---:|---:|---:|---:|:---|
| **H4** | **27** | **51.9%** | **+32.97%** | **+0.98** | −9.6% | **1.73** | **+23.19%** |

| Rang 54 paires USD | **#1** 🏆 | — | — | — | — | — | — |

### Comparaison XAUUSD vs XAGUSD (18 mois)

| Métrique | XAUUSD H4 | **XAGUSD H4** | Δ |
|:---|---:|---:|:---|
| Retour | +7.35% | **+32.97%** | **+348%** |
| Sharpe | +0.50 | **+0.98** | +96% |
| WR | 47.1% | **51.9%** | +10% |
| PF | 1.24 | **1.73** | +40% |
| FTMO | +13.35% | **+23.19%** | +74% |
| Rang 54 pairs | #14 | **#1** 🏆 | — |

> XAGUSD surperforme XAUUSD de **4.5×** sur le retour et confirme sa #1 place sur 51 paires USD testées.

### Multi-TF XAGUSD (18 mois)

| TF | Trades | WR% | Ret% | Sharpe | Verdict |
|:---:|:---:|:---:|:---:|:---:|:---|
| **H4** | 27 | 51.9% | **+32.97%** | **+0.98** | ✅ Recommandé |
| H1 | 136 | 30.9% | −29.12% | −0.67 | ❌ Perdant |

> **Seul H4 est rentable** sur 18 mois comme sur 6 mois.

### Optimisation seuil XAGUSD (18 mois)

| Seuil | Trades | WR% | Ret% | Sharpe |
|:---:|:---:|:---:|:---:|:---:|
| 1.0σ | 34 | 47.1% | +18.87% | +0.78 |
| **1.2σ** 🏆 | **33** | **51.5%** | **+39.26%** | **+1.07** |
| 1.5σ | 27 | 51.9% | +32.97% | +0.98 |
| 1.8σ | 18 | 50.0% | +17.22% | +0.63 |
| 2.0σ | 13 | 46.2% | +12.25% | +0.55 |

> Sur 18 mois, **1.2σ est optimal** (contre 1.5σ sur 6 mois). Recommandation : 1.2σ pour XAGUSD, 1.5σ pour XAUUSD.

### Portefeuille 50/50 XAUUSD + XAGUSD (18 mois)

| Actif | Retour | Sharpe | MaxDD |
|:---|---:|:---:|:---:|
| XAGUSD seul | **+32.97%** | **+0.98** | −9.6% |
| XAUUSD seul | +7.35% | +0.50 | −8.4% |
| **Portfolio 50/50** | +17.15% | +0.88 | **−7.3%** |

> Le portefeuille lisse le drawdown (−7.3% vs −9.6%) mais coupe la performance. **XAGUSD seul reste meilleur.**

---

## 5. Classement final

| Rang | Stratégie | Actif | TF | Trades | WR | Ret% | Sharpe | FTMO |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 🥇 | **DXY→XAGUSD** 🏆 | **XAGUSD** | **H4** | **27** | **51.9%** | **+32.97%** | **+0.98** | **+23.19%** |
| 🥈 | **DXY→XAUUSD** | XAUUSD | H4 | 34 | 47.1% | +7.35% | +0.50 | +13.35% |
| 3 | Stochastic | GBPUSD | H4 | 53 | 60% | +4.6% | +1.78* | — |
| 4 | Swing_SR | GBPUSD | H4 | 17 | 71% | +2.4% | +1.56* | — |
| 5 | Stochastic | XAGUSD | D1 | 11 | 73% | +137% | +3.00** | — |

> \* Meilleur Sharpe ponctuel sur un couple spécifique — la moyenne est négative.  
> ** \*\* Peu de trades (11) → non statistiquement significatif.  
> **Données 18 mois pour les stratégies DXY (jan 2025 → juil 2026).** Les classiques restent sur 6 mois (jan → juil 2026).

> \* Meilleur Sharpe ponctuel sur un couple spécifique — la moyenne est négative.  
> ** \*\* Peu de trades (11) → non statistiquement significatif.

---

## 6. Conclusion

### 🏆 Meilleure stratégie : DXY → XAGUSD H4 (18 mois)

| Critère | **XAGUSD H4** 🏆 | XAUUSD H4 |
|:---|---:|---:|
| Période | **18 mois** | 18 mois |
| Trades | **27** (~1.5/mois) | 34 |
| Win Rate | **51.9%** | 47.1% |
| Retour | **+32.97%** | +7.35% |
| Sharpe | **+0.98** | +0.50 |
| FTMO ROI | **+23.19%** | +13.35% |
| Days lost | 1 | 1 |
| Rang 54 pairs | **#1** 🏆 | #14 |
| Forces | Signal exogène, lead naturel, corrélation robuste, **#1/51 paires USD**, confirmé 18 mois |

### Constats généraux

- ✅ **2 configurations rentables** : DXY→XAGUSD H4 (+32.97%, Sharpe +0.98) et DXY→XAUUSD H4 (+7.35%, Sharpe +0.50)
- ✅ **XAGUSD surpasse XAUUSD** de **+348%** sur le retour et **+74%** sur le FTMO
- ✅ **XAGUSD #1/51** paires USD testées sur 18 mois
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
├── 20260705_1640_AUDIT.md                # Rapport d'audit bugs
├── 20260705_2215_STRATEGIE_DXY.md        # Doc stratégie DXY → XAU/XAG
├── 20260705_2248_a_GUIDE_DXY_BOT.md        # Guide bot XAUUSD
├── 20260705_2248_b_GUIDE_XAG_BOT.md        # Guide bot XAGUSD 🆕
├── 20260705_2319_ANALYSE_CORRELATION_DXY.md # Corrélation DXY vs 28+ actifs
├── 20260705_1726_RAPPORT_FTMO.md         # Backtest 32 symboles FTMO
├── 20260705_2231_a_RAPPORT_GLOBAL.md       # Ce fichier
├── 20260705_2302_TODO-RESEARCH.md        # Plan test 4 phases
└── 20260705_1150_b_README.md               # Documentation générale
```
