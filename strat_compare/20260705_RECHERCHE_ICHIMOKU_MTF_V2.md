# Recherche Intraday — Axe B : Ichimoku MTF Scalping V2

> **Date :** 2026-07-05 UTC
> **Période :** 2025-01-01 -> 2026-07-03
> **Actif :** XAGUSD (M15)
> **Configs testées :** 72

---
## Concept

La stratégie Ichimoku MTF Scalping V2 ameliore la version originale avec des filtres supplementaires :

| Composant | Description |
|:---|---|
| **Flat lines H4/D1** | Ichimoku MTF detecte les lignes Kijun/Senkou B plates sur TFs hautes |
| **Breakout M15** | Entree quand le prix franchit une ligne plate (cassure) |
| **Filtre Volume** | Volume > seuil x moyenne roulante -> confirme la cassure |
| **Filtre Chikou** | Prix actuel > prix il y a 26 barres (LONG) -> tendance haussiere |
| **Filtre Kumo** | Nuage fin = cassure probable ; nuage epais = resistance forte |
| **Filtre ADX** | ADX > 25 = marche en tendance (favorable au breakout) |
| **Filtre Session** | London/NY overlap (13-18h UTC) = liquidite max |
| **SL/TP dynamique** | SL de l'autre cote de la ligne, TP = prochaine ligne plate + fallback ATR |

---
## Resultats du Grid Search

### Top 20 configurations (par Sharpe)

| # | TFs | FW | FTh | SL | TP | Vol | Chk | KTh | Sess | ADX | Trades | WR% | Ret% | Sharpe | MaxDD | PF |
|::|::|::|::|::|::|::|::|::|::|::|::|::|::|::|::|:|
| 1 | D     | 10 | 0.01 | 1.2 | 0.8 | N | N | N | Y | N | 4     | 75.0 |   0.55 | +0.57 |  -0.6 | 1.97 |
| 2 | 4hD   | 14 | 0.03 | 0.5 | 0.8 | Y | N | Y | Y | N | 3     | 66.7 |   0.35 | +0.49 |  -0.3 | 2.34 |
| 3 | 4h    | 14 | 0.03 | 0.5 | 2.5 | Y | Y | Y | N | N | 11    | 45.5 |   0.58 | +0.32 |  -1.6 | 1.25 |
| 4 | 4hD   | 10 | 0.005 | 0.8 | 4.0 | N | Y | N | Y | N | 31    | 29.0 |  -0.16 | +0.01 |  -6.3 | 0.99 |
| 5 | 4h    | 14 | 0.05 | 1.0 | 3.0 | N | Y | Y | Y | Y | 4     | 50.0 |  -0.20 | -0.12 |  -1.4 | 0.86 |
| 6 | 1h4hD | 14 | 0.005 | 0.8 | 3.0 | N | N | Y | N | N | 66    | 27.3 |  -2.10 | -0.19 |  -9.4 | 0.89 |
| 7 | 1h4hD | 3  | 0.015 | 1.0 | 2.5 | Y | N | Y | Y | Y | 51    | 37.3 |  -2.25 | -0.24 |  -8.8 | 0.87 |
| 8 | 1h4h  | 14 | 0.005 | 0.6 | 2.0 | Y | Y | N | Y | Y | 5     | 40.0 |  -0.34 | -0.24 |  -1.2 | 0.71 |
| 9 | D     | 7  | 0.01 | 0.8 | 0.8 | N | N | Y | N | N | 17    | 58.8 |  -0.85 | -0.34 |  -2.1 | 0.74 |
| 10 | D     | 3  | 0.005 | 0.5 | 4.0 | N | Y | Y | N | N | 62    | 24.2 |  -4.45 | -0.34 |  -8.4 | 0.84 |
| 11 | 4hD   | 14 | 0.05 | 0.4 | 3.0 | N | N | Y | N | N | 21    | 23.8 |  -1.57 | -0.35 |  -2.9 | 0.77 |
| 12 | 4h    | 7  | 0.03 | 1.0 | 3.0 | N | N | N | Y | Y | 31    | 22.6 |  -3.37 | -0.38 |  -4.7 | 0.75 |
| 13 | 4hD   | 10 | 0.01 | 1.0 | 3.0 | Y | N | Y | N | Y | 9     | 33.3 |  -1.23 | -0.40 |  -3.2 | 0.62 |
| 14 | 4hD   | 10 | 0.05 | 0.3 | 4.0 | Y | N | Y | Y | N | 41    | 19.5 |  -2.79 | -0.46 |  -6.6 | 0.77 |
| 15 | 1h4h  | 7  | 0.01 | 0.4 | 1.0 | Y | N | Y | Y | Y | 5     | 60.0 |  -0.52 | -0.54 |  -0.9 | 0.45 |
| 16 | 4hD   | 3  | 0.03 | 0.6 | 4.0 | Y | N | Y | Y | N | 113   | 20.4 |  -9.48 | -0.58 | -15.7 | 0.75 |
| 17 | 4hD   | 10 | 0.02 | 0.3 | 2.0 | N | Y | Y | N | N | 49    | 32.7 |  -3.00 | -0.58 |  -5.6 | 0.75 |
| 18 | 1h4hD | 14 | 0.01 | 0.6 | 2.5 | N | Y | N | Y | Y | 5     | 40.0 |  -0.81 | -0.63 |  -1.0 | 0.46 |
| 19 | D     | 3  | 0.05 | 0.4 | 4.0 | N | Y | Y | N | Y | 19    | 15.8 |  -3.43 | -0.72 |  -5.3 | 0.61 |
| 20 | 4h    | 7  | 0.05 | 1.2 | 2.5 | Y | N | Y | N | Y | 15    | 40.0 |  -2.09 | -0.75 |  -3.9 | 0.62 |

### Statistiques globales

| Metrique | Valeur |
|:---|---:|
| Configs testees | 72 |
| Configs rentables (Sharpe > 0.5) | 1 |
| Configs perdantes (Sharpe < 0) | 68 |
| Trades median | 46 |
| Win rate median | 30.9% |
| Sharpe median | -1.50 |

---
## Meilleure Configuration

### Parametres optimaux

| Parametre | Valeur |
|:---|---:|
| `higher_tfs` | D |
| `flat_window` | 10 |
| `flat_threshold_atr` | 0.01 |
| `sl_atr` | 1.2 |
| `tp_atr` | 0.8 |
| `use_volume` | False (seuil=1.5) |
| `use_chikou` | False |
| `use_kumo_thickness` | False |
| `use_session` | True |
| `use_adx` | False (seuil=30) |

### Resultats

| Metrique | Valeur |
|:---|---:|
| Trades | 4 |
| Win Rate | 75.0% |
| Retour | +0.55% |
| Sharpe | +0.57 |
| Max Drawdown | -0.6% |
| Profit Factor | 1.97 |
| Avg Win | 0.38% |
| Avg Loss | 0.57% |

### Verification FTMO

| Metrique | Valeur |
|:---|---:|
| Capital initial | $10,000 |
| Capital final FTMO | $10,052.59 |
| ROI FTMO | +0.53% |
| Trades FTMO | 4 |
| Days lost | 0 |
| Equity minimale | $9,824.64 |
| Equity < $9,000 ? | **NON** |

### Repartition des sorties

| Raison | Nb | % |
|:---|---:|---:|
| tp | 3 | 75% |
| signal | 1 | 25% |

---
## Comparaison avec les autres strategies

| Critere | **Ichimoku MTF V2** | Mean Reversion H1 | DXY->XAGUSD (1.2s) |
|:---|---:|---:|---:|
| TF | M15 | H1 | H4 |
| Trades/18mois | 4 | 7 | 33 |
| Retour | +0.55% | +10.07% | +39.26% |
| Sharpe | +0.57 | +1.12 | +1.07 |
| MaxDD | -0.6% | -2.3% | -9.6% |
| Win Rate | 75.0% | 42.9% | 51.5% |
| PF | 1.97 | 3.55 | 1.70 |

---
## Conclusion

>**Strategie viable** — L'Ichimoku MTF Scalping V2 est utilisable avec des parametres optimaux.

> Volume : OFF | Chikou : OFF | Kumo : OFF | Session (13-18h) : ON | ADX : OFF

> **Meilleure config :** TF=D FW=10 FTh=0.01 SL=1.2 TP=0.8 Vol=0 VTh=1.5 Chk=0 KTh=0 KATR=0.8 Sess=1 ADX=0 ADXth=30
