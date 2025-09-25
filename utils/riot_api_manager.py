# utils/riot_api_manager.py
import os
import asyncio
from riotwatcher import LolWatcher, RiotWatcher, ApiError
from dotenv import load_dotenv
from typing import Optional

load_dotenv()
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

class RiotAPIManager:
    def __init__(self, api_key: str = RIOT_API_KEY):
        if not api_key:
            raise ValueError("A chave da API da Riot não foi encontrada no arquivo.env")
        self.lol_watcher = LolWatcher(api_key)
        self.riot_watcher = RiotWatcher(api_key)

    async def get_puuid_by_riot_id(self, game_name: str, tag_line: str, region: str = 'americas') -> Optional[str]:
        """
        Busca o PUUID de um jogador usando seu Riot ID (gameName#tagLine).
        A chamada da API é executada em um thread separado para não bloquear o bot.
        """
        try:
            print(f"Buscando PUUID para: {game_name}#{tag_line}")
            loop = asyncio.get_running_loop()
            
            # Adiciona timeout para evitar travamento
            account_info = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self.riot_watcher.account.by_riot_id, region, game_name, tag_line
                ),
                timeout=10.0  # Timeout de 10 segundos
            )
            
            puuid = account_info.get('puuid')
            print(f"PUUID encontrado: {puuid}")
            return puuid
            
        except asyncio.TimeoutError:
            print(f"Timeout ao buscar Riot ID: {game_name}#{tag_line}")
            return None
        except ApiError as err:
            if err.response.status_code == 404:
                print(f"Riot ID não encontrado: {game_name}#{tag_line}")
            elif err.response.status_code == 403:
                print("Erro 403: A chave da API da Riot pode ter expirado ou é inválida.")
            else:
                print(f"Erro inesperado da API da Riot: {err}")
            return None
        except Exception as e:
            print(f"Ocorreu um erro não relacionado à API: {e}")
            return None

    async def get_summoner_by_puuid(self, puuid: str, region: str = 'br1') -> Optional[dict]:
        """
        Busca informações de invocador de um jogador usando seu PUUID.
        A chamada da API é executada em um thread separado para não bloquear o bot.
        """
        try:
            print(f"Buscando summoner para PUUID: {puuid}")
            loop = asyncio.get_running_loop()
            
            # Adiciona timeout para evitar travamento
            summoner_info = await asyncio.wait_for(
                loop.run_in_executor(
                    None, self.lol_watcher.summoner.by_puuid, region, puuid
                ),
                timeout=10.0  # Timeout de 10 segundos
            )
            
            print(f"Summoner encontrado: {summoner_info.get('name', 'Nome não encontrado')}")
            return summoner_info
            
        except asyncio.TimeoutError:
            print(f"Timeout ao buscar summoner com PUUID: {puuid}")
            return None
        except ApiError as err:
            if err.response.status_code == 404:
                print(f"Invocador com PUUID {puuid} não encontrado na região {region}.")
            else:
                print(f"Erro inesperado da API da Riot ao buscar invocador: {err}")
            return None

# Instância global
riot_api_manager = RiotAPIManager()