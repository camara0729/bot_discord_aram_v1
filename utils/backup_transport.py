# utils/backup_transport.py
import os
from pathlib import Path
from typing import Optional

import aiohttp


async def send_backup_file(file_path: str, description: Optional[str] = None) -> bool:
    """Envia arquivo de backup para o webhook configurado."""
    webhook_url = os.getenv('BACKUP_WEBHOOK_URL')
    if not webhook_url:
        print("⚠️ BACKUP_WEBHOOK_URL não configurada - não foi possível enviar o backup")
        return False

    path = Path(file_path)
    if not path.exists():
        print(f"⚠️ Arquivo de backup não encontrado: {file_path}")
        return False

    timeout = aiohttp.ClientTimeout(total=60)
    data = aiohttp.FormData()
    message = description or "Backup automático do ARAM Bot"
    data.add_field('content', message)
    data.add_field('file', path.read_bytes(), filename=path.name, content_type='application/json')

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(webhook_url, data=data) as response:
            if response.status < 300:
                print("✅ Backup enviado para o webhook com sucesso")
                return True
            else:
                error_text = await response.text()
                print(f"❌ Falha ao enviar backup: HTTP {response.status} - {error_text[:200]}")
                return False
