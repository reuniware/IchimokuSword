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

## Résultats (à venir après exécution)

```bash
python -m turtle.main run --symbols EURUSD,XAUUSD --timeframes D1
```

---

## TODO

- [ ] Grid search multi-paramètres
- [ ] Walk-forward analysis
- [ ] Filtre ADX (régime de marché)
- [ ] Heatmaps Sharpe ratio
- [ ] Export rapport Markdown automatique

---

*Dernière mise à jour : 5 juillet 2026*
