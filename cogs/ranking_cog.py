# cogs/ranking_cog.py
import discord
from discord import app_commands
from discord.ext import commands

from utils.database_manager import db_manager

class RankingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ranking", description="Mostra o ranking de PDL dos jogadores.")
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        all_players = await db_manager.get_all_players()
        
        if not all_players:
            await interaction.followup.send("Nenhum jogador registrado ainda. Use `/registrar` para começar!")
            return
            
        embed = discord.Embed(title="🏆 Ranking de PDL - ARAM Scrim Master 🏆", color=discord.Color.purple())
        
        description = ""
        for i, player in enumerate(all_players[:20]): # Limita a exibição aos top 20
            rank_emoji = {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, f"**{i+1}.**")
            user = self.bot.get_user(player['discord_id']) or await self.bot.fetch_user(player['discord_id'])
            user_name = user.display_name if user else f"ID: {player['discord_id']}"
            
            description += (f"{rank_emoji} **{player['pdl']} PDL** - {user_name} "
                            f"({player['wins']}V / {player['losses']}D)\n")
        
        embed.description = description
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RankingCog(bot))