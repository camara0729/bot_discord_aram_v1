# cogs/match_cog.py
import os
import discord
from discord.ext import commands
from discord import app_commands
import requests
import time
import database as db
import mmr_calculator as mmr

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
PROVIDER_ID = int(os.getenv("RIOT_TOURNAMENT_PROVIDER_ID"))
SERVER_URL = os.getenv("SERVER_URL")

class MatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="criar_partida", description="Gera um código de torneio para uma partida personalizada.")
    async def create_match(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        provider_url = "https://americas.api.riotgames.com/lol/tournament-stub/v5/providers"
        provider_payload = {"region": "NA", "url": SERVER_URL}
        headers = {"X-Riot-Token": RIOT_API_KEY}
        
        try:
            requests.post(provider_url, json=provider_payload, headers=headers)

            tournament_url = "https://americas.api.riotgames.com/lol/tournament-stub/v5/tournaments"
            tournament_payload = {"name": f"ARAM_Match_{int(time.time())}", "providerId": PROVIDER_ID}
            response = requests.post(tournament_url, json=tournament_payload, headers=headers)
            response.raise_for_status()
            tournament_id = response.json()

            codes_url = f"https://americas.api.riotgames.com/lol/tournament-stub/v5/codes?count=1&tournamentId={tournament_id}"
            codes_payload = { "mapType": "HOWLING_ABYSS", "pickType": "ALL_RANDOM", "spectatorType": "NONE", "teamSize": 5 }
            response = requests.post(codes_url, json=codes_payload, headers=headers)
            response.raise_for_status()
            tournament_code = response.json()

            embed = discord.Embed(
                title="Código de Partida ARAM Gerado!",
                description="Use este código no cliente do LoL para criar o lobby:\n`Jogar > Personalizada > Torneio`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Código", value=f"**`{tournament_code}`**")
            embed.set_footer(text="Após a partida, use /registrar_partida com o ID da partida do histórico.")
            await interaction.followup.send(embed=embed)

        except requests.exceptions.HTTPError as e:
            await interaction.followup.send(f"Erro ao criar partida: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            await interaction.followup.send(f"Ocorreu um erro inesperado: {e}")

    @app_commands.command(name="registrar_partida", description="Registra o resultado de uma partida e atualiza o MMR.")
    @app_commands.describe(match_id="O ID da partida (ex: NA1_1234567890).")
    async def register_match(self, interaction: discord.Interaction, match_id: str):
        await interaction.response.defer()

        if db.get_match_by_id(match_id):
            await interaction.followup.send("Esta partida já foi registrada.", ephemeral=True)
            return

        region_prefix = match_id.split('_').upper()
        region_map = {
            'NA1': 'americas', 'BR1': 'americas', 'LA1': 'americas', 'LA2': 'americas',
            'EUW1': 'europe', 'EUN1': 'europe', 'TR1': 'europe', 'RU': 'europe',
            'KR': 'asia', 'JP1': 'asia'
        }
        regional_route = region_map.get(region_prefix)
        if not regional_route:
            await interaction.followup.send("Prefixo de região do Match ID inválido.", ephemeral=True)
            return

        url = f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        headers = {"X-Riot-Token": RIOT_API_KEY}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            match_info = response.json()['info']
        except requests.exceptions.HTTPError as e:
            await interaction.followup.send(f"Erro ao buscar dados da partida: {e.response.status_code}. Verifique o ID.", ephemeral=True)
            return

        participants = match_info['participants']
        unregistered_players, player_objects = [], []
        
        for p in participants:
            player_record = db.get_player_by_puuid(p['puuid'])
            if not player_record:
                unregistered_players.append(p.get('summonerName', p['puuid']))
            else:
                player_objects.append(player_record)
        
        if unregistered_players:
            await interaction.followup.send(f"Não é possível registrar. Os seguintes jogadores não estão registrados: {', '.join(unregistered_players)}", ephemeral=True)
            return

        team100_players = [p for p in player_objects if any(part['puuid'] == p['riot_puuid'] and part['teamId'] == 100 for part in participants)]
        team200_players = [p for p in player_objects if any(part['puuid'] == p['riot_puuid'] and part['teamId'] == 200 for part in participants)]
        
        team100_mmr = sum(p['mmr'] for p in team100_players) / len(team100_players) if team100_players else 1500
        team200_mmr = sum(p['mmr'] for p in team200_players) / len(team200_players) if team200_players else 1500

        expected_score_100 = mmr.calculate_expected_score(team100_mmr, team200_mmr)
        expected_score_200 = mmr.calculate_expected_score(team200_mmr, team100_mmr)

        team_stats_100 = self._get_team_total_stats([p for p in participants if p['teamId'] == 100])
        team_stats_200 = self._get_team_total_stats([p for p in participants if p['teamId'] == 200])

        processed_player_stats = {}
        mmr_changes_summary = ""

        for p_data in participants:
            player_record = next((p for p in player_objects if p['riot_puuid'] == p_data['puuid']), None)
            if not player_record: continue

            is_win, actual_score = p_data['win'], 1 if p_data['win'] else 0
            expected_score = expected_score_100 if p_data['teamId'] == 100 else expected_score_200
            team_stats = team_stats_100 if p_data['teamId'] == 100 else team_stats_200

            pdi_modifier = mmr.calculate_pdi(p_data, team_stats, participants)
            mmr_change = mmr.calculate_mmr_change(player_record['mmr'], player_record['k_factor'], expected_score, actual_score, pdi_modifier)

            stats_update = {
                'match_id': match_id, 'wins': 1 if is_win else 0, 'losses': 0 if is_win else 1,
                'lifetime_kills': p_data['kills'], 'lifetime_deaths': p_data['deaths'],
                'lifetime_assists': p_data['assists'], 'lifetime_damage_dealt': p_data,
                'lifetime_penta_kills': p_data.get('pentaKills', 0)
            }
            
            new_title, new_achievements = self._check_achievements_and_titles(p_data, participants)
            db.update_player_after_match(p_data['puuid'], mmr_change, stats_update, new_title, new_achievements)
            
            player_name = p_data.get('summonerName', player_record['riot_id'])
            mmr_changes_summary += f"{player_name}: {player_record['mmr']} -> {player_record['mmr'] + mmr_change} ({'+' if mmr_change >= 0 else ''}{mmr_change})\n"
            
            processed_player_stats[p_data['puuid']] = { 'win': is_win, 'champion_name': p_data['championName'], 'kills': p_data['kills'], 'deaths': p_data['deaths'], 'assists': p_data['assists'], 'mmr_change': mmr_change }

        winning_team = next((team for team in match_info['teams'] if team['win']), None)
        final_match_data = {
            'match_id': match_id, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(match_info / 1000)),
            'game_duration_seconds': match_info, 'winning_team_id': winning_team['teamId'] if winning_team else 0,
            'teams': { '100': {'avg_mmr': team100_mmr, 'players': [p['puuid'] for p in participants if p['teamId'] == 100]}, '200': {'avg_mmr': team200_mmr, 'players': [p['puuid'] for p in participants if p['teamId'] == 200]} },
            'player_stats': processed_player_stats
        }
        db.add_match(final_match_data)

        embed = discord.Embed(title=f"Partida `{match_id}` Registrada!", color=discord.Color.green())
        embed.add_field(name="Mudanças de MMR", value=f"```{mmr_changes_summary}```", inline=False)
        await interaction.followup.send(embed=embed)

    def _get_team_total_stats(self, team_participants):
        return {
            'totalDamageDealtToChampions': sum(p for p in team_participants),
            'damageSelfMitigated': sum(p for p in team_participants),
            'timeCCingOthers': sum(p['timeCCingOthers'] for p in team_participants),
            'supportScore': sum(p.get('totalHeal', 0) + p.get('totalShieldsOnTeammates', 0) for p in team_participants),
        }

    def _check_achievements_and_titles(self, player_stats, all_participants):
        achievements, title = [], None

        if player_stats.get('pentaKills', 0) > 0: achievements.append("Pentakill!")
        if player_stats > 75000: achievements.append("Muralha Impenetrável")
        if player_stats['timeCCingOthers'] > 100: achievements.append("Maestro do Controle")

        if player_stats == max(p for p in all_participants): title = "O Canhão de Vidro"
        elif player_stats == max(p for p in all_participants): title = "A Muralha Inabalável"
        
        player_support_score = player_stats.get('totalHeal', 0) + player_stats.get('totalShieldsOnTeammates', 0)
        max_support_score = max(p.get('totalHeal', 0) + p.get('totalShieldsOnTeammates', 0) for p in all_participants)
        if player_support_score > 0 and player_support_score == max_support_score: title = "O Guardião"
        
        min_deaths = min(p['deaths'] for p in all_participants)
        if player_stats['deaths'] == min_deaths:
            kda = (player_stats['kills'] + player_stats['assists']) / max(1, player_stats['deaths'])
            if kda >= 3.0: title = "O Intocável"

        return title, achievements

async def setup(bot: commands.Bot):
    await bot.add_cog(MatchCog(bot))