# main.py
import discord
from discord.ext import commands, tasks
import asyncio
import os
import aiohttp
from aiohttp import web
from dotenv import load_dotenv
import threading
from datetime import datetime

from utils.database_manager import db_manager

load_dotenv()

# Configurações do bot
TOKEN = os.getenv('DISCORD_TOKEN') or os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Token do Discord não encontrado. Configure a variável DISCORD_TOKEN no Render.")

# Configurações do keep-alive
PORT = int(os.getenv('PORT', 10000))  # Render usa a porta definida na variável PORT
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL', f'http://localhost:{PORT}')

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
                    print("� Arquivo de backup marcado como usado")
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

# Sistema de Keep-Alive para evitar hibernação
async def health_check(request):
    """Endpoint de health check para manter o serviço ativo."""
    return web.json_response({
        'status': 'alive',
        'bot': bot.user.name if bot.user else 'Not ready',
        'timestamp': datetime.now().isoformat(),
        'guilds': len(bot.guilds),
        'uptime': 'online'
    })

async def start_web_server():
    """Inicia servidor HTTP para keep-alive."""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"🌐 Servidor web iniciado na porta {PORT}")

@tasks.loop(minutes=10)  # Reduzido para 10 minutos para ser mais agressivo
async def keep_alive_ping():
    """Faz ping no próprio serviço a cada 10 minutos para evitar hibernação."""
    try:
        render_url = os.getenv('RENDER_EXTERNAL_URL')
        if render_url:
            timeout = aiohttp.ClientTimeout(total=30, connect=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{render_url}/ping") as response:
                    if response.status == 200:
                        current_time = datetime.now().strftime('%H:%M:%S')
                        print(f"✅ Keep-alive ping successful - {current_time}")
                    else:
                        print(f"⚠️ Keep-alive ping failed: HTTP {response.status}")
        else:
            # Fallback: fazer ping no localhost
            try:
                timeout = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(f"http://localhost:{PORT}/health") as response:
                        current_time = datetime.now().strftime('%H:%M:%S')
                        print(f"💓 Local keep-alive heartbeat - {current_time}")
            except:
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"💓 Keep-alive heartbeat (no HTTP) - {current_time}")
                
    except asyncio.TimeoutError:
        print(f"⏰ Keep-alive ping timeout - {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Erro no keep-alive ping: {e}")
        # Continue funcionando mesmo com erro

@keep_alive_ping.before_loop
async def before_keep_alive():
    """Aguarda o bot estar pronto antes de iniciar o keep-alive."""
    await bot.wait_until_ready()
    print("🚀 Sistema keep-alive iniciado")

# Carregar cogs
async def load_cogs():
    cog_files = [
        'player_cog',
        'team_cog',
        'match_cog',
        'admin_cog',
        # Adicione outros cogs aqui conforme necessário
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

async def main():
    try:
        # Executar migração automática se necessário
        await auto_migrate_if_needed()
        
        # Iniciar servidor web e bot em paralelo
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