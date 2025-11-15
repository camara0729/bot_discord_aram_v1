import json
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.database_manager import db_manager
from utils.backup_transport import send_backup_file
from backup_restore_db import backup_database

class SeasonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="temporada_iniciar", description="[ADMIN] Inicia nova temporada com reset de PDL.")
    @app_commands.describe(nome="Nome da temporada", canal="Canal para anunciar o reset")
    async def temporada_iniciar(self, interaction: discord.Interaction, nome: str, canal: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem iniciar temporadas.", ephemeral=True)
            return
        season_active = await db_manager.get_metadata('season_active')
        if season_active == '1':
            await interaction.response.send_message("⚠️ Já existe uma temporada ativa.", ephemeral=True)
            return
        view = SeasonConfirmView(self, "start", nome, canal or interaction.channel, interaction.user)
        embed = discord.Embed(
            title="⚠️ Confirmar início da temporada",
            description=(
                "Isso irá:")
        )
        embed.add_field(name="1.", value="Gerar snapshot completo do ranking.", inline=False)
        embed.add_field(name="2.", value="Resetar PDL, vitórias, derrotas, MVPs e Bagres.", inline=False)
        embed.add_field(name="3.", value="Bloquear partidas até conclusão.", inline=False)
        embed.set_footer(text="Ação irreversível. Confirme para continuar.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="temporada_finalizar", description="[ADMIN] Finaliza temporada atual e congela ranking.")
    async def temporada_finalizar(self, interaction: discord.Interaction, canal: Optional[discord.TextChannel] = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem finalizar temporadas.", ephemeral=True)
            return
        if await db_manager.get_metadata('season_active') != '1':
            await interaction.response.send_message("⚠️ Não há temporada ativa para finalizar.", ephemeral=True)
            return
        view = SeasonConfirmView(self, "finish", None, canal or interaction.channel, interaction.user)
        embed = discord.Embed(
            title="⚠️ Confirmar fim da temporada",
            description="O ranking será congelado e as partidas ficarão bloqueadas até novo início."
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _start_season(self, interaction: discord.Interaction, nome: str, channel: discord.TextChannel):
        players = await db_manager.get_full_ranking()
        if not players:
            await interaction.followup.send("📭 Nenhum jogador registrado para reset.", ephemeral=True)
            return
        await self._ensure_backup(players, nome, stage="inicio")
        await db_manager.save_season_history(nome, players)
        await db_manager.bulk_reset_player_stats()
        now = datetime.utcnow().isoformat()
        await db_manager.set_metadata('season_active', '1')
        await db_manager.set_metadata('season_name', nome)
        await db_manager.set_metadata('season_started_at', now)
        await db_manager.set_metadata('season_started_by', str(interaction.user.id))
        await db_manager.set_metadata('season_locked', '0')
        await db_manager.increment_metadata_counter('seasons_started')
        embed = discord.Embed(
            title=f"🏁 Nova temporada: {nome}",
            description="Ranking resetado! Registre partidas para subir novamente.",
            color=discord.Color.green()
        )
        embed.add_field(name="Participantes", value=str(len(players)), inline=True)
        embed.add_field(name="Iniciado por", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Boa sorte na nova temporada!")
        await channel.send(embed=embed)
        await interaction.followup.send("✅ Temporada iniciada com sucesso!", ephemeral=True)

    async def _finish_season(self, interaction: discord.Interaction, channel: discord.TextChannel):
        players = await db_manager.get_full_ranking()
        await self._ensure_backup(players, await db_manager.get_metadata('season_name') or 'Final', stage="final")
        now = datetime.utcnow().isoformat()
        await db_manager.set_metadata('season_active', '0')
        await db_manager.set_metadata('season_locked', '1')
        await db_manager.set_metadata('season_last_finished', now)
        await db_manager.increment_metadata_counter('seasons_finished')
        embed = discord.Embed(
            title="🏆 Temporada finalizada",
            description="Ranking congelado. Inicie uma nova temporada para continuar.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Finalizado por", value=interaction.user.mention, inline=True)
        embed.add_field(name="Data", value=now, inline=True)
        await channel.send(embed=embed)
        await interaction.followup.send("✅ Temporada encerrada e ranking congelado.", ephemeral=True)

    async def _ensure_backup(self, players: list, season_name: str, stage: str):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_name = season_name.replace(' ', '_')
        filename = f"season_{safe_name}_{stage}_{timestamp}.json"
        payload = {
            'season': season_name,
            'stage': stage,
            'timestamp': timestamp,
            'players': players
        }
        with open(filename, 'w', encoding='utf-8') as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)
        await send_backup_file(filename, description=f"Temporada {season_name} ({stage})")
        try:
            await backup_database(f"backup_{safe_name}_{stage}_{timestamp}.json")
        except Exception as exc:
            print(f"⚠️ Falha ao gerar backup adicional: {exc}")

class SeasonConfirmView(discord.ui.View):
    def __init__(self, cog: SeasonCog, action: str, nome: Optional[str], channel: discord.TextChannel, author: discord.Member):
        super().__init__(timeout=60)
        self.cog = cog
        self.action = action
        self.nome = nome
        self.channel = channel
        self.author_id = author.id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        if self.action == 'start':
            await self.cog._start_season(interaction, self.nome, self.channel)
        else:
            await self.cog._finish_season(interaction, self.channel)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Operação cancelada.", view=self)

async def setup(bot: commands.Bot):
    await bot.add_cog(SeasonCog(bot))
