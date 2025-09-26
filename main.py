# main.py
import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

from utils.database_manager import db_manager

load_dotenv()

# Configurações do bot
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("Token do Discord não encontrado no arquivo .env")

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Criar o bot
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} está online!')
    
    # Inicializar o banco de dados
    print("Inicializando banco de dados...")
    await db_manager.initialize_database()
    
    # Migração automática (se necessário)
    await auto_migrate_if_needed()
    
    # Sincronizar comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comando(s) slash")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

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

# Handler de erros global
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Erro no evento {event}: {args}")

async def main():
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("Bot desligado pelo usuário")
    except Exception as e:
        print(f"Erro crítico: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())