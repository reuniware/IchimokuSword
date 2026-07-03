# ⚔️ IchimokuSword

**Scanner Ichimoku Kinko Hyo pour MetaTrader 5** — Analyse les 5 éléments de l'Ichimoku (Tenkan, Kijun, Senkou A/B, Chikou) sur tous les actifs disponibles avec détection avancée : SSB plates historiques, 3 règles d'or, twist, Lagging confirmation, rejets, lignes plates.

---

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Analyse Ichimoku complète](#-analyse-ichimoku-complète)
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

- **Au-dessus** → haussier
- **En-dessous** → baissier
- **Dans** → indécision
- **Vert** (A > B) → support haussier
- **Rouge** (B > A) → résistance baissière

### TK Cross

- **TK haussier** : Tenkan passe au-dessus du Kijun → achat
- **TK baissier** : Tenkan passe en-dessous du Kijun → vente

### Chikou

- **Aligné haussier** : Chikou > prix 26p ET prix > Kijun
- **Chikou > P26** : modéré
- **Chikou < P26** : baissier

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

- `SSBx3` = 3 niveaux SSB plats détectés
- `R:0.985516` = résistance la plus proche
- `S:0.984855` = support le plus proche

### Détail complet

```text
  SSB PLATES HISTORIQUES (supports/resistances)
  10 niveaux detectes
  Resistance la plus proche : 0.985516
  Support le plus proche    : 0.984855

  Niveau         Bars   Dist%    Position     Age
  ------------------------------------------------
  0.985516       28     0.048%   v AU-DESSUS   6
  0.984537       12     0.051%   ^ EN-DESSOUS  49
  0.984855       10     0.019%   ^ EN-DESSOUS  88
```

---

## 🏆 Les 3 règles d'or (Karen Péloille)

Méthode structurée pour valider un signal Ichimoku :

| Règle | Condition | Détail |
|:-----:|-----------|--------|
| **1** | Prix du bon côté du nuage | Au-dessus (haussier) ou en-dessous (baissier) |
| **2** | Chikou aligné | Chikou > prix 26p ET prix > Kijun |
| **3** | TK Cross dans la direction | Croisement Tenkan/Kijun haussier ou baissier |

- **3/3** → signal fort ✅
- **2/3** → signal modéré ⚠️
- **0-1/3** → pas de signal ❌

---

## 🔄 Twist (croisement Senkou A/B)

Le **twist** est le moment où Senkou A croise Senkou B, faisant changer la couleur du nuage. C'est une zone de **retournement potentiel**.

- **ROUGE → VERT** : twist haussier (le nuage passe en support)
- **VERT → ROUGE** : twist baissier (le nuage passe en résistance)
- Détection du nombre de bougies depuis le dernier twist

---

## ✅ Confirmation Lagging Span

Le Chikou (close actuel projeté 26 périodes en arrière) doit franchir **le nuage ET la Kijun** pour confirmer la puissance du mouvement.

- **Chikou > K26** : au-dessus de la Kijun passée
- **Chikou > nuage passé** : franchissement du nuage
- **Franchit Kijun** : cassure récente de la Kijun
- **Franchit nuage** : cassure récente du nuage
- **Confirmé** : les 3 conditions réunies

---

## 📏 Lignes plates (passées / futures)

| Type | Élément | Signification |
|------|---------|---------------|
| **📜 Passée** | Chikou (décalé -26) | Range passé |
| **🔮 Future** | Senkou A/B (projeté +26) | Consolidation à venir |
| **📏 Actuelle** | Kijun horizontal | Range en cours |
| **📏 Actuelle** | Tenkan horizontal | Consolidation court terme |
| **📐 Nuage fin** | < 0.1% épaisseur | Support/résistance faible |

---

## ⚡ Détection des rejets

Le prix s'approche du Kijun puis rebondit :

| Type | Description |
|------|-------------|
| **Rejet haussier** | Prix sous → au-dessus (support) |
| **Rejet haussier (mèche)** | Mèche basse confirmant |
| **Rejet baissier** | Prix au-dessus → en-dessous (résistance) |
| **Rejet baissier (mèche)** | Mèche haute confirmant |
| **Éloignement** | Prix s'éloigne du Kijun |

---

## 🏆 Scoring et recommandation

Classement complet des actifs par qualité de signal :

```bash
python recommend_trade.py
```

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

### Exemple de sortie

```text
  >>> RECOMMANDATION #1 : AUDCAD en LONG
  - Score 169.8/100 — meilleur score du scan
  - 3 regles: 16 pts  |  Twist: 18 pts  |  Lagging: 30 pts
  - SSB plates: 3 niveaux (R:0.9855 S:0.9849)

  Approche descendante:
    Biais D1: HAUSSIER (3R:3/3)
    Confirmation H4: 2/3
    Execution H1: 2/3
```

---

## 📁 Structure du projet

```
IchimokuSword/
├── src/
│   ├── __init__.py
│   ├── config.py            # Configuration (timeframes, .env)
│   ├── mt5_connector.py     # Connexion MT5
│   ├── ichimoku.py          # Calculs Ichimoku complets (5 éléments + SSB plates + 3 règles + twist + lagging)
│   ├── scanner.py           # Scan de tous les symboles MT5
│   └── display.py           # Affichage console coloré
├── main.py                  # CLI (snapshot, watch, info, download)
├── recommend_trade.py       # Scoring et recommandation
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
| M5 | 5 |
| M15 | 15 |
| M30 | 30 |
| H1 | 16385 |
| H4 | 16388 |
| D1 | 16408 |
| W1 | 32769 |

### Variables d'environnement

| Variable | Description |
|----------|-------------|
| `MT5_PATH` | Chemin vers terminal64.exe |
| `MT5_LOGIN` | Numéro de compte (optionnel) |
| `MT5_PASSWORD` | Mot de passe (optionnel) |
| `MT5_SERVER` | Serveur MT5 (optionnel) |
| `ICHIMOKU_WATCHLIST` | Symboles à surveiller (csv) |

---

## 📊 Exemple de sortie scan

```
Symbole    TF   Prix        Kijun       Dist%   Kumo         TK         Chikou         3R     SSB
---------  ---- ----------- ----------- ------- ------------ ---------- -------------- ------ ---------
EURUSD     D1   1.1442      1.1505      0.55%   EN-DESSOUS   K>TK       CHIKOU<P26     1/3
AUDCAD     H4   0.98522     0.98096     0.43%   AU-DESSUS    TK>K       ALIGNE HAUT    2/3    SSBx3 R:0.9855 S:0.9849
```

---

## 📄 Licence

MIT
