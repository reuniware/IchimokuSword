# TODO — IchimokuSword

Suivi des améliorations suggérées durant les sessions de backtesting.

---

## 🛡️ Stop-Loss & Risk Management

### 1. Corriger la priorité TP > SL dans les outcomes
**Priorité :** ⭐ Haute

Actuellement le code priorise `TP_HIT` sur `SL_HIT` même si le SL a été touché en premier.
Il faut vérifier barre par barre lequel est touché en premier.

**Fichier :** `backtest_cloud_cross.py` — fonction `_build_entry()`

---

### 2. Tester différents types de SL sur le Top 3
**Priorité :** ⭐ Haute

Comparer SSB vs fixed 0.3%, 0.5%, 0.7% vs Kijun sur USDJPY + XAGUSD + XAUUSD.

Objectif : trouver le SL qui maximise le ROI FTMO.

**Commande :**
```bash
python backtest_cloud_cross.py --symbols USDJPY,XAGUSD,XAUUSD --timeframe H4 --max-bars 5000 --mtf --sl-type ssb --ftmo --no-save --quiet
python backtest_cloud_cross.py --symbols USDJPY,XAGUSD,XAUUSD --timeframe H4 --max-bars 5000 --mtf --sl-type fixed --sl-pct 0.3 --ftmo --no-save --quiet
python backtest_cloud_cross.py --symbols USDJPY,XAGUSD,XAUUSD --timeframe H4 --max-bars 5000 --mtf --sl-type fixed --sl-pct 0.5 --ftmo --no-save --quiet
python backtest_cloud_cross.py --symbols USDJPY,XAGUSD,XAUUSD --timeframe H4 --max-bars 5000 --mtf --sl-type fixed --sl-pct 0.7 --ftmo --no-save --quiet
```

---

### 3. Ajouter un SL basé sur l'ATR (Average True Range)
**Priorité :** ⭐ Moyenne

Implémenter `--sl-type atr` : SL = entry - 2×ATR(14).
L'ATR s'adapte à la volatilité, contrairement aux niveaux Ichimoku fixes.

**Fichier :** `backtest_cloud_cross.py` — fonction `_compute_sl()`

---

## 📊 Backtesting & Optimisation

### 4. Backtester tous les actifs individuellement avec SL + FTMO
**Priorité :** ⭐ Moyenne

Identifier quels actifs sont profitables en FTMO avec le pipeline complet.
Actuellement seuls USDJPY, XAGUSD, XAUUSD ont été testés.

**Commande :**
```bash
python backtest_cloud_cross.py --timeframe H4 --max-bars 5000 --mtf --sl-type ssb --ftmo --no-save --quiet
```

---

### 5. Ajouter un mode « LONG only » au backtest
**Priorité :** ⭐ Basse

Tous les backtests montrent que les SHORTS sont perdants.
Ajouter `--long-only` pour ne générer que des signaux LONG.

**Fichier :** `backtest_cloud_cross.py`

---

### 6. Backtest du pipeline combiné (scoring + mécanique)
**Priorité :** ⭐ Basse

Reprendre `backtest_combined.py` avec le SL et voir si l'intersection
scoring > 80 + pipeline mécanique améliore le win rate au-delà de 54.4%.

---

## 🔧 Qualité du code

### 7. Nettoyer le caractère Unicode `─` restant
**Priorité :** ⭐ Basse

Remplacer tous les `─` (U+2500) par `-` dans `backtest_cloud_cross.py`.
Le correctif précédent n'a peut-être pas tout couvert.

---

### 8. Ajouter des tests unitaires pour `_compute_sl()` et `_build_entry()`
**Priorité :** ⭐ Basse

Couvrir les cas : SL kijun avec < 26 barres, SL ssb avec < 52 barres,
SL fixed LONG/SHORT, SL du mauvais côté du prix.

---

## 🚀 Nouvelles fonctionnalités

### 9. Dashboard web des signaux Ichimoku
**Priorité :** ⭐ Future

Interface web affichant les signaux du pipeline en temps réel :
- TOP 3 actifs avec SL/TP calculés
- Statut Chikou H4/D1/W1
- Historique des trades simulés

---

### 10. Alertes Telegram/Discord pour les signaux
**Priorité :** ⭐ Future

Notification automatique quand un signal LONG passe tous les filtres
sur un des actifs du TOP 3.

---

*Dernière mise à jour : 5 juillet 2026*
