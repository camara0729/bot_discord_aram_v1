# main.py
import asyncio
import os
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import aiohttp
from aiohttp import web

from utils.database_manager import db_manager
from utils.backup_transport import send_backup_file

load_dotenv()

# Configurações do Render/Web Service
PORT = int(os.getenv('PORT', 10000))
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{PORT}')

# Configurações do bot
TOKEN = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Token do Discord não encontrado. Configure a variável DISCORD_TOKEN no Render.")

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Criar o bot com configurações otimizadas
bot = commands.Bot(
    command_prefix='!', 
    intents=intents,
    help_command=None,
    max_messages=1000,
    chunk_guilds_at_startup=False
)

# Evento para quando o bot estiver pronto
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user} está online!")
    print(f"📊 Conectado em {len(bot.guilds)} servidor(s)")
    
    # Inicializar o banco de dados
    print("📚 Inicializando banco de dados...")
    await db_manager.initialize_database()
    
    # Iniciar sistema keep-alive
    if not periodic_backup_task.is_running():
        periodic_backup_task.start()
        print("💾 Rotina de backup remoto iniciada")
    if not keep_alive_ping.is_running():
        keep_alive_ping.start()
        print("🚀 Sistema keep-alive iniciado")

async def auto_migrate_if_needed():
    """Executa migração automática se backup existir e banco estiver vazio."""
    import os
    from pathlib import Path
    
    backup_file = "render_migration_backup.json"
    
    if Path(backup_file).exists():
        players = await db_manager.get_all_players()
        if not players:  # Banco vazio
            print("🔄 Detectado ambiente novo - iniciando migração automática...")
            try:
                # Import dinâmico para evitar dependência circular
                from backup_restore_db import restore_database
                success = await restore_database(backup_file, confirm=True)
                if success:
                    print("✅ Migração automática concluída!")
                    # Renomear arquivo ao invés de remover para evitar migração repetida
                    os.rename(backup_file, f"{backup_file}.usado")
                    print("📁 Arquivo de backup marcado como usado")
                else:
                    print("❌ Falha na migração automática!")
            except Exception as e:
                print(f"❌ Erro na migração automática: {e}")
        else:
            print(f"📊 Banco já populado com {len(players)} jogadores - pulando migração")
            # Se há jogadores mas o backup ainda existe, marcar como usado
            if Path(backup_file).exists():
                os.rename(backup_file, f"{backup_file}.usado")
                print("📁 Backup marcado como usado (banco já tinha dados)")
    else:
        print("📋 Nenhum backup de migração encontrado")

async def remote_backup_system(force: bool = False):
    """Sistema de backup automático enviando JSON para um webhook externo."""
    from datetime import timedelta

    try:
        is_render = os.getenv('RENDER')
        if not is_render and not force:
            print("📍 Não está no Render - backup remoto ignorado")
            return

        webhook_url = os.getenv('BACKUP_WEBHOOK_URL')
        if not webhook_url:
            print("⚠️ BACKUP_WEBHOOK_URL não configurada - backup remoto inativo")
            return

        backup_frequency_hours = int(os.getenv('BACKUP_FREQUENCY_HOURS', '6'))
        backup_file = 'auto_backup_render.json'
        last_backup_marker = Path('.last_backup_time')

        should_backup = force
        if not should_backup and last_backup_marker.exists():
            try:
                last_backup = datetime.fromisoformat(last_backup_marker.read_text().strip())
                time_since_backup = datetime.now() - last_backup
                if time_since_backup >= timedelta(hours=backup_frequency_hours):
                    should_backup = True
                    print(f"⏰ Último backup há {time_since_backup} - iniciando novo backup")
                else:
                    print(f"✅ Backup recente ({time_since_backup}) - aguardando próxima janela")
            except Exception:
                should_backup = True
                print("⚠️ Não foi possível ler o último backup - recriando")
        elif not should_backup:
            should_backup = True
            print("🔍 Nenhum backup anterior - iniciando backup inicial")

        if not should_backup:
            return

        players = await db_manager.get_all_players()
        if not players:
            print("📭 Banco vazio - backup remoto ignorado")
            return

        from backup_restore_db import backup_database

        print(f"📤 Preparando backup remoto de {len(players)} jogadores...")
        success_file = await backup_database(backup_file)
        if not success_file:
            print("❌ Falha ao gerar arquivo de backup")
            return

        description = (
            f"Backup automático {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - "
            f"{len(players)} jogadores"
        )
        uploaded = await send_backup_file(success_file, description)
        if uploaded:
            last_backup_marker.write_text(datetime.now().isoformat())
            try:
                Path(success_file).unlink(missing_ok=True)
            except Exception:
                pass
        else:
            print("⚠️ Backup criado mas não foi possível enviar ao webhook")

    except Exception as e:
        print(f"❌ Erro no sistema de backup remoto: {e}")

async def restore_from_git_backup():
    """Restaura dados do último backup Git disponível."""
    import os
    from pathlib import Path
    
    try:
        backup_files = [
            "auto_backup_render.json",
            "render_migration_backup.json",
            "backup_atual_render.json"
        ]
        
        for backup_file in backup_files:
            if Path(backup_file).exists():
                print(f"🔍 Backup encontrado: {backup_file}")
                
                # Verificar se banco está vazio
                players = await db_manager.get_all_players()
                if not players:
                    print("🔄 Restaurando dados do backup Git...")
                    from backup_restore_db import restore_database
                    success = await restore_database(backup_file, confirm=True)
                    if success:
                        print("✅ Dados restaurados do backup Git!")
                        return True
                else:
                    print(f"📊 Banco já tem {len(players)} jogadores - não restaurando")
                    return True
        
        print("📋 Nenhum backup Git encontrado")
        return False
        
    except Exception as e:
        print(f"❌ Erro ao restaurar do backup Git: {e}")
        return False

async def health_check(request):
    """Endpoint de health check para manter o serviço ativo no Render."""
    return web.json_response({
        'status': 'alive',
        'bot': bot.user.name if bot.user else 'Not ready',
        'timestamp': datetime.now().isoformat(),
        'guilds': len(bot.guilds),
        'uptime': 'online'
    })

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', health_check)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Servidor web iniciado na porta {PORT}")

@tasks.loop(minutes=8)
async def keep_alive_ping():
    """Ping periódico para evitar hibernação no Render Free."""
    try:
        timeout = aiohttp.ClientTimeout(total=30, connect=15)
        target = os.getenv('RENDER_EXTERNAL_URL') or f'http://localhost:{PORT}'
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{target}/ping") as response:
                current_time = datetime.now().strftime('%H:%M:%S')
                if response.status == 200:
                    print(f"✅ Keep-alive ping successful - {current_time}")
                else:
                    print(f"⚠️ Keep-alive ping failed ({response.status}) - {current_time}")
    except Exception as e:
        current_time = datetime.now().strftime('%H:%M:%S')
        print(f"❌ Erro no keep-alive ping ({current_time}): {e}")


@keep_alive_ping.before_loop
async def before_keep_alive():
    await bot.wait_until_ready()

@tasks.loop(hours=1)
async def periodic_backup_task():
    """Executa o processo de backup remoto periodicamente."""
    try:
        await remote_backup_system()
    except Exception as e:
        print(f"⚠️ Erro no backup periódico: {e}")


@periodic_backup_task.before_loop
async def before_backup():
    await bot.wait_until_ready()

# Carregar cogs
async def load_cogs():
    cog_files = [
        'player_cog',
        'team_cog',
        'match_cog',
        'admin_cog',
        'ranking_cog',
    ]
    
    for cog_name in cog_files:
        try:
            await bot.load_extension(f'cogs.{cog_name}')
            print(f"Carregado: cogs.{cog_name}")
        except Exception as e:
            print(f"Falha ao carregar o cog {cog_name}: {e}")

# Comando de saúde para o Render
@bot.event
async def setup_hook():
    await load_cogs()
    
    # Sincronizar comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sincronizados {len(synced)} comandos slash")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")



# Handler de erros global
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Erro no evento {event}: {args}")

# Handler específico para erros de comandos
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏱️ Comando em cooldown. Tente novamente em {error.retry_after:.2f} segundos.")
    elif isinstance(error, discord.HTTPException) and error.status == 429:
        await ctx.send("⚠️ Rate limit atingido. Aguarde um momento e tente novamente.")
    elif isinstance(error, asyncio.TimeoutError):
        await ctx.send("⏰ Comando expirou. Tente novamente.")
    else:
        print(f"Erro no comando {ctx.command}: {error}")
        await ctx.send("❌ Ocorreu um erro interno. Tente novamente.")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"⏱️ Comando em cooldown. Tente novamente em {error.retry_after:.1f} segundos."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.InteractionResponded:
            pass
        return

    print(f"Erro em slash command {interaction.command}: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Ocorreu um erro interno. Tente novamente.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ocorreu um erro interno. Tente novamente.", ephemeral=True)
    except discord.InteractionResponded:
        pass

async def main():
    try:
        # Sistema de backup/restore para Render free tier
        await restore_from_git_backup()
        
        # Executar migração automática se necessário (sistema legado)
        await auto_migrate_if_needed()
        
        await asyncio.gather(
            start_web_server(),
            bot.start(TOKEN)
        )
            
    except KeyboardInterrupt:
        print("Bot desligado pelo usuário")
    except Exception as e:
        print(f"Erro crítico: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
