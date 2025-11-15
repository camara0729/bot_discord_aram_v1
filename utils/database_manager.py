# utils/database_manager.py
import aiosqlite
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import config

class DatabaseManager:
    def __init__(self, db_path: str = None):
        configured_path = db_path or os.getenv('DATABASE_PATH', 'bot_database.db')
        self.db_path = configured_path

        parent = Path(configured_path).parent
        if str(parent) not in ('.', '') and not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                fallback = Path('bot_database.db')
                print(
                    f"⚠️ Permissão negada ao criar '{parent}'. "
                    f"Usando caminho alternativo '{fallback.resolve()}'"
                )
                self.db_path = str(fallback)

    async def initialize_database(self):
        """Inicializa o banco de dados e cria as tabelas necessárias."""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabela de jogadores - Adicionado campo lol_rank e username
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    discord_id INTEGER PRIMARY KEY,
                    riot_id TEXT NOT NULL,
                    puuid TEXT NOT NULL,
                    lol_rank TEXT NOT NULL,
                    username TEXT,
                    pdl INTEGER DEFAULT 1000,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    mvp_count INTEGER DEFAULT 0,
                    bagre_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verifica se as colunas necessárias existem e adiciona se necessário
            async with db.execute("PRAGMA table_info(players)") as cursor:
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                if 'lol_rank' not in column_names:
                    await db.execute('ALTER TABLE players ADD COLUMN lol_rank TEXT DEFAULT "PRATA II"')
                    print("Coluna lol_rank adicionada à tabela players")
                if 'username' not in column_names:
                    await db.execute('ALTER TABLE players ADD COLUMN username TEXT')
                    print("Coluna username adicionada à tabela players")
            
            # Tabela de partidas
            await db.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT UNIQUE,
                    blue_team TEXT NOT NULL,
                    red_team TEXT NOT NULL,
                    winner TEXT NOT NULL,
                    mvp_id INTEGER,
                    bagre_id INTEGER,
                    duration INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mvp_id) REFERENCES players (discord_id),
                    FOREIGN KEY (bagre_id) REFERENCES players (discord_id)
                )
            ''')
            
            # Tabela de participações em partidas
            await db.execute('''
                CREATE TABLE IF NOT EXISTS match_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    discord_id INTEGER NOT NULL,
                    team TEXT NOT NULL,
                    champion TEXT,
                    kills INTEGER DEFAULT 0,
                    deaths INTEGER DEFAULT 0,
                    assists INTEGER DEFAULT 0,
                    damage_dealt INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (discord_id) REFERENCES players (discord_id),
                    FOREIGN KEY (match_id) REFERENCES matches (match_id)
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            await db.commit()
            print("Banco de dados inicializado com sucesso!")

    async def add_player(self, discord_id: int, riot_id: str, puuid: str, lol_rank: str, username: str = None) -> bool:
        """Adiciona um novo jogador ao banco de dados com PDL padrão."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO players 
                    (discord_id, riot_id, puuid, lol_rank, username, pdl, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(discord_id) DO UPDATE SET
                        riot_id = excluded.riot_id,
                        lol_rank = excluded.lol_rank,
                        username = excluded.username,
                        updated_at = CURRENT_TIMESTAMP
                ''', (discord_id, riot_id, puuid, lol_rank, username, config.DEFAULT_PDL))
                await db.commit()
                print(f"Jogador {riot_id} adicionado/atualizado com sucesso!")
                return True
        except Exception as e:
            print(f"Erro ao adicionar jogador: {e}")
            return False

    async def get_player(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """Busca um jogador pelo Discord ID."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM players WHERE discord_id = ?
                ''', (discord_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            print(f"Erro ao buscar jogador: {e}")
            return None

    async def get_all_players(self) -> List[Dict[str, Any]]:
        """Retorna todos os jogadores registrados ordenados por PDL."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM players ORDER BY pdl DESC') as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"Erro ao buscar todos os jogadores: {e}")
            return []

    async def update_player_stats(self, discord_id: int, won: bool, is_mvp: bool = False, is_bagre: bool = False) -> bool:
        """
        Atualiza as estatísticas de um jogador após uma partida.
        Calcula PDL baseado em vitória/derrota + bônus MVP/penalidade Bagre.
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Calcula mudança de PDL
                pdl_change = config.PDL_WIN if won else config.PDL_LOSS
                
                # Adiciona bônus/penalidade
                if is_mvp:
                    pdl_change += config.MVP_BONUS
                if is_bagre:
                    pdl_change += config.BAGRE_PENALTY
                
                if won:
                    await db.execute('''
                        UPDATE players 
                        SET wins = wins + 1, 
                            pdl = pdl + ?, 
                            mvp_count = mvp_count + ?,
                            bagre_count = bagre_count + ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE discord_id = ?
                    ''', (pdl_change, 1 if is_mvp else 0, 1 if is_bagre else 0, discord_id))
                else:
                    await db.execute('''
                        UPDATE players 
                        SET losses = losses + 1, 
                            pdl = pdl + ?, 
                            mvp_count = mvp_count + ?,
                            bagre_count = bagre_count + ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE discord_id = ?
                    ''', (pdl_change, 1 if is_mvp else 0, 1 if is_bagre else 0, discord_id))
                await db.commit()
                print(f"Jogador {discord_id}: PDL {'+' if pdl_change >= 0 else ''}{pdl_change}")
                return True
        except Exception as e:
            print(f"Erro ao atualizar estatísticas do jogador: {e}")
            return False

    async def get_players_for_balance(self) -> List[Dict[str, Any]]:
        """Retorna jogadores com informações para balanceamento."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT discord_id, riot_id, pdl, lol_rank, wins, losses 
                    FROM players ORDER BY pdl DESC
                ''') as cursor:
                    rows = await cursor.fetchall()
                    players = []
                    for row in rows:
                        player_data = dict(row)
                        player_data['balance_score'] = config.calculate_balance_score(
                            player_data['pdl'],
                            player_data['lol_rank'],
                            player_data['wins'],
                            player_data['losses']
                        )
                        players.append(player_data)
                    return players
        except Exception as e:
            print(f"Erro ao buscar jogadores para balanceamento: {e}")
            return []

    async def update_player_pdl(self, discord_id: int, pdl_change: int) -> bool:
        """Atualiza o PDL de um jogador (adiciona ou remove)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET pdl = pdl + ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (pdl_change, discord_id))
                await db.commit()
                print(f"PDL do jogador {discord_id} atualizado: {'+' if pdl_change >= 0 else ''}{pdl_change}")
                return True
        except Exception as e:
            print(f"Erro ao atualizar PDL: {e}")
            return False

    async def set_player_pdl(self, discord_id: int, new_pdl: int) -> bool:
        """Define o PDL de um jogador para um valor específico."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET pdl = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (new_pdl, discord_id))
                await db.commit()
                print(f"PDL do jogador {discord_id} definido para: {new_pdl}")
                return True
        except Exception as e:
            print(f"Erro ao definir PDL: {e}")
            return False

    async def reset_player_pdl(self, discord_id: int) -> bool:
        """Reseta o PDL de um jogador para o valor padrão."""
        return await self.set_player_pdl(discord_id, config.DEFAULT_PDL)

    async def update_player_mvp_count(self, discord_id: int, mvp_change: int) -> bool:
        """Atualiza a contagem de MVP de um jogador (adiciona ou remove)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET mvp_count = mvp_count + ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (mvp_change, discord_id))
                await db.commit()
                print(f"MVP count do jogador {discord_id} atualizado: {'+' if mvp_change >= 0 else ''}{mvp_change}")
                return True
        except Exception as e:
            print(f"Erro ao atualizar MVP count: {e}")
            return False

    async def update_player_bagre_count(self, discord_id: int, bagre_change: int) -> bool:
        """Atualiza a contagem de Bagre de um jogador (adiciona ou remove)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET bagre_count = bagre_count + ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (bagre_change, discord_id))
                await db.commit()
                print(f"Bagre count do jogador {discord_id} atualizado: {'+' if bagre_change >= 0 else ''}{bagre_change}")
                return True
        except Exception as e:
            print(f"Erro ao atualizar Bagre count: {e}")
            return False

    async def set_player_mvp_count(self, discord_id: int, new_count: int) -> bool:
        """Define a contagem de MVP de um jogador para um valor específico."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET mvp_count = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (new_count, discord_id))
                await db.commit()
                print(f"MVP count do jogador {discord_id} definido para: {new_count}")
                return True
        except Exception as e:
            print(f"Erro ao definir MVP count: {e}")
            return False

    async def set_player_bagre_count(self, discord_id: int, new_count: int) -> bool:
        """Define a contagem de Bagre de um jogador para um valor específico."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET bagre_count = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (new_count, discord_id))
                await db.commit()
                print(f"Bagre count do jogador {discord_id} definido para: {new_count}")
                return True
        except Exception as e:
            print(f"Erro ao definir Bagre count: {e}")
            return False

    async def reset_player_stats(self, discord_id: int) -> bool:
        """Reseta todas as estatísticas de um jogador (MVPs, Bagres, W/L)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET mvp_count = 0, 
                        bagre_count = 0,
                        wins = 0,
                        losses = 0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (discord_id,))
                await db.commit()
                print(f"Estatísticas do jogador {discord_id} resetadas")
                return True
        except Exception as e:
            print(f"Erro ao resetar estatísticas: {e}")
            return False

    async def update_player_username(self, discord_id: int, username: str) -> bool:
        """Atualiza o username de um jogador no banco de dados."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE players 
                    SET username = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (username, discord_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"Erro ao atualizar username: {e}")
            return False

    async def reset_all_pdl(self, new_pdl: int = config.DEFAULT_PDL) -> int:
        """Define o PDL de todos os jogadores para um valor específico."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    UPDATE players
                    SET pdl = ?,
                        updated_at = CURRENT_TIMESTAMP
                ''', (new_pdl,))
                await db.commit()
                return cursor.rowcount or 0
        except Exception as e:
            print(f"Erro ao resetar PDL global: {e}")
            return 0

    async def get_metadata(self, key: str) -> Optional[str]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT value FROM metadata WHERE key = ?', (key,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            print(f"Erro ao buscar metadata {key}: {e}")
            return None

    async def set_metadata(self, key: str, value: str) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO metadata(key, value)
                    VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                ''', (key, value))
                await db.commit()
                return True
        except Exception as e:
            print(f"Erro ao salvar metadata {key}: {e}")
            return False

# Instância global
db_manager = DatabaseManager()
