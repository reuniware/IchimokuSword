# Guide d'utilisation — Swing_SR Live Trading Bot

> **Script :** `strat_compare/swing_sr_bot.py`  
> **Stratégie :** Rebonds sur supports/résistances horizontaux (swing highs/lows)  
> **Broker :** Tous les brokers MetaTrader 5 (quel que soit le serveur)  
> ⚠️ **Mis à jour le 05/07/2026** — Résultats corrigés après audit (look-ahead bias). Voir [AUDIT.md](AUDIT.md).

---

## 1. Prérequis

- **MetaTrader 5** installé et connecté à un compte (démo ou réel)
- **Python 3.9+** avec les packages :
  ```bash
  pip install MetaTrader5 pandas numpy
  ```
- Un fichier `.env` à la racine du projet contenant les identifiants MT5 :
  ```
  MT5_LOGIN=12345678
  MT5_PASSWORD=votre_mdp
  MT5_SERVER=ICMarkets-Demo
  ```

---

## 2. Actifs conseillés

> ⚠️ Les résultats ci-dessous sont **corrigés** (post-audit du 05/07/2026). Les performances réelles sont modestes.

Basé sur les résultats du backtest corrigé (01/01 → 03/07/2026) :

| Actif | TF | Win Rate | ROI 6 mois | Sharpe | MaxDD | Priorité |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GBPUSD** | H4 | 70.6% | +2.4% | 1.56 | -1.3% | 🥇 |
| **XAUUSD** | H4 | 66.7% | +3.6% | 0.85 | -5.3% | 🥈 |
| **EURUSD** | H4 | 64.3% | +1.3% | 0.92 | -1.8% | 🥉 |

> **Recommandation :** H4 est préférable à H1 (moins de bruit). GBPUSD H4 est le plus fiable (MaxDD le plus bas).  
> **Rentabilité réelle :** ~2-4% sur 6 mois — ne pas s'attendre à des gains explosifs.  
> **À éviter :** H1 sur XAUUSD et EURUSD (pertes), D1 (trop peu de signaux).

---

## 3. Mode Dry-Run (simulation sans risque)

Le mode `--dry-run` exécute TOUTE la logique de trading **sans envoyer d'ordres réels** à MT5. Idéal pour :

- Vérifier que la connexion MT5 fonctionne
- Observer les signaux détectés en temps réel
- Valider les paramètres avant de passer en réel

### Commandes

```bash
# Dry-run avec les 3 actifs par défaut (EURUSD, GBPUSD, XAUUSD) en H1
python strat_compare/swing_sr_bot.py --dry-run

# Dry-run sur un seul actif
python strat_compare/swing_sr_bot.py --dry-run --symbols EURUSD

# Dry-run en H4
python strat_compare/swing_sr_bot.py --dry-run --tf H4

# Dry-run avec scan toutes les 30 secondes (au lieu de 60)
python strat_compare/swing_sr_bot.py --dry-run --interval 30
```

### Exemple de sortie dry-run

```
2026-07-05 14:02:15 [INFO] MT5 connecte | Broker: ICMarkets | Login: 12345 | Balance: 10000.00 USD
2026-07-05 14:02:15 [INFO] ======================================================================
  Swing_SR Bot DEMARRE | Mode: DRY-RUN | 2026-07-05 14:02 UTC
  Symboles: EURUSD, GBPUSD, XAUUSD | Timeframe: H1
  Swing window: 20 | Proximity: 0.8 ATR | SL: 1.5 ATR | TP: 2.0 ATR
  Risque: 2.0% | Max positions: 3 | Magic: 250706
  Intervalle: 60s
======================================================================
2026-07-05 14:02:16 [INFO]   >> GBPUSD LONG | Level=1.26100(support) | Entry=1.26150 | SL=1.26020 | TP=1.26290 | ATR=0.00085
2026-07-05 14:02:16 [INFO] [DRY-RUN] GBPUSD LONG | Lots=1.23 | Entry=1.26155 | SL=1.26020(0.11%) | TP=1.26290
```

> **Note :** `[DRY-RUN]` devant chaque ordre indique que rien n'est envoyé à MT5. Les lots, SL, TP affichés sont ceux qui **seraient** utilisés en mode réel.

---

## 4. Mode Réel (trading live)

⚠️ **ATTENTION** — Ce mode envoie de VRAIS ordres sur votre compte MT5.  
Commencez toujours par un compte **démo** et validez avec `--dry-run` d'abord.

### Commandes

```bash
# Mode réel avec les paramètres par défaut (3 actifs, H1, risque 2%)
python strat_compare/swing_sr_bot.py

# Mode réel avec risque réduit à 1%
python strat_compare/swing_sr_bot.py --risk 1.0

# Mode réel sur EURUSD uniquement, H4, risque 1.5%
python strat_compare/swing_sr_bot.py --symbols EURUSD --tf H4 --risk 1.5

# Mode réel avec max 2 positions simultanées
python strat_compare/swing_sr_bot.py --max-positions 2

# Mode réel en H1 avec scan toutes les 120 secondes
python strat_compare/swing_sr_bot.py --interval 120
```

### Paramètres recommandés par profil

| Profil | Commande | Risque | Max pos | Actifs |
|:---|:---|:---:|:---:|:---|
| **Prudent** | `--risk 1.0 --max-positions 1 --symbols EURUSD` | 1% | 1 | EURUSD |
| **Standard** | `--risk 2.0 --max-positions 3` (défaut) | 2% | 3 | EURUSD, GBPUSD, XAUUSD |
| **Agressif** | `--risk 3.0 --max-positions 5 --symbols EURUSD,GBPUSD,XAUUSD` | 3% | 5 | 3 actifs |

### Comportement en live

1. **Démarrage** : le bot se connecte à MT5 et affiche le broker, login, balance
2. **Scan** : toutes les 60s (configurable), il récupère les 300 dernières bougies H1
3. **Détection** : cherche un swing high/low récent et vérifie si le prix est proche
4. **Entrée** : si signal + confirmation bougie → ordre market avec SL et TP
5. **Sortie** : SL touché, TP touché, ou signal opposé
6. **FTMO** : si la perte du jour atteint $485 (marge 3% vs $500) → blocage total jusqu'au lendemain
7. **Arrêt** : `Ctrl+C` pour arrêter proprement

---

## 5. Paramètres CLI complets

| Flag | Défaut | Description |
|:---|:---|:---|
| `--dry-run` | off | Simulation sans ordres réels |
| `--symbols` | EURUSD,GBPUSD,XAUUSD | Actifs séparés par des virgules |
| `--tf` | H1 | Timeframe (M1, M5, M15, M30, H1, H4, D1, W1) |
| `--risk` | 2.0 | % du capital risqué par trade |
| `--max-positions` | 3 | Nombre max de positions simultanées |
| `--interval` | 60 | Secondes entre chaque scan |
| `--swing-window` | 20 | Fenêtre de détection des swing points (±N barres) |
| `--proximity` | 0.8 | Distance max au S/R en multiple d'ATR |
| `--sl-atr` | 1.5 | Stop-loss en multiple d'ATR |
| `--tp-atr` | 2.0 | Take-profit en multiple d'ATR |
| `--magic` | 250706 | Magic number MT5 (identifie les ordres du bot) |

---

## 6. Sécurité FTMO intégrée

Le bot applique automatiquement les règles FTMO :

| Règle | Implémentation |
|:---|:---|
| **Perte quotidienne max $485** | P&L suivi via balance. Si -$485 atteint → blocage jusqu'au jour suivant |
| **Risque 2% par trade** | Lot size calculé à partir de la distance SL (pas de risque fixe arbitraire) |
| **Levier 1:30** | Le `calculate_lot_size` respecte la limite de levier |
| **Anti-overtrading** | Cooldown 5 barres entre deux entrées sur le même symbole |
| **Anti-doublons** | Ignore les signaux identiques consécutifs |

---

## 7. Surveillance & Logs

Le bot affiche en continu :

```
2026-07-05 14:02:15 [INFO] MT5 connecte | Broker: ICMarkets | Login: 12345 | Balance: 10000.00 USD
2026-07-05 14:02:16 [INFO]   >> EURUSD LONG | Level=1.07500(support) | Entry=1.07530 | SL=1.07450 | TP=1.07650
2026-07-05 14:02:17 [INFO] #1 EURUSD LONG | Ticket=12345678 | Lots=1.50 | Entry=1.07535 | SL=1.07450(0.08%) | TP=1.07650
2026-07-05 15:35:22 [INFO] #2 XAUUSD SHORT | Ticket=12345679 | Lots=0.80 | Entry=2645.20 | SL=2650.50(0.20%) | TP=2635.00
2026-07-05 18:10:05 [WARNING] FTMO: LIMITE QUOTIDIENNE ATTEINTE (-$487/$485) — plus aucun trade aujourd'hui
```

**Légende des logs :**
- `[INFO]` — opération normale (connexion, signal, ordre)
- `[WARNING]` — avertissement (limite FTMO atteinte, spread élevé)
- `[ERROR]` — erreur (ordre rejeté, déconnexion)
- `[DEBUG]` — information détaillée (cooldown, signal ignoré)

---

## 8. Dépannage

| Problème | Solution |
|:---|:---|
| `Echec mt5.initialize()` | Vérifier que MT5 est ouvert et connecté |
| `Impossible d'obtenir les infos du compte` | Vérifier login/password/server dans `.env` |
| `PAS DE DONNEES (copy_rates_from_pos)` | Le symbole n'est pas disponible chez ce broker → utiliser un autre symbole |
| `ordre echoue [retcode=...]` | Vérifier que le trading automatique est activé dans MT5 (Outils → Options → Expert Advisors) |
| `spread > max — trade ignore` | Normal en période de news — le bot se protège |
| Le bot ne détecte aucun signal | Vérifier qu'il y a assez d'historique (>300 barres). Réduire `--swing-window` ou `--proximity` |

---

## 9. Checklist avant de passer en réel

- [ ] MT5 ouvert et connecté à un compte **démo**
- [ ] `.env` correctement configuré
- [ ] Trading automatique **activé** dans MT5 (Outils → Options → Expert Advisors → Autoriser le trading automatique)
- [ ] `--dry-run` testé avec succès (signaux cohérents, pas d'erreurs)
- [ ] Capital suffisant pour la taille de lot (minimum ~$500 pour 0.01 lot forex)
- [ ] Comprendre que les performances passées ne garantissent pas les résultats futurs
