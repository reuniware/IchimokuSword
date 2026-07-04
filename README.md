# ⚔️ IchimokuSword

**Scanner Ichimoku Kinko Hyo pour MetaTrader 5** — Analyse les 5 éléments de l'Ichimoku (Tenkan, Kijun, Senkou A/B, Chikou) sur tous les actifs disponibles avec détection avancée : SSB plates historiques, 3 règles d'or, twist, Lagging confirmation, rejets, lignes plates, **indice de confiance**, **backtesting** et **pipeline mécanique multi-timeframe**.

---

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Analyse Ichimoku complète](#-analyse-ichimoku-complète)
- [Indice de confiance](#-indice-de-confiance)
- [Backtesting](#-backtesting)
- [Pipeline Mécanique Cloud+Chikou](#-pipeline-mécanique-cloudchikou)
- [Recommandation de trading](#-recommandation-de-trading)
- [SSB plates historiques](#-ssb-plates-historiques)
- [Les 3 règles d'or (Karen Péloille)](#-les-3-règles-dor-karen-péloille)
- [Twist (croisement Senkou A/B)](#-twist-croisement-senkou-ab)
- [Confirmation Lagging Span](#-confirmation-lagging-span)
- [Lignes plates (passées / futures)](#-lignes-plates-passées--futures)
- [Détection des rejets](#-détection-des-rejets)
- [Scoring et recommandation](#-scoring-et-recommandation)
- [Téléchargement historique](#-téléchargement-historique)
- [Structure du projet](#-structure-du-projet)
- [Configuration](#-configuration)
- [Résultats du Backtest](#-résultats-du-backtest)

---

## 🚀 Fonctionnalités

- **Scan complet** de tous les symboles MT5 (Forex, Indices, Métaux, Crypto, Matières premières)
- **5 éléments Ichimoku** : Tenkan Sen, Kijun Sen, Senkou Span A, Senkou Span B, Chikou Span
- **Analyse du nuage Senkou (Kumo)** : position (au-dessus/dans/en-dessous), couleur (Vert/Rouge)
- **TK Cross** : croisement Tenkan/Kijun haussier ou baissier
- **Chikou Span** : alignement haussier/baissier
- **SSB plates historiques** : détection des niveaux SSB horizontaux (supports/résistances)
- **3 règles d'or** : méthode Karen Péloille — nuage + Chikou + TK
- **Twist** : changement de couleur du nuage (retournement potentiel)
- **Lagging confirmation** : Chikou franchit nuage + Kijun
- **Lignes plates** : Kijun/Tenkan/Chikou horizontaux, nuage futur fin
- **Rejets Kijun** : rebonds avec mèches
- **Indice de confiance** : score 0-100 avec label (FAIBLE -> ELEVÉE) basé sur 6 sous-scores
- **Backtesting scoring** : validation du scoring Ichimoku sur historique (D1 et H4) — 44k à 120k signaux
- **Backtesting mécanique** : pipeline Cloud+Chikou+MTF purement mécanique — 1 676 trades filtrés
- **Split Longs/Shorts** : analyse séparée des performances par direction
- **Trade plan** : niveaux d'entrée, stop, TP, RR et position sizing
- **Pénalité SHORT** : score réduit de 20% basé sur les résultats du backtest
- **Scoring intelligent** : classement des actifs (jusqu'à ~170 pts)
- **Multi-timeframes** : H1, H4, D1, W1 simultanément
- **Mode watch** : surveillance continue
- **Téléchargement historique** en JSON

---

## 📦 Installation

```bash
git clone https://github.com/reuniware/IchimokuSword.git
cd IchimokuSword
pip install -r requirements.txt
cp .env.example .env
```

### Fichier `.env` requis

```env
MT5_PATH=C:/Program Files/FTMO Global Markets MT5 Terminal/terminal64.exe
# MT5_LOGIN=123456
# MT5_PASSWORD=monmotdepasse
# MT5_SERVER=FTMO-Demo
```

### Dépendances

- `MetaTrader5` — API de connexion à MT5
- `numpy` — calculs mathématiques
- `pandas` — optionnel, pour l'export

---

## 🎯 Utilisation

### Scan unique

```bash
python main.py snapshot
python main.py snapshot --timeframe H1,H4,D1 --threshold 0.5
python main.py snapshot --symbols EURUSD,GBPUSD,XAUUSD --detail
```

### Mode watch

```bash
python main.py watch --timeframe D1 --threshold 1.0
```

### Recommandation de trading

```bash
python recommend_trade.py
```

Affiche le TOP 15 des actifs avec scoring complet, indice de confiance, verdict backtest, trade plan (stop/TP/RR) et sizing.

### Backtesting

```bash
# Backtest du scoring Ichimoku
python backtest.py                          # D1 tous les actifs
python backtest.py --timeframe H4           # H4
python backtest.py --symbols EURUSD         # Un seul actif
python backtest.py --max-bars 500           # Limiter l'historique

# Backtest mécanique Cloud+Chikou (+ MTF)
python backtest_cloud_cross.py              # D1, sans MTF
python backtest_cloud_cross.py --timeframe H4 --mtf     # H4 + TP D1/W1 + filtre Chikou MTF
python backtest_cloud_cross.py --tp-min-distance 0.5    # TP min 0.5%
```

### Infos compte

```bash
python main.py info
```

### Téléchargement historique

```bash
python main.py download XAUUSD --tf M3 --start 2026-06-20 --end 2026-06-27
```

---

## 🔬 Analyse Ichimoku complète

| Élément | Période | Formule | Rôle |
|---------|:-------:|---------|------|
| **Tenkan Sen** | 9 | (HH9 + LL9) / 2 | Tendance court terme |
| **Kijun Sen** | 26 | (HH26 + LL26) / 2 | Tendance moyen terme |
| **Senkou Span A** | 26 | (Tenkan + Kijun) / 2 | Limite du nuage |
| **Senkou Span B** | 52 | (HH52 + LL52) / 2 | Limite du nuage |
| **Chikou Span** | 26 | Close actuel décalé -26 | Confirmation |

### Nuage (Kumo)

- **Au-dessus** -> haussier
- **En-dessous** -> baissier
- **Dans** -> indécision
- **Vert** (A > B) -> support haussier
- **Rouge** (B > A) -> résistance baissière

### TK Cross

- **TK haussier** : Tenkan passe au-dessus du Kijun -> achat
- **TK baissier** : Tenkan passe en-dessous du Kijun -> vente

### Chikou

- **Aligné haussier** : Chikou > prix 26p ET prix > Kijun
- **Chikou > P26** : modéré
- **Chikou < P26** : baissier

---

## 🏆 Indice de confiance

Système de scoring multi-TF qui évalue la **fiabilité** du signal Ichimoku sur une échelle de 0 à 100.

### Composants (recommend_trade.py)

| Critère | Pts max | Description |
|:-------:|:-------:|-------------|
| **Alignment TF** | 30 | Cohérence directionnelle sur H1/H4/D1/W1 |
| **Qualité Kumo** | 20 | Position + couleur du nuage |
| **3 Règles d'or** | 20 | Validation des 3 règles |
| **Chikou** | 10 | Alignement Chikou sur les TFs |
| **Support SSB** | 10 | Présence de supports SSB proches |
| **Stabilité Kijun** | 10 | Kijun qui bouge = tendance claire |

| Score | Label | Interprétation |
|:-----:|:-----:|:--------------|
| 80-100 | **ÉLEVÉE** | Signal fiable, edge backtesté |
| 60-79 | **MOYENNE** | Signal modéré |
| 40-59 | **PRUDENCE** | Signaux mitigés |
| 0-39 | **FAIBLE** | Ne pas trader |

### Composants (display.py — single TF)

| Critère | Pts max |
|:-------:|:-------:|
| Kumo position | 25 |
| Chikou alignement | 20 |
| 3 Règles d'or | 25 |
| Stabilité Kijun | 15 |
| Lagging confirmation | 15 |

---

## 📊 Backtesting

### Backtest du scoring (`backtest.py`)

Valide le scoring Ichimoku sur l'historique réel.

**Méthodologie :**
1. Pour chaque barre passée, calcule le score Ichimoku **comme si on y était**
2. Regarde ce qui s'est passé N barres plus tard
3. Trade gagnant si la direction prédite (above_kijun) correspond au mouvement réel
4. Agrège par bracket de score et niveau de confiance

### Backtest mécanique (`backtest_cloud_cross.py`)

Valide des critères purement mécaniques (sans scoring) :

```
ENTRÉE LONG (H4) :
  1. Cloud breakout frais : 2 barres au-dessus du nuage, la 3e pas
  2. Chikou H4 > Tenkan/Kijun/SSB/Prix/Cloud à 26p H4
  3. Chikou D1 > Tenkan/Kijun/SSB à 26p D1
  4. Chikou W1 > Tenkan/Kijun/SSB à 26p W1
  -> TP = 1er niveau D1/W1 bloquant > 0.3%
```

63% des signaux sont filtrés par les vérifications Chikou D1/W1.

---

## 🏗️ Pipeline Mécanique Cloud+Chikou

Le pipeline le plus efficace identifié par le backtesting :

| Étape | Condition | Timeframe |
|:-----:|:----------|:---------:|
| **1** | Cloud breakout frais | H4 |
| **2** | Chikou > Tenkan/Kijun/SSB/Prix/Cloud à 26p | H4 |
| **3** | Chikou > Tenkan/Kijun/SSB à 26p | D1 |
| **4** | Chikou > Tenkan/Kijun/SSB à 26p | W1 |
| **TP** | Niveau bloquant D1/W1 le plus proche | D1+W1 |

**Chaque timeframe valide sa PROPRE Chikou contre ses PROPRES niveaux** — pas de comparaison cross-TF qui serait incohérente (les niveaux D1 d'il y a 26 jours n'ont pas d'échelle commune avec le close H4 actuel).

---

## 🎯 Recommandation de trading

```bash
python recommend_trade.py
```

### Scoring complet (jusqu'à ~170 pts)

| Critère | Pts max | Description |
|---------|:-------:|-------------|
| **Proximité Kijun** | 40 | Plus proche = meilleur point d'entrée |
| **Direction** | 15 | Consistance sur 4 TF |
| **Nuage Senkou** | 36 | Position et couleur |
| **TK Cross** | 44 | Croisement haussier/baissier |
| **Chikou** | 32 | Alignement haussier |
| **3 règles d'or** | 60 | 3/3 = 12 pts par TF |
| **Twist** | 36 | Changement de nuage actif |
| **Lagging** | 40 | Confirmation Chikou |
| **Lignes plates** | ± | Bonus si tendance, pénalité si range |
| **SSB plates** | ± | Résistance proche = pénalité, support = bonus |
| **Rejets** | ~20 | Rejets avec mèche |
| **Liquidité** | 5 | Majeur > indices > crosses |

### Nouveautés

| Fonctionnalité | Description |
|:---------------|:------------|
| **Indice de confiance** | Score 0-100 avec label et 6 sous-scores |
| **Backtest estimate** | Win rate estimé depuis les données du backtest H4 |
| **Verdict** | TRADE / SKIP / PRUDENCE basé sur score + confiance + direction |
| **Trade plan** | Niveaux d'entrée, stop, TP et ratio RR calculés depuis les lignes Ichimoku |
| **Position sizing** | Taille de position pour 1% risque sur compte 10k |
| **Pénalité SHORT** | Score réduit de 20% + verdict SKIP |

### Exemple de sortie

```text
  >>> RECOMMANDATION #1 : AUDCAD en LONG
  - Score 169.8/100 — meilleur score du scan
  - Confiance: 83/ELEVEE | Alignment TF=30/30, Kumo=18/20, ...
  - Backtest: ~58% win rate estime | Verdict: TRADE
  - Trade plan: Entree=0.98522 Stop=0.98096 TP=0.99100 RR=1.35
  - Sizing (10k, 1% risque): 2.34 unites, notionnel=23054.5

  Approche descendante:
    Biais D1: HAUSSIER (3R:3/3)
    Confirmation H4: 2/3
    Execution H1: 2/3
```

---

## 📐 SSB plates historiques

La **Senkou Span B** (SSB) est la moyenne des HH52/LL52. Quand elle reste horizontale pendant plusieurs bougies consécutives, elle forme un **niveau technique** qui agira plus tard comme support ou résistance.

### Détection

- Parcourt l'historique des 100 dernières bougies
- Identifie les segments où la SSB varie de moins de **0.02%**
- Un niveau est validé à partir de **3 bougies** plates consécutives
- Classement par force (nombre de bougies plates)

### Affichage dans le scan

```text
Symbole    TF   ... Lignes
---------  ---- ... -------------------
AUDCAD     H4   ... SSBx3 R:0.985516 S:0.984855
```

---

## 🏆 Les 3 règles d'or (Karen Péloille)

| Règle | Condition | Détail |
|:-----:|-----------|--------|
| **1** | Prix du bon côté du nuage | Au-dessus (haussier) ou en-dessous (baissier) |
| **2** | Chikou aligné | Chikou > prix 26p ET prix > Kijun |
| **3** | TK Cross dans la direction | Croisement Tenkan/Kijun haussier ou baissier |

---

## 🔄 Twist (croisement Senkou A/B)

- **ROUGE -> VERT** : twist haussier (le nuage passe en support)
- **VERT -> ROUGE** : twist baissier (le nuage passe en résistance)

---

## ✅ Confirmation Lagging Span

Le Chikou doit franchir le nuage ET la Kijun pour confirmer la puissance du mouvement.

---

## 📏 Lignes plates (passées / futures)

| Type | Élément | Signification |
|------|---------|---------------|
| **Passée** | Chikou (décalé -26) | Range passé |
| **Future** | Senkou A/B (projeté +26) | Consolidation à venir |
| **Actuelle** | Kijun horizontal | Range en cours |
| **Nuage fin** | < 0.1% épaisseur | Support/résistance faible |

---

## 📁 Structure du projet

```text
IchimokuSword/
├── src/
│   ├── __init__.py
│   ├── config.py            # Configuration (timeframes, .env)
│   ├── mt5_connector.py     # Connexion MT5
│   ├── ichimoku.py          # Calculs Ichimoku complets (5 éléments + SSB plates
│   │                        #   + 3 règles + twist + lagging + confiance)
│   ├── scanner.py           # Scan de tous les symboles MT5
│   └── display.py           # Affichage console coloré (incl. confiance)
├── main.py                  # CLI (snapshot, watch, info, download)
├── recommend_trade.py       # Scoring, confiance, backtest estimate, trade plan
├── backtest.py              # Backtesting scoring D1/H4 (44k-120k signaux)
├── backtest_cloud_cross.py  # Backtesting mécanique Cloud+Chikou+MTF (1 676 trades)
├── .env.example
├── requirements.txt
└── README.md
```

---

## ⚙️ Configuration

### Timeframes

| Alias | Constante MT5 |
|-------|:-------------:|
| M1 | 1 |
| H1 | 16385 |
| H4 | 16388 |
| D1 | 16408 |
| W1 | 32769 |

---

## 📊 Résultats du Backtest

### Tableau comparatif complet

| # | Stratégie | TF | Trades | LONG Win | SHORT Win | Filtrage |
|:-:|:----------|:--:|:------:|:--------:|:---------:|:--------:|
| 1 | **Scoring 80-101** | H4 | 40 000+ | **57.8%** (120H) | N/A | Score+Confiance |
| 2 | **Cloud+Chikou+MTF** | H4 | 1 259 L | **54.4%** (30H) | 49.2% | 63% rejetés |
| 3 | Scoring 80-101 | D1 | 4 021 | **53.2%** (20j) | N/A | Score+Confiance |
| 4 | Cloud+Chikou seul | H4 | 2 464 L | **53.0%** (30H) | 46.4% | Aucun |
| 5 | Cloud+Chikou seul | H4 | 2 464 L | **56.2%** (120H) | 41.0% | Aucun |

### Scoring D1 — 44,664 signaux (25 symboles)

| Bracket | Win 20j | Trades | Verdict |
|:-------:|:-------:|:------:|:-------:|
| 0-20 | 43.8% | 2,652 | A éviter |
| 20-40 | 49.8% | 11,923 | Neutre |
| 40-60 | 47.8% | 14,623 | Sous-performe |
| 60-80 | 48.3% | 11,445 | Stable |
| **80-101** | **53.2%** | 4,021 | Edge +3.2% |

### Scoring H4 — 120,675 signaux (25 symboles)

| Bracket | Win 120H | Verdict |
|:-------:|:--------:|:-------:|
| **80-101** | **57.8%** | Edge +7.8% |
| 0-20 | ~44% | A éviter |

### Split LONGS vs SHORTS (H4)

| Bracket | Longs WR | Shorts WR | Diff |
|:-------:|:--------:|:---------:|:----:|
| 80-101 | **54.6%** | N/A | — |
| 0-20 | 68.5%* | 46.8% | +21.7% |

*Petit échantillon (184 trades)

### Cloud+Chikou+MTF — 1,676 trades filtrés (25 symboles)

| Direction | Trades | Win 30H | Win 120H |
|:---------:|:------:|:-------:|:--------:|
| **LONG** | 1 259 | **54.4%** | **56.2%** |
| SHORT | 417 | 49.2% | 41.0% |
| **Skippés** | 2 862 | — | 63% filtrés |

### TP D1/W1 (sur trades filtrés)

| Direction | Trades TP | Win 30H | TP touché |
|:---------:|:---------:|:-------:|:---------:|
| LONG | 16 | **62.5%** | 100% |
| SHORT | 8 | **75.0%** | 75% |

### Conclusion

1. **H4 > D1** systématiquement : l'edge double (57.8% vs 53.2%)
2. **Longs uniquement** : les shorts perdent dans toutes les configurations
3. **Meilleur compromis** : pipeline Cloud+Chikou+MTF = 54.4% LONG sur 1 259 trades filtrés (~3/semaine)
4. **Scoring = scanner, Mécanique = trader** : le scoring capture plus d'opportunités, le pipeline mécanique est plus sélectif
5. **57% avec money management** suffit pour être rentable à long terme

---

## 📄 Licence

MIT
