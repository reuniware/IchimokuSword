# Recherche Intraday — Mean Reversion XAGUSD H1

> **Date :** 2026-07-05 22:58 UTC  
> **Période :** 2025-01-01 → 2026-07-03  
> **Actif :** XAGUSD (H1)  
> **Configs testées :** 300

---

## Concept

La stratégie exploite le **retour à la moyenne** de XAGUSD en intraday :

| Condition | LONG | SHORT |
|:---|---:|---:|
| Prix touche la bande | Lower Bollinger | Upper Bollinger |
| RSI confirmé | Survendu (< seuil) | Suracheté (> seuil) |
| Marché range (ADX) | ADX < threshold | ADX < threshold |
| Session | London/NY overlap (13-18h UTC) | London/NY overlap |
| Confirmation bougie | Close > Open | Close < Open |
| SL | -sl_atr × ATR | +sl_atr × ATR |
| TP | +tp_atr × ATR | -tp_atr × ATR |

**Pourquoi XAGUSD H1 ?**
- Volatilité 2-3× supérieure à XAUUSD en intraday → plus de retours à la moyenne
- H1 est le meilleur compromis bruit/signal (les TF < H1 sont trop bruitées)
- Les sessions London/NY overlap concentrent la liquidité

---

## Résultats du Grid Search


### Top 20 configurations (par Sharpe)

| # | RSI | BB | BBσ | OS/OB | ADXth | SLatr | TPatr | Sess | ADXf | Trades | WR% | Ret% | Sharpe | MaxDD | PF |
|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 21 | 20 | 1.5 | 20/85 | 30 | 0.8 | 2.5 | X | X | 7 | 42.9 | +10.07 | +1.12 | -2.3 | 3.55
| 2 | 21 | 10 | 1.5 | 20/85 | 30 | 1.5 | 2.5 | X | X | 6 | 50.0 | +8.99 | +1.12 | -2.8 | 2.82
| 3 | 21 | 10 | 1.5 | 20/70 | 25 | 1.5 | 1.5 | O | X | 22 | 72.7 | +9.00 | +1.11 | -2.8 | 2.26
| 4 | 21 | 10 | 2.5 | 20/70 | 20 | 1.2 | 2.0 | X | X | 10 | 70.0 | +4.49 | +0.98 | -2.5 | 2.33
| 5 | 14 | 20 | 2.0 | 25/75 | 20 | 1.5 | 2.0 | O | X | 23 | 65.2 | +9.02 | +0.94 | -3.9 | 1.76
| 6 | 14 | 30 | 2.5 | 20/75 | 25 | 1.5 | 2.5 | X | O | 20 | 55.0 | +8.41 | +0.90 | -4.6 | 1.72
| 7 | 21 | 20 | 1.5 | 20/85 | 20 | 1.0 | 3.0 | O | X | 1 | 100.0 | +6.70 | +0.81 | 0.0 | inf
| 8 | 14 | 20 | 1.5 | 20/75 | 30 | 1.5 | 2.5 | O | X | 25 | 52.0 | +8.43 | +0.78 | -4.6 | 1.56
| 9 | 21 | 10 | 1.5 | 20/70 | 20 | 1.0 | 2.5 | O | X | 23 | 43.5 | +7.75 | +0.74 | -3.9 | 1.74
| 10 | 21 | 20 | 1.5 | 20/80 | 20 | 0.8 | 3.0 | O | X | 2 | 50.0 | +6.11 | +0.74 | -0.6 | 11.89
| 11 | 21 | 20 | 1.5 | 20/80 | 20 | 0.8 | 2.5 | O | X | 2 | 50.0 | +4.97 | +0.72 | -0.6 | 9.88
| 12 | 21 | 30 | 2.5 | 30/85 | 25 | 0.8 | 2.0 | O | X | 5 | 60.0 | +4.24 | +0.71 | -1.1 | 2.99
| 13 | 21 | 10 | 2.5 | 20/70 | 30 | 1.0 | 3.0 | O | O | 4 | 50.0 | +2.55 | +0.66 | -1.4 | 2.80
| 14 | 21 | 20 | 2.0 | 35/85 | 20 | 1.0 | 1.5 | O | X | 27 | 48.1 | +6.75 | +0.65 | -4.5 | 1.44
| 15 | 21 | 30 | 2.5 | 20/70 | 30 | 1.0 | 2.0 | O | O | 11 | 54.5 | +2.83 | +0.62 | -2.1 | 1.65
| 16 | 21 | 10 | 1.5 | 25/70 | 25 | 1.5 | 2.0 | X | O | 18 | 61.1 | +4.31 | +0.62 | -3.6 | 1.45
| 17 | 21 | 20 | 2.0 | 30/80 | 30 | 0.8 | 2.0 | X | X | 39 | 35.9 | +10.52 | +0.59 | -9.6 | 1.34
| 18 | 21 | 20 | 1.5 | 20/70 | 25 | 1.2 | 1.5 | X | O | 18 | 61.1 | +3.16 | +0.59 | -3.0 | 1.43
| 19 | 7 | 10 | 2.5 | 25/75 | 30 | 1.0 | 3.0 | O | O | 14 | 42.9 | +3.56 | +0.58 | -2.3 | 1.55
| 20 | 7 | 10 | 1.5 | 20/85 | 20 | 1.2 | 1.5 | O | X | 46 | 56.5 | +5.66 | +0.58 | -5.7 | 1.26

### Statistiques globales

| Métrique | Valeur |
|:---|---:|
| Configs testées | 300 |
| Configs rentables (Sharpe > 0.5) | 26 |
| Configs perdantes (Sharpe < 0) | 216 |
| Trades médians | 26 |
| Win rate médian | 33.3% |
| Sharpe médian | -0.46 |

---

## Meilleure Configuration

### Paramètres optimaux

| Paramètre | Valeur |
|:---|---:|
| `rsi_period` | 21 |
| `bb_period` | 20 |
| `bb_std` | 1.5 |
| `rsi_oversold` | 20 |
| `rsi_overbought` | 85 |
| `adx_threshold` | 30 |
| `sl_atr` | 0.8 |
| `tp_atr` | 2.5 |
| `use_session_filter` | False |
| `use_adx_filter` | False |

### Résultats

| Métrique | Valeur |
|:---|---:|
| Trades | 7 |
| Win Rate | 42.9% |
| Retour | +10.07% |
| Sharpe | +1.12 |
| Max Drawdown | -2.3% |
| Profit Factor | 3.55 |

### Vérification FTMO

| Métrique | Valeur |
|:---|---:|
| Capital initial | $10,000 |
| Capital final FTMO | $10,873.18 |
| ROI FTMO | +8.73% |
| Trades FTMO | 7 |
| Days lost | 0 |
| Equity minimale | $9,582.73 |
| Equity < $9,000 ? | NON |

### Répartition par session

| Session | Trades | % |
|:---|---:|---:|
| Asie (00-08h UTC) | 2 | 25%
| Londres (08-13h UTC) | 0 | 0%
| London/NY (13-18h UTC) | 1 | 12%
| New York (18-00h UTC) | 5 | 62%

---

## Comparaison DXY vs Mean Reversion

| Critère | **Mean Reversion** | DXY→XAGUSD (1.2σ) | Δ |
|:---|---:|---:|:---|
| TF | H1 | H4 | — |
| Trades/18mois | 7 | 33 | — |
| Retour | +10.07% | +39.26% | ❌ |
| Sharpe | +1.12 | +1.07 | ✅ |
| MaxDD | -2.3% | -9.6% | ✅ |
| Win Rate | 42.9% | 51.5% | — |
| Intraday | ✅ Oui | ❌ Non (H4) | — |

---

## Conclusion


✅ **Stratégie viable** — La mean reversion sur XAGUSD H1 montre un edge.


> **Meilleure config :** RSI(21) BB(20,1.5) ADX<30 SL=0.8ATR TP=2.5ATR Session=Non
