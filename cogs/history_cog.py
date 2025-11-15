import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from typing import Optional, List

from utils.database_manager import db_manager

class HistoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_cards_task.start()

    def cog_unload(self):
        self.weekly_cards_task.cancel()

    @app_commands.command(name="historico", description="Mostra o histórico recente de um jogador.")
    @app_commands.describe(
        jogador="Jogador alvo (opcional)",
        periodo="Período em dias (1-90)"
    )
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.guild_id, i.user.id))
    async def historico(self, interaction: discord.Interaction, jogador: Optional[discord.Member] = None, periodo: app_commands.Range[int, 1, 90] = 30):
        target = jogador or interaction.user
        player_data = await db_manager.get_player(target.id)
        if not player_data:
            await interaction.response.send_message("❌ Jogador não registrado.", ephemeral=True)
            return

        await interaction.response.defer()
        matches = await db_manager.get_recent_matches_for_player(target.id, periodo, limit=50)
        if not matches:
            await interaction.followup.send(f"📭 Nenhuma partida encontrada nos últimos {periodo} dias.", ephemeral=True)
            return

        stats = self._compute_stats(matches)
        embed = discord.Embed(
            title=f"Histórico de {player_data.get('riot_id') or target.display_name}",
            color=discord.Color.teal()
        )
        embed.add_field(name="Período", value=f"{periodo} dias", inline=True)
        embed.add_field(name="Partidas", value=f"{stats['wins']}V / {stats['losses']}D", inline=True)
        embed.add_field(name="Streak", value=stats['streak_text'], inline=True)
        embed.add_field(name="Média de PDL", value=f"{stats['avg_pdl']:+.1f}", inline=True)
        embed.add_field(name="MVPs consecutivos", value=str(stats['mvp_streak']), inline=True)
        embed.add_field(name="Destaque", value=stats['highlight'], inline=False)
        embed.add_field(name="Últimas partidas", value=stats['recent_text'], inline=False)
        embed.set_footer(text="Dados baseados nos registros do bot")

        await interaction.followup.send(embed=embed)
        await db_manager.increment_metadata_counter('historico_used')

    @app_commands.command(name="historico_configurar_cartao", description="Define canal para o cartão semanal de destaques.")
    @app_commands.describe(canal="Canal que receberá os cartões")
    async def configurar_cartao(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem configurar.", ephemeral=True)
            return
        await db_manager.set_metadata(f'weekly_channel_{interaction.guild_id}', str(canal.id))
        await interaction.response.send_message(f"✅ Cartões semanais enviados em {canal.mention}.", ephemeral=True)

    @app_commands.command(name="historico_enviar_cartao", description="Gera cartão semanal agora.")
    async def enviar_cartao(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem enviar o cartão.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        channel_id = await db_manager.get_metadata(f'weekly_channel_{interaction.guild_id}')
        if not channel_id:
            await interaction.followup.send("⚠️ Configure um canal com `/historico_configurar_cartao`.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.followup.send("⚠️ Canal configurado não encontrado.", ephemeral=True)
            return
        embed = await self._build_weekly_card(interaction.guild.id, interaction.guild.name)
        if not embed:
            await interaction.followup.send("📭 Sem partidas suficientes para gerar o cartão.", ephemeral=True)
            return
        await channel.send(embed=embed)
        await db_manager.set_metadata(f'weekly_card_last_{interaction.guild_id}', datetime.utcnow().isoformat())
        await interaction.followup.send("✅ Cartão enviado!", ephemeral=True)

    def _compute_stats(self, matches: List[dict]) -> dict:
        wins = sum(1 for m in matches if m.get('result') == 'win')
        losses = sum(1 for m in matches if m.get('result') == 'loss')
        avg_pdl = sum(m.get('pdl_change', 0) for m in matches) / len(matches)
        streak_type = matches[0].get('result')
        streak = 0
        for match in matches:
            if match.get('result') == streak_type:
                streak += 1
            else:
                break
        streak_text = f"{streak} {'vitórias' if streak_type == 'win' else 'derrotas'}"
        mvp_streak = 0
        current = 0
        for match in matches:
            if match.get('is_mvp'):
                current += 1
                mvp_streak = max(mvp_streak, current)
            else:
                current = 0
        recent_lines = []
        for match in matches[:5]:
            icon = '✅' if match.get('result') == 'win' else '❌'
            delta = match.get('pdl_change', 0)
            timestamp = match.get('created_at')
            recent_lines.append(f"{icon} {timestamp[:10]} • {delta:+} PDL")
        highlight = "Sem destaques recentes"
        if mvp_streak >= 2:
            highlight = f"⭐ {mvp_streak} MVPs consecutivos"
        elif abs(avg_pdl) >= 10:
            highlight = f"🔥 Variação média de {avg_pdl:+.1f} PDL"
        return {
            'wins': wins,
            'losses': losses,
            'avg_pdl': avg_pdl,
            'streak_text': streak_text,
            'mvp_streak': mvp_streak,
            'recent_text': "\n".join(recent_lines),
            'highlight': highlight,
        }

    async def _build_weekly_card(self, guild_id: int, guild_name: str) -> Optional[discord.Embed]:
        rows = await db_manager.get_guild_recent_participation(guild_id, days=7)
        if not rows:
            return None
        stats = {}
        for row in rows:
            data = stats.setdefault(row['discord_id'], {'wins': 0, 'losses': 0, 'mvps': 0, 'pdl': 0})
            if row.get('result') == 'win':
                data['wins'] += 1
            elif row.get('result') == 'loss':
                data['losses'] += 1
            if row.get('is_mvp'):
                data['mvps'] += 1
            data['pdl'] += row.get('pdl_change', 0)
        sorted_by_wins = sorted(stats.items(), key=lambda item: item[1]['wins'], reverse=True)
        sorted_by_mvps = sorted(stats.items(), key=lambda item: item[1]['mvps'], reverse=True)
        embed = discord.Embed(
            title=f"🏅 Destaques da Semana - {guild_name}",
            description="Últimos 7 dias",
            color=discord.Color.gold()
        )
        def format_entry(discord_id, data):
            return f"<@{discord_id}> • {data['wins']}V/{data['losses']}D • ⭐ {data['mvps']} • {data['pdl']:+} PDL"
        top_wins = [format_entry(pid, data) for pid, data in sorted_by_wins[:3]]
        top_mvps = [format_entry(pid, data) for pid, data in sorted_by_mvps[:3]]
        embed.add_field(name="Top Vitórias", value="\n".join(top_wins) or "Sem dados", inline=False)
        embed.add_field(name="Top MVPs", value="\n".join(top_mvps) or "Sem dados", inline=False)
        embed.set_footer(text="Gerado automaticamente pelo bot ARAM")
        return embed

    @tasks.loop(hours=24)
    async def weekly_cards_task(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            channel_id = await db_manager.get_metadata(f'weekly_channel_{guild.id}')
            if not channel_id:
                continue
            last_run = await db_manager.get_metadata(f'weekly_card_last_{guild.id}')
            if last_run:
                try:
                    last_dt = datetime.fromisoformat(last_run)
                    if datetime.utcnow() - last_dt < timedelta(days=7):
                        continue
                except ValueError:
                    pass
            channel = guild.get_channel(int(channel_id))
            if not channel:
                continue
            embed = await self._build_weekly_card(guild.id, guild.name)
            if not embed:
                continue
            await channel.send(embed=embed)
            await db_manager.set_metadata(f'weekly_card_last_{guild.id}', datetime.utcnow().isoformat())

async def setup(bot: commands.Bot):
    await bot.add_cog(HistoryCog(bot))
