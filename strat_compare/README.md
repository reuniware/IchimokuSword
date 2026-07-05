# Strat Compare — Comparaison de stratégies sur forex & or

> **Période :** 01/01/2026 → 03/07/2026 (6 mois)  
> **Données :** MetaTrader5 (EURUSD, GBPUSD, XAUUSD, DXY.cash)  
> **Timeframes :** M1, M5, M15, H1, H4, D1  
> **Capital initial :** $10 000  
> **Stratégies :** 9 (7 classiques + Ichimoku + DXY Correlation)

---

## 1. Stratégies testées

| # | Stratégie | Type | Signal d'entrée |
|:--:|:---|:---|:---|
| 1 | **RSI** | Mean reversion | RSI(14) sort de la zone survendue (>30) ou surachatée (<70) |
| 2 | **Bollinger** | Mean reversion | Prix touche la bande inférieure (LONG) ou supérieure (SHORT) |
| 3 | **MACD** | Trend following | MACD(12,26,9) crossover au-dessus (LONG) ou en dessous (SHORT) |
| 4 | **Stochastic** | Mean reversion | %K(14,3) croise %D en zone survendue (<20) ou surachatée (>80) |
| 5 | **EMA Cross** | Trend following | EMA(9) croise au-dessus (LONG) ou en dessous (SHORT) de EMA(21) |
| 6 | **Swing_SR** ⭐ | S/R bounces | Rebond sur support/résistance horizontal avec confirmation bougie |
| 7 | **Parabolic SAR** | Trend following | SAR(0.02, 0.2) flippe de au-dessus à en dessous du prix (LONG) ou inverse |
| 8 | **Ichimoku Scalp** 🆕 | Flat-line breakout | Cassure d'une ligne Ichimoku plate (Kijun/Senkou B), même TF |
| 9 | **Ichimoku MTF** 🆕 | MTF Flat-line | Flat lines détectées sur H4/D1, trading sur TF basse (M15) |

### Stratégie cross-asset

| # | Stratégie | Type | Signal d'entrée |
|:--:|:---|:---|:---|
| ★ | **DXY → XAUUSD** 🆕 | Correlation | DXY.cash H1 fort (>1.5σ) → entrée inverse XAUUSD |
| ★ | **DXY → XAGUSD** 🆕🥇 | Correlation | DXY.cash H1 fort (>1.5σ) → entrée inverse XAGUSD (MEILLEURE PERF) |

> Voir [STRATEGIE_DXY.md](STRATEGIE_DXY.md) pour l'analyse complète de la stratégie de corrélation.  
> **Meilleur actif : XAGUSD** (+25.7%, Sharpe +1.45). Bot dédié : `dxy_xag_bot.py`.

---

## 2. Résultats globaux (sans FTMO, capital $10k all-in par trade)

> ⚠️ **Corrigés le 05/07/2026** — Un bug de look-ahead bias dans Swing_SR a été découvert et corrigé.
> Les résultats ci-dessous reflètent la performance **réelle** sans fuite de données futures.
> Voir [AUDIT.md](AUDIT.md) pour le détail des bugs trouvés et corrigés.

| Stratégie | Sharpe moy | Win Rate moy | Return moy | MaxDD moy | Trades moy |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Stochastic** | **-1.08** | 48.3% | **-5.99%** | -11.3% | 43 |
| RSI | -0.25 | 43.4% | -0.09% | -4.3% | 29 |
| **Swing_SR** | **0.01** | 63.6% | -1.30% | -4.9% | 37 |
| MACD | -1.03 | 39.8% | -0.39% | -8.0% | 62 |
| Bollinger | -1.30 | 42.7% | -5.68% | -9.3% | 44 |
| EMA Cross | -1.53 | 41.2% | -3.23% | -7.9% | 38 |
| Parabolic SAR | -1.68 | 39.4% | -4.38% | -9.9% | 58 |

> **Les stratégies classiques sont toutes perdantes** sur la période. La seule stratégie rentable est **DXY→XAGUSD H4** (+25.7%, Sharpe +1.45).
> Les meilleurs classiques : **Stochastic GBPUSD H4** (Sharpe 1.78, +4.58%) et **Swing_SR GBPUSD H4** (Sharpe 1.56, +2.36%).

---

## 3. Résultats FTMO (risque 2%/trade, levier 1:30, limite $485/jour)

> ⚠️ **Corrigés** — Les résultats précédents (+170% ROI) étaient artificiellement gonflés par le look-ahead bias.

| Stratégie | Sharpe moy | Win Rate moy | Return moy | MaxDD moy |
|:---|:---:|:---:|:---:|:---:|
| **Swing_SR** | **0.23** | 63.6% | **-0.28%** | -8.4% |
| RSI | -0.90 | 43.6% | -10.66% | -18.1% |
| MACD | -1.20 | 39.6% | -19.13% | -32.4% |
| Stochastic | -1.33 | 48.4% | -22.82% | -35.7% |
| EMA Cross | -1.40 | 41.0% | -19.32% | -29.4% |
| Bollinger | -1.71 | 42.7% | -25.86% | -32.1% |
| Parabolic SAR | -2.04 | 39.1% | -31.48% | -39.9% |

> **Aucune stratégie n'est viable en FTMO** sur la période. Le position sizing FTMO (risque 2% avec levier) amplifie les pertes.
> Meilleur résultat FTMO : **Stochastic GBPUSD H4** (+24.9%, Sharpe 2.00, MaxDD -10.5% — mais le MaxDD dépasse la règle FTMO de 10%).

---

## 4. Swing_SR — Explication détaillée ⭐

### Concept

Stratégie de **mean reversion** qui trade les rebonds sur des **niveaux de support et résistance horizontaux**. Contrairement aux indicateurs mathématiques (RSI, MACD, Bollinger), cette stratégie utilise des **niveaux de prix réels** — les points où le marché a historiquement rebondi ou été rejeté.

### Algorithme (5 étapes)

#### Étape 1 : Détection des Swing Points

```
swing_window = 20
```

- **Swing High** (résistance) : barre dont le `high` est le maximum de la fenêtre `[i-20, i+20]` (41 barres)
- **Swing Low** (support) : barre dont le `low` est le minimum de cette fenêtre

#### Étape 2 : Recherche du S/R le plus proche

Pour chaque barre `i`, on regarde les **80 barres précédentes** (`swing_window × 4`) et on prend le **dernier** swing low (support) ou swing high (résistance).

#### Étape 3 : Condition de proximité

```
proximity_atr = 0.8  # le prix doit être à moins de 0.8×ATR du niveau
```

- **LONG** : `0 < (prix_bas - support) < 0.8 × ATR` → prix au-dessus du support mais proche
- **SHORT** : `0 < (résistance - prix_haut) < 0.8 × ATR` → prix en dessous de la résistance mais proche

#### Étape 4 : Confirmation par la bougie 🔑

- **LONG** : la bougie doit être **haussière** → `close > open`
- **SHORT** : la bougie doit être **baissière** → `close < open`

On n'achète pas « à l'aveugle » près du support — on attend que le prix montre effectivement un rebond.

#### Étape 5 : Stop-Loss & Take-Profit

```
SL = support - 1.5×ATR   (LONG)
SL = résistance + 1.5×ATR (SHORT)
TP = entrée ± 2.0×ATR
```

Ratio risque/rendement ≈ **1.33:1** — le TP est 33% plus grand que le SL.

### Sorties possibles

| Type | Condition |
|:---|:---|
| **Take-Profit** | Prix atteint le TP (2×ATR depuis l'entrée) |
| **Stop-Loss** | Prix touche le SL (derrière le niveau S/R) |
| **Signal opposé** | Un signal inverse (LONG→SHORT ou SHORT→LONG) apparaît |
| **Fin de période** | Clôture forcée le 03/07/2026 |

### Anti-bruit

Les signaux consécutifs identiques sont filtrés (une seule entrée par niveau).

### Paramètres

| Paramètre | Valeur | Rôle |
|:---|:---:|:---|
| `swing_window` | 20 | Rayon de détection des pivots (±20 barres) |
| `proximity_atr` | 0.8 | Distance max au S/R (en multiple d'ATR) |
| `sl_atr` | 1.5 | Stop-loss placé au-delà du niveau S/R |
| `tp_atr` | 2.0 | Take-profit (2×ATR depuis l'entrée) |
| `atr_period` | 14 | Période de calcul de l'ATR |

### Pourquoi ça marche

1. **Niveaux réels** : contrairement aux bandes de Bollinger (qui bougent avec le prix), un swing high/low est un prix précis que le marché a déjà respecté
2. **Confirmation bougie** : filtre puissant → on n'entre que sur un vrai rejet
3. **Stop serré mais intelligent** : derrière un niveau structurel, pas un niveau arbitraire
4. **TP réaliste** : 2×ATR est atteignable en range, ratio R/R de 1.33 favorable
5. **Période rangeante** : janvier→juillet 2026 était majoritairement sans tendance forte → terrain idéal

### Faiblesses

| Faiblesse | Impact |
|:---|:---|
| Tendance forte | Les swing highs sont cassés → pertes en short |
| Faux swing points | Un swing high peut être un « mauvais » niveau sans signification |
| Dépendance à `swing_window` | Trop petit → pivots parasites ; trop grand → pas assez de signaux |
| Bougie de confirmation | Peut rater des opportunités en range très serré |
| ATR fixe pour SL/TP | Peut sous-estimer la volatilité en news → stops touchés |

---

## 5. Détail Swing_SR par symbole/timeframe (corrigé)

| Symbole | TF | Trades | Win Rate | Return | Sharpe | MaxDD |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| GBPUSD | H4 | 17 | 70.6% | +2.36% | 1.56 | -1.3% |
| XAUUSD | H4 | 18 | 66.7% | +3.58% | 0.85 | -5.3% |
| EURUSD | H4 | 14 | 64.3% | +1.25% | 0.92 | -1.8% |
| GBPUSD | H1 | 43 | 65.1% | +1.02% | 0.43 | -3.5% |
| XAUUSD | H1 | 51 | 58.8% | -8.34% | -0.86 | -11.7% |
| EURUSD | H1 | 63 | 55.6% | -7.64% | -0.87 | -5.9% |

> **H4 est préférable à H1** pour Swing_SR (moins de bruit, meilleur ratio). XAUUSD H4 a le meilleur rendement (+3.6%) mais aussi le MaxDD le plus élevé (-5.3%).

---

## 6. Structure du module

```
strat_compare/
├── __init__.py         # Package init
├── config.py           # Période, symboles, timeframes, stratégies, coûts
├── signals.py          # 9 générateurs de signaux + indicateurs communs (Ichimoku inclus)
├── engine.py           # Moteur de backtesting + mode FTMO
├── main.py             # CLI : python -m strat_compare.main compare [--ftmo] [--tfs ...]
├── swing_sr_bot.py     # LIVE TRADING BOT : Swing_SR sur MT5 (tous brokers)
├── _corr_analysis.py   # Analyse de corrélation XAUUSD vs DXY.cash
├── _dxy_xau_backtest.py # Backtest stratégie DXY → XAUUSD (multi-TF)
├── _verify_indicators.py # Tests de validation des indicateurs (30/30 PASS)
├── _trace_verify.py    # Trace PnL pas à pas
├── AUDIT.md            # Rapport d'audit complet (bugs, corrections, validateurs)
├── STRATEGIE_DXY.md    # Documentation stratégie DXY → XAUUSD
├── RAPPORT_FTMO.md     # Synthèse backtest 32 symboles FTMO
├── GUIDE.md            # Guide d'utilisation du bot live
└── README.md           # Ce fichier
```

### Commandes

```bash
# Backtest standard (toutes les stratégies)
python -m strat_compare.main compare

# Backtest FTMO (position sizing risque 2%, levier 1:30)
python -m strat_compare.main compare --ftmo

# FTMO avec risque personnalisé + symboles spécifiques
python -m strat_compare.main compare --ftmo --ftmo-risk 1.5 --symbols EURUSD,GBPUSD
```

---

## 7. Live Trading Bot — `swing_sr_bot.py` 🤖

Robot de trading **live** pour la stratégie Swing_SR, compatible avec **tous les brokers MetaTrader 5**.

### Fonctionnalités

| Feature | Description |
|:---|:---|
| **Multi-symbole** | Scanne jusqu'à N symboles simultanément |
| **Multi-timeframe** | M1, M5, M15, M30, H1, H4, D1, W1 |
| **Position sizing** | Risque configurable (% du capital) par trade, lot size calculé automatiquement |
| **Gestion positions** | Fermeture automatique sur signal opposé, filtre anti-doublons |
| **Cooldown** | Délai minimum entre deux entrées sur le même symbole |
| **Filtre spread** | Rejette les trades si le spread est trop élevé |
| **Fallback fill policy** | IOC → RETURN automatique si le broker ne supporte pas IOC |
| **Reconnexion auto** | Reconnexion si MT5 se déconnecte en cours de session |
| **Dry-run** | Mode simulation sans ordres réels (`--dry-run`) |
| **Anti look-ahead** | Analyse la dernière bougie **complétée** (jamais la bougie en cours) |
| **FTMO daily loss limit** | Bloque tout trading si la perte du jour atteint $485. Réduit le risque par trade pour rester dans la limite |

### Usage

```bash
# Mode simulation (test sans risque)
python swing_sr_bot.py --dry-run

# Mode réel avec paramètres par défaut (EURUSD,GBPUSD,XAUUSD, H1, risque 2%)
python swing_sr_bot.py

# Personnalisé : symboles spécifiques, H4, risque 1.5%
python swing_sr_bot.py --symbols EURUSD,GBPUSD --tf H4 --risk 1.5

# Scan toutes les 5 minutes (au lieu de 60s)
python swing_sr_bot.py --interval 300
```

### Paramètres CLI

| Flag | Défaut | Description |
|:---|:---|:---|
| `--dry-run` | off | Simulation : pas d'ordres réels |
| `--symbols` | EURUSD,GBPUSD,XAUUSD | Symboles séparés par virgule |
| `--tf` | H1 | Timeframe |
| `--risk` | 2.0 | % risque par trade |
| `--max-positions` | 3 | Max positions simultanées |
| `--interval` | 60 | Secondes entre chaque scan |
| `--swing-window` | 20 | Fenêtre swing points |
| `--proximity` | 0.8 | Proximité S/R en ATR |
| `--sl-atr` | 1.5 | Stop-loss en ATR |
| `--tp-atr` | 2.0 | Take-profit en ATR |
| `--magic` | 250706 | Magic number MT5 |

### Logique de trading (identique au backtest)

1. **Fetch** : récupère les 300 dernières bougies H1 via `copy_rates_from_pos`
2. **Swing points** : détecte swing highs/lows avec fenêtre ±20
3. **Proximité** : vérifie si le prix est à moins de 0.8×ATR d'un S/R
4. **Confirmation** : bougie haussière près du support → LONG ; bougie baissière près de la résistance → SHORT
5. **Ordre** : market order avec SL= niveau ± 1.5×ATR, TP = entrée ± 2.0×ATR
6. **Cooldown** : 5 bougies minimum entre deux entrées sur le même symbole

### Sécurité

- **Anti look-ahead** : analyse la barre `n-2` (dernière complétée), jamais `n-1` (barre en cours)
- **Anti-doublon** : ignore un signal identique au précédent
- **Filtre spread** : rejette si spread > 0.05%
- **Position existante** : si déjà LONG, ignore les nouveaux LONG ; si SHORT apparait, ferme le LONG d'abord
- **Max positions** : limite globale configurable (défaut 3)
- **Reconnexion** : si `terminal_info()` renvoie None, tente une reconnexion automatique
- **FTMO daily loss** : `$485` max par jour (marge 3%) — bloque tout trading si atteint ; réduit le risque par trade pour rester dans la limite

### Exemple de log

```
2026-07-05 14:02:15 [INFO] MT5 connecte | Broker: ICMarkets | Login: 12345 | Balance: 10000.00 USD | Levier: 1:30
2026-07-05 14:02:15 [INFO] ======================================================================
  Swing_SR Bot DEMARRE | Mode: LIVE | 2026-07-05 14:02 UTC
  Symboles: EURUSD, GBPUSD, XAUUSD | Timeframe: H1
  Swing window: 20 | Proximity: 0.8 ATR | SL: 1.5 ATR | TP: 2.0 ATR
  Risque: 2.0% | Max positions: 3 | Magic: 250706
  Intervalle: 60s
======================================================================
2026-07-05 14:02:16 [INFO]   >> GBPUSD LONG | Level=1.26100(support) | Entry=1.26150 | SL=1.26020 | TP=1.26290 | ATR=0.00085
2026-07-05 14:02:17 [INFO] #1 GBPUSD LONG | Ticket=12345678 | Lots=1.23 | Entry=1.26155 | SL=1.26020(0.11%) | TP=1.26290
```

---

## 8. Conclusion (corrigée)

> ⚠️ Les résultats initiaux (Swing_SR Sharpe 5.5, +170% FTMO) étaient **artificiellement gonflés** par un bug de look-ahead bias. Après correction le 05/07/2026, la réalité est plus sobre. Voir [AUDIT.md](AUDIT.md).

### Constats réels

- **Aucune stratégie n'est rentable** sur la période jan→juil 2026 avec des coûts réalistes
- **Swing_SR** (Sharpe 0.01, Return -1.3%) n'est pas meilleur que les autres — son avantage apparent était le bug
- **Stochastic H4** est le meilleur performer ponctuel (Sharpe 1.78, +4.6% GBPUSD) mais pas robuste
- **Aucune stratégie n'est viable en FTMO** avec le position sizing réel (toutes perdent de l'argent)
- Le marché de jan→juil 2026 était un **range sans tendance claire** — défavorable aux stratégies testées

### Limites de l'étude

- Période de 6 mois seulement (01/01→03/07/2026)
- Marché majoritairement rangeant sur cette période
- Non testé en conditions de crise ou de tendance forte
- 3 symboles seulement (forex + or)
- Les résultats FTMO sont théoriques (slippage réel, exécution, etc.)

### Prochaines étapes suggérées

1. **Lancer le bot XAGUSD en dry-run** : `python dxy_xag_bot.py --dry-run`
2. **Backtest longue période** (2020-2026) pour voir le comportement en tendance et en crise
3. **Ajout de trailing stop** sur XAGUSD pour voir si on peut réduire le drawdown (−9.6%)
4. **Walk-forward analysis** pour détecter l'overfitting
