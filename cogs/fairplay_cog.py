import os
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.database_manager import db_manager
from utils.ops_logger import log_ops_event

FAIRPLAY_LIMIT_DEFAULT = int(os.getenv('FAIRPLAY_LIMIT', '3'))
FAIRPLAY_TIMEOUT_DEFAULT = int(os.getenv('FAIRPLAY_TIMEOUT_MINUTES', '30'))

class FairPlayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.group = app_commands.Group(name="fairplay", description="Gerencie incidentes de fair play")
        self.group.command(name="registrar", description="[ADMIN] Registra um incidente de fair play.")(self.registrar)
        self.group.command(name="resolver", description="[ADMIN] Resolve um incidente.")(self.resolver)
        self.group.command(name="listar", description="Lista incidentes de um jogador.")(self.listar)
        self.group.command(name="configurar", description="[ADMIN] Ajusta limites de penalidade.")(self.configurar)

    async def cog_load(self):
        self.bot.tree.add_command(self.group)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.group.name, type=self.group.type)

    async def registrar(self, interaction: discord.Interaction, jogador: discord.Member, motivo: str, descricao: Optional[str] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem registrar incidentes.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        limit, timeout = await self._thresholds(interaction.guild_id)
        incident_id = await db_manager.add_fairplay_incident(
            guild_id=interaction.guild_id,
            discord_id=jogador.id,
            reason=motivo,
            description=descricao or "",
            created_by=interaction.user.id
        )
        await db_manager.increment_metadata_counter('fairplay_incidents')
        active = await db_manager.count_active_incidents(interaction.guild_id, jogador.id)
        penalty_info = None
        if active >= limit:
            penalty_until = (datetime.utcnow() + timedelta(minutes=timeout)).isoformat()
            await db_manager.set_incident_penalty(incident_id, penalty_until)
            penalty_info = penalty_until
            await db_manager.increment_metadata_counter('fairplay_penalties_applied')
            await self._notify_penalty(interaction.guild, jogador, penalty_until, motivo)
        embed = discord.Embed(
            title="🚨 Incidente registrado",
            description=f"Jogador: {jogador.mention}\nMotivo: **{motivo}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Incidentes ativos", value=str(active), inline=True)
        if penalty_info:
            embed.add_field(name="Penalidade", value=f"Bloqueado até {penalty_info}", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        await log_ops_event('fairplay.incident', guild_id=interaction.guild_id, user_id=jogador.id, details={'incident_id': incident_id, 'reason': motivo})

    async def resolver(self, interaction: discord.Interaction, incidente_id: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem resolver incidentes.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        resolved = await db_manager.resolve_fairplay_incident(incidente_id, interaction.user.id)
        if resolved:
            await db_manager.increment_metadata_counter('fairplay_resolved')
            await interaction.followup.send(f"✅ Incidente `{incidente_id}` resolvido.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Incidente não encontrado ou já resolvido.", ephemeral=True)

    async def listar(self, interaction: discord.Interaction, jogador: Optional[discord.Member] = None):
        target = jogador or interaction.user
        incidents = await db_manager.list_fairplay_incidents(interaction.guild_id, target.id, limit=10)
        if not incidents:
            await interaction.response.send_message("📭 Nenhum incidente registrado.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Histórico de Fair Play - {target.display_name}", color=discord.Color.blurple())
        for incident in incidents:
            status = incident['status']
            penalty = incident['penalty_until'] or '—'
            embed.add_field(
                name=f"ID {incident['id']} • {status.upper()}",
                value=f"Motivo: {incident['reason']}\nPenalidade até: {penalty}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def configurar(self, interaction: discord.Interaction, limite: int, timeout_minutos: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem configurar.", ephemeral=True)
            return
        await db_manager.set_metadata(f'fairplay_limit_{interaction.guild_id}', str(limite))
        await db_manager.set_metadata(f'fairplay_timeout_{interaction.guild_id}', str(timeout_minutos))
        await interaction.response.send_message(f"✅ Limite atualizado para {limite} incidentes e {timeout_minutos} minutos de bloqueio.", ephemeral=True)

    async def _thresholds(self, guild_id: int):
        limit_meta = await db_manager.get_metadata(f'fairplay_limit_{guild_id}')
        timeout_meta = await db_manager.get_metadata(f'fairplay_timeout_{guild_id}')
        limit = int(limit_meta) if limit_meta else FAIRPLAY_LIMIT_DEFAULT
        timeout = int(timeout_meta) if timeout_meta else FAIRPLAY_TIMEOUT_DEFAULT
        return limit, timeout

    async def _notify_penalty(self, guild: discord.Guild, member: discord.Member, penalty_until: str, reason: str):
        message = (
            f"⚠️ {member.mention}, você atingiu o limite de incidentes ({reason}).\n"
            f"Você está bloqueado de participar por {penalty_until}. Procure a moderação se necessário."
        )
        channel = guild.system_channel or guild.text_channels[0]
        if channel:
            await channel.send(message)
        try:
            await member.send(
                f"Você recebeu uma penalidade no servidor {guild.name}. Bloqueio até {penalty_until}."
            )
        except Exception:
            pass

    async def check_penalty(self, guild_id: int, member: discord.Member) -> Optional[str]:
        info = await db_manager.is_player_under_penalty(guild_id, member.id)
        if not info:
            return None
        return f"⚠️ {member.mention}, você está bloqueado até {info['penalty_until']} devido à política de fair play."

async def setup(bot: commands.Bot):
    await bot.add_cog(FairPlayCog(bot))
