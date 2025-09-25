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
    
    # Sincronizar comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comando(s) slash")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

# Carregar cogs
async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            cog_name = f'cogs.{filename[:-3]}'
            try:
                # Verificar se o cog já está carregado e descarregar se necessário
                if cog_name in bot.extensions:
                    await bot.reload_extension(cog_name)
                    print(f"Recarregado: {cog_name}")
                else:
                    await bot.load_extension(cog_name)
                    print(f"Carregado: {cog_name}")
            except Exception as e:
                print(f"Falha ao carregar o cog {filename[:-3]}: {e}")

async def main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())