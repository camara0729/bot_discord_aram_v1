# main.py
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import database as db

# Carregar variáveis de ambiente do arquivo.env
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Configurar intents do bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class AramBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or("/"), intents=intents)

    async def setup_hook(self):
        """
        Hook que é executado após o login, mas antes de conectar ao WebSocket.
        Ideal para carregar extensões e sincronizar a árvore de comandos.
        """
        print("Carregando cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'Cog "{filename[:-3]}" carregado com sucesso.')
                except Exception as e:
                    print(f'Erro ao carregar o cog "{filename[:-3]}": {e}')
        
        try:
            # Sincroniza os comandos de barra com o Discord
            synced = await self.tree.sync()
            print(f"Sincronizados {len(synced)} comandos.")
        except Exception as e:
            print(f"Erro ao sincronizar comandos: {e}")

    async def on_ready(self):
        """
        Evento que é acionado quando o bot está online e pronto.
        """
        print(f'Bot conectado como {self.user}')
        print('Inicializando o banco de dados...')
        db.initialize_database()
        print('Banco de dados pronto.')

# Instanciar e executar o bot
bot = AramBot()
bot.run(DISCORD_BOT_TOKEN)