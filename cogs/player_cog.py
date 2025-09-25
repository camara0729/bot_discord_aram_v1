# cogs/player_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.database_manager import db_manager
from utils.riot_api_manager import riot_api_manager
import config

class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="registrar", description="Registre seu Riot ID para participar das scrims.")
    @app_commands.describe(
        riot_id="Seu Riot ID completo (ex: NomeDeInvocador#BR1)", 
        rank="Seu rank atual no LoL (ex: Ouro IV) - usado apenas para balanceamento"
    )
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
            puuid = await riot_api_manager.get_puuid_by_riot_id(game_name, tag_line)
            print(f"PUUID retornado: {puuid}")
            
            if not puuid:
                await interaction.followup.send("Riot ID não encontrado. Verifique se digitou corretamente e tente novamente.")
                return

            print(f"Salvando no banco de dados...")
            await db_manager.add_player(interaction.user.id, riot_id, puuid, rank.upper())
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
            
        except Exception as e:
            print(f"Erro durante o registro: {e}")
            await interaction.followup.send(f"Ocorreu um erro durante o registro: {str(e)}")

    @app_commands.command(name="perfil", description="Veja o perfil de um jogador.")
    @app_commands.describe(jogador="O jogador cujo perfil você quer ver (opcional, mostra o seu se não for especificado).")
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

    @app_commands.command(name="leaderboard", description="Veja o ranking dos jogadores.")
    async def leaderboard(self, interaction: discord.Interaction):
        players = await db_manager.get_all_players()
        
        if not players:
            await interaction.response.send_message("Nenhum jogador registrado ainda.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🏆 Ranking ARAM",
            description="Classificação baseada no sistema PDL",
            color=discord.Color.gold()
        )
        
        # Mostrar top 10
        top_players = players[:10]
        
        ranking_text = ""
        for i, player in enumerate(top_players, 1):
            # Buscar usuário do Discord
            user = self.bot.get_user(player['discord_id'])
            username = user.display_name if user else "Usuário Desconhecido"
            
            # Informações do elo
            elo_info = config.get_elo_by_pdl(player['pdl'])
            
            # Emoji da posição
            position_emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"`{i:2d}`"
            
            ranking_text += f"{position_emoji} {elo_info['emoji']} **{username}**\n"
            ranking_text += f"     {elo_info['name']} - {player['pdl']} PDL\n"
            ranking_text += f"     {player['wins']}W/{player['losses']}L\n\n"
        
        embed.description = ranking_text
        embed.set_footer(text=f"Total de jogadores: {len(players)}")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))