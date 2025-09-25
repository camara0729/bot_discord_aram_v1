# cogs/match_cog.py
import discord
from discord import app_commands
from discord.ext import commands
import itertools
import re
from typing import List, Optional

from utils.database_manager import db_manager
import config

# Variável global para armazenar temporariamente os times gerados
# Em uma aplicação de produção maior, isso seria gerenciado por um cache (ex: Redis)
# ou uma tabela de "partidas pendentes" no banco de dados.
# Para este escopo, uma variável global simples é suficiente.
last_generated_teams = {}

class MatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="times", description="Forma times balanceados para uma partida de ARAM.")
    @app_commands.describe(jogadores="Mencione de 2 a 10 jogadores registrados para a partida.")
    async def times(self, interaction: discord.Interaction, jogadores: str):
        
        await interaction.response.defer()
        
        # CORREÇÃO: Lógica de parsing de menções de usuário
        try:
            player_ids = [int(uid) for uid in re.findall(r'\d+', jogadores)]
        except (ValueError, TypeError):
            await interaction.followup.send("Formato de jogadores inválido. Por favor, mencione os jogadores usando `@`.", ephemeral=True)
            return

        if not (2 <= len(player_ids) <= 10) or len(player_ids) % 2!= 0:
            await interaction.followup.send("O número de jogadores deve ser par, entre 2 e 10.", ephemeral=True)
            return

        players_data = []
        for pid in player_ids:
            player = await db_manager.get_player(pid)
            if not player:
                user = await self.bot.fetch_user(pid)
                await interaction.followup.send(f"O jogador {user.mention} não está registrado. Use `/registrar`.", ephemeral=True)
                return
            players_data.append(player)

        # Algoritmo de balanceamento por força bruta
        team_size = len(players_data) // 2
        best_teams = None
        min_pdl_diff = float('inf')

        for team1_combination in itertools.combinations(players_data, team_size):
            team1_pdl = sum(p['pdl'] for p in team1_combination)
            
            team2_players = [p for p in players_data if p not in team1_combination]
            team2_pdl = sum(p['pdl'] for p in team2_players)
            
            pdl_diff = abs(team1_pdl - team2_pdl)
            
            if pdl_diff < min_pdl_diff:
                min_pdl_diff = pdl_diff
                best_teams = (list(team1_combination), team2_players)

        # Armazena os times gerados para o comando /resultado
        global last_generated_teams
        # CORREÇÃO: Acessa corretamente os times da tupla 'best_teams'
        last_generated_teams[interaction.channel.id] = {
            'team1': [p['discord_id'] for p in best_teams],
            'team2': [p['discord_id'] for p in best_teams[49]]
        }

        # Cria a resposta visual
        embed = discord.Embed(title="⚔️ Times Balanceados para o ARAM! ⚔️", color=discord.Color.blue())
        
        # CORREÇÃO: Acessa corretamente os times para criar as menções
        team1_mentions = [f"<@{p['discord_id']}> ({p['pdl']} PDL)" for p in best_teams]
        team1_total_pdl = sum(p['pdl'] for p in best_teams)
        embed.add_field(name=f"🔵 Time 1 (Total: {team1_total_pdl} PDL)", value="\n".join(team1_mentions), inline=False)

        team2_mentions = [f"<@{p['discord_id']}> ({p['pdl']} PDL)" for p in best_teams[49]]
        team2_total_pdl = sum(p['pdl'] for p in best_teams[49])
        embed.add_field(name=f"🔴 Time 2 (Total: {team2_total_pdl} PDL)", value="\n".join(team2_mentions), inline=False)
        
        embed.set_footer(text=f"Diferença de PDL: {min_pdl_diff}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="resultado", description="Reporta o resultado da última partida gerada neste canal.")
    @app_commands.describe(vencedores="Mencione todos os jogadores do time vencedor.", mvp="O melhor jogador da partida.", bagre="O pior jogador da partida.")
    async def resultado(self, interaction: discord.Interaction, vencedores: str, mvp: Optional[discord.Member] = None, bagre: Optional[discord.Member] = None):
        await interaction.response.defer()
        
        channel_id = interaction.channel.id
        if channel_id not in last_generated_teams:
            await interaction.followup.send("Nenhum time foi gerado recentemente neste canal. Use `/times` primeiro.", ephemeral=True)
            return

        teams = last_generated_teams[channel_id]
        all_players_ids = teams['team1'] + teams['team2']
        
        # CORREÇÃO: Lógica de parsing de menções de usuário
        try:
            winner_ids = {int(uid) for uid in re.findall(r'\d+', vencedores)}
        except (ValueError, TypeError):
            await interaction.followup.send("Formato de vencedores inválido. Por favor, mencione os jogadores usando `@`.", ephemeral=True)
            return

        # Validação
        if not winner_ids.issubset(set(all_players_ids)):
            await interaction.followup.send("Um ou mais vencedores mencionados não estavam na partida original.", ephemeral=True)
            return
        
        if mvp and mvp.id not in all_players_ids:
            await interaction.followup.send("O MVP mencionado não estava na partida.", ephemeral=True)
            return
        
        if bagre and bagre.id not in all_players_ids:
            await interaction.followup.send("O Bagre mencionado não estava na partida.", ephemeral=True)
            return

        if mvp and bagre and mvp.id == bagre.id:
            await interaction.followup.send("O MVP e o Bagre não podem ser o mesmo jogador.", ephemeral=True)
            return

        # Determina o time vencedor
        if winner_ids.issubset(set(teams['team1'])):
            winning_team_num = 1
            losing_team_ids = teams['team2']
        elif winner_ids.issubset(set(teams['team2'])):
            winning_team_num = 2
            losing_team_ids = teams['team1']
        else:
            await interaction.followup.send("Os vencedores mencionados não formam um time completo da partida anterior.", ephemeral=True)
            return

        # Busca dados dos jogadores para cálculo de PDL
        winner_players_data = [await db_manager.get_player(pid) for pid in winner_ids]
        loser_players_data = [await db_manager.get_player(pid) for pid in losing_team_ids]

        avg_pdl_winners = sum(p['pdl'] for p in winner_players_data) / len(winner_players_data)
        avg_pdl_losers = sum(p['pdl'] for p in loser_players_data) / len(loser_players_data)

        # Cálculo de PDL (Elo)
        expected_win_winners = 1 / (1 + 10**((avg_pdl_losers - avg_pdl_winners) / 400))
        pdl_change = int(config.K_FACTOR * (1 - expected_win_winners))
        
        # Bônus/Penalidade para MVP e Bagre
        pdl_change_mvp = pdl_change + config.MVP_BONUS_PDL
        pdl_change_bagre = -pdl_change - config.BAGRE_PENALTY_PDL

        participants_data = []
        embed = discord.Embed(title=f"🏁 Resultado da Partida Registrado! 🏁", description=f"Time {winning_team_num} foi o vencedor!", color=discord.Color.gold())
        
        # Processa vencedores
        winner_details = []
        for p in winner_players_data:
            delta = pdl_change_mvp if mvp and p['discord_id'] == mvp.id else pdl_change
            participants_data.append({'discord_id': p['discord_id'], 'team_number': winning_team_num, 'pdl_delta': delta, 'is_mvp': (mvp and p['discord_id'] == mvp.id)})
            winner_details.append(f"<@{p['discord_id']}>: {p['pdl']} `+{delta}` ➔ **{p['pdl'] + delta} PDL** {'⭐' if mvp and p['discord_id'] == mvp.id else ''}")
        
        # Processa perdedores
        loser_details = []
        for p in loser_players_data:
            delta = pdl_change_bagre if bagre and p['discord_id'] == bagre.id else -pdl_change
            participants_data.append({'discord_id': p['discord_id'], 'team_number': 3 - winning_team_num, 'pdl_delta': delta, 'is_bagre': (bagre and p['discord_id'] == bagre.id)})
            loser_details.append(f"<@{p['discord_id']}>: {p['pdl']} `{delta}` ➔ **{p['pdl'] + delta} PDL** {'💩' if bagre and p['discord_id'] == bagre.id else ''}")

        # Salva no banco de dados
        await db_manager.create_match_record(winning_team_num, participants_data)

        embed.add_field(name="🏆 Vencedores", value="\n".join(winner_details), inline=False)
        embed.add_field(name="💔 Perdedores", value="\n".join(loser_details), inline=False)
        
        await interaction.followup.send(embed=embed)
        
        # Limpa os times gerados para este canal
        del last_generated_teams[channel_id]


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchCog(bot))