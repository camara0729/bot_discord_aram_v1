# cogs/team_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Any
import random

from utils.database_manager import db_manager
from utils.last_team_store import save_last_teams
import config

class TeamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="times", description="Gere times balanceados para uma partida ARAM.")
    @app_commands.describe(participantes="Número de participantes (4, 6, 8 ou 10)")
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def times(self, interaction: discord.Interaction, participantes: int):
        # Validar número de participantes
        if participantes not in [4, 6, 8, 10]:
            await interaction.response.send_message("❌ Número de participantes deve ser 4, 6, 8 ou 10!", ephemeral=True)
            return
        
        # Criar embed inicial
        embed = discord.Embed(
            title="⚔️ Criando Times ARAM",
            description=f"**Participantes necessários:** {participantes}\n**Participantes atuais:** 0\n\n🎯 Clique no botão abaixo para entrar na partida!",
            color=discord.Color.blue()
        )
        
        # Criar view com botão de participar
        view = ParticipantSelectionView(participantes, interaction.user, interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)

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
                blue_text += f"   `⚖️ Score: {player['balance_score']:.2f}`\n"
            
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
                red_text += f"   `⚖️ Score: {player['balance_score']:.2f}`\n"
            
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
            
            guild_id = interaction.guild_id
            save_last_teams(guild_id, [player['user'].id for player in blue_team], [player['user'].id for player in red_team])
            
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
        """Gera times balanceados buscando todas as combinações possíveis."""
        from itertools import combinations

        total_players = len(players_data)
        team_size = total_players // 2

        if total_players < 2 or total_players % 2 != 0:
            return players_data[:team_size], players_data[team_size:]

        scores = [p['balance_score'] for p in players_data]
        total_strength = sum(scores)

        best_blue = []
        best_red = []
        best_difference = float('inf')

        for combo in combinations(range(total_players), team_size):
            if 0 not in combo:  # evita combinações duplicadas (inversão Azul/Vermelho)
                continue

            blue_team = [players_data[i] for i in combo]
            red_team = [players_data[i] for i in range(total_players) if i not in combo]

            blue_strength = sum(scores[i] for i in combo)
            red_strength = total_strength - blue_strength
            difference = abs(blue_strength - red_strength)

            if difference < best_difference:
                best_difference = difference
                best_blue = blue_team
                best_red = red_team

                if difference == 0:
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

class ParticipantSelectionView(discord.ui.View):
    def __init__(self, max_participants: int, creator: discord.Member, guild_id: int):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.max_participants = max_participants
        self.creator = creator
        self.participants = []
        self.guild_id = guild_id
        
    @discord.ui.button(label="🎮 Entrar na Partida", style=discord.ButtonStyle.primary, emoji="🎮")
    async def join_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        
        # Verificar se já está na lista
        if user.id in [p.id for p in self.participants]:
            await interaction.response.send_message("❌ Você já está na lista de participantes!", ephemeral=True)
            return
            
        # Verificar se está registrado
        player_data = await db_manager.get_player(user.id)
        if not player_data:
            await interaction.response.send_message("❌ Você precisa estar registrado! Use `/registrar` primeiro.", ephemeral=True)
            return
        
        # Adicionar à lista
        self.participants.append(user)
        
        # Atualizar embed
        embed = discord.Embed(
            title="⚔️ Criando Times ARAM",
            description=(
                f"**Participantes necessários:** {self.max_participants}\n"
                f"**Participantes atuais:** {len(self.participants)}\n\n🎯 Clique no botão abaixo para entrar na partida!"
            ),
            color=discord.Color.blue()
        )
        
        # Lista de participantes
        participant_list = "\n".join([f"{i+1}. {p.mention}" for i, p in enumerate(self.participants)])
        embed.add_field(
            name="👥 Participantes Confirmados",
            value=participant_list if participant_list else "Nenhum participante ainda",
            inline=False
        )
        
        # Se completou o número necessário, habilitar balanceamento
        if len(self.participants) == self.max_participants:
            embed.color = discord.Color.green()
            embed.description = (
                f"✅ **{self.max_participants}** participantes confirmados!\n"
                "🎲 Clique em 'Balancear Times' para gerar os times!"
            )
            
            # Adicionar botão de balanceamento
            balance_button = discord.ui.Button(label="🎲 Balancear Times", style=discord.ButtonStyle.success)
            balance_button.callback = self.balance_teams
            self.add_item(balance_button)
            
            # Remover botão de entrar
            button.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🚪 Sair da Partida", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def leave_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        
        if user.id not in [p.id for p in self.participants]:
            await interaction.response.send_message("❌ Você não está na lista de participantes!", ephemeral=True)
            return
            
        # Remover da lista
        self.participants = [p for p in self.participants if p.id != user.id]
        
        # Atualizar embed
        embed = discord.Embed(
            title="⚔️ Criando Times ARAM",
            description=(
                f"**Participantes necessários:** {self.max_participants}\n"
                f"**Participantes atuais:** {len(self.participants)}\n\n🎯 Clique no botão abaixo para entrar na partida!"
            ),
            color=discord.Color.blue()
        )
        
        # Lista de participantes
        if self.participants:
            participant_list = "\n".join([f"{i+1}. {p.mention}" for i, p in enumerate(self.participants)])
            embed.add_field(
                name="👥 Participantes Confirmados",
                value=participant_list,
                inline=False
            )
        
        # Reabilitar botão de entrar se necessário
        for item in self.children:
            if "Entrar na Partida" in item.label:
                item.disabled = False
                break
        
        # Remover botão de balanceamento se existir
        self.children = [item for item in self.children if "Balancear Times" not in item.label]
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def balance_teams(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            players_data = []
            for player in self.participants:
                player_data = await db_manager.get_player(player.id)
                if not player_data:
                    await interaction.followup.send(f"❌ {player.mention} não está registrado!", ephemeral=True)
                    return

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

            team_cog = interaction.client.get_cog('TeamCog')
            if not team_cog:
                await interaction.followup.send("❌ Erro interno: TeamCog não encontrado", ephemeral=True)
                return

            blue_team, red_team = team_cog._balance_teams(players_data)

            blue_avg = sum(p['balance_score'] for p in blue_team) / len(blue_team)
            red_avg = sum(p['balance_score'] for p in red_team) / len(red_team)
            difference = abs(blue_avg - red_avg)

            embed = discord.Embed(
                title="⚔️ Times Balanceados",
                description=f"Partida ARAM - {len(self.participants)} jogadores",
                color=discord.Color.green()
            )

            blue_text = ""
            for i, player in enumerate(blue_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                blue_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                blue_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"

            embed.add_field(name="🔵 Time Azul", value=blue_text, inline=True)

            red_text = ""
            for i, player in enumerate(red_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                red_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                red_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"

            embed.add_field(name="🔴 Time Vermelho", value=red_text, inline=True)

            balance_quality = team_cog._get_balance_quality(difference)
            embed.add_field(
                name="📊 Estatísticas",
                value=(
                    f"**Força Média Time Azul:** {blue_avg:.1f}\n"
                    f"**Força Média Time Vermelho:** {red_avg:.1f}\n"
                    f"**Diferença:** {difference:.1f}\n"
                    f"**Qualidade:** {balance_quality['emoji']} {balance_quality['text']}"
                ),
                inline=False
            )

            guild_id = interaction.guild_id or self.guild_id
            save_last_teams(guild_id, [player['user'].id for player in blue_team], [player['user'].id for player in red_team])
            final_view = BalancedTeamsView(blue_team, red_team, self.participants, guild_id)
            await interaction.edit_original_response(embed=embed, view=final_view)

        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao balancear times: {str(e)}", ephemeral=True)
            
    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Só o criador pode cancelar
        if interaction.user.id != self.creator.id:
            await interaction.response.send_message("❌ Apenas o criador da partida pode cancelar!", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="❌ Partida Cancelada",
            description="A criação de times foi cancelada.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class BalancedTeamsView(discord.ui.View):
    def __init__(self, blue_team, red_team, all_participants, guild_id: int):
        super().__init__(timeout=1800)  # 30 minutos
        self.blue_team = blue_team
        self.red_team = red_team
        self.all_participants = all_participants
        self.guild_id = guild_id
    
    @discord.ui.button(label="🔄 Rebalancear", style=discord.ButtonStyle.secondary)
    async def rebalance(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Mesmo código de balanceamento, mas reorganiza os times
        await interaction.response.defer(thinking=True)
        
        try:
            # Usar algoritmo diferente ou embaralhar
            import random
            players_data = []
            for participant in self.all_participants:
                for team in [self.blue_team, self.red_team]:
                    for player in team:
                        if player['user'].id == participant.id:
                            players_data.append(player)
                            break
            
            # Embaralhar e rebalancear
            random.shuffle(players_data)
            team_cog = interaction.client.get_cog('TeamCog')
            new_blue, new_red = team_cog._balance_teams(players_data)
            
            # Atualizar times
            self.blue_team = new_blue
            self.red_team = new_red
            save_last_teams(self.guild_id, [player['user'].id for player in new_blue], [player['user'].id for player in new_red])
            
            # Recalcular e atualizar embed (código similar ao balance_teams)
            blue_avg = sum(p['balance_score'] for p in new_blue) / len(new_blue)
            red_avg = sum(p['balance_score'] for p in new_red) / len(new_red)
            difference = abs(blue_avg - red_avg)
            
            embed = discord.Embed(
                title="⚔️ Times Rebalanceados",
                description=f"Partida ARAM - {len(self.all_participants)} jogadores",
                color=discord.Color.green()
            )
            
            # Times (mesmo código do balance_teams)
            blue_text = ""
            for i, player in enumerate(new_blue, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                blue_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                blue_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"
            
            embed.add_field(name="🔵 Time Azul", value=blue_text, inline=True)
            
            red_text = ""
            for i, player in enumerate(new_red, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                red_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\n"
                red_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\n"
            
            embed.add_field(name="🔴 Time Vermelho", value=red_text, inline=True)
            
            balance_quality = team_cog._get_balance_quality(difference)
            embed.add_field(
                name="📊 Estatísticas",
                value=(
                    f"**Força Média Time Azul:** {blue_avg:.1f}\n"
                    f"**Força Média Time Vermelho:** {red_avg:.1f}\n"
                    f"**Diferença:** {difference:.1f}\n"
                    f"**Qualidade:** {balance_quality['emoji']} {balance_quality['text']}"
                ),
                inline=False
            )
            
            await interaction.edit_original_response(embed=embed, view=self)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao rebalancear: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))
