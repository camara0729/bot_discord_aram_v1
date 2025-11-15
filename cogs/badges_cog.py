import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

from utils.database_manager import db_manager
from utils.ops_logger import log_ops_event

BADGE_CHOICES = [
    app_commands.Choice(name="Fila Ativa", value="queue_active"),
    app_commands.Choice(name="Top Ranking", value="top_rank")
]

class BadgesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    badges = app_commands.Group(name="badges", description="Gerencie badges e roles automáticas")

    @badges.command(name="configurar", description="[ADMIN] Configura uma badge")
    @app_commands.describe(role="Role que será atribuída", criterio="Critério adicional (ex.: quantidade de jogadores, etc)")
    @app_commands.choices(badge=BADGE_CHOICES)
    async def configurar(self, interaction: discord.Interaction, badge: app_commands.Choice[str], role: discord.Role, criterio: Optional[str] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem configurar badges.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        await db_manager.upsert_badge_config(interaction.guild_id, badge.value, badge.name, role.id, criterio)
        await interaction.followup.send(f"✅ Badge `{badge.name}` associada à role {role.mention}", ephemeral=True)

    @badges.command(name="listar", description="Lista as badges configuradas")
    async def listar(self, interaction: discord.Interaction):
        configs = await db_manager.get_badge_configs(interaction.guild_id)
        if not configs:
            await interaction.response.send_message("📭 Nenhuma badge configurada.", ephemeral=True)
            return
        embed = discord.Embed(title="Badges configuradas", color=discord.Color.gold())
        for cfg in configs:
            role = interaction.guild.get_role(cfg['role_id'])
            embed.add_field(
                name=f"{cfg['name']} ({cfg['badge_type']})",
                value=f"Role: {role.mention if role else cfg['role_id']}\nCritério: {cfg.get('criteria_value') or '—'}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @badges.command(name="claim", description="Força uma reavaliação das suas badges")
    async def claim(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.update_top_rank_badge(interaction.guild, notify=False)
        fairplay = self.bot.get_cog('FairPlayCog')
        await interaction.followup.send("🔔 Reavaliação executada!", ephemeral=True)

    async def assign_queue_badge(self, member: discord.Member, remove: bool = False):
        config = await db_manager.get_badge_config(member.guild.id, 'queue_active')
        if not config:
            return
        role = member.guild.get_role(config['role_id'])
        if not role or not await self._has_role_permissions(member.guild, role):
            return
        if remove:
            if role in member.roles:
                await member.remove_roles(role, reason='Queue finalizada')
                await db_manager.remove_badge_assignment(member.guild.id, role.id, member.id)
                await db_manager.increment_metadata_counter('badge_roles_removed')
            return
        if role in member.roles:
            return
        await member.add_roles(role, reason='Fila ativa')
        await db_manager.record_badge_assignment(member.guild.id, role.id, member.id)
        await db_manager.increment_metadata_counter('badge_roles_assigned')

    async def update_top_rank_badge(self, guild: discord.Guild, notify: bool = True):
        config = await db_manager.get_badge_config(guild.id, 'top_rank')
        if not config:
            return
        role = guild.get_role(config['role_id'])
        if not role or not await self._has_role_permissions(guild, role):
            return
        top_count = int(config.get('criteria_value') or 5)
        players = await db_manager.get_all_players()
        top_players = [p['discord_id'] for p in players[:top_count]]
        current_holders = await db_manager.list_badge_holders(guild.id, role.id)
        to_add = set(top_players) - set(current_holders)
        to_remove = set(current_holders) - set(top_players)
        for discord_id in to_add:
            member = guild.get_member(discord_id)
            if not member:
                continue
            if role not in member.roles:
                await member.add_roles(role, reason='Top ranking badge')
            await db_manager.record_badge_assignment(guild.id, role.id, discord_id)
            await db_manager.increment_metadata_counter('badge_roles_assigned')
            if notify:
                await self._notify_member(member, role)
        for discord_id in to_remove:
            member = guild.get_member(discord_id)
            if member and role in member.roles:
                await member.remove_roles(role, reason='Saiu do Top ranking')
                await db_manager.increment_metadata_counter('badge_roles_removed')
            await db_manager.remove_badge_assignment(guild.id, role.id, discord_id)

    async def _notify_member(self, member: discord.Member, role: discord.Role):
        try:
            await member.send(f"🎉 Você recebeu a role especial {role.name} no servidor {member.guild.name}!")
        except Exception:
            pass

    async def _has_role_permissions(self, guild: discord.Guild, role: discord.Role) -> bool:
        me = guild.me
        if not me or role.position >= me.top_role.position:
            await log_ops_event('badges.role_hierarchy', guild_id=guild.id, details={'role_id': role.id})
            return False
        return True

async def setup(bot: commands.Bot):
    await bot.add_cog(BadgesCog(bot))
