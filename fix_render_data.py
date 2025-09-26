#!/usr/bin/env python3
"""
Script de correção simples e direto para os dados no Render
Execute no terminal do Render: python fix_render_data.py
"""

import asyncio
import aiosqlite

async def fix_render_data():
    """Corrige diretamente os dados incorretos no banco"""
    
    print("🔄 Corrigindo dados do ranking...")
    
    # Correções baseadas nos dados originais vs dados incorretos
    corrections = [
        # Sérgio: de 1110 PDL, 5W/1L para 1175 PDL, 7W/1L
        ("UPDATE players SET pdl = 1175, wins = 7, losses = 1, mvp_count = 5, bagre_count = 1 WHERE discord_id = 267713314086191125", "Sérgio"),
        
        # mateusabb: de 1105 PDL, 5W/1L para 1065 PDL, 5W/3L  
        ("UPDATE players SET pdl = 1065, wins = 5, losses = 3, mvp_count = 1, bagre_count = 1 WHERE discord_id = 267830206302126081", "mateusabb"),
        
        # Feitosa: mantém 1060 PDL, 3W/1L (está correto)
        
        # paredao: de 1010 PDL, 2W/2L para 1060 PDL, 4W/2L
        ("UPDATE players SET pdl = 1060, wins = 4, losses = 2, mvp_count = 0, bagre_count = 0 WHERE discord_id = 348276973853999105", "paredao"),
        
        # Pedro Luiz: de 1020 PDL, 3W/3L para 980 PDL, 3W/5L
        ("UPDATE players SET pdl = 980, wins = 3, losses = 5, mvp_count = 1, bagre_count = 0 WHERE discord_id = 682749260961153144", "Pedro Luiz"),
        
        # Guilherme: de 1010 PDL, 2W/2L para 965 PDL, 2W/4L
        ("UPDATE players SET pdl = 965, wins = 2, losses = 4, mvp_count = 0, bagre_count = 1 WHERE discord_id = 534894751330205699", "Guilherme"),
        
        # Daydrex: de 955 PDL, 0W/2L para 910 PDL, 0W/4L
        ("UPDATE players SET pdl = 910, wins = 0, losses = 4, mvp_count = 0, bagre_count = 2 WHERE discord_id = 760704217055756288", "Daydrex"),
        
        # lcris: de 920 PDL, 1W/5L para 970 PDL, 3W/5L
        ("UPDATE players SET pdl = 970, wins = 3, losses = 5, mvp_count = 0, bagre_count = 1 WHERE discord_id = 1042259376070742087", "lcris"),
        
        # Fausto: de 915 PDL, 1W/5L para 965 PDL, 3W/5L
        ("UPDATE players SET pdl = 965, wins = 3, losses = 5, mvp_count = 0, bagre_count = 2 WHERE discord_id = 297136556966150145", "Fausto")
    ]
    
    try:
        async with aiosqlite.connect("bot_database.db") as db:
            for sql, name in corrections:
                await db.execute(sql)
                print(f"✅ {name} - dados corrigidos")
            
            await db.commit()
            
            # Verificar resultado
            print("\n🏆 Ranking após correção:")
            async with db.execute("""
                SELECT riot_id, pdl, wins, losses 
                FROM players 
                ORDER BY pdl DESC
            """) as cursor:
                players = await cursor.fetchall()
                
                for i, (riot_id, pdl, wins, losses) in enumerate(players, 1):
                    name = riot_id.split('#')[0]
                    # Determinar elo
                    if pdl >= 1200:
                        elo_emoji = "⚪"
                        elo_name = "Prata"
                    elif pdl >= 800:
                        elo_emoji = "🟤"  
                        elo_name = "Bronze"
                    else:
                        elo_emoji = "🟫"
                        elo_name = "Ferro"
                    
                    if i <= 3:
                        medals = ["🥇", "🥈", "🥉"]
                        print(f"{medals[i-1]} {elo_emoji} {name}")
                    else:
                        print(f" {i:2d} {elo_emoji} {name}")
                    
                    print(f"{elo_name} - {pdl} PDL")
                    print(f"{wins}W/{losses}L\n")
                
                print(f"Total de jogadores: {len(players)}")
            
        print("\n🎉 Correção concluída com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro durante correção: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Correção de Dados - Bot ARAM Discord")
    print("=" * 40)
    
    result = asyncio.run(fix_render_data())
    if result:
        print("\n✅ Execute o comando /ranking no Discord para ver os dados corretos!")
    else:
        print("\n❌ Correção falhou. Verifique os logs.")