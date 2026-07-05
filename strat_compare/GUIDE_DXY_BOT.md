# GUIDE DXY_BOT — Bot Live DXY.cash → XAUUSD H4

> **Version :** 1.1  
> **Fichier :** `strat_compare/dxy_xau_bot.py`  
> **Backtest associé :** `strat_compare/_dxy_xau_backtest.py`  
> **Stratégie détaillée :** `strat_compare/STRATEGIE_DXY.md`  
> **Variante XAGUSD :** `strat_compare/GUIDE_XAG_BOT.md`

---

## 1. Concept

Le bot exploite la **corrélation inverse forte** entre le Dollar Index (DXY.cash) et l'Or (XAUUSD) :

```
DXY ↗ fort  ──▶  XAUUSD doit ↘  →  SHORT XAUUSD
DXY ↘ fort  ──▶  XAUUSD doit ↗  →  LONG XAUUSD
```

- **Corrélation Pearson :** −0.72 (H1, H4, D1)
- **Lead DXY :** 5-20 barres sur tous les TFs
- **Meilleur TF :** H4 (20 trades/6 mois, 55% WR, Sharpe +1.25)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                 DxyXauBot.run()                       │
│  Boucle infinie (intervalle 300s par défaut)         │
│                                                       │
│  ┌─────────────────────────────────────────────┐    │
│  │           DxyXauBot.run_once()                │    │
│  │                                               │    │
│  │  1. _reset_daily()     → Reset FTMO jour     │    │
│  │  2. Check FTMO limit   → Bloque si atteinte  │    │
│  │  3. fetch_bars() × 4   → DXY H1/H4 + XAU H4/M15│  │
│  │  4. detect_dxy_signal() → Algo 7 étapes      │    │
│  │  5. Cooldown check      → min N barres H4    │    │
│  │  6. Anti-doublon        → Pas 2 signaux ident│    │
│  │  7. Gestion positions   → Ferme si opposé    │    │
│  │  8. FTMO risk scaling   → Réduit si marge <  │    │
│  │  9. place_order()       → SL/TP sur prix réel│    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Sources de données (4 flux parallèles)

| Source | Symbole | TF | Rôle |
|:---|:---|:---|:---|
| `dxy_h1` | DXY.cash | H1 | Signal principal (retour > seuil) |
| `dxy_h4` | DXY.cash | H4 | Filtre tendance (close vs SMA20) |
| `xau_h4` | XAUUSD | H4 | Trading : ATR, confirmation bougie |
| `xau_corr` | XAUUSD | M15 | Resample → H1 pour corrélation |

---

## 3. Algorithme de détection (`detect_dxy_signal`)

### Étape 1 — Détection signal DXY H1

```
dxy_ret = close.pct_change() * 100
dxy_std = rolling(50, min_periods=20).std()  // avec expanding fallback

i_h1 = len(df) - 2   // dernière barre H1 COMPLÉTÉE (anti-look-ahead)

SI |dxy_ret[i_h1]| > threshold × dxy_std[i_h1]:
    → DXY_UP   → trade_dir = SHORT
    → DXY_DOWN → trade_dir = LONG
SINON:
    → None (pas de signal)
```

### Étape 2 — Filtre corrélation roulante

```
xau_h1 = XAUUSD_M15.resample('1h').last()
rolling_corr(20) = corr(xau_h1_ret, dxy_h1_ret)

SI corr[i_h1] > -0.3:   // corrélation pas assez négative
    → None (régime "safe haven" ou décorrélé)
```

**Important :** la corrélation est lue à la même barre H1 (`i_h1`) que le signal DXY — pas de look-ahead.

### Étape 3 — Filtre tendance DXY H4

```
dxy_h4_sma = DXY_H4.close.rolling(20).mean()
dxy_h4_trend_h1 = dxy_h4_sma.reindex(H1.index, method='ffill')

h4_bullish = DXY_H1.close[i_h1] > dxy_h4_trend_h1[i_h1]

SI trade_dir == SHORT ET NOT h4_bullish: → None
SI trade_dir == LONG  ET h4_bullish:     → None
```

Ne shorter que si DXY est haussier sur H4. Ne longer que si DXY est baissier.

### Étape 4 — Alignement temporel

```
h1_signal_time = DXY_H1.index[i_h1]
i_xau = XAU_H4.index.get_indexer([h1_signal_time], method='ffill')

SI i_xau >= len(XAU_H4) - 1:  → None  // barre H4 incomplete
```

Trouve la barre H4 qui **contient** le timestamp du signal DXY H1. N'utilise que les barres complétées.

### Étape 5 — Confirmation bougie XAUUSD H4

```
SI LONG  ET close[i_xau] <= open[i_xau]: → None
SI SHORT ET close[i_xau] >= open[i_xau]: → None
```

### Étape 6 — Calcul ATR

```
ATR = Wilder(14) sur XAUUSD H4
a = ATR[i_xau]
```

### Étape 7 — Retour signal

```python
return {
    "direction": "LONG" | "SHORT",
    "atr": a,                    # ATR H4 courant
    "dxy_direction": "UP"|"DOWN",
    "dxy_ret": ret_i,            # % retour DXY H1
    "dxy_threshold": thresh_i,   # seuil utilisé
    "correlation": corr_val,     # rolling corr(20)
    "candle_close": curr_close,
    "bar_time": timestamp,       # pour cooldown
}
```

---

## 4. Exécution d'ordre (`place_order`)

Le SL/TP sont **recalculés** à partir du prix d'exécution réel (tick), pas du prix historique :

```python
exec_price = tick.ask           # LONG
exec_price = tick.bid           # SHORT

sl_price = exec_price ± 1.5 × ATR
tp_price = exec_price ± 3.0 × ATR
```

**Ratio R:R = 1:2** (3.0 / 1.5 = 2.0).

### Anti-look-ahead garanti

| Élément | Mécanisme |
|:---|:---|
| Signal DXY H1 | `len(df) - 2` → barre complétée |
| Rolling std DXY | `rolling(50)` + `expanding` fallback, sans forward data |
| Corrélation | Lue à `i_h1` (même barre que le signal) |
| Tendance H4 | SMA projetée H4→H1, lue à `i_h1` |
| Confirmation bougie | Barre H4 contenant le signal DXY, complétée uniquement |
| SL/TP | Recalculés depuis le tick d'exécution |

---

## 5. Paramètres

### Configuration par défaut

```python
DEFAULT_CONFIG = {
    # Actifs
    "dxy_symbol": "DXY.cash",
    "trade_symbol": "XAUUSD",
    "dxy_tf": "H1",
    "trade_tf": "H4",
    "corr_tf": "M15",

    # Stratégie
    "threshold_std": 1.5,        # Seuil DXY en écarts-types
    "std_window": 50,            # Fenêtre rolling std
    "sl_atr": 1.5,               # SL en ATR
    "tp_atr": 3.0,               # TP en ATR
    "atr_period": 14,
    "rolling_corr_min": -0.3,    # Corrélation minimum
    "h4_sma_period": 20,         # SMA H4 pour trend
    "cooldown_bars": 2,          # Barres H4 entre signaux

    # Risk
    "risk_pct": 2.0,
    "daily_loss_limit": 485.0,   # FTMO 5% de $10k = $500, marge $15

    # Data
    "min_bars_dxy_h1": 300,
    "min_bars_dxy_h4": 100,
    "min_bars_xau_h4": 300,
    "min_bars_xau_corr": 5000,   # M15 pour corrélation H1
}
```

### Ajustements recommandés

| Paramètre | Défaut | Si trop peu de trades | Si trop de pertes |
|:---|:---|:---|:---|
| `threshold_std` | 1.5 | Baisser à 1.2 | Monter à 2.0 |
| `sl_atr` | 1.5 | — | Augmenter à 2.0 |
| `tp_atr` | 3.0 | — | — |
| `rolling_corr_min` | −0.3 | Remonter à −0.1 | Baisser à −0.5 |
| `cooldown_bars` | 2 | Baisser à 1 | Augmenter à 4 |

---

## 6. Usage

### Lancer le bot

```bash
# Mode réel (ATTENTION : ordres exécutés)
cd strat_compare
python dxy_xau_bot.py

# Mode simulation (dry-run) — recommandé pour tester
python dxy_xau_bot.py --dry-run

# Personnaliser le risque
python dxy_xau_bot.py --risk 1.0 --sl-atr 2.0 --cooldown 4

# Changer l'intervalle de scan
python dxy_xau_bot.py --interval 600   # 10 minutes
```

### Options CLI

```
--dry-run        Simulation (pas d'ordres réels)
--risk FLOAT     % risque par trade (défaut: 2.0)
--threshold FLOAT Seuil DXY en σ (défaut: 1.5)
--sl-atr FLOAT   SL en ATR (défaut: 1.5)
--tp-atr FLOAT   TP en ATR (défaut: 3.0)
--cooldown INT   Cooldown en barres H4 (défaut: 2)
--interval INT   Intervalle scan secondes (défaut: 300)
--magic INT      Magic number MT5 (défaut: 260706)
```

### Sortie typique

```
2026-07-05 14:30:15 [INFO] ======================================================================
2026-07-05 14:30:15 [INFO]   DXY->XAUUSD Bot DEMARRE | Mode: DRY-RUN | 2026-07-05 14:30 UTC
2026-07-05 14:30:15 [INFO]   Signal: DXY.cash H1 | Trading: XAUUSD H4 | Corr: XAUUSD M15
2026-07-05 14:30:15 [INFO]   Threshold: 1.5σ | SL: 1.5 ATR | TP: 3.0 ATR | Risque: 2.0%
2026-07-05 14:30:15 [INFO]   Filtres: corr < -0.3 | trend H4 DXY SMA20 | Cooldown: 2 barres
2026-07-05 14:30:15 [INFO] ======================================================================
2026-07-05 14:35:20 [INFO] [DRY-RUN] XAUUSD SHORT | Lots=0.05 | Entry=2650.50 | SL=2665.20 | TP=2606.10 | ...
2026-07-05 14:35:20 [INFO]   >> XAUUSD SHORT | Close=2648.30 | ATR=9.80 | DXY=UP(0.453%) | Corr=-0.612
```

---

## 7. Règles FTMO

### Limite de perte quotidienne

- **Limite :** $485/jour (marge de sécurité vs $500 FTMO)
- **Calcul :** `account.equity - start_of_day_equity` (inclut le PnL flottant)
- Une fois la limite atteinte : **plus aucun trade** jusqu'au jour suivant

### Réduction de risque

Si le risque du trade (2% × equity) dépasse la marge restante avant la limite FTMO, le risque est automatiquement réduit :

```python
remaining = daily_limit + daily_pnl     # marge restante
if max_risk > remaining:
    risk_pct = max(remaining / equity * 100, 0.1)
```

---

## 8. Cooldown et anti-doublon

| Mécanisme | Règle | But |
|:---|:---|:---|
| **Cooldown** | Min 2 barres H4 (8h) entre deux trades | Éviter le surtrading |
| **Anti-doublon** | Pas 2 signaux consécutifs de même direction | Éviter la ré-entrée après SL/TP |

L'anti-doublon se reset automatiquement quand un signal opposé est tradé.

---

## 9. Gestion des erreurs

| Situation | Comportement |
|:---|:---|
| MT5 déconnecté | Reconnexion automatique toutes les 5s |
| Données insuffisantes (fetch None) | Skip du cycle, log DEBUG |
| Fallback fetch (broker limité) | Essaie 50000→20000→10000→5000→1000 barres |
| Spread > max | Trade ignoré, log WARNING |
| Ordre IOC refusé | Fallback automatique vers RETURN |
| close_position échoue | Position conservée, skip du signal, log ERROR |
| Exception dans run_once | Catch, log ERROR, continue la boucle |

---

## 10. Dépendances

```
MetaTrader5  (pip install MetaTrader5)
pandas
numpy
python-dotenv (via src.config.load_env)
```

---

## 11. Fichiers liés

| Fichier | Contenu |
|:---|:---|
| Fichier | Contenu |
|:---|:---|
| `strat_compare/dxy_xau_bot.py` | Bot live XAUUSD (ce guide) |
| `strat_compare/dxy_xag_bot.py` | **Bot live XAGUSD** (Argent, meilleure perf) |
| `strat_compare/GUIDE_XAG_BOT.md` | Guide complet du bot XAGUSD |
| `strat_compare/_dxy_xau_backtest.py` | Backtest multi-TF XAUUSD |
| `strat_compare/_corr_analysis.py` | Analyse de corrélation DXY/XAUUSD |
| `strat_compare/STRATEGIE_DXY.md` | Doc stratégie complète (XAU + XAG) |
| `strat_compare/ANALYSE_CORRELATION_DXY.md` | Corrélation DXY vs 28+ actifs |
| `strat_compare/RAPPORT_GLOBAL.md` | Synthèse toutes stratégies |
| `strat_compare/SPECS_STRATEGIES.md` | Spécifications techniques |
| `strat_compare/TODO-RESEARCH.md` | Plan de test en 4 phases |
| `src/config.py` | load_env() pour credentials MT5 |

---

## 12. Pour aller plus loin — XAGUSD (Argent)

Un bot dédié à **XAGUSD (Silver)** a été développé sur le même principe : `strat_compare/dxy_xag_bot.py`.

| Métrique | **XAGUSD H4** 🥇 | XAUUSD H4 |
|:---|---:|---:|
| Retour 6 mois | **+25.70%** | +9.22% |
| Sharpe | **+1.45** | +1.25 |
| Win Rate | **55.6%** | 55.0% |
| FTMO 6 mois | **+18.29%** | +14.48% |

> Voir [GUIDE_XAG_BOT.md](GUIDE_XAG_BOT.md) pour l'installation et l'utilisation du bot XAGUSD.
