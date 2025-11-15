import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import List

import config
from utils.database_manager import db_manager
from utils.last_team_store import save_last_teams

class QueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue_group = app_commands.Group(name="fila", description="Gerencie filas ARAM")
        self.queue_group.command(name="criar", description="Crie uma fila de jogadores para partidas ARAM.")(self.create_queue)
        self.queue_group.command(name="status", description="Mostra o status das filas ativas.")(self.queue_status)
        self.queue_group.command(name="cancelar", description="Cancela uma fila específica.")(self.cancel_queue)

    async def cog_load(self):
        self.bot.tree.add_command(self.queue_group)
        await self._restore_views()

    async def cog_unload(self):
        self.bot.tree.remove_command(self.queue_group.name, type=self.queue_group.type)

    async def _restore_views(self):
        queues = await db_manager.get_active_queues()
        for queue in queues:
            view = QueueView(self, queue['id'])
            self.bot.add_view(view, message_id=queue['message_id'])

    @app_commands.describe(
        nome="Nome da fila",
        modo="Modo ou descrição da fila",
        slots="Número de vagas (4 a 10)",
        canal="Canal onde o painel será criado"
    )
    async def create_queue(self, interaction: discord.Interaction, nome: str, modo: str = "ARAM", slots: app_commands.Range[int, 4, 10] = 10, canal: discord.TextChannel | None = None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Apenas administradores podem criar filas.", ephemeral=True)
            return

        target_channel = canal or interaction.channel
        if not target_channel:
            await interaction.followup.send("❌ Não foi possível determinar o canal para publicar a fila.", ephemeral=True)
            return

        existing = await db_manager.get_queue_by_name(interaction.guild_id, nome)
        if existing and existing['status'] == 'aberta':
            await interaction.followup.send("❌ Já existe uma fila aberta com esse nome.", ephemeral=True)
            return

        queue_id = await db_manager.create_queue(
            guild_id=interaction.guild_id,
            channel_id=target_channel.id,
            message_id=0,
            name=nome,
            mode=modo,
            slots=slots,
            created_by=interaction.user.id
        )

        view = QueueView(self, queue_id)
        embed = await self._build_queue_embed({
            'id': queue_id,
            'name': nome,
            'mode': modo,
            'slots': slots,
            'guild_id': interaction.guild_id,
            'status': 'aberta'
        }, [])
        message = await target_channel.send(embed=embed, view=view)
        self.bot.add_view(view, message_id=message.id)
        await db_manager.update_queue_message(queue_id, message.id)
        await interaction.followup.send(f"✅ Fila `{nome}` criada em {target_channel.mention}!", ephemeral=True)

    @app_commands.describe(nome="Nome da fila (opcional)" )
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.guild_id, i.user.id))
    async def queue_status(self, interaction: discord.Interaction, nome: str = None):
        await interaction.response.defer(ephemeral=True)
        if nome:
            queue = await db_manager.get_queue_by_name(interaction.guild_id, nome)
            if not queue:
                await interaction.followup.send("❌ Fila não encontrada.", ephemeral=True)
                return
            players = await db_manager.get_queue_players(queue['id'])
            embed = await self._build_queue_embed(queue, players)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        queues = await db_manager.get_active_queues(interaction.guild_id)
        if not queues:
            await interaction.followup.send("Não há filas abertas no momento.", ephemeral=True)
            return

        embed = discord.Embed(title="Filas ativas", color=discord.Color.blue())
        for queue in queues:
            players = await db_manager.get_queue_players(queue['id'])
            embed.add_field(
                name=f"{queue['name']} - {len(players)}/{queue['slots']}",
                value=", ".join([f"<@{pid}>" for pid in players]) or "Sem jogadores",
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.describe(nome="Nome da fila a cancelar")
    async def cancel_queue(self, interaction: discord.Interaction, nome: str):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Apenas administradores podem cancelar filas.", ephemeral=True)
            return

        queue = await db_manager.get_queue_by_name(interaction.guild_id, nome)
        if not queue or queue['status'] != 'aberta':
            await interaction.followup.send("❌ Fila não encontrada ou já finalizada.", ephemeral=True)
            return

        await db_manager.update_queue_status(queue['id'], 'cancelada')
        await self._edit_queue_message(queue, "❌ Fila cancelada", discord.Color.red(), None)
        await interaction.followup.send(f"🛑 Fila `{nome}` cancelada.", ephemeral=True)

    async def handle_join(self, interaction: discord.Interaction, queue_id: int):
        queue = await db_manager.get_queue(queue_id)
        if not queue or queue['status'] != 'aberta':
            await interaction.response.send_message("❌ Esta fila não está mais ativa.", ephemeral=True)
            return

        player = await db_manager.get_player(interaction.user.id)
        if not player:
            await interaction.response.send_message("❌ Você precisa se registrar primeiro com `/registrar`.", ephemeral=True)
            return

        added = await db_manager.add_player_to_queue(queue_id, interaction.user.id)
        if not added:
            await interaction.response.send_message("⚠️ Você já está participando desta fila.", ephemeral=True)
            return

        players = await db_manager.get_queue_players(queue_id)
        await self._update_queue_embed(queue, players, interaction)
        await interaction.response.send_message("✅ Você entrou na fila!", ephemeral=True)

        if len(players) >= queue['slots']:
            await db_manager.update_queue_status(queue_id, 'montando')
            await self._finalize_queue(queue, players)

    async def handle_leave(self, interaction: discord.Interaction, queue_id: int):
        queue = await db_manager.get_queue(queue_id)
        if not queue or queue['status'] != 'aberta':
            await interaction.response.send_message("❌ Esta fila não está mais ativa.", ephemeral=True)
            return

        removed = await db_manager.remove_player_from_queue(queue_id, interaction.user.id)
        if not removed:
            await interaction.response.send_message("⚠️ Você não estava na fila.", ephemeral=True)
            return

        players = await db_manager.get_queue_players(queue_id)
        await self._update_queue_embed(queue, players, interaction)
        await interaction.response.send_message("🚪 Você saiu da fila.", ephemeral=True)

    async def _build_queue_embed(self, queue: dict, players: List[int]):
        embed = discord.Embed(
            title=f"Fila: {queue['name']}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Modo", value=queue['mode'], inline=True)
        embed.add_field(name="Slots", value=f"{len(players)}/{queue['slots']}", inline=True)
        embed.add_field(
            name="Participantes",
            value="\n".join([f"{idx+1}. <@{pid}>" for idx, pid in enumerate(players)]) or "Sem jogadores",
            inline=False
        )
        embed.set_footer(text="Fila automática - Clique nos botões para participar")
        return embed

    async def _update_queue_embed(self, queue: dict, players: List[int], interaction: discord.Interaction | None):
        embed = await self._build_queue_embed(queue, players)
        view = QueueView(self, queue['id'])
        target_message = None
        if interaction and interaction.message:
            target_message = interaction.message
        else:
            target_message = await self._fetch_queue_message(queue)
        if target_message:
            await target_message.edit(embed=embed, view=view)
            self.bot.add_view(view, message_id=target_message.id)

    async def _finalize_queue(self, queue: dict, players: List[int]):
        guild = self.bot.get_guild(queue['guild_id'])
        channel = guild.get_channel(queue['channel_id']) if guild else None
        if not guild or not channel:
            await db_manager.update_queue_status(queue['id'], 'erro')
            print(f"❌ Não foi possível localizar guild ou canal para fila {queue['name']}")
            return

        team_cog = self.bot.get_cog('TeamCog')
        if not team_cog:
            await db_manager.update_queue_status(queue['id'], 'erro')
            await channel.send("❌ Não foi possível montar os times: TeamCog não está carregado.")
            return

        players_data = []
        members_missing = []
        for player_id in players:
            member = guild.get_member(player_id)
            if not member:
                try:
                    member = await guild.fetch_member(player_id)
                except Exception:
                    members_missing.append(player_id)
                    continue
            player_data = await db_manager.get_player(player_id)
            if not player_data:
                members_missing.append(player_id)
                continue
            balance_score = config.calculate_balance_score(
                player_data['pdl'],
                player_data.get('lol_rank', 'PRATA II'),
                player_data['wins'],
                player_data['losses']
            )
            players_data.append({'user': member, 'data': player_data, 'balance_score': balance_score})

        if members_missing:
            await db_manager.update_queue_status(queue['id'], 'aberta')
            for pid in members_missing:
                await db_manager.remove_player_from_queue(queue['id'], pid)
            players = await db_manager.get_queue_players(queue['id'])
            await channel.send(
                "⚠️ Não foi possível montar times porque alguns jogadores não estão disponíveis: " +
                ", ".join([f"<@{pid}>" for pid in members_missing])
            )
            await self._update_queue_embed(queue, players, None)
            return

        blue_team, red_team = team_cog._balance_teams(players_data)
        blue_avg = sum(p['balance_score'] for p in blue_team) / len(blue_team)
        red_avg = sum(p['balance_score'] for p in red_team) / len(red_team)
        difference = abs(blue_avg - red_avg)
        balance_quality = team_cog._get_balance_quality(difference)

        embed = discord.Embed(
            title=f"⚔️ Fila {queue['name']} completa!",
            description=f"{len(players)} jogadores",
            color=discord.Color.green()
        )

        def format_team(team):
            lines = []
            for idx, player in enumerate(team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                lines.append(f"{idx}. {elo_info['emoji']} {player['user'].mention}")
                lines.append(f"   `{elo_info['name']} - {player['data']['pdl']} PDL`")
            return "\n".join(lines)

        embed.add_field(name="🔵 Time Azul", value=format_team(blue_team), inline=True)
        embed.add_field(name="🔴 Time Vermelho", value=format_team(red_team), inline=True)
        embed.add_field(
            name="📊 Estatísticas",
            value=(
                f"Força média azul: {blue_avg:.1f}\n"
                f"Força média vermelha: {red_avg:.1f}\n"
                f"Diferença: {difference:.1f} ({balance_quality['emoji']} {balance_quality['text']})"
            ),
            inline=False
        )
        await channel.send(embed=embed)

        save_last_teams(
            guild.id,
            [player['user'].id for player in blue_team],
            [player['user'].id for player in red_team]
        )

        await db_manager.update_queue_status(queue['id'], 'concluida')
        await db_manager.increment_metadata_counter('queues_completed')
        await self._edit_queue_message(queue, "✅ Fila concluída! Times montados no canal.", discord.Color.dark_green(), None)
        print(f"📈 Fila {queue['name']} concluída com sucesso")

    async def _fetch_queue_message(self, queue: dict) -> discord.Message | None:
        guild = self.bot.get_guild(queue['guild_id'])
        if not guild:
            return None
        channel = guild.get_channel(queue['channel_id'])
        if not channel:
            return None
        try:
            return await channel.fetch_message(queue['message_id'])
        except Exception:
            return None

    async def _edit_queue_message(self, queue: dict, status_text: str, color: discord.Color, view: discord.ui.View | None):
        message = await self._fetch_queue_message(queue)
        if not message:
            return
        embed = discord.Embed(title=f"Fila: {queue['name']}", description=status_text, color=color)
        await message.edit(embed=embed, view=view)

class QueueView(discord.ui.View):
    def __init__(self, cog: QueueCog, queue_id: int):
        super().__init__(timeout=None)
        self.add_item(JoinQueueButton(cog, queue_id))
        self.add_item(LeaveQueueButton(cog, queue_id))

class JoinQueueButton(discord.ui.Button):
    def __init__(self, cog: QueueCog, queue_id: int):
        super().__init__(style=discord.ButtonStyle.success, label="Entrar", custom_id=f"queue_join:{queue_id}")
        self.cog = cog
        self.queue_id = queue_id

    async def callback(self, interaction: discord.Interaction):
        await self.cog.handle_join(interaction, self.queue_id)

class LeaveQueueButton(discord.ui.Button):
    def __init__(self, cog: QueueCog, queue_id: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="Sair", custom_id=f"queue_leave:{queue_id}")
        self.cog = cog
        self.queue_id = queue_id

    async def callback(self, interaction: discord.Interaction):
        await self.cog.handle_leave(interaction, self.queue_id)

async def setup(bot: commands.Bot):
    await bot.add_cog(QueueCog(bot))
