#!/usr/bin/env python3
"""
Script para corrigir dados após migração no Render
Execute este script diretamente no terminal do Render para corrigir os dados dos jogadores
"""

import asyncio
import aiosqlite
import json
from pathlib import Path

async def fix_player_data():
    """Corrige os dados dos jogadores baseado no backup original"""
    
    # Dados corretos baseados no backup original
    correct_data = [
        {
            "discord_id": 267713314086191125,  # Sérgio (Jajalo#BBG)
            "pdl": 1175,
            "wins": 7,
            "losses": 1,
            "mvp_count": 5,
            "bagre_count": 1
        },
        {
            "discord_id": 267830206302126081,  # mateusabb (coquinho3#cria)
            "pdl": 1065,
            "wins": 5,
            "losses": 3,
            "mvp_count": 1,
            "bagre_count": 1
        },
        {
            "discord_id": 207835175135084544,  # Feitosa (AmoMinhaMulher#BBG)
            "pdl": 1060,
            "wins": 3,
            "losses": 1,
            "mvp_count": 1,
            "bagre_count": 0
        },
        {
            "discord_id": 348276973853999105,  # paredao (paredesk1ng#ola)
            "pdl": 1060,
            "wins": 4,
            "losses": 2,
            "mvp_count": 0,
            "bagre_count": 0
        },
        {
            "discord_id": 682749260961153144,  # Pedro Luiz (PEU#1013)
            "pdl": 980,
            "wins": 3,
            "losses": 5,
            "mvp_count": 1,
            "bagre_count": 0
        },
        {
            "discord_id": 1042259376070742087,  # lcris (lcris56#cria1)
            "pdl": 970,
            "wins": 3,
            "losses": 5,
            "mvp_count": 0,
            "bagre_count": 1
        },
        {
            "discord_id": 297136556966150145,  # Fausto (faustin#1412)
            "pdl": 965,
            "wins": 3,
            "losses": 5,
            "mvp_count": 0,
            "bagre_count": 2
        },
        {
            "discord_id": 534894751330205699,  # Guilherme (FIshyzin#LLL)
            "pdl": 965,
            "wins": 2,
            "losses": 4,
            "mvp_count": 0,
            "bagre_count": 1
        },
        {
            "discord_id": 760704217055756288,  # Daydrex (DAYDREX#BR1)
            "pdl": 910,
            "wins": 0,
            "losses": 4,
            "mvp_count": 0,
            "bagre_count": 2
        }
    ]
    
    db_path = "bot_database.db"
    
    try:
        async with aiosqlite.connect(db_path) as db:
            print("🔄 Iniciando correção dos dados...")
            
            # Corrigir cada jogador
            for player_data in correct_data:
                await db.execute("""
                    UPDATE players 
                    SET pdl = ?, wins = ?, losses = ?, mvp_count = ?, bagre_count = ?
                    WHERE discord_id = ?
                """, (
                    player_data["pdl"],
                    player_data["wins"], 
                    player_data["losses"],
                    player_data["mvp_count"],
                    player_data["bagre_count"],
                    player_data["discord_id"]
                ))
            
            await db.commit()
            
            # Verificar se a correção funcionou
            print("\n✅ Dados corrigidos! Verificando...")
            async with db.execute("""
                SELECT riot_id, pdl, wins, losses, mvp_count, bagre_count 
                FROM players 
                ORDER BY pdl DESC
            """) as cursor:
                players = await cursor.fetchall()
                
                print("\n🏆 Ranking após correção:")
                for i, (riot_id, pdl, wins, losses, mvp, bagre) in enumerate(players, 1):
                    name = riot_id.split('#')[0]
                    print(f"{i:2d}. {name} - {pdl} PDL ({wins}W/{losses}L) MVP:{mvp} Bagre:{bagre}")
                    
            print(f"\n✅ Correção concluída! Total de jogadores: {len(players)}")
            
    except Exception as e:
        print(f"❌ Erro durante a correção: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🔧 Script de Correção de Dados - Bot ARAM")
    print("=" * 50)
    
    try:
        result = asyncio.run(fix_player_data())
        if result:
            print("\n🎉 Dados corrigidos com sucesso!")
            print("O bot agora deve mostrar os dados corretos no ranking.")
        else:
            print("\n❌ Falha na correção dos dados.")
    except Exception as e:
        print(f"\n💥 Erro crítico: {e}")