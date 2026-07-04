"""
Configuration centralisée pour IchimokuSword.
S'inspire du pattern config.py du projet InelidaMarketScan.
"""

import os
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Timeframes MT5 (noms et constantes)
# ---------------------------------------------------------------------------
TIMEFRAME_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 16385,
    "H4": 16388,
    "D1": 16408,
    "W1": 32769,
    "MN1": 49153,
}

TIMEFRAME_LABELS = {
    1: "M1", 5: "M5", 15: "M15", 30: "M30",
    16385: "H1", 16388: "H4", 16408: "D1",
    32769: "W1", 49153: "MN1",
}

# ---------------------------------------------------------------------------
# Constantes Ichimoku
# ---------------------------------------------------------------------------
KIJUN_PERIOD = 26       # Période par défaut du Kijun Sen
TENKAN_PERIOD = 9       # Période du Tenkan Sen (pour référence future)
CHIKOU_SHIFT = 26       # Décalage du Chikou Span
SENKOU_B_PERIOD = 52    # Période du Senkou Span B

# ---------------------------------------------------------------------------
# Configuration chargeable depuis .env
# ---------------------------------------------------------------------------

@dataclass
class MT5Config:
    """Paramètres de connexion MetaTrader 5."""
    path: str = ""
    login: int = 0
    password: str = ""
    server: str = ""
    timeout_ms: int = 5000
    retry_delay: float = 1.0
    max_retries: int = 3


@dataclass
class ScanConfig:
    """Paramètres de scan Kijun Sen."""
    timeframes: List[int] = field(default_factory=lambda: [16408])  # D1 par défaut
    kijun_period: int = KIJUN_PERIOD
    min_bars: int = 100
    watch_interval_sec: float = 60.0  # Intervalle en mode watch
    scan_all_symbols: bool = True  # Scanner tous les symboles ou seulement la watchlist


@dataclass
class AlertConfig:
    """Seuils d'alerte."""
    kijun_proximity_pct: float = 1.0  # Seuil par défaut pour "approche du Kijun"


# ---------------------------------------------------------------------------
# Watchlist par défaut (utilisée si scan_all_symbols = False)
# ---------------------------------------------------------------------------
DEFAULT_WATCHLIST = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF",
    "EURJPY", "GBPJPY", "EURGBP",
    "XAUUSD", "XAGUSD",
    "US30.cash", "US100.cash", "US500.cash",
    "GER40.cash", "UK100.cash", "FRA40.cash",
    "AUS200.cash", "N25.cash", "HK50.cash",
    "WTI", "BRENT",
]

# ---------------------------------------------------------------------------
# Chargement du .env simplifié
# ---------------------------------------------------------------------------

def load_env(env_path: str = ".env") -> None:
    """Charge les variables depuis un fichier .env."""
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if value:
                os.environ.setdefault(key, value)


def make_mt5_config() -> "MT5Config":
    """Construit MT5Config depuis les variables d'environnement."""
    return MT5Config(
        path=os.environ.get("MT5_PATH", ""),
        login=int(os.environ.get("MT5_LOGIN", "0")),
        password=os.environ.get("MT5_PASSWORD", ""),
        server=os.environ.get("MT5_SERVER", ""),
    )


def resolve_watchlist(cli_symbols: List[str] | None = None) -> List[str]:
    """Résout la watchlist : priorité CLI > .env > DEFAULT_WATCHLIST.

    Args:
        cli_symbols: Liste optionnelle passée via la CLI.

    Returns:
        Liste des symboles à scanner.
    """
    if cli_symbols:
        return cli_symbols
    env_symbols = os.environ.get("ICHIMOKU_WATCHLIST", "")
    if env_symbols:
        return [s.strip().upper() for s in env_symbols.split(",") if s.strip()]
    return DEFAULT_WATCHLIST.copy()
