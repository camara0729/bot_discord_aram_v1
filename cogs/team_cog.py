# cogs/team_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Any
import random

from utils.database_manager import db_manager
import config

class TeamCog(commands.Cog):
    last_teams = None  # Variável de classe para armazenar últimos times
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="times", description="Gere times balanceados para uma partida ARAM.")
    @app_commands.describe(participantes="Número de participantes (4, 6, 8 ou 10)")
    @commands.cooldown(1, 10, commands.BucketType.guild)
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
        view = ParticipantSelectionView(participantes, interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    # Alias para compatibilidade: muitos usuários usam /time
    @app_commands.command(name="time", description="(Alias de /times) Gere times balanceados para uma partida ARAM.")
    @app_commands.describe(participantes="Número de participantes (4, 6, 8 ou 10)")
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def time(self, interaction: discord.Interaction, participantes: int):
        await self.times(interaction, participantes)
    
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
        """Gera times balanceados usando algoritmo otimizado."""
        # Ordenar por força (balance_score)
        sorted_players = sorted(players_data, key=lambda x: x['balance_score'], reverse=True)
        
        team_size = len(sorted_players) // 2
        
        # Para 4 jogadores, usar força bruta para encontrar o melhor balanceamento
        if len(sorted_players) == 4:
            return self._balance_teams_4_players(sorted_players)
        
        # Para mais jogadores, usar algoritmo otimizado
        return self._balance_teams_optimized(sorted_players, team_size)

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

    def _balance_teams_4_players(self, players: List[Dict]) -> tuple:
        """Balanceamento otimizado específico para 4 jogadores usando força bruta."""
        from itertools import combinations
        
        best_difference = float('inf')
        best_blue = None
        best_red = None
        
        print(f"🧮 Analisando {len(list(combinations(range(4), 2)))} combinações para 4 jogadores:")
        
        # Para 4 jogadores, existem apenas 3 combinações possíveis de 2x2
        combination_num = 1
        for blue_indices in combinations(range(4), 2):
            red_indices = [i for i in range(4) if i not in blue_indices]
            
            blue_team = [players[i] for i in blue_indices]
            red_team = [players[i] for i in red_indices]
            
            blue_strength = sum(p['balance_score'] for p in blue_team)
            red_strength = sum(p['balance_score'] for p in red_team)
            difference = abs(blue_strength - red_strength)
            
            blue_names = " + ".join([p['user'].display_name for p in blue_team])
            red_names = " + ".join([p['user'].display_name for p in red_team])
            
            print(f"   Opção {combination_num}: [{blue_names}] vs [{red_names}]")
            print(f"   Força: {blue_strength:.2f} vs {red_strength:.2f} | Diferença: {difference:.2f}")
            
            if difference < best_difference:
                best_difference = difference
                best_blue = blue_team
                best_red = red_team
            
            combination_num += 1
        
        print(f"✅ Melhor combinação encontrada com diferença de {best_difference:.2f}")
        return best_blue, best_red

    def _balance_teams_optimized(self, players: List[Dict], team_size: int) -> tuple:
        """Algoritmo de balanceamento otimizado para mais de 4 jogadores."""
        # Algoritmo greedy melhorado
        blue_team = []
        red_team = []
        blue_strength = 0
        red_strength = 0
        
        # Adicionar jogadores um por vez, sempre no time mais fraco
        for player in players:
            if len(blue_team) == team_size:
                red_team.append(player)
                red_strength += player['balance_score']
            elif len(red_team) == team_size:
                blue_team.append(player)
                blue_strength += player['balance_score']
            else:
                # Adicionar no time mais fraco
                if blue_strength <= red_strength:
                    blue_team.append(player)
                    blue_strength += player['balance_score']
                else:
                    red_team.append(player)
                    red_strength += player['balance_score']
        
        # Tentar otimização por troca se a diferença for muito grande
        if abs(blue_strength - red_strength) > 5 and len(players) <= 10:
            optimized_blue, optimized_red = self._try_swaps_optimization(blue_team, red_team)
            if optimized_blue and optimized_red:
                blue_team, red_team = optimized_blue, optimized_red
        
        return blue_team, red_team

    def _try_swaps_optimization(self, blue_team: List[Dict], red_team: List[Dict]) -> tuple:
        """Tenta melhorar o balanceamento trocando jogadores entre times."""
        best_blue = blue_team.copy()
        best_red = red_team.copy()
        
        current_blue_strength = sum(p['balance_score'] for p in blue_team)
        current_red_strength = sum(p['balance_score'] for p in red_team)
        best_difference = abs(current_blue_strength - current_red_strength)
        
        # Tentar todas as trocas possíveis (1 por 1)
        for i, blue_player in enumerate(blue_team):
            for j, red_player in enumerate(red_team):
                # Calcular nova força após troca
                new_blue_strength = current_blue_strength - blue_player['balance_score'] + red_player['balance_score']
                new_red_strength = current_red_strength - red_player['balance_score'] + blue_player['balance_score']
                new_difference = abs(new_blue_strength - new_red_strength)
                
                if new_difference < best_difference:
                    # Aplicar troca
                    new_blue = blue_team.copy()
                    new_red = red_team.copy()
                    new_blue[i] = red_player
                    new_red[j] = blue_player
                    
                    best_blue = new_blue
                    best_red = new_red
                    best_difference = new_difference
        
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
    def __init__(self, max_participants: int, creator: discord.Member):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.max_participants = max_participants
        self.creator = creator
        self.participants = []
        
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
            description=f"**Participantes necessários:** {self.max_participants}\\n**Participantes atuais:** {len(self.participants)}\\n\\n🎯 Clique no botão abaixo para entrar na partida!",
            color=discord.Color.blue()
        )
        
        # Lista de participantes
        participant_list = "\\n".join([f"{i+1}. {p.mention}" for i, p in enumerate(self.participants)])
        embed.add_field(
            name="👥 Participantes Confirmados",
            value=participant_list if participant_list else "Nenhum participante ainda",
            inline=False
        )
        
        # Se completou o número necessário, habilitar balanceamento
        if len(self.participants) == self.max_participants:
            embed.color = discord.Color.green()
            embed.description = f"✅ **{self.max_participants}** participantes confirmados!\\n🎲 Clique em 'Balancear Times' para gerar os times!"
            
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
            description=f"**Participantes necessários:** {self.max_participants}\\n**Participantes atuais:** {len(self.participants)}\\n\\n🎯 Clique no botão abaixo para entrar na partida!",
            color=discord.Color.blue()
        )
        
        # Lista de participantes
        if self.participants:
            participant_list = "\\n".join([f"{i+1}. {p.mention}" for i, p in enumerate(self.participants)])
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
        try:
            # Não usar followup.edit_message; edite diretamente a mensagem do componente
            
            # Buscar dados dos jogadores
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
            
            # Gerar teams usando o método existente
            team_cog = interaction.client.get_cog('TeamCog')
            if not team_cog:
                await interaction.followup.send("❌ Erro interno: TeamCog não encontrado", ephemeral=True)
                return
                
            blue_team, red_team = team_cog._balance_teams(players_data)
            
            # Calcular diferença de força
            blue_avg = sum(p['balance_score'] for p in blue_team) / len(blue_team)
            red_avg = sum(p['balance_score'] for p in red_team) / len(red_team)
            difference = abs(blue_avg - red_avg)
            
            # Criar embed final
            embed = discord.Embed(
                title="⚔️ Times Balanceados",
                description=f"Partida ARAM - {len(self.participants)} jogadores",
                color=discord.Color.green()
            )
            
            # Time Azul
            blue_text = ""
            for i, player in enumerate(blue_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                blue_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\\n"
                blue_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\\n"
            
            embed.add_field(name="🔵 Time Azul", value=blue_text, inline=True)
            
            # Time Vermelho  
            red_text = ""
            for i, player in enumerate(red_team, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                red_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\\n"
                red_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\\n"
            
            embed.add_field(name="🔴 Time Vermelho", value=red_text, inline=True)
            
            # Estatísticas
            balance_quality = team_cog._get_balance_quality(difference)
            embed.add_field(
                name="📊 Estatísticas",
                value=f"**Força Média Time Azul:** {blue_avg:.1f}\\n"
                      f"**Força Média Time Vermelho:** {red_avg:.1f}\\n"
                      f"**Diferença:** {difference:.1f}\\n"
                      f"**Qualidade:** {balance_quality['emoji']} {balance_quality['text']}",
                inline=False
            )
            
            # View com ações finais
            final_view = BalancedTeamsView(blue_team, red_team, self.participants)
            # Edita a mensagem original do painel de participantes
            await interaction.message.edit(embed=embed, view=final_view)
            
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
    def __init__(self, blue_team, red_team, all_participants):
        super().__init__(timeout=1800)  # 30 minutos
        self.blue_team = blue_team
        self.red_team = red_team
        self.all_participants = all_participants
        
        # Armazenar globalmente para resultado rápido
        TeamCog.last_teams = {
            'blue': blue_team,
            'red': red_team,
            'participants': all_participants
        }
    
    @discord.ui.button(label="🔄 Rebalancear", style=discord.ButtonStyle.secondary)
    async def rebalance(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Mesmo código de balanceamento, mas reorganiza os times
        await interaction.response.defer()
        
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
            TeamCog.last_teams = {
                'blue': new_blue,
                'red': new_red,
                'participants': self.all_participants
            }
            
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
                blue_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\\n"
                blue_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\\n"
            
            embed.add_field(name="🔵 Time Azul", value=blue_text, inline=True)
            
            red_text = ""
            for i, player in enumerate(new_red, 1):
                elo_info = config.get_elo_by_pdl(player['data']['pdl'])
                red_text += f"{i}. {elo_info['emoji']} {player['user'].mention}\\n"
                red_text += f"   `{elo_info['name']} - {player['data']['pdl']} PDL`\\n"
            
            embed.add_field(name="🔴 Time Vermelho", value=red_text, inline=True)
            
            balance_quality = team_cog._get_balance_quality(difference)
            embed.add_field(
                name="📊 Estatísticas",
                value=f"**Força Média Time Azul:** {blue_avg:.1f}\\n"
                      f"**Força Média Time Vermelho:** {red_avg:.1f}\\n"
                      f"**Diferença:** {difference:.1f}\\n"
                      f"**Qualidade:** {balance_quality['emoji']} {balance_quality['text']}",
                inline=False
            )
            
            # Edita a mensagem do componente diretamente após o defer
            await interaction.message.edit(embed=embed, view=self)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao rebalancear: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))