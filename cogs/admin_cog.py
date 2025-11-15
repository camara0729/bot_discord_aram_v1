# cogs/admin_cog.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os
from utils.database_manager import db_manager
from utils.backup_transport import send_backup_file
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
            async with aiosqlite.connect(db_manager.db_path) as db:
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
            async with aiosqlite.connect(db_manager.db_path) as db:
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
            embed.set_footer(text="Use /ranking para verificar!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="limpar_ids_ficticios", description="[ADMIN] Remove registros com IDs fictícios do banco.")
    @app_commands.default_permissions(administrator=True)
    async def limpar_ids_ficticios(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            import aiosqlite
            async with aiosqlite.connect(db_manager.db_path) as db:
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

    @app_commands.command(name="restaurar_dados", description="[ADMIN] Restaura os dados para o estado correto atual.")
    @app_commands.default_permissions(administrator=True)
    async def restaurar_dados(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Dados corretos como devem estar (preserve MVPs/Bagres se já existirem)
            corrections = {
                267830206302126081: {"pdl": 1220, "wins": 12, "losses": 4, "name": "mateusabb"},
                207835175135084544: {"pdl": 1115, "wins": 5, "losses": 1, "name": "Feitosa"},
                1042259376070742087: {"pdl": 1100, "wins": 8, "losses": 5, "name": "lcris"},
                682749260961153144: {"pdl": 1065, "wins": 9, "losses": 9, "name": "Pedro Luiz"},
                267713314086191125: {"pdl": 1060, "wins": 8, "losses": 8, "name": "Sérgio"},
                348276973853999105: {"pdl": 1045, "wins": 5, "losses": 4, "name": "paredao"},
                534894751330205699: {"pdl": 1030, "wins": 8, "losses": 8, "name": "Guilherme"},
                760704217055756288: {"pdl": 910, "wins": 0, "losses": 4, "name": "Daydrex"},
                297136556966150145: {"pdl": 850, "wins": 5, "losses": 13, "name": "Fausto"}
            }
            
            import aiosqlite
            corrected_count = 0
            errors = []
            
            async with aiosqlite.connect(db_manager.db_path) as db:
                for discord_id, stats in corrections.items():
                    try:
                        # Verificar se o jogador existe
                        async with db.execute("SELECT discord_id FROM players WHERE discord_id = ?", (discord_id,)) as cursor:
                            if await cursor.fetchone():
                                # Buscar MVP/Bagre atuais para preservar
                                async with db.execute("SELECT mvp_count, bagre_count FROM players WHERE discord_id = ?", (discord_id,)) as c2:
                                    cur = await c2.fetchone()
                                current_mvp = cur[0] if cur else 0
                                current_bagre = cur[1] if cur else 0

                                await db.execute("""
                                    UPDATE players 
                                    SET pdl = ?, wins = ?, losses = ?, mvp_count = ?, bagre_count = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE discord_id = ?
                                """, (stats["pdl"], stats["wins"], stats["losses"], current_mvp, current_bagre, discord_id))
                                corrected_count += 1
                            else:
                                errors.append(f"{stats['name']} não encontrado")
                    except Exception as e:
                        errors.append(f"{stats['name']}: {str(e)}")
                
                await db.commit()
            
            embed = discord.Embed(
                title="✅ Dados Restaurados!",
                description=f"{corrected_count} jogadores tiveram seus dados corrigidos para o estado atual correto.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Dados Corrigidos",
                value="• mateusabb: 1220 PDL, 12W/4L (🟡 Ouro)\n"
                      "• Feitosa: 1115 PDL, 5W/1L\n"
                      "• lcris: 1100 PDL, 8W/5L\n"
                      "• Pedro Luiz: 1065 PDL, 9W/9L\n"
                      "• Sérgio: 1060 PDL, 8W/8L\n"
                      "• paredao: 1045 PDL, 5W/4L\n"
                      "• Guilherme: 1030 PDL, 8W/8L\n"
                      "• Daydrex: 910 PDL, 0W/4L (🟤 Bronze)\n"
                      "• Fausto: 850 PDL, 5W/13L (🟤 Bronze)",
                inline=False
            )
            
            if errors:
                embed.add_field(
                    name="⚠️ Erros",
                    value="\n".join(errors[:5]),
                    inline=False
                )
            
            embed.add_field(
                name="🎯 Próximo Passo",
                value=(
                    "Execute `/ranking` para verificar os dados corretos!\n"
                    "Se precisar adicionar um jogador faltando, use `/addplayer usuario:@Nicous riot_id:Nick#TAG rank:BRONZE III pdl:910 wins:1 losses:5`.\n"
                    "Depois ajuste MVPs/Bagres com `/ajustar_stats` se necessário."
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="fazer_backup", description="[ADMIN] Cria backup manual e envia para o webhook configurado.")
    @app_commands.default_permissions(administrator=True)
    async def fazer_backup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from datetime import datetime
            from backup_restore_db import backup_database
            
            # Verificar quantos dados temos
            players = await db_manager.get_all_players()
            if not players:
                await interaction.followup.send("❌ Não há dados para backup!")
                return
                
            await interaction.followup.send(f"🔄 Criando backup de {len(players)} jogadores...")
            
            # Criar backup
            backup_file = f"manual_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            success_file = await backup_database(backup_file)
            
            if success_file:
                uploaded = await send_backup_file(success_file, f"Backup manual acionado por {interaction.user.display_name}")
                if uploaded:
                    await interaction.followup.send(
                        f"✅ Backup criado e enviado!\n📁 Arquivo: `{success_file}`\n👥 Jogadores: {len(players)}"
                    )
                else:
                    await interaction.followup.send(
                        f"⚠️ Backup criado mas não foi possível enviá-lo automaticamente.\n"
                        f"📁 Arquivo local: `{success_file}`\nConfigure `BACKUP_WEBHOOK_URL` para habilitar o envio."
                    )
            else:
                await interaction.followup.send("❌ Falha ao criar arquivo de backup!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="restaurar_backup", description="[ADMIN] Restaura dados de um backup específico.")
    @app_commands.describe(arquivo="Nome do arquivo de backup (ex: backup_20240101_120000.json)")
    @app_commands.default_permissions(administrator=True)
    async def restaurar_backup(self, interaction: discord.Interaction, arquivo: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from pathlib import Path
            from backup_restore_db import restore_database
            
            # Verificar se arquivo existe
            if not Path(arquivo).exists():
                await interaction.followup.send(f"❌ Arquivo não encontrado: `{arquivo}`")
                return
            
            # Verificar dados atuais
            current_players = await db_manager.get_all_players()
            
            # Pedir confirmação se há dados
            if current_players:
                embed = discord.Embed(
                    title="⚠️ CONFIRMAÇÃO NECESSÁRIA",
                    description=f"Existem **{len(current_players)} jogadores** no banco atual!\n\n**Isso irá SUBSTITUIR todos os dados atuais!**",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="Para continuar:",
                    value=f"Digite `/confirmar_restore arquivo:{arquivo}` nos próximos 60 segundos.",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Se não há dados, pode restaurar diretamente
            await interaction.followup.send(f"🔄 Restaurando dados de `{arquivo}`...")
            
            success = await restore_database(arquivo, confirm=True)
            
            if success:
                # Verificar quantos jogadores foram restaurados
                restored_players = await db_manager.get_all_players()
                await interaction.followup.send(f"✅ Restauração concluída!\n👥 Jogadores restaurados: {len(restored_players)}")
            else:
                await interaction.followup.send("❌ Falha na restauração!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="confirmar_restore", description="[ADMIN] Confirma a restauração de backup (substitui todos os dados!).")
    @app_commands.describe(arquivo="Nome do arquivo de backup para restaurar")
    @app_commands.default_permissions(administrator=True)
    async def confirmar_restore(self, interaction: discord.Interaction, arquivo: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from pathlib import Path
            from backup_restore_db import restore_database
            
            # Verificar se arquivo existe
            if not Path(arquivo).exists():
                await interaction.followup.send(f"❌ Arquivo não encontrado: `{arquivo}`")
                return
            
            await interaction.followup.send(f"🔄 RESTAURANDO DADOS de `{arquivo}`...\n⚠️ **TODOS OS DADOS ATUAIS SERÃO SUBSTITUÍDOS!**")
            
            success = await restore_database(arquivo, confirm=True)
            
            if success:
                # Verificar quantos jogadores foram restaurados
                restored_players = await db_manager.get_all_players()
                
                embed = discord.Embed(
                    title="✅ Restauração Concluída!",
                    description=f"Dados restaurados com sucesso de `{arquivo}`",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="👥 Jogadores Restaurados",
                    value=f"**{len(restored_players)}** jogadores",
                    inline=True
                )
                embed.add_field(
                    name="🎯 Próximo Passo",
                    value="Execute `/ranking` para verificar os dados!",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Falha na restauração!")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="status_backup", description="[ADMIN] Verifica status do sistema de backup.")
    @app_commands.default_permissions(administrator=True)
    async def status_backup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            import os
            from pathlib import Path
            from datetime import datetime
            
            # Informações básicas
            players = await db_manager.get_all_players()
            is_render = os.getenv('RENDER')
            webhook_url = os.getenv('BACKUP_WEBHOOK_URL')
            
            embed = discord.Embed(
                title="📊 Status do Sistema de Backup",
                color=discord.Color.blue()
            )
            
            # Dados atuais
            embed.add_field(
                name="📈 Dados Atuais",
                value=f"👥 **{len(players)}** jogadores registrados\n🏗️ Ambiente: {'Render Free Tier' if is_render else 'Local/Outro'}",
                inline=False
            )
            
            embed.add_field(
                name="🌐 Webhook",
                value="✅ Configurado" if webhook_url else "⚠️ Configure BACKUP_WEBHOOK_URL para envio automático",
                inline=False
            )

            embed.add_field(
                name="💽 Local do Banco",
                value=f"`{db_manager.db_path}`",
                inline=False
            )
            
            # Verificar arquivos de backup
            backup_files = []
            for pattern in ["*backup*.json", "render_migration_backup.json"]:
                backup_files.extend(Path('.').glob(pattern))
            
            if backup_files:
                backup_info = ""
                for file in sorted(backup_files)[:5]:  # Mostrar apenas os 5 mais recentes
                    stat = file.stat()
                    size_kb = stat.st_size / 1024
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                    backup_info += f"📁 `{file.name}` ({size_kb:.1f}KB) - {mod_time.strftime('%d/%m %H:%M')}\n"
                
                embed.add_field(
                    name="💾 Arquivos de Backup Locais",
                    value=backup_info or "Nenhum arquivo encontrado",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💾 Arquivos de Backup Locais",
                    value="📭 Nenhum arquivo local encontrado",
                    inline=False
                )
            
            # Verificar último backup automático
            last_backup_file = ".last_backup_time"
            if Path(last_backup_file).exists():
                try:
                    with open(last_backup_file, 'r') as f:
                        last_backup_str = f.read().strip()
                    last_backup = datetime.fromisoformat(last_backup_str)
                    time_since = datetime.now() - last_backup
                    
                    embed.add_field(
                        name="🕐 Último Backup Automático",
                        value=f"⏰ {time_since} atrás\n📅 {last_backup.strftime('%d/%m/%Y %H:%M:%S')}",
                        inline=False
                    )
                except:
                    embed.add_field(
                        name="🕐 Último Backup Automático",
                        value="⚠️ Erro ao ler timestamp",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="🕐 Último Backup Automático",
                    value="❓ Nenhum backup automático registrado",
                    inline=False
                )
            
            embed.add_field(
                name="🛠️ Comandos Úteis",
                value="`/fazer_backup` - Backup manual\n`/restaurar_backup arquivo:nome.json` - Restaurar backup\n`/listar_backups` - Ver arquivos disponíveis",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

    @app_commands.command(name="listar_backups", description="[ADMIN] Lista todos os arquivos de backup disponíveis.")
    @app_commands.default_permissions(administrator=True)
    async def listar_backups(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from pathlib import Path
            from datetime import datetime
            import json
            
            # Procurar arquivos de backup
            backup_patterns = ["*backup*.json", "render_migration_backup.json*"]
            all_backups = []
            
            for pattern in backup_patterns:
                all_backups.extend(Path('.').glob(pattern))
            
            if not all_backups:
                await interaction.followup.send("📭 Nenhum arquivo de backup encontrado!")
                return
            
            # Ordenar por data de modificação (mais recentes primeiro)
            all_backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            embed = discord.Embed(
                title="📋 Arquivos de Backup Disponíveis",
                description=f"Encontrados **{len(all_backups)}** arquivos de backup",
                color=discord.Color.blue()
            )
            
            backup_list = ""
            for i, backup_file in enumerate(all_backups[:10]):  # Mostrar apenas os 10 mais recentes
                stat = backup_file.stat()
                size_kb = stat.st_size / 1024
                mod_time = datetime.fromtimestamp(stat.st_mtime)
                
                # Tentar ler informações do backup
                try:
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        backup_data = json.load(f)
                    player_count = backup_data.get('total_players', 'N/A')
                    backup_date = backup_data.get('backup_date', 'N/A')
                    extra_info = f" - {player_count} jogadores"
                except:
                    extra_info = ""
                
                backup_list += f"📁 **`{backup_file.name}`**\n"
                backup_list += f"   📊 {size_kb:.1f}KB • 🕐 {mod_time.strftime('%d/%m/%Y %H:%M')}{extra_info}\n\n"
            
            if len(all_backups) > 10:
                backup_list += f"... e mais {len(all_backups) - 10} arquivos"
            
            embed.add_field(
                name="📂 Arquivos (mais recentes primeiro)",
                value=backup_list,
                inline=False
            )
            
            embed.add_field(
                name="💡 Como usar",
                value="Para restaurar: `/restaurar_backup arquivo:nome_do_arquivo.json`",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
