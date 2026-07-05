# Turtle — Backtest Comparatif Turtle Originale vs Turtle Soup

Backtester comparant deux strategies opposées basées sur le canal de Donchian :

1. **Turtle originale** (Richard Dennis, années 1980) — trend-following
2. **Turtle Soup** (Linda Bradford Raschke, 1996) — contrarian / faux breakouts

Les données sont récupérées via **MetaTrader 5**.

---

## Installation

```bash
pip install MetaTrader5 numpy pandas matplotlib
```

Nécessite un terminal MT5 installé et configuré (via `.env` à la racine du projet).

---

## Utilisation

```bash
# Backtest simple (H4 + D1, tous les actifs configurés)
python -m turtle.main run

# Backtest avec symboles spécifiques
python -m turtle.main run --symbols EURUSD,XAUUSD,US500.cash

# Analyse comparative uniquement
python -m turtle.main compare --symbols EURUSD,XAUUSD

# Tests unitaires
python -m turtle.main test
```

---

## Structure

```
turtle/
├── __init__.py         # Package init
├── config.py           # Paramètres des stratégies, symboles, coûts
├── data_fetcher.py     # Récupération données via MT5
├── signals.py          # Canaux Donchian, Turtle Orig, Turtle Soup
├── engine.py           # Moteur de backtesting (positions, coûts, SL/TP)
├── metrics.py          # CAGR, Sharpe, Sortino, max DD, profit factor
├── visualization.py    # Courbes equity, heatmaps, distribution, corrélation
├── comparison.py       # Analyse comparative (corrélation, portefeuille combiné)
├── main.py             # CLI (run, compare, grid, test)
├── test_turtle.py      # Tests unitaires (données synthétiques)
└── README.md           # Ce fichier
```

---

## Règles des stratégies

### Turtle Originale

| Élément | Paramètre | Défaut |
|:--------|:---------:|:------:|
| Canal entrée S1 | `n1` | 20 |
| Canal entrée S2 | `n2` | 55 |
| Canal sortie | `n_exit` | 10 |
| Période ATR | `atr_period` | 20 |
| Stop-loss | `stop_multiplier` × ATR | 2.0 |
| Pyramidage | jusqu'à `max_units` unités | 4 |
| Pas pyramidage | `pyramid_step` × ATR | 0.5 |

### Turtle Soup

| Élément | Paramètre | Défaut |
|:--------|:---------:|:------:|
| Période canal | `n` | 20 |
| Écart min. extrêmes | `min_ecart` | 3 |
| Stop buffer | `stop_buffer` × ATR | 1.0 |
| Take-profit | `take_profit_mode` | milieu_range |

---

## Anti-biais

- **Look-ahead** : tous les signaux utilisent `close.shift(1)`, jamais la close actuelle
- **Survivorship** : géré par l'utilisateur (choix des symboles)
- **Overfitting** : split train/test configurable, paramètres dans `config.py`
- **Coûts réalistes** : spread, slippage, commissions par classe d'actif

---

## Résultats — Backtest EURUSD & XAUUSD (D1, ~10 ans, avec coûts)

```bash
python -m turtle.main run --symbols EURUSD,XAUUSD --timeframes D1 --costs
```

### Turtle Originale (trend-following)

| Symbole | Trades | Win Rate | CAGR | Sharpe | MaxDD | Profit Factor |
|:--------|:------:|:--------:|:----:|:------:|:-----:|:-------------:|
| EURUSD | **0** | — | — | — | — | — |
| XAUUSD | **0** | — | — | — | — | — |

> **0 trade sur 10 ans en Daily.** Le canal Donchian 20/55 avec close > canal haut est trop rare en D1 sur le forex. Le timeframe Daily n'est pas adapté à cette stratégie — H1 ou H4 seraient plus pertinents.

### Turtle Soup (contrarian)

| Symbole | Trades | Win Rate | CAGR | Sharpe | MaxDD | Profit Factor |
|:--------|:------:|:--------:|:----:|:------:|:-----:|:-------------:|
| EURUSD | 1 404 | **3.5%** | −98.0% | −12.80 | −100% | 0.02 |
| XAUUSD | 1 687 | **0.1%** | −100% | −15.87 | −100% | 0.02 |

> **Destruction totale du capital sur les deux actifs.** La stratégie génère trop de faux signaux (1 400-1 700 trades) avec un win rate inférieur à 4%. Le ratio gain/perte moyen est de 0.1:1 — chaque trade perdant efface 10 trades gagnants. **Après coûts de transaction réalistes (spread + slippage), la stratégie est ruinée.**

### Conclusion honnête

1. **Turtle Originale en D1 ne génère aucun signal** — le timeframe est trop large pour les breakouts Donchian.
2. **Turtle Soup en D1 génère trop de signaux parasites** — le win rate de 0-3.5% est inférieur au hasard.
3. **Les coûts de transaction aggravent la situation** — spread + slippage Forex rendent ces stratégies non viables en l'état.
4. **Prochaines étapes recommandées :** tester sur H1/H4, ajouter filtre ADX, optimiser les paramètres via grid search.

### Corrélation entre stratégies

Non calculable (Turtle Originale = 0 trade). L'hypothèse d'anti-corrélation n'a pas pu être testée sur ce jeu de données.

---

## TODO

- [ ] Tester sur H1/H4 (plus de breakouts)
- [x] Brancher config Turtle Soup (stop_buffer, take_profit_mode, rr_ratio)
- [x] Vectoriser la détection des setups Turtle Soup
- [ ] Grid search multi-paramètres
- [ ] Walk-forward analysis
- [ ] Filtre ADX (régime de marché)
- [ ] Heatmaps Sharpe ratio
- [ ] Export rapport Markdown automatique

---

*Dernière mise à jour : 5 juillet 2026*
