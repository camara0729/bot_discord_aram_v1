# database.py
import sqlite3
import json

DB_NAME = 'aram_bot.db'

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Cria as tabelas do banco de dados se elas não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabela de jogadores
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            discord_id TEXT PRIMARY KEY,
            riot_puuid TEXT UNIQUE NOT NULL,
            riot_id TEXT NOT NULL,
            mmr INTEGER DEFAULT 1500,
            k_factor INTEGER DEFAULT 40,
            current_title TEXT,
            stats TEXT,
            achievements TEXT,
            match_history TEXT
        )
    ''')

    # Tabela de partidas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            match_id TEXT PRIMARY KEY,
            timestamp TEXT,
            game_duration_seconds INTEGER,
            winning_team_id INTEGER,
            teams TEXT,
            player_stats TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- Funções de Jogador ---

def add_player(discord_id, riot_puuid, riot_id):
    """Adiciona um novo jogador ao banco de dados."""
    conn = get_db_connection()
    try:
        stats = {
            "wins": 0, "losses": 0, "total_games": 0,
            "lifetime_kills": 0, "lifetime_deaths": 0, "lifetime_assists": 0,
            "lifetime_damage_dealt": 0, "lifetime_penta_kills": 0
        }
        # CORRIGIDO: Adicionado '' como argumento para json.dumps para criar listas JSON vazias.
        conn.execute(
            'INSERT INTO players (discord_id, riot_puuid, riot_id, stats, achievements, match_history) VALUES (?,?,?,?,?,?)',
            (str(discord_id), riot_puuid, riot_id, json.dumps(stats), json.dumps(), json.dumps())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Jogador já existe
    finally:
        conn.close()

def get_player_by_discord_id(discord_id):
    """Busca um jogador pelo seu ID do Discord."""
    conn = get_db_connection()
    player = conn.execute('SELECT * FROM players WHERE discord_id =?', (str(discord_id),)).fetchone()
    conn.close()
    return player

def get_player_by_puuid(puuid):
    """Busca um jogador pelo seu PUUID da Riot."""
    conn = get_db_connection()
    player = conn.execute('SELECT * FROM players WHERE riot_puuid =?', (puuid,)).fetchone()
    conn.close()
    return player

def update_player_after_match(puuid, mmr_change, stats_update, new_title, new_achievements):
    """Atualiza os dados de um jogador após uma partida."""
    conn = get_db_connection()
    player = get_player_by_puuid(puuid)
    if not player:
        conn.close()
        return

    new_mmr = player['mmr'] + mmr_change
    stats = json.loads(player['stats'])
    stats['total_games'] += 1
    new_k_factor = 20 if stats['total_games'] > 20 else 40

    for key, value in stats_update.items():
        if key in stats:
            stats[key] += value

    match_history = json.loads(player['match_history'])
    match_history.insert(0, stats_update['match_id'])
    if len(match_history) > 20:
        match_history.pop()

    achievements = json.loads(player['achievements'])
    for ach in new_achievements:
        if ach not in achievements:
            achievements.append(ach)
    
    final_title = new_title if new_title else player['current_title']

    conn.execute(
        '''
        UPDATE players
        SET mmr =?, k_factor =?, stats =?, current_title =?, achievements =?, match_history =?
        WHERE riot_puuid =?
        ''',
        (new_mmr, new_k_factor, json.dumps(stats), final_title, json.dumps(achievements), json.dumps(match_history), puuid)
    )
    conn.commit()
    conn.close()

def get_all_players():
    """Retorna todos os jogadores para o ranking."""
    conn = get_db_connection()
    players = conn.execute('SELECT discord_id, riot_id, mmr, stats FROM players ORDER BY mmr DESC').fetchall()
    conn.close()
    return players

# --- Funções de Partida ---

def add_match(match_data):
    """Adiciona uma partida processada ao banco de dados."""
    conn = get_db_connection()
    try:
        conn.execute(
            'INSERT INTO matches (match_id, timestamp, game_duration_seconds, winning_team_id, teams, player_stats) VALUES (?,?,?,?,?,?)',
            (
                match_data['match_id'],
                match_data['timestamp'],
                match_data['game_duration_seconds'],
                match_data['winning_team_id'],
                json.dumps(match_data['teams']),
                json.dumps(match_data['player_stats'])
            )
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_match_by_id(match_id):
    """Busca uma partida pelo seu ID."""
    conn = get_db_connection()
    match = conn.execute('SELECT * FROM matches WHERE match_id =?', (match_id,)).fetchone()
    conn.close()
    return match