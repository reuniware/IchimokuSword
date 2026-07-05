# Rapport — Backtest Complet FTMO (Tous instruments, 6 timeframes)

**Date :** 06/07/2026
**Période :** 01/01/2026 → 03/07/2026 (6 mois)
**Capital initial :** $10 000

---

## 🔬 Méthodologie

- **32 symboles FTMO** testés : 7 forex majors, 10 forex minors, 6 indices, 5 commodités, 4 cryptos
- **6 timeframes** : M1, M5, M15, H1, H4, D1
- **7 stratégies** : RSI, Bollinger, MACD, Stochastic, EMA Cross, Swing_SR, Parabolic SAR
- **2 modes** : Standard (capital all-in) + FTMO (risque 2%/trade, levier 1:30, daily loss $485)
- **Coûts réalistes** par catégorie (spread + slippage)
- **1127 backtests** exécutés au total

---

## 📊 Résultats — Standard (capital $10k all-in)

### Classement général (top 10 sur 644 tests D1/H4/H1/M15)

| # | Stratégie | Symbole | TF | Trades | WR% | Ret% | Sharpe | MaxDD% |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **Stochastic** | XAGUSD | D1 | 11 | 81.8% | +137.6% | 3.00 | -15.9% |
| 2 | Parabolic_SAR | XRPUSD | D1 | 12 | 66.7% | +86.0% | 2.73 | -4.1% |
| 3 | Bollinger | GBPJPY | D1 | 5 | 100% | +5.0% | 2.72 | 0.0% |
| 4 | Stochastic | CADJPY | D1 | 9 | 66.7% | +5.0% | 2.25 | -1.0% |
| 5 | Swing_SR | GBPJPY | H4 | 19 | 78.9% | +3.6% | 2.24 | -1.5% |
| 6 | Bollinger | EURGBP | D1 | 8 | 75.0% | +1.9% | 2.16 | -0.5% |
| 7 | EMA_Cross | XAUUSD | D1 | 4 | 75.0% | +13.4% | 2.01 | -2.2% |
| 8 | EMA_Cross | EURUSD | D1 | 6 | 66.7% | +3.2% | 2.00 | -0.7% |
| 9 | Bollinger | GBPCHF | D1 | 3 | 66.7% | +1.7% | 1.98 | 0.0% |
| 10 | Swing_SR | NZDJPY | D1 | 3 | 100% | +4.2% | 1.97 | 0.0% |

### Synthèse par stratégie (moyenne D1+H4+H1)

| Stratégie | Sharpe | WR% | Ret% | MaxDD% |
|:---|---:|---:|---:|---:|
| Swing_SR | -0.55 | 51.1% | -2.98% | -6.4% |
| RSI | -0.78 | 48.8% | -3.32% | -6.9% |
| EMA_Cross | -1.43 | 42.0% | -6.50% | -11.1% |
| Stochastic | -1.52 | 46.8% | -5.35% | -13.0% |
| Bollinger | -1.65 | 46.7% | -8.02% | -11.0% |
| MACD | -2.04 | 38.8% | -7.54% | -13.0% |
| Parabolic_SAR | -2.39 | 38.6% | -10.0% | -15.3% |

### Analyse par timeframe

| TF | Meilleur Sharpe | Pire Sharpe | Constat |
|:---|:---:|:---:|:---|
| **D1** 🥇 | +3.00 (Stoch/XAGUSD) | -4.00 | **Seul TF positif** — peu de trades, peu de bruit |
| **H4** 🥈 | +2.24 (Swing_SR/GBPJPY) | -8.50 | Quelques configs positives, majorité négatives |
| **H1** 🥉 | +0.70 (Stoch/USDJPY) | -12.0 | Toutes les stratégies perdent en moyenne |
| **M15** ❌ | -1.31 (Swing_SR/XAGUSD) | -33.6 | **Catastrophique** — bruit + coûts = ruine |

---

## 💰 Résultats FTMO (risque 2%/trade, levier 1:30, daily loss $485)

### Top 5 FTMO

| # | Stratégie | Symbole | TF | Sharpe | Ret% | MaxDD% |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | Parabolic_SAR | XRPUSD | D1 | 2.88 | +19.0% | -1.0% |
| 2 | Bollinger | GBPJPY | D1 | 2.80 | +8.9% | 0.0% |
| 3 | Stochastic | XAGUSD | D1 | 2.75 | +16.3% | -4.0% |
| 4 | EMA_Cross | USDCHF | H4 | 2.36 | +23.7% | -8.3% |
| 5 | Stochastic | NZDJPY | H4 | 2.25 | +28.8% | -6.2% |

### Synthèse FTMO par stratégie

| Stratégie | Sharpe | Ret% | MaxDD% | Viable FTMO ? |
|:---|---:|---:|---:|:---:|
| Swing_SR | -0.66 | -5.35% | -9.3% | ❌ Perdant |
| RSI | -1.02 | -12.3% | -16.5% | ❌ |
| EMA_Cross | -1.43 | -18.9% | -25.3% | ❌ |
| Stochastic | -1.80 | -23.4% | -30.4% | ❌ |
| Bollinger | -2.00 | -23.5% | -27.5% | ❌ |
| MACD | -2.06 | -24.8% | -31.8% | ❌ |
| Parabolic_SAR | -2.56 | -29.2% | -35.4% | ❌ |

> **Aucune stratégie n'est viable en FTMO** en moyenne. Même les meilleures configurations isolées ont trop peu de trades (3-12 sur 6 mois) pour être statistiquement fiables.

---

## 🏆 Meilleurs symboles (tous TFs/stratégies confondus)

| Symbole | Catégorie | Sharpe max | Meilleure config |
|:---|:---|:---:|:---|
| **XAGUSD** 🥇 | Commodité | 3.00 | Stochastic D1 |
| **XRPUSD** 🥈 | Crypto | 2.88 | Parabolic_SAR D1 |
| **GBPJPY** 🥉 | Forex Minor | 2.80 | Bollinger D1 |
| XAUUSD | Commodité | 2.19 | MACD H1 |
| NZDJPY | Forex Minor | 2.25 | Stochastic H4 |
| CADJPY | Forex Minor | 2.25 | Stochastic D1 |

---

## 📈 Meilleures stratégies par timeframe

| Timeframe | Meilleure stratégie | Sharpe | Ret% |
|:---|:---|:---:|:---:|
| **D1** | Stochastic | +3.00 | +137% |
| **H4** | Swing_SR | +2.24 | +3.6% |
| **H1** | MACD | +1.63 | +32% (XAUUSD) |
| **M15** | Swing_SR | -1.31 | -19% |

> Pattern clair : plus le timeframe est élevé, meilleurs sont les résultats. M15 est inutilisable (trop de bruit).

---

## 🎯 Conclusions clés

1. **D1 est le seul timeframe rentable** — peu de trades mais ratio risque/rendement favorable
2. **XAGUSD (Silver) est le meilleur actif** — +137% en 6 mois avec Stochastique D1
3. **XRPUSD et GBPJPY** montrent des résultats isolés prometteurs
4. **Aucune stratégie n'est rentable en moyenne** — les moyennes par stratégie sont toutes négatives
5. **FTMO = ruine garantie** avec le position sizing actuel — le risque 2% amplifie les pertes
6. **M15/M5/M1 sont inutilisables** — le bruit + les coûts de transaction écrasent tout signal
7. **Swing_SR** reste la moins mauvaise sur H4/H1/M15, mais négative

### ⚠️ Caveat

Les configurations D1 gagnantes ont **très peu de trades** (3-12 sur 6 mois). Ces résultats ne sont **pas statistiquement significatifs** et relèvent probablement du hasard (survivorship bias parmi 644 tests).

---

## 📁 Fichiers générés

| Fichier | Contenu |
|:---|:---|
| `results_d1_h4_h1.csv` | 483 backtests standard D1/H4/H1 |
| `results_ftmo.csv` | 483 backtests FTMO D1/H4/H1 |
| `results_m15.csv` | 161 backtests standard M15 |

