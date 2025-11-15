# utils/last_team_store.py
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

LAST_TEAMS_FILE = Path('last_teams.json')


def _load_store() -> Dict[str, Dict[str, List[int]]]:
    if LAST_TEAMS_FILE.exists():
        try:
            with open(LAST_TEAMS_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as exc:
            print(f"⚠️ Erro ao ler arquivo de times: {exc}")
    return {}


def save_last_teams(guild_id: int, blue_team: List[int], red_team: List[int]) -> None:
    data = _load_store()
    data[str(guild_id)] = {
        'blue_team': blue_team,
        'red_team': red_team,
        'timestamp': datetime.utcnow().isoformat()
    }

    try:
        with open(LAST_TEAMS_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2)
    except Exception as exc:
        print(f"⚠️ Erro ao salvar times: {exc}")


def load_last_teams(guild_id: int) -> Optional[Dict[str, List[int]]]:
    data = _load_store()
    return data.get(str(guild_id))


def clear_last_teams(guild_id: int) -> None:
    data = _load_store()
    if str(guild_id) in data:
        del data[str(guild_id)]
        try:
            with open(LAST_TEAMS_FILE, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2)
        except Exception as exc:
            print(f"⚠️ Erro ao limpar times: {exc}")
