# cogs/ranking_cog.py
import discord
from discord import app_commands
from discord.ext import commands

from utils.database_manager import db_manager
import config

class RankingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ranking", description="Mostra o ranking de PDL dos jogadores.")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        all_players = await db_manager.get_all_players()
        
        if not all_players:
            await interaction.followup.send("Nenhum jogador registrado ainda. Use `/registrar` para começar!")
            return
            
        embed = discord.Embed(
            title="🏆 Ranking de PDL - ARAM Scrim Master 🏆",
            color=discord.Color.purple()
        )
        
        description = ""
        for i, player in enumerate(all_players[:20]):  # Limita a exibição aos top 20
            rank_emoji = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "🏅")
            riot_name = player.get('riot_id') or player.get('username')
            if not riot_name:
                user = self.bot.get_user(player['discord_id'])
                if not user:
                    try:
                        user = await self.bot.fetch_user(player['discord_id'])
                    except Exception:
                        user = None
                riot_name = user.display_name if user else f"ID: {player['discord_id']}"

            elo_info = config.get_elo_by_pdl(player['pdl'])
            position = i + 1
            wins = player['wins']
            losses = player['losses']
            mvp_count = player.get('mvp_count', 0)
            bagre_count = player.get('bagre_count', 0)
            
            description += (
                f"{rank_emoji} #{position} {elo_info['emoji']} **{riot_name}** - {player['pdl']} PDL "
                f"({wins}V/{losses}D) • ⭐ {mvp_count} • 💩 {bagre_count}\n"
            )
        
        embed.description = description
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RankingCog(bot))
