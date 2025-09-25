# utils/database_manager.py
import aiosqlite
import os
from typing import Optional, Dict, Any, List
import config

class DatabaseManager:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path

    async def initialize_database(self):
        """Inicializa o banco de dados e cria as tabelas necessárias."""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabela de jogadores - Adicionado campo lol_rank
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    discord_id INTEGER PRIMARY KEY,
                    riot_id TEXT NOT NULL,
                    puuid TEXT NOT NULL,
                    lol_rank TEXT NOT NULL,
                    pdl INTEGER DEFAULT 1000,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    mvp_count INTEGER DEFAULT 0,
                    bagre_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verifica se a coluna lol_rank existe e adiciona se necessário
            async with db.execute("PRAGMA table_info(players)") as cursor:
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                if 'lol_rank' not in column_names:
                    await db.execute('ALTER TABLE players ADD COLUMN lol_rank TEXT DEFAULT "PRATA II"')
                    print("Coluna lol_rank adicionada à tabela players")
            
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
            
            await db.commit()
            print("Banco de dados inicializado com sucesso!")

    async def add_player(self, discord_id: int, riot_id: str, puuid: str, lol_rank: str) -> bool:
        """Adiciona um novo jogador ao banco de dados com PDL padrão."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO players 
                    (discord_id, riot_id, puuid, lol_rank, pdl, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (discord_id, riot_id, puuid, lol_rank, config.DEFAULT_PDL))
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

# Instância global
db_manager = DatabaseManager()