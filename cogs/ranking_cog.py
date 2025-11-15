# cogs/ranking_cog.py
import json
from datetime import datetime
from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.database_manager import db_manager
import config

class RankingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.publish_task.start()

    def cog_unload(self):
        self.publish_task.cancel()

    @app_commands.command(name="ranking", description="Mostra o ranking de PDL dos jogadores.")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def ranking(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await self._build_ranking_embed(interaction.guild, update_snapshot=False)
        if not embed:
            await interaction.followup.send("Nenhum jogador registrado ainda. Use `/registrar` para começar!")
            return
        await db_manager.increment_metadata_counter('ranking_command_used')
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ranking_publicar", description="[ADMIN] Publica o ranking em um canal e mantém atualizado")
    @app_commands.describe(canal="Canal onde o ranking será publicado")
    async def ranking_publicar(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem publicar o ranking.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        embed = await self._build_ranking_embed(interaction.guild, update_snapshot=True)
        if not embed:
            await interaction.followup.send("Nenhum jogador registrado ainda.", ephemeral=True)
            return
        message = await canal.send(embed=embed)
        await db_manager.set_metadata(f'ranking_channel_{interaction.guild_id}', str(canal.id))
        await db_manager.set_metadata(f'ranking_message_{interaction.guild_id}', str(message.id))
        await interaction.followup.send(f"✅ Ranking publicado em {canal.mention}.", ephemeral=True)

    @tasks.loop(hours=1)
    async def publish_task(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channel_id = await db_manager.get_metadata(f'ranking_channel_{guild.id}')
            message_id = await db_manager.get_metadata(f'ranking_message_{guild.id}')
            if not channel_id or not message_id:
                continue
            channel = guild.get_channel(int(channel_id))
            if not channel:
                continue
            try:
                message = await channel.fetch_message(int(message_id))
            except Exception:
                message = None
            embed = await self._build_ranking_embed(guild, update_snapshot=True)
            if not embed:
                continue
            if message:
                await message.edit(embed=embed)
            else:
                new_message = await channel.send(embed=embed)
                await db_manager.set_metadata(f'ranking_message_{guild.id}', str(new_message.id))
            await db_manager.increment_metadata_counter('ranking_embeds_updated')

    @publish_task.before_loop
    async def before_publish_task(self):
        await self.bot.wait_until_ready()

    async def _build_ranking_embed(self, guild: Optional[discord.Guild], update_snapshot: bool) -> Optional[discord.Embed]:
        players = await db_manager.get_ranking_snapshot(10)
        if not players:
            return None
        key = f'ranking_snapshot_{guild.id if guild else 0}'
        prev_snapshot = await db_manager.get_metadata(key)
        prev_map = json.loads(prev_snapshot) if prev_snapshot else {}
        snapshot_map = {}

        embed = discord.Embed(
            title="🏆 Ranking de PDL - ARAM Scrim Master 🏆",
            color=discord.Color.purple()
        )
        lines: List[str] = []
        for i, player in enumerate(players, 1):
            rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "🏅")
            riot_name = player.get('riot_id') or player.get('username') or f"ID: {player['discord_id']}"
            elo_info = config.get_elo_by_pdl(player['pdl'])
            prev_pdl = prev_map.get(str(player['discord_id']), player['pdl'])
            delta = player['pdl'] - prev_pdl
            snapshot_map[str(player['discord_id'])] = player['pdl']
            lines.append(
                f"{rank_emoji} #{i} {elo_info['emoji']} **{riot_name}** - {player['pdl']} PDL ({delta:+d})"
            )

        embed.description = "\n".join(lines)
        timestamp = datetime.utcnow().strftime('%d/%m %H:%M UTC')
        embed.set_footer(text=f"Atualizado em {timestamp}")

        if update_snapshot:
            await db_manager.set_metadata(key, json.dumps(snapshot_map))
            await db_manager.set_metadata(f'ranking_last_update_{guild.id if guild else 0}', datetime.utcnow().isoformat())
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(RankingCog(bot))
