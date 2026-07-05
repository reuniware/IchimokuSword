# Spécifications Techniques — Toutes les Stratégies

> **Objectif :** Document suffisamment détaillé pour qu'un bot ou une personne puisse réimplémenter chaque stratégie dans n'importe quel langage (Python, MQL5, Pine Script, etc.) sans lire le code source.

---

## Table des matières

1. [Stratégie 1 : RSI Mean Reversion](#s1-rsi)
2. [Stratégie 2 : Bollinger Bands Mean Reversion](#s2-bollinger)
3. [Stratégie 3 : MACD Crossover](#s3-macd)
4. [Stratégie 4 : Stochastic Oversold/Overbought](#s4-stochastic)
5. [Stratégie 5 : EMA Cross](#s5-ema)
6. [Stratégie 6 : Swing Support/Resistance](#s6-swing-sr)
7. [Stratégie 7 : Parabolic SAR Flip](#s7-psar)
8. [Stratégie 8 : Ichimoku Scalp (Single TF)](#s8-ichimoku-scalp)
9. [Stratégie 9 : Ichimoku MTF Scalp](#s9-ichimoku-mtf)
10. [Stratégie 10 : DXY → XAUUSD Correlation](#s10-dxy-xau)
11. [Indicateurs Communs](#indicateurs)
12. [Gestion des Coûts](#couts)

---

<a name="indicateurs"></a>

## Indicateurs Communs

Ces indicateurs sont utilisés par plusieurs stratégies. Implémentez-les une seule fois.

### ATR — Average True Range (Wilder)

```
Input:  high[], low[], close[], period=14
Output: atr[]

TR[i] = max(
    high[i] - low[i],
    |high[i] - close[i-1]|,
    |low[i]  - close[i-1]|
)

atr[0] = TR[0]  // seed
for i = 1 to N-1:
    atr[i] = atr[i-1] + (1/period) * (TR[i] - atr[i-1])
    // Équivalent à : atr[i] = WilderSmooth(TR, period)[i]
```

**Note :** Le lissage Wilder est un EMA avec α = 1/period (pas le α standard 2/(period+1)).

### RSI — Relative Strength Index (Wilder)

```
Input:  close[], period=14
Output: rsi[]

delta[i] = close[i] - close[i-1]
gain[i]  = max(delta[i], 0)
loss[i]  = max(-delta[i], 0)

avg_gain = WilderSmooth(gain, period)
avg_loss = WilderSmooth(loss, period)

rs[i] = avg_gain[i] / (avg_loss[i] + ε)   // ε = 1e-10 (évite division par 0)
rsi[i] = 100 - 100 / (1 + rs[i])
```

### EMA — Exponential Moving Average

```
Input:  series[], period
Output: ema[]

α = 2 / (period + 1)
ema[0] = series[0]  // seed
for i = 1 to N-1:
    ema[i] = α * series[i] + (1-α) * ema[i-1]
```

### MACD

```
Input:  close[], fast=12, slow=26, signal=9
Output: macd_line[], signal_line[], histogram[]

ema_fast  = EMA(close, fast)
ema_slow  = EMA(close, slow)
macd_line[i] = ema_fast[i] - ema_slow[i]
signal_line  = EMA(macd_line, signal)
histogram[i] = macd_line[i] - signal_line[i]
```

### Bollinger Bands

```
Input:  close[], period=20, std_mult=2.0
Output: middle[], upper[], lower[]

middle[i] = SMA(close, period)[i]           // moyenne simple
std[i]    = StdDev(close, period, ddof=0)[i] // écart-type population (N, pas N-1)
upper[i]  = middle[i] + std_mult * std[i]
lower[i]  = middle[i] - std_mult * std[i]
```

### Stochastic Oscillator

```
Input:  high[], low[], close[], k_period=14, smooth=3, d_period=3
Output: k_slow[], d_slow[]

// Fast %K
lowest[i]  = min(low[i-k_period+1 ... i])
highest[i] = max(high[i-k_period+1 ... i])
fast_k[i]  = 100 * (close[i] - lowest[i]) / (highest[i] - lowest[i] + ε)

// Slow %K = SMA du Fast %K
k_slow[i] = SMA(fast_k, smooth)[i]

// %D = SMA du Slow %K
d_slow[i] = SMA(k_slow, d_period)[i]
```

### Parabolic SAR

```
Input:  high[], low[], step=0.02, maximum=0.2
Output: sar[]

// Initialisation
trend[0] = +1               // 1 = uptrend, -1 = downtrend
sar[0]   = low[0]
ep[0]    = high[0]           // extreme point
af[0]    = step              // acceleration factor

for i = 1 to N-1:
    prev_sar   = sar[i-1]
    prev_ep    = ep[i-1]
    prev_af    = af[i-1]
    prev_trend = trend[i-1]

    // Calcul du nouveau SAR
    new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

    if prev_trend == +1:  // uptrend
        new_sar = min(new_sar, low[i-1])
        if i >= 2: new_sar = min(new_sar, low[i-2])

        if high[i] > prev_ep:
            new_ep = high[i]
            new_af = min(prev_af + step, maximum)
        else:
            new_ep = prev_ep
            new_af = prev_af

        // Reversal check
        if low[i] < new_sar:
            new_trend = -1
            new_sar = prev_ep    // SAR = dernier EP uptrend
            new_ep = low[i]
            new_af = step
        else:
            new_trend = +1

    else:  // downtrend
        new_sar = max(new_sar, high[i-1])
        if i >= 2: new_sar = max(new_sar, high[i-2])

        if low[i] < prev_ep:
            new_ep = low[i]
            new_af = min(prev_af + step, maximum)
        else:
            new_ep = prev_ep
            new_af = prev_af

        // Reversal check
        if high[i] > new_sar:
            new_trend = +1
            new_sar = prev_ep    // SAR = dernier EP downtrend
            new_ep = high[i]
            new_af = step
        else:
            new_trend = -1

    sar[i]   = new_sar
    ep[i]    = new_ep
    af[i]    = new_af
    trend[i] = new_trend
```

### Ichimoku Kinko Hyo

```
Input:  high[], low[], tenkan_p=9, kijun_p=26, senkou_b_p=52, displacement=26
Output: tenkan[], kijun[], senkou_a[], senkou_b[]

// Composants bruts
tenkan[i]    = (max(high[i-tenkan_p+1 ... i]) + min(low[i-tenkan_p+1 ... i])) / 2
kijun[i]     = (max(high[i-kijun_p+1 ... i])  + min(low[i-kijun_p+1 ... i]))  / 2
senkou_a_raw[i] = (tenkan[i] + kijun[i]) / 2
senkou_b_raw[i] = (max(high[i-senkou_b_p+1 ... i]) + min(low[i-senkou_b_p+1 ... i])) / 2

// Nuage "actif" = valeurs calculées il y a 26 barres, projetées à la barre courante
senkou_a[i] = senkou_a_raw[i - displacement]
senkou_b[i] = senkou_b_raw[i - displacement]

// Note : les 26 premières valeurs de senkou_a/b sont NaN (indéfinies)
```

---

<a name="s1-rsi"></a>

## Stratégie 1 : RSI Mean Reversion

**Type :** Mean reversion  
**TF recommandé :** H1, H4  
**Actifs :** Tous

### Concept

Le RSI identifie les zones de surachat/survente. Quand le RSI sort d'une zone extrême, on anticipe un retour à la moyenne.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `rsi_period` | 14 | Période du RSI |
| `oversold` | 30 | Seuil de survente |
| `overbought` | 70 | Seuil de surachat |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 2.0 | Take-profit en multiple d'ATR |
| `atr_period` | 14 | Période de l'ATR |

### Algorithme

```
Pour chaque barre i (après warmup de 30 barres):
    rsi_curr = RSI[i]
    rsi_prev = RSI[i-1]
    atr      = ATR[i]

    // Signal LONG : RSI sort de la zone survendue
    if rsi_prev <= oversold AND rsi_curr > oversold:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = close[i] + tp_atr * atr

    // Signal SHORT : RSI sort de la zone surachatée
    if rsi_prev >= overbought AND rsi_curr < overbought:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = close[i] - tp_atr * atr
```

### Anti-look-ahead

- RSI[i] est calculé avec les données jusqu'à la barre i (close[i] inclus)
- Le cross utilise `rsi_prev` (barre i-1) et `rsi_curr` (barre i) → pas de fuite

### Sorties

| Type | Condition |
|:---|:---|
| Stop-Loss | Prix touche sl_price |
| Take-Profit | Prix touche tp_price |
| Signal opposé | Un signal inverse apparaît (LONG → SHORT ou SHORT → LONG) |
| Fin de période | Clôture forcée |

### Résultats (moyenne H1+H4, EURUSD/GBPUSD/XAUUSD)

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −0.25 | 43.4% | −0.1% | 29 |

---

<a name="s2-bollinger"></a>

## Stratégie 2 : Bollinger Bands Mean Reversion

**Type :** Mean reversion  
**TF recommandé :** H4  
**Actifs :** Tous

### Concept

Quand le prix touche une bande de Bollinger, on anticipe un retour vers la moyenne mobile centrale.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `bb_period` | 20 | Période de la SMA et de l'écart-type |
| `bb_std` | 2.0 | Multiplicateur de l'écart-type |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 1.5 | Si > 0, TP = middle band ; si = 0, pas de TP |
| `atr_period` | 14 | Période de l'ATR |

### Algorithme

```
Pour chaque barre i (après warmup):
    middle[i], upper[i], lower[i] = Bollinger(close, bb_period, bb_std)
    atr = ATR[i]

    prev_close = close[i-1]
    prev_lower = lower[i-1]
    prev_upper = upper[i-1]

    // Signal LONG : close précédent ≤ bande inférieure
    if prev_close <= prev_lower:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = middle[i]    // retour à la moyenne

    // Signal SHORT : close précédent ≥ bande supérieure
    if prev_close >= prev_upper:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = middle[i]

    // Filtre anti-doublons
    if entry_signal[i] == entry_signal[i-1]:
        entry_signal[i] = None  // ignore les signaux consécutifs identiques
```

### Anti-look-ahead

- `prev_close`, `prev_lower`, `prev_upper` utilise `shift(1)` → barre i-1
- À la barre i, on regarde si la barre i-1 a touché la bande → pas de fuite

### Sorties

Identiques à RSI.

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −1.30 | 42.7% | −5.7% | 44 |

---

<a name="s3-macd"></a>

## Stratégie 3 : MACD Crossover

**Type :** Trend following  
**TF recommandé :** H4  
**Actifs :** Tous

### Concept

Le croisement de la ligne MACD au-dessus/en dessous de sa ligne de signal indique un changement de tendance.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `fast` | 12 | Période EMA rapide |
| `slow` | 26 | Période EMA lente |
| `signal` | 9 | Période ligne de signal |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 2.0 | Take-profit en multiple d'ATR |
| `atr_period` | 14 | Période ATR |

### Algorithme

```
Pour chaque barre i:
    macd, signal, hist = MACD(close, fast, slow, signal_period)
    atr = ATR[i]

    macd_prev  = macd[i-1]
    sig_prev   = signal[i-1]

    // LONG : MACD croise au-dessus de la ligne de signal
    if macd_prev <= sig_prev AND macd[i] > signal[i]:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = close[i] + tp_atr * atr

    // SHORT : MACD croise en dessous de la ligne de signal
    if macd_prev >= sig_prev AND macd[i] < signal[i]:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = close[i] - tp_atr * atr
```

### Anti-look-ahead

- MACD[i] utilise close[i] (connu à la barre i)
- Cross check utilise macd_prev et sig_prev (i-1) → pas de fuite

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −1.03 | 39.8% | −0.4% | 62 |

---

<a name="s4-stochastic"></a>

## Stratégie 4 : Stochastic Oversold/Overbought

**Type :** Mean reversion  
**TF recommandé :** H4  
**Actifs :** Tous

### Concept

Le %K stochastique croise %D dans une zone extrême → signal de retournement.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `stoch_k` | 14 | Période du %K fast |
| `stoch_d` | 3 | Période du %D |
| `stoch_smooth` | 3 | Lissage du %K |
| `oversold` | 20 | Seuil de survente |
| `overbought` | 80 | Seuil de surachat |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 2.0 | Take-profit en multiple d'ATR |

### Algorithme

```
Pour chaque barre i:
    k, d = Stochastic(high, low, close, stoch_k, stoch_d, stoch_smooth)
    atr = ATR[i]

    k_prev = k[i-1]
    d_prev = d[i-1]

    // LONG : %K croise au-dessus de %D près de la zone survendue
    if k_prev < oversold AND k[i] > d[i] AND k[i] <= oversold + 10:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = close[i] + tp_atr * atr

    // SHORT : %K croise en dessous de %D près de la zone surachatée
    if k_prev > overbought AND k[i] < d[i] AND k[i] >= overbought - 10:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = close[i] - tp_atr * atr
```

### Note sur le cross

On vérifie que `k[i] > d[i]` (pas juste au-dessus du seuil) pour confirmer le croisement. Le buffer ±10 autour des seuils évite de prendre des signaux trop éloignés de la zone extrême.

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −1.08 | 48.3% | −6.0% | 43 |

> Meilleur Sharpe ponctuel : 1.78 (GBPUSD H4)

---

<a name="s5-ema"></a>

## Stratégie 5 : EMA Cross

**Type :** Trend following  
**TF recommandé :** H4  
**Actifs :** Tous

### Concept

Deux EMA (rapide et lente). Le croisement indique un changement de tendance.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `fast` | 9 | Période EMA rapide |
| `slow` | 21 | Période EMA lente |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 2.0 | Take-profit en multiple d'ATR |

### Algorithme

```
Pour chaque barre i:
    ema_f = EMA(close, fast)
    ema_s = EMA(close, slow)
    atr   = ATR[i]

    f_prev = ema_f[i-1]
    s_prev = ema_s[i-1]

    // LONG : EMA rapide croise au-dessus de la lente
    if f_prev <= s_prev AND ema_f[i] > ema_s[i]:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = close[i] + tp_atr * atr

    // SHORT : EMA rapide croise en dessous de la lente
    if f_prev >= s_prev AND ema_f[i] < ema_s[i]:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = close[i] - tp_atr * atr
```

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −1.53 | 41.2% | −3.2% | 38 |

---

<a name="s6-swing-sr"></a>

## Stratégie 6 : Swing Support/Resistance

**Type :** Support/Resistance bounces  
**TF recommandé :** H4  
**Actifs :** EURUSD, GBPUSD, XAUUSD

### Concept

Détecte les points pivots (swing highs/lows) qui forment des niveaux de support/résistance horizontaux. Entre quand le prix rebondit sur un niveau, avec confirmation de la bougie.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `swing_window` | 20 | Rayon de détection des pivots (±N barres) |
| `proximity_atr` | 0.8 | Distance max au niveau S/R (en multiple d'ATR) |
| `sl_atr` | 1.5 | Stop-loss au-delà du niveau S/R |
| `tp_atr` | 2.0 | Take-profit depuis l'entrée |
| `atr_period` | 14 | Période ATR |

### Étape 1 : Détection des Swing Points

```
is_swing_high[i] = (high[i] == max(high[i-window ... i+window]))
is_swing_low[i]  = (low[i]  == min(low[i-window ... i+window]))
```

**Anti-look-ahead critique :** Un swing à l'index `j` n'est confirmé qu'après avoir vu les barres jusqu'à `j + window`. À la barre `i`, on ne peut utiliser que les swings avec `j ≤ i - window`.

```
confirmed_end = i - swing_window + 1  // +1 car intervalle exclusif à droite
```

### Étape 2 : Recherche du S/R le plus proche

```
search_start = max(0, confirmed_end - swing_window * 4)
// On regarde les swing points confirmés dans [search_start, confirmed_end)

recent_swing_lows  = low[search_start : confirmed_end] filtré par is_swing_low
recent_swing_highs = high[search_start : confirmed_end] filtré par is_swing_high

support    = recent_swing_lows[-1]   // dernier swing low = support
resistance = recent_swing_highs[-1]  // dernier swing high = résistance
```

### Étape 3-4 : Condition de proximité + Confirmation

```
prox = proximity_atr * ATR[i]

// LONG : prix au-dessus du support mais proche
dist_to_support = low[i] - support
if 0 < dist_to_support < prox AND close[i] > open[i]:
    entry_signal[i] = LONG
    sl[i] = support - sl_atr * ATR[i]
    tp[i] = close[i] + tp_atr * ATR[i]

// SHORT : prix en dessous de la résistance mais proche
dist_to_res = resistance - high[i]
if 0 < dist_to_res < prox AND close[i] < open[i]:
    entry_signal[i] = SHORT
    sl[i] = resistance + sl_atr * ATR[i]
    tp[i] = close[i] - tp_atr * ATR[i]
```

### Anti-look-ahead

- Les swings utilisent `confirmed_end = i - swing_window + 1` → zéro fuite
- La confirmation utilise `close[i]` et `open[i]` (barre courante, OK)

### Filtre anti-doublons

```
if entry_signal[i] == entry_signal[i-1]:
    entry_signal[i] = None
```

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| +0.01 | 63.6% | −1.3% | 37 |

> Meilleur Sharpe ponctuel : 1.56 (GBPUSD H4)

---

<a name="s7-psar"></a>

## Stratégie 7 : Parabolic SAR Flip

**Type :** Trend following  
**TF recommandé :** H4  
**Actifs :** Tous

### Concept

Le Parabolic SAR flippe au-dessus → en dessous du prix = retournement haussier, et inversement.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `step` | 0.02 | Pas d'accélération |
| `maximum` | 0.2 | Accélération max |
| `sl_atr` | 1.5 | Stop-loss en multiple d'ATR |
| `tp_atr` | 2.0 | Take-profit en multiple d'ATR |

### Algorithme

```
Pour chaque barre i:
    sar = ParabolicSAR(high, low, step, maximum)
    atr = ATR[i]

    // Position du SAR par rapport au close à i-1
    sar_above_prev = sar[i-1] > close[i-1]
    sar_below_prev = sar[i-1] < close[i-1]

    // LONG : SAR flippe de au-dessus → en dessous du prix
    if sar_above_prev AND sar[i] < close[i]:
        entry_signal[i] = LONG
        sl[i] = close[i] - sl_atr * atr
        tp[i] = close[i] + tp_atr * atr

    // SHORT : SAR flippe de en dessous → au-dessus du prix
    if sar_below_prev AND sar[i] > close[i]:
        entry_signal[i] = SHORT
        sl[i] = close[i] + sl_atr * atr
        tp[i] = close[i] - tp_atr * atr
```

### Anti-look-ahead

- SAR[i] est calculé avec high/low jusqu'à la barre i
- Le flip compare `sar[i-1]` vs `close[i-1]` avec `sar[i]` vs `close[i]` → pas de fuite

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −1.68 | 39.4% | −4.4% | 58 |

---

<a name="s8-ichimoku-scalp"></a>

## Stratégie 8 : Ichimoku Flat-Line Scalp (Single TF)

**Type :** Flat-line breakout  
**TF recommandé :** H4 (le seul TF où ça a du sens)  
**Actifs :** XAUUSD, EURUSD, GBPUSD

### Concept

Les lignes Ichimoku (Kijun-sen, Senkou B) forment des segments **parfaitement horizontaux** quand le marché est en équilibre. Quand le prix casse une ligne plate, on entre dans la direction de la cassure.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `flat_window` | 7 | Barres pour vérifier la platitude |
| `flat_threshold_atr` | 0.01 | Tolérance de platitude (range < threshold × ATR) |
| `sl_atr` | 0.6 | Stop-loss de l'autre côté de la ligne (en ATR) |
| `tp_atr` | 1.5 | Take-profit fallback (si pas de ligne plate suivante) |
| `tenkan_p` | 9 | Période Tenkan |
| `kijun_p` | 26 | Période Kijun |
| `senkou_b_p` | 52 | Période Senkou B |
| `displacement` | 26 | Décalage Senkou |

### Étape 1 : Détection des lignes plates

```
// Pour les 4 lignes (Tenkan, Kijun, Senkou A, Senkou B)
pour chaque ligne:
    range[i] = max(ligne[i-flat_window+1 ... i]) - min(ligne[i-flat_window+1 ... i])
    is_flat[i] = range[i] < flat_threshold_atr * ATR[i]
```

Les lignes Ichimoku sont mathématiquement plates quand le max/min de leur période de calcul n'évolue pas. `0.01 × ATR` est donc un seuil quasi nul — on ne détecte que les plats parfaits.

### Étape 2 : Signal d'entrée

```
// Lignes d'entrée : Kijun et Senkou B uniquement (les plus solides)
// Lignes TP     : les 4 lignes (Tenkan, Kijun, Senkou A, Senkou B)

flat_entries = {kijun, senkou_b} filtré par is_flat
flat_all     = {tenkan, kijun, senkou_a, senkou_b} filtré par is_flat

// LONG : close franchit une ligne plate vers le haut + bougie haussière
if prev_close < flat_line[i] AND close[i] > flat_line[i] AND close[i] > open[i]:
    entry_signal[i] = LONG
    sl[i] = flat_line[i] - sl_atr * ATR[i]

    // TP = prochaine ligne plate au-dessus (min 0.15 ATR d'écart)
    higher = {v dans flat_all où v > flat_line[i] + 0.15 * ATR[i]}
    tp[i] = min(higher) si higher non vide, sinon close[i] + tp_atr * ATR[i]

// SHORT : close franchit une ligne plate vers le bas + bougie baissière
if prev_close > flat_line[i] AND close[i] < flat_line[i] AND close[i] < open[i]:
    entry_signal[i] = SHORT
    sl[i] = flat_line[i] + sl_atr * ATR[i]

    lower = {v dans flat_all où v < flat_line[i] - 0.15 * ATR[i]}
    tp[i] = max(lower) si lower non vide, sinon close[i] - tp_atr * ATR[i]
```

### Priorité entre lignes

Si plusieurs lignes sont franchies simultanément : **Senkou B > Kijun** (la plus lente est la plus fiable).

### TP minimum

Si la distance au TP est inférieure à 0.5 ATR, on utilise le fallback ATR (tp_atr × ATR).

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −9.56 (M15) | 33.2% | −19.5% | 432 |

> Stratégie perdante en l'état. Le problème : trop peu de lignes plates en 6 mois, et le SL 0.6 ATR est trop serré pour la volatilité XAUUSD M15.

---

<a name="s9-ichimoku-mtf"></a>

## Stratégie 9 : Ichimoku MTF Flat-Line Scalp

**Type :** Multi-timeframe flat-line breakout  
**TF signal :** H4, D1 (lignes plates)  
**TF trading :** M15, M5 (exécution)  
**Actifs :** XAUUSD, EURUSD, GBPUSD

### Concept

Identique à la stratégie 8, mais les lignes plates sont détectées sur des TFs **supérieures** (H4, D1) puis projetées sur la TF de trading (M15). Les niveaux de TF haute sont des S/R plus solides.

### Pipeline MTF (anti-look-ahead)

```
Étape 1 : Resample TF basse → TF haute
    df_high = Resample(df_low, '4H' ou '1D')
    // Agrégation : open=first, high=max, low=min, close=last

Étape 2 : Ichimoku sur TF haute
    tenkan_h, kijun_h, senkou_a_h, senkou_b_h = Ichimoku(df_high)

Étape 3 : Flat line detection sur TF haute
    pour chaque ligne dans {tenkan_h, kijun_h, senkou_a_h, senkou_b_h}:
        range[i] = max(ligne[i-flat_window+1 ... i]) - min(ligne[i-flat_window+1 ... i])
        is_flat[i] = range[i] < flat_threshold_atr * ATR_high[i]
        flat_series_h[i] = ligne[i] si is_flat[i], sinon NaN

Étape 4 : Projection anti-look-ahead vers TF basse
    // shift(1) : la flat line de la période H4 N n'est connue qu'à N+1
    // reindex(ffill) : forward-fill sur toutes les barres de TF basse
    flat_low[i] = flat_series_h.shift(1).reindex(df_low.index, method='ffill')[i]
```

### Justification de `shift(1) + reindex(ffill)`

```
Exemple H4 → M15 :
  H4 08:00 (période 08:00-11:59) → flat line connue à 12:00
  shift(1) : valeur 08:00 décalée à l'index 12:00 sur H4
  reindex ffill M15 : les barres 08:00-11:45 voient la flat line de 04:00-07:59
                      les barres 12:00-15:45 voient la flat line de 08:00-11:59 ✓
```

### Étape 5 : Signal (identique à stratégie 8, mais sur TF basse)

```
// Les flat lines sont maintenant dans l'index de TF basse
// Entrée : Kijun et Senkou B (toutes TFs hautes confondues)
// TP     : toute ligne plate (toute TF, toute ligne)
// Priorité : Senkou B > Kijun > Senkou A > Tenkan
//            Au sein du même type, TF supérieure prioritaire (D1 > H4)
```

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `higher_tfs` | "4h,D" | TFs hautes séparées par des virgules (W, D, 12h, 4h, 1h) |
| `flat_window` | 5 | Barres de TF haute pour platitude |
| `flat_threshold_atr` | 0.01 | Tolérance |
| `sl_atr` | 0.6 | Stop-loss en ATR de TF basse |
| `tp_atr` | 1.5 | Take-profit fallback en ATR de TF basse |

### Résultats

| Sharpe | WR | Ret% | Trades |
|:---:|:---:|:---:|:---:|
| −4.42 (M15) | 26.2% | −9.4% | 195 |

> Meilleur que single-TF (−9.56) mais toujours perdant. Le filtre MTF réduit le bruit, mais les flat lines H4/D1 sont trop rares en 6 mois.

---

<a name="s10-dxy-xau"></a>

## Stratégie 10 : DXY → XAUUSD Correlation Scalping

**Type :** Cross-asset correlation  
**TF signal :** DXY.cash H1 (détection)  
**TF trading :** XAUUSD M1, M5, M15, H1, H4  
**Actif tradé :** XAUUSD uniquement

### Concept

DXY (US Dollar Index) et XAUUSD (or) sont fortement anti-corrélés (Pearson −0.72). DXY anticipe XAUUSD de 5 à 20 barres. On détecte les mouvements anormalement forts de DXY sur H1, et on entre en position inverse sur XAUUSD.

### Paramètres

| Paramètre | Défaut | Description |
|:---|:---:|:---|
| `THRESHOLD_STD` | 1.5 | Seuil de détection DXY en écarts-types |
| `STD_WINDOW` | 50 | Fenêtre glissante pour l'écart-type DXY |
| `SL_ATR` | 1.5 | Stop-loss en ATR du TF de trading |
| `TP_ATR` | 3.0 | Take-profit en ATR du TF de trading |
| `ROLLING_CORR_MIN` | −0.3 | Corrélation rolling minimum (doit être plus négative) |
| `H4_SMA_PERIOD` | 20 | SMA H4 DXY pour filtre de tendance |
| `COOLDOWN_BARS` | variable | Cooldown entre signaux (M1=30, M5=12, M15=8, H1=3, H4=2) |

### Pré-requis : Données

```
Nécessite DEUX symboles :
  - DXY.cash (US Dollar Index) en H1 et H4
  - XAUUSD (Gold) dans le TF de trading souhaité

Période minimum : 200 barres H1 + 30 barres H4 + 200 barres TF trading
```

### Algorithme complet

#### Phase A : Détection du signal DXY (H1)

```
// 1. Calculer les returns DXY H1
dxy_ret[i] = (dxy_close[i] / dxy_close[i-1] - 1) * 100   // en %

// 2. Calculer l'écart-type ROULANT (ANTI-LOOK-AHEAD)
//    ⚠️ Ne PAS utiliser l'écart-type global (utilise le futur)
dxy_std[i] = StdDev(dxy_ret[max(0, i-STD_WINDOW+1) ... i], min_periods=20)
//    Pour les 19 premières barres : expanding std (fenêtre qui s'élargit)

// 3. Détecter les mouvements forts
threshold[i] = THRESHOLD_STD * dxy_std[i]

dxy_strong_up[i]   = dxy_ret[i] >  threshold[i]   // DXY explose → signal SHORT XAU (-1)
dxy_strong_down[i] = dxy_ret[i] < -threshold[i]   // DXY s'effondre → signal LONG XAU (+1)
```

#### Phase B : Filtres sur DXY

```
// Filtre 1 : Rolling corrélation XAUUSD vs DXY (sur H1 aligné)
xau_h1_close = Resample(XAUUSD_TF, '1H', agg='last')
corr[i] = PearsonCorrelation(
    PctChange(xau_h1_close[i-19 ... i]),
    PctChange(dxy_h1_close[i-19 ... i])
)
// Ne trader que si corr[i] < ROLLING_CORR_MIN (-0.3)
// → La relation inverse doit être ACTIVE

// Filtre 2 : Tendance H4 DXY
dxy_h4_sma[i] = SMA(dxy_h4_close, H4_SMA_PERIOD)
dxy_h4_bullish[i] = dxy_h1_close[i] > dxy_h4_sma[i]  // DXY au-dessus de sa SMA H4
// SHORT XAU uniquement si DXY H4 bullish (tendance dollar haussière)
// LONG  XAU uniquement si DXY H4 bearish
```

#### Phase C : Projection sur TF de trading

```
// Signal DXY H1 → projeté sur TF XAUUSD

dxy_signal_h1[i] =  0                // neutre
dxy_signal_h1[i] = +1 si dxy_strong_down[i]    // LONG XAU
dxy_signal_h1[i] = -1 si dxy_strong_up[i]      // SHORT XAU

// shift(1) : signal H1 barre N dispo à partir de N+1
// reindex ffill : forward-fill sur toutes les barres du TF trading
dxy_signal_tf[j] = dxy_signal_h1.shift(1).reindex(tf_index, ffill)[j]
```

#### Phase D : Génération des signaux XAUUSD

```
Pour chaque barre j du TF trading (après warmup):
    // Cooldown
    if j - last_signal_bar < COOLDOWN_BARS:
        continue

    sig = dxy_signal_tf[j]
    if sig == 0: continue

    // Filtre rolling corrélation (projeté sur TF trading)
    if corr_tf[j] existe ET corr_tf[j] > ROLLING_CORR_MIN:
        continue

    // Filtre tendance H4 (projeté sur TF trading)
    if sig == -1 ET NOT dxy_h4_bullish_tf[j]: continue
    if sig == +1 ET dxy_h4_bullish_tf[j]: continue

    // Confirmation bougie
    if sig == +1 ET NOT (close[j] > open[j]): continue   // attendre bougie haussière
    if sig == -1 ET NOT (close[j] < open[j]): continue   // attendre bougie baissière

    // Signal !
    if sig == +1:
        entry_signal[j] = LONG
        sl[j] = close[j] - SL_ATR * ATR[j]
        tp[j] = close[j] + TP_ATR * ATR[j]
    else:
        entry_signal[j] = SHORT
        sl[j] = close[j] + SL_ATR * ATR[j]
        tp[j] = close[j] - TP_ATR * ATR[j]

    last_signal_bar = j
```

### Sorties

| Type | Condition |
|:---|:---|
| Stop-Loss | Prix touche sl_price |
| Take-Profit | Prix atteint tp_price |
| Signal opposé | DXY fort dans l'autre sens |
| Fin de période | Clôture forcée |

### Anti-look-ahead (checklist)

| Élément | Mesure |
|:---|:---|
| `dxy_std` | Rolling 50 barres (pas global) |
| `dxy_signal_tf` | shift(1) + ffill (pas d'anticipation) |
| `dxy_h4_bullish_tf` | reindex + shift(1) + reindex ffill |
| `corr_tf` | Rolling 20 barres, pas expanding |
| Confirmation bougie | close[i] et open[i] (barre courante) |

### Résultats multi-TF

| TF | Trades | WR% | Ret% | Sharpe | FTMO |
|:---|---:|---:|---:|---:|:---|
| **H4** 🏆 | 20 | **55.0%** | **+9.22%** | **+1.25** | **+14.5%** |
| H1 | 65 | 43.1% | +5.86% | +0.64 | — |
| M15 | 146 | 33.6% | −17.4% | −2.95 | −44.6% |
| M5 | 182 | 35.7% | −13.0% | −3.26 | — |
| M1 | 119 | 27.7% | −10.8% | −16.9 | — |

### Notes d'implémentation

- **DXY.cash** doit être disponible chez le broker (vérifié sur MT5 standard)
- **Ne pas utiliser `close[i]` de DXY H1** avant la fin de la barre — toujours utiliser `shift(1)` pour la projection
- La rolling std doit utiliser **minimum 20 barres** pour être statistiquement significative
- Les 3 filtres réduisent le nombre de signaux mais augmentent la qualité : sans filtres, la stratégie perd davantage
- Le cooldown est crucial sur TFs basses (M1, M5) pour éviter l'overtrading

---

<a name="couts"></a>

## Gestion des Coûts de Transaction

Toutes les stratégies intègrent les coûts suivants à l'entrée ET à la sortie :

```
LONG:
    entry_price = close[i] * (1 + spread_pct/100 + slippage_pct/100)
    exit_price  = close_exit * (1 - spread_pct/100 - slippage_pct/100)

SHORT:
    entry_price = close[i] * (1 - spread_pct/100 - slippage_pct/100)
    exit_price  = close_exit * (1 + spread_pct/100 + slippage_pct/100)
```

### Coûts par catégorie (valeurs indicatives)

| Catégorie | Spread | Slippage | Exemples |
|:---|---:|---:|:---|
| Forex Majors | 0.005% | 0.010% | EURUSD, USDJPY |
| Forex Minors | 0.015% | 0.015% | GBPJPY, EURGBP |
| Indices | 0.020% | 0.030% | US30, GER40 |
| Commodities | 0.025% | 0.030% | XAUUSD, USOIL |
| Crypto | 0.080% | 0.050% | BTCUSD, ETHUSD |

---

## Règles Générales du Backtest Engine

### Une position à la fois

```
Pas de pyramiding. Si une position est déjà ouverte :
  - Les nouveaux signaux d'entrée sont ignorés
  - Un signal opposé ferme la position existante
```

### Ordre de priorité des sorties

```
1. Stop-Loss (prioritaire)
2. Take-Profit
3. Signal opposé
4. Clôture forcée (fin de période)
```

### Calcul du PnL

```
Si pas de FTMO:
    pnl_pct = (exit_price_cost / entry_price_cost - 1) * 100
    Si SHORT: pnl_pct = -pnl_pct
    pnl_abs  = capital * pnl_pct / 100

Si FTMO:
    sl_dist_pct = |sl - entry_price_cost| / entry_price_cost * 100
    risk_amount = capital * risk_pct / 100
    position_value = risk_amount / (sl_dist_pct / 100)
    position_value = min(position_value, capital * max_leverage)
    pnl_abs = position_value * pnl_pct / 100
```

### Métriques

| Métrique | Formule |
|:---|:---|
| Sharpe | `mean(daily_returns) / std(daily_returns) * sqrt(252)` |
| MaxDD | `min((equity - equity.cummax()) / equity.cummax() * 100)` |
| Profit Factor | `sum(pnls > 0) / abs(sum(pnls < 0))` |
| Win Rate | `count(pnls > 0) / count(all) * 100` |
| CAGR | `(final / initial)^(1/years) - 1` × 100 |

---

## Résumé des Performances

| Rang | Stratégie | TF | Sharpe | WR% | Ret% | FTMO |
|:---:|:---|:---:|:---:|:---:|:---:|:---|
| 🥇 | DXY→XAUUSD | H4 | +1.25 | 55% | +9.2% | +14.5% |
| 🥈 | Stochastic | H4 | +1.78* | 60% | +4.6% | — |
| 🥉 | Swing_SR | H4 | +1.56* | 71% | +2.4% | — |
| 4 | Ichimoku MTF | M15 | −4.42 | 26% | −9.4% | — |
| 5 | MACD | H4 | −1.03* | 40% | −0.4% | — |
| 6-10 | Autres | — | < 0 | — | < 0 | — |

> \* Meilleur Sharpe ponctuel sur un couple spécifique (ex: Stochastic GBPUSD H4). La moyenne sur tous les symboles/TFs est négative.

---

*Document généré le 06/07/2026 — Spécifications suffisantes pour réimplémentation dans tout langage.*
