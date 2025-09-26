# cogs/admin_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os
from utils.database_manager import db_manager
import config

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="adicionar_pdl", description="[ADMIN] Adiciona ou remove PDL de um jogador.")
    @app_commands.describe(
        jogador="O jogador que receberá/perderá os pontos",
        quantidade="Quantidade de PDL (positivo para adicionar, negativo para remover)"
    )
    @app_commands.default_permissions(administrator=True)
    async def adicionar_pdl(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        quantidade: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Verificar se o jogador está registrado
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado! Use `/registrar` primeiro.")
                return
            
            old_pdl = player_data['pdl']
            
            # Atualizar PDL
            success = await db_manager.update_player_pdl(jogador.id, quantidade)
            
            if success:
                # Buscar dados atualizados
                updated_data = await db_manager.get_player(jogador.id)
                new_pdl = updated_data['pdl']
                
                # Informações de elo
                old_elo = config.get_elo_by_pdl(old_pdl)
                new_elo = config.get_elo_by_pdl(new_pdl)
                
                embed = discord.Embed(
                    title="✅ PDL Atualizado!",
                    description=f"PDL de {jogador.mention} foi modificado com sucesso!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**PDL Anterior:** {old_pdl}\n"
                          f"**PDL Atual:** {new_pdl}\n"
                          f"**Diferença:** {'+' if quantidade >= 0 else ''}{quantidade}",
                    inline=True
                )
                
                embed.add_field(
                    name="🏆 Elos",
                    value=f"**Anterior:** {old_elo['emoji']} {old_elo['name']}\n"
                          f"**Atual:** {new_elo['emoji']} {new_elo['name']}",
                    inline=True
                )
                
                # Verificar mudança de elo
                if old_elo['name'] != new_elo['name']:
                    if new_pdl > old_pdl:
                        embed.add_field(
                            name="🎉 Promoção!", 
                            value=f"{jogador.mention} subiu para {new_elo['emoji']} {new_elo['name']}!", 
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="📉 Rebaixamento", 
                            value=f"{jogador.mention} caiu para {new_elo['emoji']} {new_elo['name']}", 
                            inline=False
                        )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao atualizar PDL!")
                
        except Exception as e:
            print(f"Erro ao adicionar PDL: {e}")
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="definir_pdl", description="[ADMIN] Define o PDL de um jogador para um valor específico.")
    @app_commands.describe(
        jogador="O jogador que terá o PDL definido",
        valor="Valor específico de PDL"
    )
    @app_commands.default_permissions(administrator=True)
    async def definir_pdl(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        valor: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Verificar se o jogador está registrado
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_pdl = player_data['pdl']
            
            # Definir PDL
            success = await db_manager.set_player_pdl(jogador.id, valor)
            
            if success:
                # Informações de elo
                old_elo = config.get_elo_by_pdl(old_pdl)
                new_elo = config.get_elo_by_pdl(valor)
                
                embed = discord.Embed(
                    title="✅ PDL Definido!",
                    description=f"PDL de {jogador.mention} foi definido para {valor}!",
                    color=new_elo['color']
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**PDL Anterior:** {old_pdl}\n"
                          f"**PDL Atual:** {valor}\n"
                          f"**Diferença:** {'+' if (valor - old_pdl) >= 0 else ''}{valor - old_pdl}",
                    inline=True
                )
                
                embed.add_field(
                    name="🏆 Novo Elo",
                    value=f"{new_elo['emoji']} **{new_elo['name']}**",
                    inline=True
                )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao definir PDL!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="resetar_pdl", description="[ADMIN] Reseta o PDL de um jogador para o padrão (1000).")
    @app_commands.describe(jogador="O jogador que terá o PDL resetado")
    @app_commands.default_permissions(administrator=True)
    async def resetar_pdl(self, interaction: discord.Interaction, jogador: discord.Member):
        await interaction.response.defer(ephemeral=True)
        
        try:
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_pdl = player_data['pdl']
            
            # Resetar para PDL padrão
            success = await db_manager.reset_player_pdl(jogador.id)
            
            if success:
                elo_info = config.get_elo_by_pdl(config.DEFAULT_PDL)
                embed = discord.Embed(
                    title="🔄 PDL Resetado!",
                    description=f"PDL de {jogador.mention} foi resetado para {config.DEFAULT_PDL}",
                    color=elo_info['color']
                )
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**PDL Anterior:** {old_pdl}\n"
                          f"**PDL Atual:** {config.DEFAULT_PDL}",
                    inline=True
                )
                embed.add_field(
                    name="🏆 Novo Elo", 
                    value=f"{elo_info['emoji']} **{elo_info['name']}**", 
                    inline=True
                )
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao resetar PDL!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="historico_pdl", description="Veja o breakdown detalhado do PDL de um jogador.")
    @app_commands.describe(jogador="O jogador cujo histórico você quer ver (opcional)")
    async def historico_pdl(self, interaction: discord.Interaction, jogador: Optional[discord.Member] = None):
        target_user = jogador or interaction.user
        
        player_data = await db_manager.get_player(target_user.id)
        if not player_data:
            await interaction.response.send_message(f"{target_user.mention} não está registrado!", ephemeral=True)
            return
        
        # Calcular breakdown do PDL
        pdl_from_wins = player_data['wins'] * config.PDL_WIN
        pdl_from_losses = player_data['losses'] * config.PDL_LOSS
        mvp_bonus = player_data['mvp_count'] * config.MVP_BONUS
        bagre_penalty = player_data['bagre_count'] * config.BAGRE_PENALTY
        
        calculated_pdl = config.DEFAULT_PDL + pdl_from_wins + pdl_from_losses + mvp_bonus + bagre_penalty
        manual_adjustments = player_data['pdl'] - calculated_pdl
        
        elo_info = config.get_elo_by_pdl(player_data['pdl'])
        
        embed = discord.Embed(
            title=f"📊 Histórico de PDL - {target_user.display_name}",
            color=elo_info['color']
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(
            name="🎯 Breakdown do PDL",
            value=f"**PDL Inicial:** {config.DEFAULT_PDL}\n"
                  f"**Vitórias:** +{pdl_from_wins} ({player_data['wins']} × {config.PDL_WIN})\n"
                  f"**Derrotas:** {pdl_from_losses} ({player_data['losses']} × {config.PDL_LOSS})\n"
                  f"**Bônus MVP:** +{mvp_bonus} ({player_data['mvp_count']} × {config.MVP_BONUS})\n"
                  f"**Penalidade Bagre:** {bagre_penalty} ({player_data['bagre_count']} × {config.BAGRE_PENALTY})\n"
                  f"**Ajustes Manuais:** {'+' if manual_adjustments >= 0 else ''}{manual_adjustments}",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Status Atual",
            value=f"**PDL Total:** {player_data['pdl']}\n"
                  f"**Elo:** {elo_info['emoji']} {elo_info['name']}",
            inline=True
        )
        
        # Estatísticas gerais
        total_games = player_data['wins'] + player_data['losses']
        win_rate = (player_data['wins'] / total_games * 100) if total_games > 0 else 0
        
        embed.add_field(
            name="📈 Estatísticas",
            value=f"**Partidas:** {total_games}\n"
                  f"**Taxa Vitória:** {win_rate:.1f}%\n"
                  f"**MVPs:** {player_data['mvp_count']}\n"
                  f"**Bagres:** {player_data['bagre_count']}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="adicionar_mvp", description="[ADMIN] Adiciona ou remove MVPs de um jogador.")
    @app_commands.describe(
        jogador="O jogador que receberá/perderá MVPs",
        quantidade="Quantidade de MVPs (positivo para adicionar, negativo para remover)"
    )
    @app_commands.default_permissions(administrator=True)
    async def adicionar_mvp(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        quantidade: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Verificar se o jogador está registrado
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_mvp = player_data['mvp_count']
            new_mvp = max(0, old_mvp + quantidade)  # Não permite valores negativos
            
            # Verificar se a operação resultaria em valor negativo
            if old_mvp + quantidade < 0:
                await interaction.followup.send(f"❌ Não é possível remover {abs(quantidade)} MVPs. {jogador.mention} tem apenas {old_mvp} MVPs.")
                return
            
            # Atualizar MVP count
            success = await db_manager.update_player_mvp_count(jogador.id, quantidade)
            
            if success:
                embed = discord.Embed(
                    title="⭐ MVPs Atualizados!",
                    description=f"MVPs de {jogador.mention} foram modificados com sucesso!",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**MVPs Anteriores:** {old_mvp}\n"
                          f"**MVPs Atuais:** {new_mvp}\n"
                          f"**Diferença:** {'+' if quantidade >= 0 else ''}{quantidade}",
                    inline=True
                )
                
                # Calcular impacto no PDL (se aplicável)
                pdl_impact = quantidade * config.MVP_BONUS
                if pdl_impact != 0:
                    embed.add_field(
                        name="💰 Impacto no PDL",
                        value=f"**Bônus MVP:** {'+' if pdl_impact >= 0 else ''}{pdl_impact} PDL\n"
                              f"*(Nota: O PDL não foi alterado automaticamente)*",
                        inline=True
                    )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao atualizar MVPs!")
                
        except Exception as e:
            print(f"Erro ao adicionar MVP: {e}")
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="adicionar_bagre", description="[ADMIN] Adiciona ou remove Bagres de um jogador.")
    @app_commands.describe(
        jogador="O jogador que receberá/perderá Bagres",
        quantidade="Quantidade de Bagres (positivo para adicionar, negativo para remover)"
    )
    @app_commands.default_permissions(administrator=True)
    async def adicionar_bagre(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        quantidade: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Verificar se o jogador está registrado
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_bagre = player_data['bagre_count']
            new_bagre = max(0, old_bagre + quantidade)  # Não permite valores negativos
            
            # Verificar se a operação resultaria em valor negativo
            if old_bagre + quantidade < 0:
                await interaction.followup.send(f"❌ Não é possível remover {abs(quantidade)} Bagres. {jogador.mention} tem apenas {old_bagre} Bagres.")
                return
            
            # Atualizar Bagre count
            success = await db_manager.update_player_bagre_count(jogador.id, quantidade)
            
            if success:
                embed = discord.Embed(
                    title="💩 Bagres Atualizados!",
                    description=f"Bagres de {jogador.mention} foram modificados!",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**Bagres Anteriores:** {old_bagre}\n"
                          f"**Bagres Atuais:** {new_bagre}\n"
                          f"**Diferença:** {'+' if quantidade >= 0 else ''}{quantidade}",
                    inline=True
                )
                
                # Calcular impacto no PDL (se aplicável)
                pdl_impact = quantidade * config.BAGRE_PENALTY
                if pdl_impact != 0:
                    embed.add_field(
                        name="💰 Impacto no PDL",
                        value=f"**Penalidade Bagre:** {pdl_impact} PDL\n"
                              f"*(Nota: O PDL não foi alterado automaticamente)*",
                        inline=True
                    )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao atualizar Bagres!")
                
        except Exception as e:
            print(f"Erro ao adicionar Bagre: {e}")
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="definir_mvp", description="[ADMIN] Define a quantidade de MVPs de um jogador.")
    @app_commands.describe(
        jogador="O jogador que terá os MVPs definidos",
        valor="Quantidade específica de MVPs"
    )
    @app_commands.default_permissions(administrator=True)
    async def definir_mvp(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        valor: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        if valor < 0:
            await interaction.followup.send("❌ A quantidade de MVPs não pode ser negativa!")
            return
        
        try:
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_mvp = player_data['mvp_count']
            success = await db_manager.set_player_mvp_count(jogador.id, valor)
            
            if success:
                embed = discord.Embed(
                    title="⭐ MVPs Definidos!",
                    description=f"MVPs de {jogador.mention} foram definidos para {valor}!",
                    color=discord.Color.gold()
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**MVPs Anteriores:** {old_mvp}\n"
                          f"**MVPs Atuais:** {valor}\n"
                          f"**Diferença:** {'+' if (valor - old_mvp) >= 0 else ''}{valor - old_mvp}",
                    inline=True
                )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao definir MVPs!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="definir_bagre", description="[ADMIN] Define a quantidade de Bagres de um jogador.")
    @app_commands.describe(
        jogador="O jogador que terá os Bagres definidos",
        valor="Quantidade específica de Bagres"
    )
    @app_commands.default_permissions(administrator=True)
    async def definir_bagre(
        self, 
        interaction: discord.Interaction, 
        jogador: discord.Member, 
        valor: int
    ):
        await interaction.response.defer(ephemeral=True)
        
        if valor < 0:
            await interaction.followup.send("❌ A quantidade de Bagres não pode ser negativa!")
            return
        
        try:
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            old_bagre = player_data['bagre_count']
            success = await db_manager.set_player_bagre_count(jogador.id, valor)
            
            if success:
                embed = discord.Embed(
                    title="💩 Bagres Definidos!",
                    description=f"Bagres de {jogador.mention} foram definidos para {valor}!",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="📊 Mudanças",
                    value=f"**Bagres Anteriores:** {old_bagre}\n"
                          f"**Bagres Atuais:** {valor}\n"
                          f"**Diferença:** {'+' if (valor - old_bagre) >= 0 else ''}{valor - old_bagre}",
                    inline=True
                )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Erro ao definir Bagres!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="resetar_stats", description="[ADMIN] Reseta todas as estatísticas de um jogador.")
    @app_commands.describe(jogador="O jogador que terá as estatísticas resetadas")
    @app_commands.default_permissions(administrator=True)
    async def resetar_stats(self, interaction: discord.Interaction, jogador: discord.Member):
        await interaction.response.defer(ephemeral=True)
        
        try:
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            # Criar view de confirmação
            view = ResetStatsConfirmView(jogador, player_data)
            
            embed = discord.Embed(
                title="⚠️ RESETAR ESTATÍSTICAS",
                description=f"Tem certeza que deseja resetar TODAS as estatísticas de {jogador.mention}?",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="📊 Estatísticas Atuais",
                value=f"**Vitórias:** {player_data['wins']}\n"
                      f"**Derrotas:** {player_data['losses']}\n"
                      f"**MVPs:** {player_data['mvp_count']}\n"
                      f"**Bagres:** {player_data['bagre_count']}",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Após Reset",
                value=f"**Vitórias:** 0\n"
                      f"**Derrotas:** 0\n"
                      f"**MVPs:** 0\n"
                      f"**Bagres:** 0",
                inline=True
            )
            
            embed.add_field(
                name="⚠️ ATENÇÃO",
                value="**O PDL NÃO será alterado!**\nApenas as estatísticas serão resetadas.",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

class ResetStatsConfirmView(discord.ui.View):
    def __init__(self, player: discord.Member, player_data: dict):
        super().__init__(timeout=60)
        self.player = player
        self.player_data = player_data

    @discord.ui.button(label="✅ SIM, RESETAR", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            success = await db_manager.reset_player_stats(self.player.id)
            
            if success:
                embed = discord.Embed(
                    title="✅ Estatísticas Resetadas!",
                    description=f"Todas as estatísticas de {self.player.mention} foram resetadas com sucesso!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="📊 Estatísticas Resetadas",
                    value=f"**Vitórias:** {self.player_data['wins']} → 0\n"
                          f"**Derrotas:** {self.player_data['losses']} → 0\n"
                          f"**MVPs:** {self.player_data['mvp_count']} → 0\n"
                          f"**Bagres:** {self.player_data['bagre_count']} → 0",
                    inline=False
                )
                
                embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message("❌ Erro ao resetar estatísticas!", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {str(e)}", ephemeral=True)

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Reset Cancelado",
            description="Reset das estatísticas foi cancelado.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))