#!/usr/bin/env python3
# external_pinger.py - Serviço externo para pingar o bot (opcional)
import asyncio
import aiohttp
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# URL do seu bot no Render (será definida após deploy)
BOT_URL = os.getenv('BOT_URL', 'https://seu-bot.onrender.com')

async def ping_bot():
    """Faz ping no bot para mantê-lo ativo."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BOT_URL}/ping", timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Bot ativo - {data.get('bot', 'Unknown')} - {datetime.now().strftime('%H:%M:%S')}")
                    return True
                else:
                    print(f"⚠️ Resposta inesperada: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Erro ao pingar bot: {e}")
        return False

async def keep_bot_alive():
    """Loop principal para manter o bot ativo."""
    print("🚀 Iniciando pinger externo do bot...")
    print(f"🎯 URL do bot: {BOT_URL}")
    
    while True:
        try:
            success = await ping_bot()
            if success:
                print("💓 Bot mantido ativo")
            else:
                print("❌ Falha ao pingar bot")
            
            # Esperar 12 minutos (menor que os 15 minutos de hibernação)
            await asyncio.sleep(720)  # 12 minutos
            
        except KeyboardInterrupt:
            print("🛑 Pinger externo interrompido")
            break
        except Exception as e:
            print(f"❌ Erro no loop principal: {e}")
            await asyncio.sleep(60)  # Esperar 1 minuto em caso de erro

if __name__ == "__main__":
    print("🤖 Pinger Externo do Bot Discord ARAM")
    print("=" * 40)
    print("Este script mantém o bot ativo pingando ele a cada 12 minutos.")
    print("Configure BOT_URL no .env com a URL do seu bot no Render.")
    print("Exemplo: BOT_URL=https://seu-bot.onrender.com")
    print("=" * 40)
    
    if BOT_URL == 'https://seu-bot.onrender.com':
        print("⚠️ ATENÇÃO: Configure a variável BOT_URL no .env!")
        print("Use a URL que o Render forneceu para seu bot.")
    else:
        asyncio.run(keep_bot_alive())