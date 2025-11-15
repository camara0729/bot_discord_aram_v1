# cogs/match_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict, Any
import re

from utils.database_manager import db_manager
from utils.last_team_store import load_last_teams, clear_last_teams
import config

class MatchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="registrar_partida", description="Registre o resultado de uma partida ARAM.")
    @app_commands.describe(
        vencedor="Qual time venceu a partida",
        time_azul="Jogadores do time azul (separados por vírgula)",
        time_vermelho="Jogadores do time vermelho (separados por vírgula)",
        mvp="Jogador que foi MVP da partida (opcional)",
        bagre="Jogador que foi Bagre da partida (opcional)"
    )
    @app_commands.choices(vencedor=[
        app_commands.Choice(name="🔵 Time Azul", value="azul"),
        app_commands.Choice(name="🔴 Time Vermelho", value="vermelho")
    ])
    async def registrar_partida(
        self, 
        interaction: discord.Interaction, 
        vencedor: str,
        time_azul: str,
        time_vermelho: str,
        mvp: Optional[discord.Member] = None,
        bagre: Optional[discord.Member] = None
    ):
        await interaction.response.defer()
        
        try:
            # Processar jogadores dos times
            blue_players = await self._parse_players(interaction, time_azul)
            red_players = await self._parse_players(interaction, time_vermelho)
            
            if not blue_players or not red_players:
                await interaction.followup.send("❌ Erro ao processar os jogadores dos times!")
                return
            
            # Verificar se todos estão registrados
            all_players = blue_players + red_players
            for player in all_players:
                player_data = await db_manager.get_player(player.id)
                if not player_data:
                    await interaction.followup.send(f"❌ {player.mention} não está registrado! Use `/registrar` primeiro.")
                    return
            
            # Verificar MVP e Bagre
            if mvp and mvp not in all_players:
                await interaction.followup.send("❌ MVP deve estar em um dos times!")
                return
            
            if bagre and bagre not in all_players:
                await interaction.followup.send("❌ Bagre deve estar em um dos times!")
                return
            
            # Determinar vencedores e perdedores
            winners = blue_players if vencedor == "azul" else red_players
            losers = red_players if vencedor == "azul" else blue_players
            
            # Atualizar estatísticas dos jogadores
            pdl_changes = {}
            
            # Processar vencedores
            for player in winners:
                is_mvp = (mvp and player.id == mvp.id)
                is_bagre = (bagre and player.id == bagre.id)
                
                await db_manager.update_player_stats(
                    discord_id=player.id,
                    won=True,
                    is_mvp=is_mvp,
                    is_bagre=is_bagre
                )
                
                # Calcular mudança de PDL para mostrar
                pdl_change = config.PDL_WIN
                if is_mvp:
                    pdl_change += config.MVP_BONUS
                if is_bagre:
                    pdl_change += config.BAGRE_PENALTY
                
                pdl_changes[player.id] = pdl_change
            
            # Processar perdedores
            for player in losers:
                is_mvp = (mvp and player.id == mvp.id)
                is_bagre = (bagre and player.id == bagre.id)
                
                await db_manager.update_player_stats(
                    discord_id=player.id,
                    won=False,
                    is_mvp=is_mvp,
                    is_bagre=is_bagre
                )
                
                # Calcular mudança de PDL para mostrar
                pdl_change = config.PDL_LOSS
                if is_mvp:
                    pdl_change += config.MVP_BONUS
                if is_bagre:
                    pdl_change += config.BAGRE_PENALTY
                
                pdl_changes[player.id] = pdl_change
            
            # Criar embed de resultado
            embed = discord.Embed(
                title="🏆 Partida Registrada!",
                description=f"Resultado registrado com sucesso!",
                color=discord.Color.blue() if vencedor == "azul" else discord.Color.red()
            )
            
            # Time vencedor
            winner_team_name = "🔵 Time Azul" if vencedor == "azul" else "🔴 Time Vermelho"
            winner_text = ""
            for player in winners:
                pdl_change = pdl_changes[player.id]
                winner_text += f"• {player.mention} (**+{pdl_change}** PDL)\n"
            
            embed.add_field(
                name=f"{winner_team_name} (Vencedor)",
                value=winner_text,
                inline=True
            )
            
            # Time perdedor
            loser_team_name = "🔴 Time Vermelho" if vencedor == "azul" else "🔵 Time Azul"
            loser_text = ""
            for player in losers:
                pdl_change = pdl_changes[player.id]
                sign = "+" if pdl_change >= 0 else ""
                loser_text += f"• {player.mention} (**{sign}{pdl_change}** PDL)\n"
            
            embed.add_field(
                name=f"{loser_team_name} (Perdedor)",
                value=loser_text,
                inline=True
            )
            
            # MVP e Bagre
            special_text = ""
            if mvp:
                special_text += f"⭐ **MVP:** {mvp.mention} (+{config.MVP_BONUS} PDL extra)\n"
            if bagre:
                special_text += f"💩 **Bagre:** {bagre.mention} ({config.BAGRE_PENALTY} PDL extra)\n"
            
            if special_text:
                embed.add_field(name="🎯 Destaques", value=special_text, inline=False)
            
            embed.set_footer(text="Use /ranking para ver o ranking atualizado!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Erro ao registrar partida: {e}")
            await interaction.followup.send(f"❌ Erro ao registrar partida: {str(e)}")

    @app_commands.command(name="resultado_rapido", description="Registre resultado rapidamente usando os últimos times gerados.")
    @app_commands.describe(
        vencedor="Qual time venceu a partida",
        mvp="Jogador que foi MVP da partida (opcional)",
        bagre="Jogador que foi Bagre da partida (opcional)"
    )
    @app_commands.choices(vencedor=[
        app_commands.Choice(name="🔵 Time Azul", value="azul"),
        app_commands.Choice(name="🔴 Time Vermelho", value="vermelho")
    ])
    async def resultado_rapido(
        self, 
        interaction: discord.Interaction, 
        vencedor: str,
        mvp: Optional[discord.Member] = None,
        bagre: Optional[discord.Member] = None
    ):
        await interaction.response.defer()
        
        try:
            last_teams = load_last_teams(interaction.guild_id)
            if not last_teams:
                embed = discord.Embed(
                    title="❌ Nenhum Time Encontrado",
                    description="Não há times recentes salvos. Use `/times` primeiro para gerar os times!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                return

            blue_team_ids = last_teams.get('blue_team', [])
            red_team_ids = last_teams.get('red_team', [])
            if not blue_team_ids or not red_team_ids:
                await interaction.followup.send("❌ Arquivo de times recente está incompleto. Gere novos times com `/times`.", ephemeral=True)
                return

            all_player_ids = blue_team_ids + red_team_ids
            for player_id in all_player_ids:
                player_data = await db_manager.get_player(player_id)
                if not player_data:
                    await interaction.followup.send(f"❌ <@{player_id}> não está registrado! Use `/registrar` primeiro.")
                    return

            if mvp and mvp.id not in all_player_ids:
                await interaction.followup.send("❌ MVP deve estar em um dos times!")
                return

            if bagre and bagre.id not in all_player_ids:
                await interaction.followup.send("❌ Bagre deve estar em um dos times!")
                return

            winners = blue_team_ids if vencedor == "azul" else red_team_ids
            losers = red_team_ids if vencedor == "azul" else blue_team_ids
            
            # Atualizar estatísticas dos jogadores
            pdl_changes = {}
            
            # Processar vencedores
            for player_id in winners:
                is_mvp = (mvp and player_id == mvp.id)
                is_bagre = (bagre and player_id == bagre.id)
                
                await db_manager.update_player_stats(
                    discord_id=player_id,
                    won=True,
                    is_mvp=is_mvp,
                    is_bagre=is_bagre
                )
                
                # Calcular mudança de PDL para mostrar
                pdl_change = config.PDL_WIN
                if is_mvp:
                    pdl_change += config.MVP_BONUS
                if is_bagre:
                    pdl_change += config.BAGRE_PENALTY
                
                pdl_changes[player_id] = pdl_change
            
            # Processar perdedores
            for player_id in losers:
                is_mvp = (mvp and player_id == mvp.id)
                is_bagre = (bagre and player_id == bagre.id)
                
                await db_manager.update_player_stats(
                    discord_id=player_id,
                    won=False,
                    is_mvp=is_mvp,
                    is_bagre=is_bagre
                )
                
                # Calcular mudança de PDL para mostrar
                pdl_change = config.PDL_LOSS
                if is_mvp:
                    pdl_change += config.MVP_BONUS
                if is_bagre:
                    pdl_change += config.BAGRE_PENALTY
                
                pdl_changes[player_id] = pdl_change
            
            # Criar embed de resultado
            embed = discord.Embed(
                title="⚡ Resultado Rápido Registrado!",
                description=f"Partida registrada usando os últimos times gerados!",
                color=discord.Color.blue() if vencedor == "azul" else discord.Color.red()
            )
            
            # Time vencedor
            winner_team_name = "🔵 Time Azul" if vencedor == "azul" else "🔴 Time Vermelho"
            winner_text = ""
            for player_id in winners:
                pdl_change = pdl_changes[player_id]
                winner_text += f"• {self._mention_player(interaction.guild, player_id)} (**+{pdl_change}** PDL)\n"
            
            embed.add_field(
                name=f"{winner_team_name} (Vencedor)",
                value=winner_text,
                inline=True
            )
            
            # Time perdedor
            loser_team_name = "🔴 Time Vermelho" if vencedor == "azul" else "🔵 Time Azul"
            loser_text = ""
            for player_id in losers:
                pdl_change = pdl_changes[player_id]
                sign = "+" if pdl_change >= 0 else ""
                loser_text += f"• {self._mention_player(interaction.guild, player_id)} (**{sign}{pdl_change}** PDL)\n"
            
            embed.add_field(
                name=f"{loser_team_name} (Perdedor)",
                value=loser_text,
                inline=True
            )
            
            # MVP e Bagre
            special_text = ""
            if mvp:
                special_text += f"⭐ **MVP:** {mvp.mention} (+{config.MVP_BONUS} PDL extra)\n"
            if bagre:
                special_text += f"💩 **Bagre:** {bagre.mention} ({config.BAGRE_PENALTY} PDL extra)\n"
            
            if special_text:
                embed.add_field(name="🎯 Destaques", value=special_text, inline=False)
            
            embed.set_footer(text="⚡ Resultado registrado rapidamente! Use /ranking para ver o ranking.")
            
            await interaction.followup.send(embed=embed)
            
            # Limpar times salvos após usar
            clear_last_teams(interaction.guild.id)
            
        except Exception as e:
            print(f"Erro ao registrar resultado rápido: {e}")
            await interaction.followup.send(f"❌ Erro ao registrar resultado rápido: {str(e)}")

    async def _parse_players(self, interaction: discord.Interaction, jogadores_str: str) -> List[discord.Member]:
        """Processa a string de jogadores e retorna lista de membros válidos."""
        players = []
        
        # Regex para encontrar mentions do Discord <@!?id> ou <@id>
        mention_pattern = r'<@!?(\d+)>'
        
        # Primeiro, extrair todas as mentions
        mentions = re.findall(mention_pattern, jogadores_str)
        
        for user_id_str in mentions:
            try:
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id)
                if member:
                    players.append(member)
                else:
                    print(f"Membro não encontrado: {user_id}")
            except ValueError:
                print(f"ID inválido na mention: {user_id_str}")
        
        # Se não encontrou mentions, tentar processar como nomes/IDs separados
        if not players:
            # Remover mentions da string e dividir por vírgula e espaços
            clean_str = re.sub(mention_pattern, '', jogadores_str)
            
            # Dividir por vírgula primeiro
            parts = [part.strip() for part in clean_str.split(',')]
            
            # Depois dividir por espaços
            all_parts = []
            for part in parts:
                if part:
                    all_parts.extend(part.split())
            
            for part in all_parts:
                part = part.strip()
                if not part:
                    continue
                    
                # Verificar se é só um ID numérico
                if part.isdigit():
                    try:
                        user_id = int(part)
                        member = interaction.guild.get_member(user_id)
                        if member:
                            players.append(member)
                        else:
                            print(f"Membro não encontrado pelo ID: {user_id}")
                    except ValueError:
                        print(f"ID inválido: {part}")
                else:
                    # Tentar buscar por nome/nick
                    member = discord.utils.find(
                        lambda m: m.display_name.lower() == part.lower() or m.name.lower() == part.lower(),
                        interaction.guild.members
                    )
                    if member:
                        players.append(member)
                    else:
                        print(f"Usuário não encontrado: {part}")
        
        # Remover duplicatas mantendo ordem
        seen = set()
        unique_players = []
        for player in players:
            if player.id not in seen:
                seen.add(player.id)
                unique_players.append(player)
        
        return unique_players

    def _mention_player(self, guild: discord.Guild, player_id: int) -> str:
        member = guild.get_member(player_id) if guild else None
        if member:
            return member.mention
        return f"<@{player_id}>"

async def setup(bot: commands.Bot):
    await bot.add_cog(MatchCog(bot))
