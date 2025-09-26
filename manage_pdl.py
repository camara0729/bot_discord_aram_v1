#!/usr/bin/env python3
# manage_pdl.py - Script para gerenciar PDL via terminal
import asyncio
import aiosqlite
import sys
from utils.database_manager import db_manager
import config

async def list_players():
    """Lista todos os jogadores registrados."""
    players = await db_manager.get_all_players()
    if not players:
        print("❌ Nenhum jogador registrado.")
        return
    
    print("\n📋 Jogadores Registrados:")
    print("-" * 60)
    for i, player in enumerate(players, 1):
        elo_info = config.get_elo_by_pdl(player['pdl'])
        print(f"{i:2d}. ID: {player['discord_id']}")
        print(f"    Riot ID: {player['riot_id']}")
        print(f"    PDL: {player['pdl']} ({elo_info['name']})")
        print(f"    W/L: {player['wins']}/{player['losses']}")
        print("-" * 60)

async def update_pdl(discord_id: int, amount: int):
    """Atualiza PDL de um jogador."""
    # Verificar se existe
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_pdl = player['pdl']
    success = await db_manager.update_player_pdl(discord_id, amount)
    
    if success:
        updated_player = await db_manager.get_player(discord_id)
        new_pdl = updated_player['pdl']
        old_elo = config.get_elo_by_pdl(old_pdl)
        new_elo = config.get_elo_by_pdl(new_pdl)
        
        print(f"✅ PDL atualizado com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"PDL: {old_pdl} → {new_pdl} ({amount:+d})")
        print(f"Elo: {old_elo['name']} → {new_elo['name']}")
        
        if old_elo['name'] != new_elo['name']:
            if new_pdl > old_pdl:
                print(f"🎉 PROMOÇÃO para {new_elo['name']}!")
            else:
                print(f"📉 Rebaixamento para {new_elo['name']}")
    else:
        print("❌ Erro ao atualizar PDL.")

async def set_pdl(discord_id: int, value: int):
    """Define PDL de um jogador para um valor específico."""
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_pdl = player['pdl']
    success = await db_manager.set_player_pdl(discord_id, value)
    
    if success:
        old_elo = config.get_elo_by_pdl(old_pdl)
        new_elo = config.get_elo_by_pdl(value)
        
        print(f"✅ PDL definido com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"PDL: {old_pdl} → {value}")
        print(f"Elo: {old_elo['name']} → {new_elo['name']}")
    else:
        print("❌ Erro ao definir PDL.")

async def update_mvp(discord_id: int, amount: int):
    """Atualiza MVP count de um jogador."""
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_mvp = player['mvp_count']
    
    # Verificar se resultaria em valor negativo
    if old_mvp + amount < 0:
        print(f"❌ Não é possível remover {abs(amount)} MVPs. Jogador tem apenas {old_mvp} MVPs.")
        return
    
    success = await db_manager.update_player_mvp_count(discord_id, amount)
    
    if success:
        new_mvp = old_mvp + amount
        print(f"✅ MVP count atualizado com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"MVPs: {old_mvp} → {new_mvp} ({amount:+d})")
    else:
        print("❌ Erro ao atualizar MVP count.")

async def update_bagre(discord_id: int, amount: int):
    """Atualiza Bagre count de um jogador."""
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_bagre = player['bagre_count']
    
    # Verificar se resultaria em valor negativo
    if old_bagre + amount < 0:
        print(f"❌ Não é possível remover {abs(amount)} Bagres. Jogador tem apenas {old_bagre} Bagres.")
        return
    
    success = await db_manager.update_player_bagre_count(discord_id, amount)
    
    if success:
        new_bagre = old_bagre + amount
        print(f"✅ Bagre count atualizado com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"Bagres: {old_bagre} → {new_bagre} ({amount:+d})")
    else:
        print("❌ Erro ao atualizar Bagre count.")

async def set_mvp(discord_id: int, value: int):
    """Define MVP count de um jogador para um valor específico."""
    if value < 0:
        print("❌ MVP count não pode ser negativo.")
        return
    
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_mvp = player['mvp_count']
    success = await db_manager.set_player_mvp_count(discord_id, value)
    
    if success:
        print(f"✅ MVP count definido com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"MVPs: {old_mvp} → {value}")
    else:
        print("❌ Erro ao definir MVP count.")

async def set_bagre(discord_id: int, value: int):
    """Define Bagre count de um jogador para um valor específico."""
    if value < 0:
        print("❌ Bagre count não pode ser negativo.")
        return
    
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    old_bagre = player['bagre_count']
    success = await db_manager.set_player_bagre_count(discord_id, value)
    
    if success:
        print(f"✅ Bagre count definido com sucesso!")
        print(f"Jogador: {player['riot_id']}")
        print(f"Bagres: {old_bagre} → {value}")
    else:
        print("❌ Erro ao definir Bagre count.")

async def reset_stats(discord_id: int):
    """Reseta todas as estatísticas de um jogador."""
    player = await db_manager.get_player(discord_id)
    if not player:
        print(f"❌ Jogador com ID {discord_id} não encontrado.")
        return
    
    print(f"⚠️  RESETAR ESTATÍSTICAS - {player['riot_id']}")
    print(f"Estatísticas atuais:")
    print(f"  Vitórias: {player['wins']}")
    print(f"  Derrotas: {player['losses']}")
    print(f"  MVPs: {player['mvp_count']}")
    print(f"  Bagres: {player['bagre_count']}")
    
    confirm = input("Tem certeza? Digite 'CONFIRMAR' para continuar: ")
    
    if confirm.upper() == "CONFIRMAR":
        success = await db_manager.reset_player_stats(discord_id)
        
        if success:
            print(f"✅ Estatísticas resetadas com sucesso!")
            print(f"Jogador: {player['riot_id']}")
            print("Todas as estatísticas foram zeradas (PDL mantido).")
        else:
            print("❌ Erro ao resetar estatísticas.")
    else:
        print("❌ Reset cancelado.")

async def show_help():
    """Mostra ajuda do script."""
    print("\n🔧 Gerenciador de Stats - Bot Discord ARAM")
    print("=" * 60)
    print("Uso: python manage_pdl.py [comando] [argumentos]")
    print("\n📊 COMANDOS PDL:")
    print("  list                    - Lista todos os jogadores")
    print("  add [discord_id] [pdl]  - Adiciona PDL a um jogador")
    print("  remove [discord_id] [pdl] - Remove PDL de um jogador")
    print("  set [discord_id] [pdl]  - Define PDL específico")
    print("  reset [discord_id]      - Reseta PDL para 1000")
    print("\n⭐ COMANDOS MVP:")
    print("  add-mvp [discord_id] [count]    - Adiciona MVPs")
    print("  remove-mvp [discord_id] [count] - Remove MVPs")
    print("  set-mvp [discord_id] [count]    - Define MVP count")
    print("\n💩 COMANDOS BAGRE:")
    print("  add-bagre [discord_id] [count]    - Adiciona Bagres")
    print("  remove-bagre [discord_id] [count] - Remove Bagres")
    print("  set-bagre [discord_id] [count]    - Define Bagre count")
    print("\n🔄 COMANDOS RESET:")
    print("  reset-stats [discord_id]  - Reseta todas as stats (W/L/MVP/Bagre)")
    print("  help                      - Mostra esta ajuda")
    print("\n📝 EXEMPLOS:")
    print("  python manage_pdl.py list")
    print("  python manage_pdl.py add 123456789 50")
    print("  python manage_pdl.py add-mvp 123456789 2")
    print("  python manage_pdl.py remove-bagre 123456789 1")
    print("  python manage_pdl.py set-mvp 123456789 5")
    print("  python manage_pdl.py reset-stats 123456789")

async def main():
    if len(sys.argv) < 2:
        await show_help()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "list":
            await list_players()
        
        elif command == "add":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py add [discord_id] [pdl]")
                return
            discord_id = int(sys.argv[2])
            amount = int(sys.argv[3])
            await update_pdl(discord_id, amount)
        
        elif command == "remove":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py remove [discord_id] [pdl]")
                return
            discord_id = int(sys.argv[2])
            amount = -int(sys.argv[3])  # Negativo para remover
            await update_pdl(discord_id, amount)
        
        elif command == "set":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py set [discord_id] [pdl]")
                return
            discord_id = int(sys.argv[2])
            value = int(sys.argv[3])
            await set_pdl(discord_id, value)
        
        elif command == "reset":
            if len(sys.argv) != 3:
                print("❌ Uso: python manage_pdl.py reset [discord_id]")
                return
            discord_id = int(sys.argv[2])
            await set_pdl(discord_id, config.DEFAULT_PDL)
        
        elif command == "add-mvp":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py add-mvp [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            amount = int(sys.argv[3])
            await update_mvp(discord_id, amount)
        
        elif command == "remove-mvp":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py remove-mvp [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            amount = -int(sys.argv[3])  # Negativo para remover
            await update_mvp(discord_id, amount)
        
        elif command == "set-mvp":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py set-mvp [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            value = int(sys.argv[3])
            await set_mvp(discord_id, value)
        
        elif command == "add-bagre":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py add-bagre [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            amount = int(sys.argv[3])
            await update_bagre(discord_id, amount)
        
        elif command == "remove-bagre":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py remove-bagre [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            amount = -int(sys.argv[3])  # Negativo para remover
            await update_bagre(discord_id, amount)
        
        elif command == "set-bagre":
            if len(sys.argv) != 4:
                print("❌ Uso: python manage_pdl.py set-bagre [discord_id] [count]")
                return
            discord_id = int(sys.argv[2])
            value = int(sys.argv[3])
            await set_bagre(discord_id, value)
        
        elif command == "reset-stats":
            if len(sys.argv) != 3:
                print("❌ Uso: python manage_pdl.py reset-stats [discord_id]")
                return
            discord_id = int(sys.argv[2])
            await reset_stats(discord_id)
        
        elif command == "help":
            await show_help()
        
        else:
            print(f"❌ Comando '{command}' não reconhecido.")
            await show_help()
    
    except ValueError:
        print("❌ IDs e valores de PDL devem ser números inteiros.")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())