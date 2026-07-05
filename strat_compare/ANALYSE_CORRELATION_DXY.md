# ANALYSE_CORRELATION_DXY.md

> **Date :** 05/07/2026  
> **Analyse :** Corrélation DXY.cash vs tous les actifs disponibles (forex, commodités, indices, cryptos)  
> **Période :** 01/01/2026 → 03/07/2026 (6 mois)  
> **Méthode :** Pearson sur close, Spearman, Pearson sur returns — TFs H1, H4, D1

---

## 🔬 Méthodologie

- **Source DXY :** `DXY.cash` (H1, H4, D1)
- **Actifs testés :** 28 symboles répartis en 4 catégories (forex major/minor, commodités, cryptos)
- **Métriques :**
  - **Pearson close :** corrélation linéaire des prix (niveaux)
  - **Spearman close :** corrélation de rang des prix (monotonie)
  - **Pearson returns :** corrélation des rendements journaliers/barre

---

## 📊 Résultats par timeframe

### H1 (2915 barres DXY)

| Actif | Catégorie | Pearson Close | Spearman | Returns | Force |
|:---|---:|---:|---:|---:|:---|
| EURUSD | forex_major | −0.9833 | −0.9831 | −0.5808 | *** |
| USDCHF | forex_major | +0.9795 | +0.9846 | +0.6116 | *** |
| GBPUSD | forex_major | −0.9596 | −0.9638 | −0.5158 | *** |
| USDJPY | forex_major | +0.9047 | +0.9078 | +0.4821 | *** |
| XAUUSD | commodities | −0.7223 | −0.6736 | −0.5028 | *** |
| XAGUSD | commodities | −0.6947 | −0.6474 | −0.4882 | *** |
| USDCAD | forex_major | +0.6863 | +0.6779 | +0.3576 | *** |
| XPDUSD | commodities | −0.6683 | −0.5817 | −0.2948 | *** |
| BCHUSD | cryptos | −0.6473 | −0.5102 | −0.2297 | *** |
| XPTUSD | commodities | −0.6192 | −0.5426 | −0.2756 | *** |
| EURGBP | forex_minor | −0.4348 | −0.3525 | −0.2668 | * |
| ADAUSD | cryptos | −0.4375 | −0.4274 | −0.1752 | * |
| XRPUSD | cryptos | −0.4202 | −0.3587 | −0.1607 | * |
| LTCUSD | cryptos | −0.4057 | −0.3732 | −0.1524 | * |
| DOGEUSD | cryptos | −0.3929 | −0.3405 | −0.1487 | * |
| DOTUSD | cryptos | −0.3740 | −0.3089 | −0.1342 | * |
| BTCUSD | cryptos | −0.3335 | −0.2589 | −0.1194 | * |

> *** = Pearson > 0.6 | * = Pearson > 0.3

### H4 (ca. 730 barres DXY)

| Actif | Catégorie | Pearson Close | Spearman | Returns | Force |
|:---|---:|---:|---:|---:|:---|
| EURUSD | forex_major | −0.9818 | −0.9819 | −0.6480 | *** |
| USDCHF | forex_major | +0.9686 | +0.9768 | +0.6442 | *** |
| GBPUSD | forex_major | −0.9458 | −0.9506 | −0.5752 | *** |
| USDJPY | forex_major | +0.9122 | +0.9085 | +0.5851 | *** |
| XAUUSD | commodities | −0.7216 | −0.6758 | −0.5221 | *** |
| XAGUSD | commodities | −0.7079 | −0.6620 | −0.5138 | *** |
| USDCAD | forex_major | +0.6034 | +0.5868 | +0.3338 | *** |
| XPDUSD | commodities | −0.6627 | −0.5691 | −0.3600 | *** |
| BCHUSD | cryptos | −0.6634 | −0.5345 | −0.2952 | *** |
| XPTUSD | commodities | −0.6424 | −0.5679 | −0.3324 | *** |
| BTCUSD | cryptos | −0.3681 | −0.2910 | −0.1650 | * |
| ETHUSD | cryptos | −0.3752 | −0.3101 | −0.1630 | * |
| EURGBP | forex_minor | −0.4876 | −0.4028 | −0.3545 | * |

### D1 (ca. 155 barres DXY)

| Actif | Catégorie | Pearson Close | Spearman | Returns | Force |
|:---|---:|---:|---:|---:|:---|
| EURUSD | forex_major | −0.9888 | −0.9854 | −0.7809 | *** |
| USDCHF | forex_major | +0.9492 | +0.9720 | +0.7166 | *** |
| GBPUSD | forex_major | −0.9399 | −0.9389 | −0.6956 | *** |
| USDJPY | forex_major | +0.8512 | +0.8652 | +0.6246 | *** |
| XAUUSD | commodities | −0.7441 | −0.7050 | −0.4838 | *** |
| XAGUSD | commodities | −0.7038 | −0.6585 | −0.5045 | *** |
| USDCAD | forex_major | +0.6396 | +0.6188 | +0.3816 | *** |
| XPDUSD | commodities | −0.6839 | −0.5965 | −0.3853 | *** |
| XPTUSD | commodities | −0.6188 | −0.5363 | −0.3522 | *** |
| BCHUSD | cryptos | −0.6851 | −0.5361 | −0.3102 | *** |
| EURGBP | forex_minor | −0.4880 | −0.4001 | −0.3938 | * |
| BTCUSD | cryptos | −0.3867 | −0.3337 | −0.2561 | * |

---

## 🏆 Classement des candidats pour stratégie cross-asset

| Rang | Actif | Pearson D1 | Returns D1 | Points forts | Points faibles |
|:---:|:---|---:|---:|:---|---:|
| 🥇 | **XAUUSD** | −0.74 | −0.48 | Déjà backtesté (+9.2% en 6 mois), liquide, pas composant DXY | Mois perdants possibles (−2.5% en juin) |
| 🥈 | **XAGUSD** | −0.70 | −0.50 | Forte corrélation, plus volatile que XAU = potentiel > | Plus large spread, slippage plus élevé |
| 🥉 | **XPDUSD** | −0.68 | −0.39 | Corrélation solide, peu de bruit | Liquidité plus faible, spreads larges |
| 4 | **BCHUSD** | −0.69 | −0.31 | Corrélation surprenante pour une crypto | Très volatile, corrélation instable dans le temps |
| 5 | **XPTUSD** | −0.62 | −0.35 | Corrélation constante | Peu de trades, liquidité faible |

### Non retenus

| Actif | Pearson | Raison |
|:---|---:|:---|
| EURUSD | −0.99 | Composant du DXY à 57% → corrélation circulaire |
| USDCHF | +0.95 | Composant du DXY |
| GBPUSD | −0.94 | Composant du DXY à 12% |
| USDJPY | +0.85 | Composant du DXY |
| Cryptos mineures | <0.40 | Corrélation trop faible pour un signal exploitable |

---

## 🔑 Conclusion

```
DXY.cash
  │
  ├── forte corrélation (0.6-0.99) ──→ EURUSD, GBPUSD, USDCHF, USDJPY ← composants DXY
  │                                      (corrélation circulaire = pas d'edge)
  │
  ├── forte corrélation (0.6-0.75) ──→ XAUUSD, XAGUSD, XPDUSD, XPTUSD ← commodités
  │                                      (véritable edge cross-asset)
  │
  └── corrélation faible (<0.4) ─────→ AUDUSD, NZDUSD, cryptos, indices
                                         (inexploitable)
```

- **XAUUSD est le meilleur actif** pour une stratégie DXY cross-asset : forte corrélation (−0.74), pas un composant du DXY, liquidité parfaite, backtesté rentable
- **XAGUSD est le challenger** à tester en priorité (même corrélation, plus de volatilité)
- **Les forex majors** sont trop corrélés structurellement au DXY (ils le composent)
- **Les cryptos** ont une corrélation trop instable et faible pour un trading cross-asset fiable

### Prochaines étapes possibles

1. Backtest stratégie DXY→XAGUSD H4 (mêmes paramètres que XAUUSD)
2. Backtest multi-TF sur XAGUSD (H1, H4, D1)
3. Backtest combiné XAUUSD + XAGUSD (diversification)
