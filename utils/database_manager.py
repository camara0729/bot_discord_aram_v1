# utils/database_manager.py
import aiosqlite
import os
import json
import uuid
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
                    guild_id INTEGER DEFAULT 0,
                    pdl_summary TEXT,
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
                    result TEXT,
                    pdl_change INTEGER DEFAULT 0,
                    is_mvp INTEGER DEFAULT 0,
                    is_bagre INTEGER DEFAULT 0,
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

            await db.execute('''
                CREATE TABLE IF NOT EXISTS queues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER,
                    name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    slots INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'aberta',
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, name)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS queue_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queue_id INTEGER NOT NULL,
                    discord_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(queue_id, discord_id),
                    FOREIGN KEY(queue_id) REFERENCES queues(id) ON DELETE CASCADE
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS season_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    season_name TEXT NOT NULL,
                    discord_id INTEGER NOT NULL,
                    riot_id TEXT,
                    pdl INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    mvp_count INTEGER,
                    bagre_count INTEGER,
                    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Garantir colunas extras após upgrades
            async with db.execute("PRAGMA table_info(matches)") as cursor:
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                if 'guild_id' not in column_names:
                    await db.execute('ALTER TABLE matches ADD COLUMN guild_id INTEGER DEFAULT 0')
                if 'pdl_summary' not in column_names:
                    await db.execute('ALTER TABLE matches ADD COLUMN pdl_summary TEXT')

            async with db.execute("PRAGMA table_info(match_participants)") as cursor:
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                if 'result' not in column_names:
                    await db.execute("ALTER TABLE match_participants ADD COLUMN result TEXT")
                if 'pdl_change' not in column_names:
                    await db.execute("ALTER TABLE match_participants ADD COLUMN pdl_change INTEGER DEFAULT 0")
                if 'is_mvp' not in column_names:
                    await db.execute("ALTER TABLE match_participants ADD COLUMN is_mvp INTEGER DEFAULT 0")
                if 'is_bagre' not in column_names:
                    await db.execute("ALTER TABLE match_participants ADD COLUMN is_bagre INTEGER DEFAULT 0")

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

    async def bulk_reset_player_stats(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE players
                SET pdl = ?, wins = 0, losses = 0, mvp_count = 0, bagre_count = 0,
                    updated_at = CURRENT_TIMESTAMP
            ''', (config.DEFAULT_PDL,))
            await db.commit()

    async def save_season_history(self, season_name: str, players: List[Dict[str, Any]]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany('''
                INSERT INTO season_history (season_name, discord_id, riot_id, pdl, wins, losses, mvp_count, bagre_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (
                    season_name,
                    player['discord_id'],
                    player.get('riot_id'),
                    player['pdl'],
                    player['wins'],
                    player['losses'],
                    player.get('mvp_count', 0),
                    player.get('bagre_count', 0)
                )
                for player in players
            ])
            await db.commit()

    async def get_full_ranking(self) -> List[Dict[str, Any]]:
        return await self.get_all_players()

    async def create_match(
        self,
        guild_id: int,
        blue_team: List[int],
        red_team: List[int],
        winner: str,
        mvp_id: Optional[int],
        bagre_id: Optional[int],
        pdl_changes: Dict[int, int],
        duration: Optional[int] = None
    ) -> str:
        """Registra partida na tabela matches e retorna match_id."""
        match_identifier = f"{guild_id}-{uuid.uuid4().hex[:8]}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO matches (match_id, guild_id, blue_team, red_team, winner, mvp_id, bagre_id, duration, pdl_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                match_identifier,
                guild_id,
                json.dumps(blue_team),
                json.dumps(red_team),
                winner,
                mvp_id,
                bagre_id,
                duration,
                json.dumps(pdl_changes)
            ))
            await db.commit()
        return match_identifier

    async def add_match_participants(self, match_id: str, participants: List[Dict[str, Any]]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany('''
                INSERT INTO match_participants (match_id, discord_id, team, result, pdl_change, is_mvp, is_bagre)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                (
                    match_id,
                    entry['discord_id'],
                    entry['team'],
                    entry['result'],
                    entry.get('pdl_change', 0),
                    1 if entry.get('is_mvp') else 0,
                    1 if entry.get('is_bagre') else 0
                )
                for entry in participants
            ])
            await db.commit()

    async def get_recent_matches_for_player(self, discord_id: int, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        query = '''
            SELECT mp.match_id, mp.team, mp.result, mp.pdl_change, mp.is_mvp, mp.is_bagre,
                   mp.created_at, m.winner, m.mvp_id, m.bagre_id
            FROM match_participants mp
            JOIN matches m ON mp.match_id = m.match_id
            WHERE mp.discord_id = ?
              AND mp.created_at >= datetime('now', ?)
            ORDER BY mp.created_at DESC
            LIMIT ?
        '''
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, (discord_id, f'-{int(days)} days', limit)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"Erro ao buscar histórico do jogador {discord_id}: {e}")
            return []

    async def get_guild_recent_participation(self, guild_id: int, days: int = 7) -> List[Dict[str, Any]]:
        query = '''
            SELECT mp.discord_id, mp.result, mp.is_mvp, mp.pdl_change
            FROM match_participants mp
            JOIN matches m ON mp.match_id = m.match_id
            WHERE m.guild_id = ?
              AND mp.created_at >= datetime('now', ?)
        '''
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, (guild_id, f'-{int(days)} days')) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"Erro ao buscar histórico da guild {guild_id}: {e}")
            return []

    async def create_queue(self, guild_id: int, channel_id: int, message_id: int, name: str, mode: str, slots: int, created_by: int) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO queues (guild_id, channel_id, message_id, name, mode, slots, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (guild_id, channel_id, message_id, name, mode, slots, created_by))
                await db.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Erro ao criar fila: {e}")
            raise

    async def update_queue_message(self, queue_id: int, message_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE queues SET message_id = ? WHERE id = ?', (message_id, queue_id))
            await db.commit()

    async def get_queue(self, queue_id: int) -> Optional[Dict[str, Any]]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM queues WHERE id = ?', (queue_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            print(f"Erro ao buscar fila: {e}")
            return None

    async def get_queue_by_name(self, guild_id: int, name: str) -> Optional[Dict[str, Any]]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM queues WHERE guild_id = ? AND name = ?', (guild_id, name)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            print(f"Erro ao buscar fila por nome: {e}")
            return None

    async def get_active_queues(self, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = 'SELECT * FROM queues WHERE status = "aberta"'
        params: tuple[Any, ...] = ()
        if guild_id:
            query += ' AND guild_id = ?'
            params = (guild_id,)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            print(f"Erro ao listar filas ativas: {e}")
            return []

    async def add_player_to_queue(self, queue_id: int, discord_id: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO queue_players (queue_id, discord_id) VALUES (?, ?)
                ''', (queue_id, discord_id))
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            return False
        except Exception as e:
            print(f"Erro ao adicionar jogador à fila: {e}")
            return False

    async def remove_player_from_queue(self, queue_id: int, discord_id: int) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('DELETE FROM queue_players WHERE queue_id = ? AND discord_id = ?', (queue_id, discord_id))
                await db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao remover jogador da fila: {e}")
            return False

    async def get_queue_players(self, queue_id: int) -> List[int]:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('SELECT discord_id FROM queue_players WHERE queue_id = ? ORDER BY joined_at', (queue_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
        except Exception as e:
            print(f"Erro ao buscar jogadores da fila: {e}")
            return []

    async def update_queue_status(self, queue_id: int, status: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE queues SET status = ? WHERE id = ?', (status, queue_id))
            await db.commit()

    async def increment_metadata_counter(self, key: str) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO metadata(key, value)
                    VALUES(?, '1')
                    ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1
                ''', (key,))
                await db.commit()
        except Exception as e:
            print(f"Erro ao incrementar contador {key}: {e}")

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
