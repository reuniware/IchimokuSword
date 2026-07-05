# Strat Compare — Comparaison de stratégies sur forex & or

> **Période :** 01/01/2026 → 03/07/2026 (6 mois)  
> **Données :** MetaTrader5 (EURUSD, GBPUSD, XAUUSD)  
> **Timeframes :** H1, H4  
> **Capital initial :** $10 000

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

---

## 2. Résultats globaux (sans FTMO, capital $10k all-in par trade)

| Stratégie | Sharpe moy | Win Rate moy | Return moy | MaxDD moy | Trades moy |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Swing_SR** 🥇 | **5.47** | **81.8%** | **+24.1%** | **-1.7%** | 62 |
| MACD 🥈 | 0.76 | 41.0% | +7.2% | -5.4% | 146 |
| Stochastic 🥉 | 0.54 | 48.8% | +0.2% | -7.2% | 141 |
| RSI | 0.47 | 44.1% | +2.5% | -3.5% | 55 |
| Parabolic SAR | 0.22 | 40.6% | +3.1% | -7.0% | 161 |
| Bollinger | -0.15 | 43.0% | -1.7% | -7.2% | 101 |
| EMA Cross | -0.24 | 41.4% | +0.7% | -5.7% | 86 |

> **Swing_SR écrase toutes les autres stratégies** avec un Sharpe 7× supérieur au 2ème et un Win Rate 2× supérieur.

---

## 3. Résultats FTMO (risque 2%/trade, levier 1:30, limite $485/jour)

| Stratégie | Sharpe moy | Win Rate moy | Return moy | MaxDD moy |
|:---|:---:|:---:|:---:|:---:|
| **Swing_SR** 🥇 | **5.66** | 81.8% | **+75.0%** | **-2.9%** |
| MACD | 1.13 | 40.8% | +25.2% | -17.4% ❌ |
| Stochastic | 0.65 | 48.7% | +6.1% | -20.9% ❌ |
| Parabolic SAR | 0.40 | 40.4% | +7.7% | -27.2% ❌ |
| EMA Cross | 0.28 | 41.3% | +0.4% | -19.7% ❌ |
| RSI | 0.05 | 44.3% | +2.7% | -12.9% ❌ |
| Bollinger | -0.29 | 43.0% | -7.4% | -21.7% ❌ |

> **Seule Swing_SR respecte les règles FTMO** (MaxDD < 10% + daily loss $485/jour). La limite quotidienne réduit le return de 79.5% → 75.0% (impact mineur car Swing_SR perd rarement $485 en un jour).

### Top 3 FTMO (Swing_SR H1)

| # | Symbole | Trades | Win Rate | Capital final | Gain net | ROI | Sharpe | MaxDD |
|:--:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **GBPUSD** | 106 | 83.0% | **$25 867** | **+$15 867** | **+158.7%** | 8.50 | -3.9% |
| 2 | EURUSD | 111 | 79.3% | $22 015 | +$12 015 | +120.2% | 7.29 | -3.0% |
| 3 | XAUUSD | 91 | 81.3% | $20 949 | +$10 949 | +109.5% | 6.87 | -4.0% |

> L'impact de la limite $485/jour : -$1 116 sur GBPUSD, -$761 sur EURUSD, -$836 sur XAUUSD. Perte modérée vu le gain total.

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

## 5. Comparaison H1 vs H4 (Swing_SR)

| Symbole | TF | Trades | Win Rate | Return | Sharpe | MaxDD |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| GBPUSD | H1 | 106 | 83.0% | +17.0% | 7.97 | -0.8% |
| GBPUSD | H4 | 27 | 77.8% | +8.4% | 4.26 | -1.0% |
| EURUSD | H1 | 111 | 79.3% | +12.9% | 6.94 | -0.6% |
| EURUSD | H4 | 22 | 81.8% | +5.9% | 3.28 | -0.9% |
| XAUUSD | H1 | 91 | 81.3% | +71.9% | 6.32 | -4.1% |
| XAUUSD | H4 | 16 | 87.5% | +28.3% | 4.04 | -2.5% |

> **H1 est systématiquement supérieur à H4** (plus de trades, meilleur Sharpe). XAUUSD H1 est le plus rentable en absolu mais avec un MaxDD plus élevé.

---

## 6. Structure du module

```
strat_compare/
├── __init__.py         # Package init
├── config.py           # Période, symboles, timeframes, stratégies, coûts
├── signals.py          # 7 générateurs de signaux + indicateurs communs
├── engine.py           # Moteur de backtesting + mode FTMO
├── main.py             # CLI : python -m strat_compare.main compare [--ftmo]
├── swing_sr_bot.py     # LIVE TRADING BOT : Swing_SR sur MT5 (tous brokers)
├── GUIDE.md            # Guide d'utilisation complet du bot (dry-run, reel, actifs)
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

## 8. Conclusion

Sur la période **janvier→juillet 2026**, la stratégie **Swing_SR** (rebonds sur supports/résistances) domine **très largement** toutes les autres :

- **Sharpe 5.5×** supérieur au 2ème
- **Win rate 2×** supérieur (82% vs 41-49%)
- **MaxDD 4×** inférieur (-1.7% vs -5 à -7%)
- **Seule stratégie viable en FTMO** (MaxDD < 10%)

Les stratégies classiques de trend-following (MACD, EMA Cross, Parabolic SAR) et de mean reversion mathématique (RSI, Bollinger, Stochastic) sont **largement battues** par l'approche basée sur les niveaux de prix structurels.

### Limites de l'étude

- Période de 6 mois seulement (01/01→03/07/2026)
- Marché majoritairement rangeant sur cette période
- Non testé en conditions de crise ou de tendance forte
- 3 symboles seulement (forex + or)
- Les résultats FTMO sont théoriques ( slippage réel, exécution, etc. )

### Prochaines étapes suggérées

1. **Grid search** sur `swing_window` et `proximity_atr` pour optimiser Swing_SR
2. **Filtre ADX** : désactiver les trades LONG/SHORT selon le régime de tendance
3. **Backtest longue période** (2023-2026) pour valider la robustesse
4. **Ajout d'indices** (US500, GER40) pour diversification
5. **Walk-forward analysis** pour détecter l'overfitting
