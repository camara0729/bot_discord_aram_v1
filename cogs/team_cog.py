# cogs/team_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Any
import random

from utils.database_manager import db_manager
import config

class TeamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="times", description="Gere times balanceados para uma partida ARAM.")
    @app_commands.describe(jogadores="Lista de jogadores separados por vírgula (ex: @user1, @user2, @user3...)")
    @commands.cooldown(1, 10, commands.BucketType.guild)  # 1 uso a cada 10 segundos por servidor
    async def times(self, interaction: discord.Interaction, jogadores: str):
        await interaction.response.defer()
        
        try:
            # Adicionar timeout para evitar processos longos
            import asyncio
            async def process_teams():
                return await self._process_team_balancing(interaction, jogadores)
            
            # Timeout de 30 segundos
            result = await asyncio.wait_for(process_teams(), timeout=30.0)
            return result
            
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Comando expirou. O processamento demorou muito. Tente com menos jogadores.")
            return
        except discord.HTTPException as e:
            if e.status == 429:
                await interaction.followup.send("⚠️ Muitas requisições. Aguarde um momento e tente novamente.")
            else:
                await interaction.followup.send("❌ Erro de conexão com o Discord. Tente novamente.")
            return
        except Exception as e:
            print(f"Erro no comando times: {e}")
            await interaction.followup.send("❌ Erro interno. Tente novamente.")
            return
    
    async def _process_team_balancing(self, interaction: discord.Interaction, jogadores: str):
        try:
            # Processar a string de jogadores
            player_list = await self._parse_players(interaction, jogadores)
            
            if not player_list:
                await interaction.followup.send("❌ Nenhum jogador válido encontrado!")
                return
            
            # Verificar número de jogadores
            if len(player_list) < 4:
                await interaction.followup.send("❌ Mínimo de 4 jogadores necessário!")
                return
            
            if len(player_list) > 10:
                await interaction.followup.send("❌ Máximo de 10 jogadores permitido!")
                return
            
            if len(player_list) % 2 != 0:
                await interaction.followup.send("❌ Número de jogadores deve ser par!")
                return
            
            # Buscar dados dos jogadores
            players_data = []
            for player in player_list:
                player_data = await db_manager.get_player(player.id)
                if not player_data:
                    await interaction.followup.send(f"❌ {player.mention} não está registrado! Use `/registrar` primeiro.")
                    return
                
                # Calcular score de balanceamento
                balance_score = config.calculate_balance_score(
                    player_data['pdl'],
                    player_data.get('lol_rank', 'PRATA II'),
                    player_data['wins'],
                    player_data['losses']
                )
                
                players_data.append({
                    'user': player,
                    'data': player_data,
                    'balance_score': balance_score
                })
            
            # Gerar times balanceados
            blue_team, red_team = self._balance_teams(players_data)
            
            # Calcular diferença de força
            blue_avg = sum(p['balance_score'] for p in blue_team) / len(blue_team)
            red_avg = sum(p['balance_score'] for p in red_team) / len(red_team)
            difference = abs(blue_avg - red_avg)
            
            # Criar embed
            embed = discord.Embed(
                title="⚔️ Times Balanceados",
                description=f"Partida ARAM - {len(player_list)} jogadores",
                color=discord.Color.blue()
            )
            
            # Time Azul
            blue_text = ""
            for i, player in enumerate(blue_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                blue_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                blue_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"
            
            embed.add_field(
                name="🔵 Time Azul",
                value=blue_text,
                inline=True
            )
            
            # Time Vermelho
            red_text = ""
            for i, player in enumerate(red_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                red_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                red_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"
            
            embed.add_field(
                name="🔴 Time Vermelho",
                value=red_text,
                inline=True
            )
            
            # Estatísticas de balanceamento
            balance_quality = self._get_balance_quality(difference)
            embed.add_field(
                name="📊 Estatísticas",
                value=f"**Força Média Time Azul:** {blue_avg:.1f}\n"
                      f"**Força Média Time Vermelho:** {red_avg:.1f}\n"
                      f"**Diferença:** {difference:.1f}\n"
                      f"**Qualidade:** {balance_quality['emoji']} {balance_quality['text']}",
                inline=False
            )
            
            # View com botões
            view = TeamActionsView(blue_team, red_team)
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"Erro no comando times: {e}")
            await interaction.followup.send(f"❌ Erro ao gerar times: {str(e)}")

    async def _parse_players(self, interaction: discord.Interaction, jogadores_str: str) -> List[discord.Member]:
        """Processa a string de jogadores e retorna lista de membros válidos."""
        players = []
        
        # Dividir por vírgula e limpar espaços
        player_parts = [part.strip() for part in jogadores_str.split(',')]
        
        for part in player_parts:
            if not part:
                continue
                
            # Tentar extrair mention do Discord
            if part.startswith('<@') and part.endswith('>'):
                # É uma mention
                user_id = part.replace('<@', '').replace('>', '').replace('!', '')
                try:
                    user_id = int(user_id)
                    member = interaction.guild.get_member(user_id)
                    if member:
                        players.append(member)
                    else:
                        print(f"Membro não encontrado: {user_id}")
                except ValueError:
                    print(f"ID inválido: {user_id}")
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

    def _balance_teams(self, players_data: List[Dict]) -> tuple:
        """Gera times balanceados usando algoritmo de balanceamento."""
        # Ordenar por força (balance_score)
        sorted_players = sorted(players_data, key=lambda x: x['balance_score'], reverse=True)
        
        team_size = len(sorted_players) // 2
        
        # Algoritmo de draft alternado otimizado
        blue_team = []
        red_team = []
        
        # Primeira tentativa: draft alternado simples
        for i, player in enumerate(sorted_players):
            if i % 2 == 0:
                blue_team.append(player)
            else:
                red_team.append(player)
        
        # Verificar se precisa otimizar
        blue_strength = sum(p['balance_score'] for p in blue_team)
        red_strength = sum(p['balance_score'] for p in red_team)
        
        # Se a diferença for muito grande, tentar melhorar
        if abs(blue_strength - red_strength) > 10:
            best_blue, best_red = self._optimize_teams(sorted_players, team_size)
            if best_blue and best_red:
                blue_team, red_team = best_blue, best_red
        
        return blue_team, red_team

    def _optimize_teams(self, players: List[Dict], team_size: int) -> tuple:
        """Otimiza o balanceamento tentando diferentes combinações."""
        from itertools import combinations
        
        best_difference = float('inf')
        best_blue = None
        best_red = None
        
        # Limitar tentativas para performance
        max_attempts = min(1000, len(list(combinations(range(len(players)), team_size))))
        attempts = 0
        
        for blue_indices in combinations(range(len(players)), team_size):
            if attempts >= max_attempts:
                break
            attempts += 1
            
            red_indices = [i for i in range(len(players)) if i not in blue_indices]
            
            blue_team = [players[i] for i in blue_indices]
            red_team = [players[i] for i in red_indices]
            
            blue_strength = sum(p['balance_score'] for p in blue_team)
            red_strength = sum(p['balance_score'] for p in red_team)
            
            difference = abs(blue_strength - red_strength)
            
            if difference < best_difference:
                best_difference = difference
                best_blue = blue_team
                best_red = red_team
                
                # Se encontrou balanceamento perfeito, parar
                if difference < 2:
                    break
        
        return best_blue, best_red

    def _get_balance_quality(self, difference: float) -> Dict[str, str]:
        """Retorna a qualidade do balanceamento baseado na diferença."""
        if difference <= 2:
            return {"emoji": "🟢", "text": "Excelente"}
        elif difference <= 5:
            return {"emoji": "🟡", "text": "Bom"}
        elif difference <= 10:
            return {"emoji": "🟠", "text": "Razoável"}
        else:
            return {"emoji": "🔴", "text": "Desbalanceado"}

class TeamActionsView(discord.ui.View):
    def __init__(self, blue_team: List[Dict], red_team: List[Dict]):
        super().__init__(timeout=300)
        self.blue_team = blue_team
        self.red_team = red_team

    @discord.ui.button(label="🔄 Rebalancear", style=discord.ButtonStyle.secondary)
    async def rebalance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Rebalanceando times...", ephemeral=True)
        # Aqui você pode implementar lógica para rebalancear
        
    @discord.ui.button(label="✅ Confirmar Times", style=discord.ButtonStyle.success)
    async def confirm_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ Times Confirmados!",
            description="Boa sorte na partida! Lembrem-se de reportar o resultado após o jogo.",
            color=discord.Color.green()
        )
        
        blue_mentions = " ".join([p['user'].mention for p in self.blue_team])
        red_mentions = " ".join([p['user'].mention for p in self.red_team])
        
        embed.add_field(name="🔵 Time Azul", value=blue_mentions, inline=False)
        embed.add_field(name="🔴 Time Vermelho", value=red_mentions, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Times Cancelados",
            description="Geração de times cancelada.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))