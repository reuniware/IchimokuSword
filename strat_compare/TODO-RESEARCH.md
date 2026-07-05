# TODO-RESEARCH — Stratégie DXY.cash → XAUUSD / XAGUSD H4

> **Date :** 05/07/2026  
> **Stratégie retenue :** DXY.cash H1 fort (>1.5σ) → H4 inverse  
> **Meilleur actif :** **XAGUSD (Argent)** — +25.7%, Sharpe +1.45  
> **Alternative :** XAUUSD (Or) — +9.2%, Sharpe +1.25  
> **Bots disponibles :**  
>   - `strat_compare/dxy_xau_bot.py` (XAUUSD, magic 260706)  
>   - `strat_compare/dxy_xag_bot.py` (XAGUSD 🥇, magic 270706)  
> **Guides :**  
>   - `strat_compare/GUIDE_DXY_BOT.md`  
>   - `strat_compare/GUIDE_XAG_BOT.md` 🆕

---

## 📋 Rappel des performances backtest

| Période | Trades | WR% | Ret% | Sharpe | MaxDD |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Jan-Jul 2026 (6 mois)** | 15-20 | 53-55% | **+6.8% à +9.2%** | **+1.21** | −4.5% |
| Juin 2026 seul | 4 | 25% | −2.47% | −1.82 | −3.8% |

> **XAGUSD est le meilleur actif** (+25.7%, Sharpe +1.45). XAUUSD est l'alternative (+9.2%, Sharpe +1.25).  
> Les 2 bots partagent le même code (symbole, magic number et spread max changent).  
> La stratégie est **rentable sur 6 mois** mais a des **mois perdants** (Juin −2.5% sur XAU).

---

## 🔧 Prérequis

- [ ] **MetaTrader 5** installé et connecté à un compte (demo ou réel)
- [ ] **Symbole DXY.cash** disponible chez le broker (vérifié : OK sur le broker actuel)
- [ ] **Symbole XAUUSD et/ou XAGUSD** disponible
- [ ] **Historique minimum** : 3 mois de DXY H1 + actif H4/M15 (pour warmup des indicateurs)
- [ ] **Fichier `.env`** configuré avec les credentials MT5 (login, password, server)
- [ ] **Dépendances Python** : `MetaTrader5`, `pandas`, `numpy`, `python-dotenv`
- [ ] **Capital minimum recommandé** : $10 000 (standard) ou $10 000 (FTMO)
- [ ] **Choix de l'actif** : XAGUSD recommandé (meilleure perf), XAUUSD possible (moins de drawdown)

---

## 🧪 Phase 1 — Dry-run (simulation)

> **Objectif :** Vérifier que le bot démarre, fetch les données, détecte les signaux sans erreur.

- [ ] **1.1** Choisir l'actif : **XAGUSD recommandé** (bot `dxy_xag_bot.py`) ou XAUUSD (`dxy_xau_bot.py`)
- [ ] **1.2** Lancer le bot en dry-run :
  ```bash
  cd strat_compare
  python dxy_xag_bot.py --dry-run          # XAGUSD (recommandé)
  # ou
  python dxy_xau_bot.py --dry-run          # XAUUSD (alternative)
  ```
- [ ] **1.3** Vérifier que les 4 sources de données sont fetchées sans erreur :
  - `DXY.cash H1` → signal
  - `DXY.cash H4` → filtre tendance
  - `XAGUSD/XAUUSD H4` → trading
  - `XAGUSD/XAUUSD M15` → corrélation
- [ ] **1.4** Vérifier qu'aucun `ERROR` n'apparaît dans les logs
- [ ] **1.5** Laisser tourner **24-48h** pour voir si un signal est détecté
- [ ] **1.6** Noter le nombre de signaux détectés et leur direction (LONG/SHORT)
- [ ] **1.7** Vérifier les valeurs de corrélation dans les logs (`Corr=-0.xxx`) — doit être < −0.3 pour un trade
- [ ] **1.8** Vérifier que le cooldown (2 barres H4 = 8h) est respecté
- [ ] **1.9** Vérifier que l'anti-doublon fonctionne (pas 2 signaux identiques consécutifs)
- [ ] **1.10** Si XAGUSD, vérifier que le spread max (0.08%) n'est pas dépassé en permanence

---

## 🎮 Phase 2 — Demo account (ordre réels, argent fictif)

> **Objectif :** Valider l'exécution des ordres, le position sizing, les SL/TP.

- [ ] **2.1** Ouvrir un compte **demo** MT5 avec $10 000
- [ ] **2.2** Lancer le bot en mode réel sur le compte demo :
  ```bash
  python dxy_xag_bot.py                     # XAGUSD (recommande)
  # ou
  python dxy_xau_bot.py                     # XAUUSD
  ```
- [ ] **2.3** Vérifier que le premier ordre est bien placé (checker dans MT5) :
  - Magic number = **270706** (XAG) ou **260706** (XAU)
  - SL et TP bien positionnés (1.5 ATR / 3.0 ATR)
  - Taille de lot correcte (2% de risque)
- [ ] **2.4** Vérifier que le SL/TP sont calculés depuis le **prix d'exécution réel** (tick), pas le close historique
- [ ] **2.5** Laisser tourner **1-2 semaines** (5-10 trades attendus)
- [ ] **2.6** Comparer les trades réels avec les attentes du backtest :
  - WR% proche de 50-55% ?
  - Avg win ~+2.5%, avg loss ~−1.8% ?
  - Profit factor > 1.0 ?
- [ ] **2.7** Vérifier que la limite FTMO quotidienne ($485) n'est jamais atteinte
- [ ] **2.8** Vérifier le fallback IOC→RETURN sur les ordres (log `IOC non supporte` ne doit pas apparaître en erreur)

---

## 💰 Phase 3 — Live (petit capital)

> **Objectif :** Valider avec de l'argent réel, risque minimal.

- [ ] **3.1** Alimenter un compte réel avec **$500 minimum**
- [ ] **3.2** Réduire le risque à **0.5% par trade** :
  ```bash
  python dxy_xau_bot.py --risk 0.5
  ```
- [ ] **3.3** Laisser tourner **1 mois** (3-5 trades attendus)
- [ ] **3.4** Vérifier que le slippage réel correspond aux hypothèses du backtest
- [ ] **3.5** Vérifier que le spread XAUUSD ne dépasse pas 0.05% pendant les sessions Londres/NY
- [ ] **3.6** Comparer PnL réel vs backtest sur la même période
- [ ] **3.7** Si résultats positifs, passer au risque 1% puis 2%

---

## 🏆 Phase 4 — FTMO Challenge (optionnel)

> **Objectif :** Passer le challenge FTMO avec cette stratégie.

- [ ] **4.1** Vérifier les règles FTMO actuelles (daily loss 5%, max loss 10%, profit target 10%)
- [ ] **4.2** Ajuster `daily_loss_limit` si nécessaire (actuellement $485 pour un compte $10k)
- [ ] **4.3** Le bot gère déjà :
  - ✅ Limite quotidienne avec equity (pas balance)
  - ✅ Réduction automatique du risque si marge FTMO restante faible
  - ✅ Blocage du trading si limite atteinte
- [ ] **4.4** Backtest FTMO déjà fait : +14.5% ROI, 1 jour perdu sur 6 mois → **viable**
- [ ] **4.5** Lancer le bot sur le compte challenge FTMO
- [ ] **4.6** Surveiller le `days_lost` — si >2-3 jours perdus, évaluer l'arrêt

---

## 📊 Monitoring continu

> À vérifier **chaque semaine** pendant le live :

- [ ] Nombre de trades vs attendu (~3/mois)
- [ ] Win rate (cible : 50-55%)
- [ ] Profit factor (cible : >1.3)
- [ ] Max drawdown (cible : <10%)
- [ ] Jours FTMO perdus (cible : 0-1/mois)
- [ ] Écarts slippage réel vs backtest
- [ ] Périodes sans signal >2 semaines → vérifier que DXY.cash est toujours dispo

---

## ⚠️ Points de vigilance

| Risque | Probabilité | Mitigation |
|:---|:---|:---|
| DXY.cash non disponible chez le broker | Faible | Vérifié OK, fallback: tester `USDOLLAR` ou `DXY` |
| Mois perdant (−2.5% comme Juin) | 1 mois sur 6 | Accepter la variance, ne pas suroptimiser |
| Corrélation XAU/DXY qui casse (régime « safe haven ») | Rare | Le filtre `rolling_corr < -0.3` bloque automatiquement |
| MT5 déconnexion | Occasionnel | Reconnexion automatique dans le bot |
| 3-4 trades/mois = résultats bruyants | Élevé | Accepter, c'est inhérent au H4 |
| FTMO daily loss hit | Possible | Le bot bloque le trading jusqu'au lendemain |

---

## 📁 Fichiers de référence

| Fichier | Utilité |
|:---|:---|
| `strat_compare/dxy_xag_bot.py` | **Bot live XAGUSD** (recommande, +25.7%) |
| `strat_compare/dxy_xau_bot.py` | Bot live XAUUSD (alternative, +9.2%) |
| `strat_compare/GUIDE_XAG_BOT.md` | Guide complet du bot XAGUSD 🆕 |
| `strat_compare/GUIDE_DXY_BOT.md` | Guide complet du bot XAUUSD |
| `strat_compare/STRATEGIE_DXY.md` | Doc stratégie : analyse corrélation, algo, résultats |
| `strat_compare/ANALYSE_CORRELATION_DXY.md` | Analyse corrélation DXY vs 28+ actifs |
| `strat_compare/_dxy_xau_backtest.py` | Backtest multi-TF XAUUSD |
| `strat_compare/_corr_analysis.py` | Analyse de corrélation XAUUSD vs DXY |
| `strat_compare/RAPPORT_GLOBAL.md` | Synthèse toutes stratégies |
| `strat_compare/SPECS_STRATEGIES.md` | Spécifications techniques |
| `src/config.py` | `load_env()` pour credentials MT5 |
