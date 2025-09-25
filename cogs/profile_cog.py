# cogs/profile_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import database as db
import json
import re

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balancear_times", description="Balanceia times com base no MMR dos jogadores.")
    @app_commands.describe(jogadores="Mencione todos os jogadores para a partida (6, 8 ou 10).")
    async def balance_teams(self, interaction: discord.Interaction, jogadores: str):
        await interaction.response.defer()
        
        user_ids = re.findall(r'<@!?(\d+)>', jogadores)
        
        if len(user_ids) not in [1, 2, 3]:
            await interaction.followup.send("Por favor, mencione 6, 8 ou 10 jogadores para balancear.", ephemeral=True)
            return

        player_data = []
        for user_id in user_ids:
            user = interaction.guild.get_member(int(user_id))
            if not user:
                await interaction.followup.send(f"Não foi possível encontrar o usuário com ID {user_id} no servidor.", ephemeral=True)
                return
            
            player = db.get_player_by_discord_id(user.id)
            if not player:
                await interaction.followup.send(f"O jogador {user.mention} não está registrado.", ephemeral=True)
                return
            player_data.append({'user': user, 'mmr': player['mmr']})

        player_data.sort(key=lambda x: x['mmr'], reverse=True)

        team_a, team_b = [], []
        assignment_pattern = [team_a, team_b, team_b, team_a, team_a, team_b, team_b, team_a, team_a, team_b]

        for i, player in enumerate(player_data):
            assignment_pattern[i].append(player)
            
        avg_mmr_a = sum(p['mmr'] for p in team_a) / len(team_a)
        avg_mmr_b = sum(p['mmr'] for p in team_b) / len(team_b)

        embed = discord.Embed(title="Times Balanceados", color=discord.Color.gold())
        embed.add_field(
            name=f"🔵 Equipe Azul (MMR Médio: {avg_mmr_a:.0f})",
            value="\n".join([f"{p['user'].mention} ({p['mmr']})" for p in team_a]),
            inline=True
        )
        embed.add_field(
            name=f"🔴 Equipe Vermelha (MMR Médio: {avg_mmr_b:.0f})",
            value="\n".join([f"{p['user'].mention} ({p['mmr']})" for p in team_b]),
            inline=True
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="perfil", description="Mostra o perfil de um jogador.")
    @app_commands.describe(jogador="O jogador cujo perfil você quer ver (opcional, padrão: você).")
    async def profile(self, interaction: discord.Interaction, jogador: discord.Member = None):
        await interaction.response.defer()
        target_user = jogador or interaction.user
        player = db.get_player_by_discord_id(target_user.id)

        if not player:
            await interaction.followup.send(f"{target_user.mention} não está registrado.", ephemeral=True)
            return

        stats = json.loads(player['stats'])
        achievements = json.loads(player['achievements'])
        
        kda = (stats['lifetime_kills'] + stats['lifetime_assists']) / max(1, stats['lifetime_deaths'])
        win_rate = (stats['wins'] / max(1, stats['total_games'])) * 100 if stats['total_games'] > 0 else 0

        embed = discord.Embed(title=f"Perfil de {player['riot_id']}", color=target_user.color)
        if target_user.avatar:
            embed.set_thumbnail(url=target_user.avatar.url)
        
        embed.add_field(name="MMR", value=f"**{player['mmr']}**", inline=True)
        embed.add_field(name="Título Atual", value=player['current_title'] or "Nenhum", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.add_field(name="Vitórias", value=stats['wins'], inline=True)
        embed.add_field(name="Derrotas", value=stats['losses'], inline=True)
        embed.add_field(name="Taxa de Vitória", value=f"{win_rate:.2f}%", inline=True)
        
        embed.add_field(name="KDA Médio", value=f"{kda:.2f}", inline=True)
        embed.add_field(name="Total de Partidas", value=stats['total_games'], inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        if achievements:
            embed.add_field(name="🏆 Conquistas", value=" | ".join(achievements), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ranking", description="Exibe o ranking de MMR do servidor.")
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        players = db.get_all_players()
        
        embed = discord.Embed(title="🏆 Ranking de MMR - Top 10", color=discord.Color.purple())
        
        description = ""
        for i, player in enumerate(players[:10]):
            user = interaction.guild.get_member(int(player['discord_id']))
            stats = json.loads(player['stats'])
            win_rate = (stats['wins'] / max(1, stats['total_games'])) * 100 if stats['total_games'] > 0 else 0
            description += f"**{i+1}.** {user.mention if user else player['riot_id']} - **{player['mmr']} MMR** ({win_rate:.1f}% WR)\n"
            
        if not description:
            description = "Nenhum jogador no ranking ainda."
            
        embed.description = description
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))