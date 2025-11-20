# cogs/player_cog.py
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, Dict

from utils.database_manager import db_manager
from utils.riot_api_manager import riot_api_manager
from utils.ops_logger import log_ops_event, format_exception
import config

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rank_auto_sync.start()

    def cog_unload(self):
        self.rank_auto_sync.cancel()

    @app_commands.command(name="registrar", description="Registre seu Riot ID para participar das scrims.")
    @app_commands.describe(
        riot_id="Seu Riot ID completo (ex: NomeDeInvocador#BR1)", 
        rank="Seu rank atual no LoL (ex: Ouro IV) - usado apenas para balanceamento"
    )
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def registrar(self, interaction: discord.Interaction, riot_id: str, rank: str):
        await interaction.response.defer(ephemeral=True)
        
        print(f"Iniciando registro para usuário {interaction.user.display_name} com Riot ID: {riot_id}")

        if '#' not in riot_id:
            await interaction.followup.send("Formato de Riot ID inválido. Use Nome#Tagline (ex: MeuNick#BR1).")
            return

        game_name, tag_line = riot_id.split('#', 1)
        print(f"Game name: {game_name}, Tag line: {tag_line}")

        # Validar se o rank é válido
        if rank.upper() not in config.RANK_WEIGHTS:
            valid_ranks = ", ".join(config.RANK_WEIGHTS.keys())
            await interaction.followup.send(f"Rank '{rank}' não é válido. Ranks válidos: {valid_ranks}")
            return

        try:
            import asyncio
            
            # Adicionar timeout para a chamada da API da Riot
            async def get_puuid_with_timeout():
                return await riot_api_manager.get_puuid_by_riot_id(game_name, tag_line)
            
            puuid = await asyncio.wait_for(get_puuid_with_timeout(), timeout=15.0)
            print(f"PUUID retornado: {puuid}")
            
            if not puuid:
                await interaction.followup.send("Riot ID não encontrado. Verifique se digitou corretamente e tente novamente.")
                return

            print(f"Salvando no banco de dados...")
            await db_manager.add_player(interaction.user.id, riot_id, puuid, rank.upper(), interaction.user.display_name)
            print(f"Registro concluído!")
            
            # Buscar elo inicial
            elo_info = config.get_elo_by_pdl(config.DEFAULT_PDL)
            
            embed = discord.Embed(
                title="✅ Registro Concluído!",
                description=f"Bem-vindo, {interaction.user.mention}! Você foi registrado com sucesso.",
                color=elo_info["color"]
            )
            embed.add_field(name="Riot ID", value=riot_id, inline=True)
            embed.add_field(name="Rank LoL", value=rank, inline=True)
            embed.add_field(name=f"{elo_info['emoji']} Elo ARAM", value=f"**{elo_info['name']}** ({config.DEFAULT_PDL} PDL)", inline=False)
            embed.add_field(name="ℹ️ Informação", value="Seu rank do LoL é usado apenas para balanceamento de times. Seu elo ARAM é baseado no sistema de PDL!", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except asyncio.TimeoutError:
            print("Timeout na API da Riot")
            await interaction.followup.send("⏰ A verificação do Riot ID demorou muito. Tente novamente em alguns momentos.")
        except discord.HTTPException as e:
            if e.status == 429:
                await interaction.followup.send("⚠️ Muitas requisições. Aguarde um momento e tente novamente.")
            else:
                await interaction.followup.send("❌ Erro de conexão. Tente novamente.")
        except Exception as e:
            print(f"Erro durante o registro: {e}")
            await interaction.followup.send("❌ Ocorreu um erro interno. Tente novamente.")

    @app_commands.command(name="perfil", description="Veja o perfil de um jogador.")
    @app_commands.describe(jogador="O jogador cujo perfil você quer ver (opcional, mostra o seu se não for especificado).")
    @app_commands.checks.cooldown(1, 3.0, key=lambda i: i.user.id)
    async def perfil(self, interaction: discord.Interaction, jogador: Optional[discord.Member] = None):
        target_user = jogador or interaction.user
        
        player_data = await db_manager.get_player(target_user.id)
        if not player_data:
            await interaction.response.send_message(f"{target_user.mention} não está registrado. Use `/registrar` para se cadastrar.", ephemeral=True)
            return

        total_games = player_data['wins'] + player_data['losses']
        win_rate = (player_data['wins'] / total_games * 100) if total_games > 0 else 0
        
        # Informações do elo atual
        elo_info = config.get_elo_by_pdl(player_data['pdl'])
        
        # Calcular score de balanceamento
        balance_score = config.calculate_balance_score(
            player_data['pdl'],
            player_data.get('lol_rank', 'PRATA II'),
            player_data['wins'],
            player_data['losses']
        )

        embed = discord.Embed(
            title=f"Perfil de {target_user.display_name}",
            color=elo_info["color"]
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="🆔 Riot ID", value=player_data['riot_id'], inline=True)
        embed.add_field(name="🏆 Rank LoL", value=player_data.get('lol_rank', 'Não informado'), inline=True)
        embed.add_field(name=f"{elo_info['emoji']} Elo ARAM", value=f"**{elo_info['name']}**", inline=True)
        embed.add_field(name="📊 PDL", value=f"**{player_data['pdl']}** pontos", inline=True)
        embed.add_field(name="⚖️ Score Balanceamento", value=f"{balance_score}/100", inline=True)
        embed.add_field(name="📈 W/L", value=f"**{player_data['wins']}**W / **{player_data['losses']}**L", inline=True)
        embed.add_field(name="📊 Taxa de Vitória", value=f"**{win_rate:.1f}%**", inline=True)
        embed.add_field(name="⭐ MVPs", value=f"**{player_data['mvp_count']}**", inline=True)
        embed.add_field(name="💩 Bagres", value=f"**{player_data['bagre_count']}**", inline=True)
        
        await interaction.response.send_message(embed=embed)

    async def _sync_player_rank(self, player_data: Dict, source: str):
        try:
            puuid = player_data.get('puuid')
            if not puuid or puuid == 'manual_puuid':
                puuid = await self._fetch_puuid(player_data)
                if not puuid:
                    return False, "❌ Não foi possível obter seu PUUID. Verifique o Riot ID no `/registrar`.", {}
                await db_manager.update_player_puuid(player_data['discord_id'], puuid)

            platform = self._platform_from_riot_id(player_data.get('riot_id'))
            rank_info = await riot_api_manager.get_rank_for_puuid(puuid, platform)
            if not rank_info:
                return False, "⚠️ Não encontramos partidas ranqueadas recentes para sincronizar.", {}

            await db_manager.update_player_rank_sync(player_data['discord_id'], rank_info['rank'], source)
            return True, "Sincronização realizada.", rank_info

        except Exception as exc:
            await log_ops_event(
                'riot.sync_failed',
                guild_id=None,
                user_id=player_data.get('discord_id'),
                details={'source': source},
                stacktrace=format_exception(exc)
            )
            return False, "❌ Ocorreu um erro durante a sincronização. Tente novamente mais tarde.", {}

    async def _fetch_puuid(self, player_data: Dict) -> Optional[str]:
        riot_id = player_data.get('riot_id')
        if not riot_id or '#' not in riot_id:
            return None
        game_name, tag_line = riot_id.split('#', 1)
        return await riot_api_manager.get_puuid_by_riot_id(game_name, tag_line)

    def _platform_from_riot_id(self, riot_id: Optional[str]) -> str:
        if riot_id and '#' in riot_id:
            tag = riot_id.split('#', 1)[1].lower()
            platform_map = {
                'br': 'br1',
                'br1': 'br1',
                'na': 'na1',
                'na1': 'na1',
                'lan': 'la1',
                'la1': 'la1',
                'las': 'la2',
                'la2': 'la2',
                'euw': 'euw1',
                'euw1': 'euw1',
                'eune': 'eun1',
                'eun1': 'eun1',
                'kr': 'kr',
                'jp': 'jp1',
                'jp1': 'jp1',
                'oce': 'oc1',
                'oc1': 'oc1',
                'tr': 'tr1',
                'tr1': 'tr1',
                'ru': 'ru',
                'pbe': 'pbe1',
                'pbe1': 'pbe1'
            }
            return platform_map.get(tag, 'br1')
        return 'br1'

    @tasks.loop(hours=24)
    async def rank_auto_sync(self):
        await self.bot.wait_until_ready()
        players = await db_manager.get_players_needing_rank_sync(days=7, limit=5)
        if not players:
            return
        for player in players:
            success, _, rank_info = await self._sync_player_rank(player, source='auto')
            if success:
                await db_manager.increment_metadata_counter('rank_sync_auto')
            await asyncio.sleep(2)
        percent = await self._calculate_sync_percent()
        if percent is not None:
            await db_manager.set_metadata('rank_sync_percent_30d', f"{percent:.2f}")

    async def _calculate_sync_percent(self) -> Optional[float]:
        total = await db_manager.count_players()
        if total == 0:
            return None
        recent = await db_manager.count_players_synced_since(30)
        return (recent / total) * 100

    @rank_auto_sync.before_loop
    async def before_rank_auto_sync(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="sincronizar_elo", description="Sincroniza seu elo direto da Riot")
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def sincronizar_elo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player_data = await db_manager.get_player(interaction.user.id)
        if not player_data:
            await interaction.followup.send("❌ Você precisa se registrar primeiro com `/registrar`.")
            return

        success, message, rank_info = await self._sync_player_rank(player_data, source='manual')
        if not success:
            await interaction.followup.send(message)
            return

        embed = discord.Embed(
            title="🔁 Sincronização de Elo",
            description=f"Riot ID: **{player_data['riot_id']}**",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Rank atualizado", value=rank_info['rank'], inline=True)
        if rank_info.get('lp') is not None:
            embed.add_field(name="LP", value=f"{rank_info['lp']} LP", inline=True)
        if rank_info.get('queue'):
            embed.add_field(name="Fila", value=rank_info['queue'], inline=True)
        await interaction.followup.send(embed=embed)
        await db_manager.increment_metadata_counter('rank_sync_manual')

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
