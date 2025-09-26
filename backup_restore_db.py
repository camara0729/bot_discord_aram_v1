#!/usr/bin/env python3
# backup_restore_db.py - Sistema de backup e restauração do banco
import asyncio
import aiosqlite
import json
import sys
from datetime import datetime
from pathlib import Path
from utils.database_manager import db_manager
import config

async def backup_database(backup_file: str = None):
    """Cria backup do banco de dados em formato JSON."""
    if not backup_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_database_{timestamp}.json"
    
    try:
        print(f"📋 Criando backup do banco de dados...")
        
        # Buscar todos os dados
        players = await db_manager.get_all_players()
        
        # Buscar matches se existirem
        matches = []
        try:
            async with aiosqlite.connect(db_manager.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM matches') as cursor:
                    rows = await cursor.fetchall()
                    matches = [dict(row) for row in rows]
        except:
            print("⚠️ Tabela matches não encontrada ou vazia")
        
        # Buscar match_participants se existirem
        participants = []
        try:
            async with aiosqlite.connect(db_manager.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM match_participants') as cursor:
                    rows = await cursor.fetchall()
                    participants = [dict(row) for row in rows]
        except:
            print("⚠️ Tabela match_participants não encontrada ou vazia")
        
        # Criar estrutura do backup
        backup_data = {
            "backup_date": datetime.now().isoformat(),
            "version": "1.0",
            "total_players": len(players),
            "total_matches": len(matches),
            "data": {
                "players": players,
                "matches": matches,
                "match_participants": participants
            }
        }
        
        # Salvar backup
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)
        
        file_size = Path(backup_file).stat().st_size / 1024  # KB
        
        print(f"✅ Backup criado com sucesso!")
        print(f"📁 Arquivo: {backup_file}")
        print(f"📊 Jogadores: {len(players)}")
        print(f"🎮 Partidas: {len(matches)}")
        print(f"📏 Tamanho: {file_size:.1f} KB")
        
        return backup_file
        
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return None

async def restore_database(backup_file: str, confirm: bool = False):
    """Restaura banco de dados a partir de backup JSON."""
    try:
        # Verificar se arquivo existe
        if not Path(backup_file).exists():
            print(f"❌ Arquivo de backup não encontrado: {backup_file}")
            return False
        
        # Carregar backup
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"📋 Informações do Backup:")
        print(f"📅 Data: {backup_data.get('backup_date', 'Desconhecida')}")
        print(f"👥 Jogadores: {backup_data.get('total_players', 0)}")
        print(f"🎮 Partidas: {backup_data.get('total_matches', 0)}")
        
        if not confirm:
            response = input("\n⚠️ ATENÇÃO: Isso irá SUBSTITUIR todos os dados atuais!\nTem certeza? Digite 'CONFIRMAR': ")
            if response.upper() != "CONFIRMAR":
                print("❌ Restauração cancelada.")
                return False
        
        print(f"\n🔄 Iniciando restauração...")
        
        # Recriar banco de dados
        await db_manager.initialize_database()
        
        # Limpar dados existentes
        async with aiosqlite.connect(db_manager.db_path) as db:
            await db.execute("DELETE FROM match_participants")
            await db.execute("DELETE FROM matches")
            await db.execute("DELETE FROM players")
            await db.commit()
        
        # Restaurar jogadores
        players_data = backup_data['data']['players']
        restored_players = 0
        
        for player in players_data:
            try:
                async with aiosqlite.connect(db_manager.db_path) as db:
                    await db.execute('''
                        INSERT INTO players 
                        (discord_id, riot_id, puuid, lol_rank, pdl, wins, losses, mvp_count, bagre_count, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        player['discord_id'], player['riot_id'], player['puuid'], 
                        player.get('lol_rank', 'PRATA II'), player['pdl'], 
                        player['wins'], player['losses'], player['mvp_count'], player['bagre_count'],
                        player.get('created_at'), player.get('updated_at')
                    ))
                    await db.commit()
                restored_players += 1
            except Exception as e:
                print(f"⚠️ Erro ao restaurar jogador {player.get('riot_id', 'Unknown')}: {e}")
        
        # Restaurar matches (se existirem)
        matches_data = backup_data['data'].get('matches', [])
        restored_matches = 0
        
        for match in matches_data:
            try:
                async with aiosqlite.connect(db_manager.db_path) as db:
                    await db.execute('''
                        INSERT INTO matches 
                        (match_id, blue_team, red_team, winner, mvp_id, bagre_id, duration, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        match['match_id'], match['blue_team'], match['red_team'],
                        match['winner'], match.get('mvp_id'), match.get('bagre_id'),
                        match.get('duration'), match.get('created_at')
                    ))
                    await db.commit()
                restored_matches += 1
            except Exception as e:
                print(f"⚠️ Erro ao restaurar partida {match.get('match_id', 'Unknown')}: {e}")
        
        print(f"\n✅ Restauração concluída!")
        print(f"👥 Jogadores restaurados: {restored_players}/{len(players_data)}")
        print(f"🎮 Partidas restauradas: {restored_matches}/{len(matches_data)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao restaurar backup: {e}")
        return False

async def migrate_to_render():
    """Prepara migração para o Render."""
    print("🚀 Preparando migração para o Render...")
    
    # Criar backup
    backup_file = await backup_database("render_migration_backup.json")
    
    if backup_file:
        print(f"\n📋 Instruções para migração:")
        print(f"1. Faça upload do arquivo '{backup_file}' para seu repositório Git")
        print(f"2. No seu código, use a função restore_database() no startup")
        print(f"3. Configure as variáveis de ambiente no Render:")
        print(f"   - DISCORD_TOKEN")
        print(f"   - RIOT_API_KEY")
        print(f"4. O banco será restaurado automaticamente no primeiro deploy")
        
        # Criar script de migração automática
        migration_script = f'''# migration_startup.py - Adicione ao main.py
import os
from pathlib import Path

async def auto_migrate_on_startup():
    """Migra dados automaticamente no primeiro startup do Render."""
    backup_file = "render_migration_backup.json"
    
    # Só executa se o backup existir e o banco estiver vazio
    if Path(backup_file).exists():
        players = await db_manager.get_all_players()
        if not players:  # Banco vazio
            print("🔄 Detectado ambiente novo - iniciando migração automática...")
            from backup_restore_db import restore_database
            success = await restore_database(backup_file, confirm=True)
            if success:
                print("✅ Migração automática concluída!")
                # Opcional: remover arquivo de backup após migração
                os.remove(backup_file)
            else:
                print("❌ Falha na migração automática!")
'''
        
        with open("migration_startup.py", "w") as f:
            f.write(migration_script)
        
        print(f"5. Arquivo 'migration_startup.py' criado - integre ao seu main.py")

async def show_help():
    """Mostra ajuda do script."""
    print("\n🗃️ Sistema de Backup/Restauração - Bot Discord ARAM")
    print("=" * 60)
    print("Uso: python backup_restore_db.py [comando] [argumentos]")
    print("\nComandos disponíveis:")
    print("  backup [arquivo]           - Cria backup do banco atual")
    print("  restore [arquivo]          - Restaura banco de um backup")
    print("  migrate                    - Prepara migração para Render")
    print("  help                       - Mostra esta ajuda")
    print("\nExemplos:")
    print("  python backup_restore_db.py backup")
    print("  python backup_restore_db.py backup meu_backup.json")
    print("  python backup_restore_db.py restore backup_20250926_123456.json")
    print("  python backup_restore_db.py migrate")

async def main():
    if len(sys.argv) < 2:
        await show_help()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "backup":
            backup_file = sys.argv[2] if len(sys.argv) > 2 else None
            await backup_database(backup_file)
        
        elif command == "restore":
            if len(sys.argv) < 3:
                print("❌ Uso: python backup_restore_db.py restore [arquivo_backup]")
                return
            backup_file = sys.argv[2]
            await restore_database(backup_file)
        
        elif command == "migrate":
            await migrate_to_render()
        
        elif command == "help":
            await show_help()
        
        else:
            print(f"❌ Comando '{command}' não reconhecido.")
            await show_help()
    
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())