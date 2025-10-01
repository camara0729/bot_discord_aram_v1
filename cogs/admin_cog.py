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

    @app_commands.command(name="ajustar_stats", description="[ADMIN] Ajusta qualquer estatística de um jogador.")
    @app_commands.describe(
        jogador="O jogador a ser ajustado",
        pdl="Modificar PDL (ex: +50, -30, ou 1200 para definir valor)",
        vitorias="Modificar vitórias (ex: +2, -1, ou 15 para definir valor)",
        derrotas="Modificar derrotas (ex: +1, -1, ou 5 para definir valor)",
        mvps="Modificar MVPs (ex: +1, -1, ou 3 para definir valor)",
        bagres="Modificar bagres (ex: +1, -1, ou 2 para definir valor)"
    )
    @app_commands.default_permissions(administrator=True)
    async def ajustar_stats(
        self,
        interaction: discord.Interaction,
        jogador: discord.Member,
        pdl: str = None,
        vitorias: str = None, 
        derrotas: str = None,
        mvps: str = None,
        bagres: str = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Verificar se o jogador está registrado
            player_data = await db_manager.get_player(jogador.id)
            if not player_data:
                await interaction.followup.send(f"❌ {jogador.mention} não está registrado!")
                return
            
            changes = []
            old_values = {}
            new_values = {}
            
            # Função helper para processar valores
            def process_value(current_val, change_str, stat_name):
                if not change_str:
                    return current_val, None
                    
                old_values[stat_name] = current_val
                
                if change_str.startswith('+'):
                    new_val = current_val + int(change_str[1:])
                    changes.append(f"+{change_str[1:]} {stat_name}")
                elif change_str.startswith('-'):
                    new_val = max(0, current_val - int(change_str[1:]))
                    changes.append(f"-{change_str[1:]} {stat_name}")
                else:
                    new_val = int(change_str)
                    changes.append(f"Definir {stat_name} = {new_val}")
                
                new_values[stat_name] = new_val
                return new_val, new_val
            
            # Processar cada stat
            new_pdl, _ = process_value(player_data['pdl'], pdl, 'PDL')
            new_wins, _ = process_value(player_data['wins'], vitorias, 'vitórias')
            new_losses, _ = process_value(player_data['losses'], derrotas, 'derrotas')
            new_mvp, _ = process_value(player_data['mvp_count'], mvps, 'MVPs')
            new_bagre, _ = process_value(player_data['bagre_count'], bagres, 'bagres')
            
            if not changes:
                await interaction.followup.send("❌ Nenhuma alteração especificada!")
                return
            
            # Atualizar no banco
            import aiosqlite
            async with aiosqlite.connect("bot_database.db") as db:
                await db.execute("""
                    UPDATE players 
                    SET pdl = ?, wins = ?, losses = ?, mvp_count = ?, bagre_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                """, (new_pdl, new_wins, new_losses, new_mvp, new_bagre, jogador.id))
                await db.commit()
            
            # Criar embed de resultado
            old_elo = config.get_elo_by_pdl(old_values.get('PDL', player_data['pdl']))
            new_elo = config.get_elo_by_pdl(new_pdl)
            
            embed = discord.Embed(
                title="✅ Estatísticas Ajustadas!",
                description=f"Stats de {jogador.mention} foram atualizados:",
                color=new_elo['color']
            )
            
            # Mostrar mudanças
            embed.add_field(
                name="📊 Alterações",
                value="\n".join(changes),
                inline=False
            )
            
            # Stats atuais
            stats_text = f"**PDL:** {new_pdl} ({new_elo['emoji']} {new_elo['name']})\n"
            stats_text += f"**Record:** {new_wins}W/{new_losses}L\n"
            stats_text += f"**MVPs:** {new_mvp} | **Bagres:** {new_bagre}"
            
            embed.add_field(
                name="📈 Stats Atuais",
                value=stats_text,
                inline=False
            )
            
            embed.set_footer(text=f"Comando executado por {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
            
        except ValueError:
            await interaction.followup.send("❌ Formato inválido! Use: +10, -5, ou 1200")
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="addplayer", description="[ADMIN] Adiciona jogador manualmente.")
    @app_commands.describe(
        usuario="Usuário do Discord",
        riot_id="Riot ID (ex: Nome#TAG)", 
        rank="Rank LoL",
        pdl="PDL inicial",
        wins="Vitórias",
        losses="Derrotas"
    )
    @app_commands.default_permissions(administrator=True)
    async def addplayer(
        self, 
        interaction: discord.Interaction, 
        usuario: discord.Member,
        riot_id: str,
        rank: str = "BRONZE III",
        pdl: int = 1000,
        wins: int = 0,
        losses: int = 0
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validar rank
            if rank.upper() not in config.RANK_WEIGHTS:
                valid_ranks = ", ".join(config.RANK_WEIGHTS.keys())
                await interaction.followup.send(f"❌ Rank '{rank}' inválido. Válidos: {valid_ranks}")
                return
            
            import aiosqlite
            async with aiosqlite.connect("bot_database.db") as db:
                # Verificar se já existe
                async with db.execute("SELECT discord_id FROM players WHERE discord_id = ?", (usuario.id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Se já existe, atualizar
                    await db.execute("""
                        UPDATE players 
                        SET riot_id = ?, lol_rank = ?, username = ?, pdl = ?, wins = ?, losses = ?, 
                            updated_at = datetime('now')
                        WHERE discord_id = ?
                    """, (riot_id, rank.upper(), usuario.display_name, pdl, wins, losses, usuario.id))
                    action = "atualizado"
                else:
                    # Se não existe, inserir
                    await db.execute("""
                        INSERT INTO players 
                        (discord_id, riot_id, puuid, lol_rank, username, pdl, wins, losses, mvp_count, bagre_count, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """, (usuario.id, riot_id, "manual_puuid", rank.upper(), usuario.display_name, pdl, wins, losses, 0, 0))
                    action = "adicionado"
                
                await db.commit()
            
            # Buscar elo info
            elo_info = config.get_elo_by_pdl(pdl)
            
            embed = discord.Embed(
                title="✅ Jogador Adicionado!",
                description=f"{usuario.mention} foi {action} com sucesso:",
                color=elo_info['color']
            )
            embed.add_field(name="🎮 Riot ID", value=riot_id, inline=True)
            embed.add_field(name="🏅 Rank LoL", value=rank, inline=True)
            embed.add_field(name=f"{elo_info['emoji']} PDL", value=f"{pdl} ({elo_info['name']})", inline=True)
            embed.add_field(name="📊 Record", value=f"{wins}W/{losses}L", inline=True)
            embed.set_footer(text="Use /leaderboard para verificar!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="limpar_ids_ficticios", description="[ADMIN] Remove registros com IDs fictícios do banco.")
    @app_commands.default_permissions(administrator=True)
    async def limpar_ids_ficticios(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            import aiosqlite
            async with aiosqlite.connect("bot_database.db") as db:
                # Remover o ID fictício do Nicous
                await db.execute("DELETE FROM players WHERE discord_id = ?", (1234567890123456789,))
                
                # Remover outros IDs fictícios ou inválidos (muito grandes ou pequenos)
                await db.execute("DELETE FROM players WHERE discord_id > 9999999999999999999 OR discord_id < 100000000000000000")
                
                await db.commit()
            
            embed = discord.Embed(
                title="✅ IDs Fictícios Removidos",
                description="Registros com IDs fictícios foram removidos do banco de dados.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="atualizar_nomes", description="[ADMIN] Atualiza os nomes dos jogadores no banco de dados.")
    @app_commands.default_permissions(administrator=True)
    async def atualizar_nomes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            all_players = await db_manager.get_all_players()
            if not all_players:
                await interaction.followup.send("❌ Nenhum jogador encontrado.")
                return
                
            updated_count = 0
            failed_count = 0
            
            for player in all_players:
                try:
                    user = self.bot.get_user(player['discord_id'])
                    if not user:
                        try:
                            user = await self.bot.fetch_user(player['discord_id'])
                        except:
                            user = None
                    
                    if user:
                        success = await db_manager.update_player_username(player['discord_id'], user.display_name)
                        if success:
                            updated_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    print(f"Erro ao atualizar username: {e}")
                    failed_count += 1
            
            embed = discord.Embed(
                title="✅ Nomes Atualizados",
                description=f"Atualizados: {updated_count}\nFalharam: {failed_count}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))