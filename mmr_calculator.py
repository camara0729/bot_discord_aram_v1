# mmr_calculator.py
import math

def calculate_expected_score(player_avg_mmr, opponent_avg_mmr):
    """Calcula a probabilidade de vitória esperada para uma equipe."""
    return 1 / (1 + math.pow(10, (opponent_avg_mmr - player_avg_mmr) / 400))

def calculate_pdi(player_stats, team_stats, all_player_stats):
    """Calcula o Índice de Diferença do Jogador (PDI)."""
    pdi_score = 0
    weights = {
        'totalDamageDealtToChampions': 0.40,
        'damageSelfMitigated': 0.25,
        'timeCCingOthers': 0.20,
        'totalHealOnTeammates': 0.20, # Combina cura e escudos
        'deaths': -0.30,
        'pentaKills': 5.0 # Bônus fixo, não ponderado
    }

    # Dano
    if team_stats > 0:
        damage_share = player_stats / team_stats
        pdi_score += damage_share * weights

    # Sobrevivência
    if team_stats > 0:
        mitigation_share = player_stats / team_stats
        pdi_score += mitigation_share * weights
    
    # Mortes (penalidade)
    avg_deaths = sum(p['deaths'] for p in all_player_stats) / len(all_player_stats)
    if avg_deaths > 0:
        death_ratio = (avg_deaths - player_stats['deaths']) / avg_deaths
        pdi_score += death_ratio * abs(weights['deaths'])

    # Utilidade
    if team_stats['timeCCingOthers'] > 0:
        cc_share = player_stats['timeCCingOthers'] / team_stats['timeCCingOthers']
        pdi_score += cc_share * weights['timeCCingOthers']
    
    total_support = player_stats.get('totalHealOnTeammates', 0) + player_stats.get('totalShieldsOnTeammates', 0)
    team_total_support = team_stats.get('totalHealOnTeammates', 0) + team_stats.get('totalShieldsOnTeammates', 0)
    if team_total_support > 0:
        support_share = total_support / team_total_support
        pdi_score += support_share * weights

    # Bônus de Pentakill
    if player_stats.get('pentaKills', 0) > 0:
        pdi_score += weights['pentaKills'] * player_stats['pentaKills']

    # Normaliza o PDI para um modificador entre -0.2 e +0.2
    return max(-0.2, min(0.2, (pdi_score - 0.5) * 0.4))

def calculate_mmr_change(player_mmr, player_k_factor, expected_score, actual_score, pdi_modifier):
    """Calcula a mudança de MMR para um jogador."""
    modified_actual_score = actual_score + pdi_modifier
    mmr_change = player_k_factor * (modified_actual_score - expected_score)
    return round(mmr_change)
