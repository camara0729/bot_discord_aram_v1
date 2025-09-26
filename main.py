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

# Criar o bot
bot = commands.Bot(command_prefix='!', intents=intents)

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
                    # Remover arquivo de backup após migração bem-sucedida
                    os.remove(backup_file)
                    print("🗑️ Arquivo de backup removido")
                else:
                    print("❌ Falha na migração automática!")
            except Exception as e:
                print(f"❌ Erro na migração automática: {e}")
        else:
            print(f"📊 Banco já populado com {len(players)} jogadores")
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

@tasks.loop(minutes=10)
async def keep_alive_ping():
    """Faz ping no próprio serviço a cada 10 minutos para evitar hibernação."""
    try:
        if RENDER_URL and 'render' in RENDER_URL:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{RENDER_URL}/ping", timeout=30) as response:
                    if response.status == 200:
                        print(f"✅ Keep-alive ping successful - {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        print(f"⚠️ Keep-alive ping failed: {response.status}")
        else:
            print(f"💓 Keep-alive heartbeat - {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Erro no keep-alive ping: {e}")

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