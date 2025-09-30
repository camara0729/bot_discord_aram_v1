# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Configurações do Discord
DISCORD_BOT_TOKEN = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')

# Configurações da API da Riot
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

# Sistema de PDL e Elos
DEFAULT_PDL = 1000
PDL_WIN = 25
PDL_LOSS = -20
MVP_BONUS = 5
BAGRE_PENALTY = -5

# Sistema de Elos baseado em PDL
ELOS = {
    "Ferro": {"min": 0, "max": 799, "color": 0x8B4513, "emoji": "🟫"},
    "Bronze": {"min": 800, "max": 999, "color": 0xCD7F32, "emoji": "🟤"},
    "Prata": {"min": 1000, "max": 1199, "color": 0xC0C0C0, "emoji": "⚪"},
    "Ouro": {"min": 1200, "max": 1399, "color": 0xFFD700, "emoji": "🟡"},
    "Platina": {"min": 1400, "max": 1599, "color": 0x00FFFF, "emoji": "🔵"},
    "Esmeralda": {"min": 1600, "max": 1799, "color": 0x50C878, "emoji": "💚"},
    "Diamante": {"min": 1800, "max": 1999, "color": 0x87CEEB, "emoji": "💎"},
    "Mestre": {"min": 2000, "max": 2199, "color": 0x9370DB, "emoji": "🔮"},
    "Grão-Mestre": {"min": 2200, "max": 2399, "color": 0xFF0000, "emoji": "🔴"},
    "Desafiante": {"min": 2400, "max": 9999, "color": 0xFFD700, "emoji": "👑"}
}

# Mapeamento de ranks do LoL para uso no balanceamento (não afeta PDL inicial)
RANK_WEIGHTS = {
    # Ferro
    "FERRO IV": 1, "FERRO III": 2, "FERRO II": 3, "FERRO I": 4,
    # Bronze
    "BRONZE IV": 5, "BRONZE III": 6, "BRONZE II": 7, "BRONZE I": 8,
    # Prata
    "PRATA IV": 9, "PRATA III": 10, "PRATA II": 11, "PRATA I": 12,
    # Ouro
    "OURO IV": 13, "OURO III": 14, "OURO II": 15, "OURO I": 16,
    # Platina
    "PLATINA IV": 17, "PLATINA III": 18, "PLATINA II": 19, "PLATINA I": 20,
    # Esmeralda
    "ESMERALDA IV": 21, "ESMERALDA III": 22, "ESMERALDA II": 23, "ESMERALDA I": 24,
    # Diamante
    "DIAMANTE IV": 25, "DIAMANTE III": 26, "DIAMANTE II": 27, "DIAMANTE I": 28,
    # Mestre+
    "MESTRE": 29, "GRÃO-MESTRE": 30, "DESAFIANTE": 31
}

def get_elo_by_pdl(pdl: int) -> dict:
    """Retorna o elo baseado no PDL atual."""
    for elo_name, elo_data in ELOS.items():
        if elo_data["min"] <= pdl <= elo_data["max"]:
            return {"name": elo_name, **elo_data}
    return {"name": "Desafiante", **ELOS["Desafiante"]}

def calculate_balance_score(pdl: int, lol_rank: str, wins: int, losses: int) -> float:
    """
    Calcula um score de balanceamento considerando:
    - PDL atual (peso 60%)
    - Rank do LoL (peso 25%) 
    - Taxa de vitória nas partidas personalizadas (peso 15%)
    """
    # Score baseado no PDL (normalizado para 0-100)
    pdl_score = min(100, (pdl / 22) if pdl > 0 else 0)
    
    # Score baseado no rank do LoL
    rank_weight = RANK_WEIGHTS.get(lol_rank.upper(), 10)
    rank_score = (rank_weight / 31) * 100  # Normalizado para 0-100
    
    # Score baseado na taxa de vitória
    total_games = wins + losses
    if total_games > 0:
        win_rate = wins / total_games
        win_rate_score = win_rate * 100
    else:
        win_rate_score = 50  # Neutro para jogadores sem partidas
    
    # Peso final: PDL(60%) + Rank LoL(25%) + Win Rate(15%)
    final_score = (pdl_score * 0.6) + (rank_score * 0.25) + (win_rate_score * 0.15)
    
    return round(final_score, 2)