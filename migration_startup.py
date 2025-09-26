# migration_startup.py - Adicione ao main.py
import os
from pathlib import Path
from utils.database_manager import db_manager

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
