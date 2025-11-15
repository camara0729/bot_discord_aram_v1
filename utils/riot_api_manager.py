# utils/riot_api_manager.py
import os
import asyncio
from datetime import datetime, timedelta
from riotwatcher import LolWatcher, RiotWatcher, ApiError
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv()
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

class RiotAPIManager:
    def __init__(self, api_key: str = RIOT_API_KEY):
        if not api_key:
            raise ValueError("A chave da API da Riot não foi encontrada no arquivo.env")
        self.lol_watcher = LolWatcher(api_key)
        self.riot_watcher = RiotWatcher(api_key)
        self.rate_semaphore = asyncio.Semaphore(5)
        self.rank_cache: Dict[str, Any] = {}

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

    async def get_rank_for_puuid(self, puuid: str, platform: str = 'br1') -> Optional[Dict[str, Any]]:
        cache_key = f"{puuid}:{platform}"
        cached = self.rank_cache.get(cache_key)
        if cached and cached['expires_at'] > datetime.utcnow():
            return cached['data']

        async with self.rate_semaphore:
            summoner = await self.get_summoner_by_puuid(puuid, platform)
            if not summoner:
                return None
            loop = asyncio.get_running_loop()
            try:
                league_entries = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, self.lol_watcher.league.by_summoner, platform, summoner['id']
                    ),
                    timeout=10.0
                )
            except ApiError as err:
                if err.response.status_code == 429:
                    print("⚠️ Rate limit da Riot atingido ao buscar elo.")
                else:
                    print(f"Erro na API da Riot ao buscar elo: {err}")
                return None
            except Exception as exc:
                print(f"Erro inesperado na sincronização de elo: {exc}")
                return None

        if not league_entries:
            return None

        entry = self._select_best_entry(league_entries)
        if not entry:
            return None

        tier_pt = self._translate_tier(entry.get('tier'))
        division = entry.get('rank') or ''
        lp = entry.get('leaguePoints', 0)
        if tier_pt in {"MESTRE", "GRÃO-MESTRE", "DESAFIANTE"}:
            rank_label = tier_pt
        else:
            rank_label = f"{tier_pt} {division}".strip()

        data = {
            'rank': rank_label,
            'tier': tier_pt,
            'division': division,
            'lp': lp,
            'queue': entry.get('queueType')
        }
        self.rank_cache[cache_key] = {
            'data': data,
            'expires_at': datetime.utcnow() + timedelta(minutes=15)
        }
        return data

    def _select_best_entry(self, entries: list) -> Optional[dict]:
        solo = next((e for e in entries if e.get('queueType') == 'RANKED_SOLO_5x5'), None)
        if solo:
            return solo
        if entries:
            return entries[0]
        return None

    def _translate_tier(self, tier: Optional[str]) -> str:
        mapping = {
            'IRON': 'FERRO',
            'BRONZE': 'BRONZE',
            'SILVER': 'PRATA',
            'GOLD': 'OURO',
            'PLATINUM': 'PLATINA',
            'EMERALD': 'ESMERALDA',
            'DIAMOND': 'DIAMANTE',
            'MASTER': 'MESTRE',
            'GRANDMASTER': 'GRÃO-MESTRE',
            'CHALLENGER': 'DESAFIANTE'
        }
        return mapping.get(tier or '', 'FERRO')

# Instância global
riot_api_manager = RiotAPIManager()
