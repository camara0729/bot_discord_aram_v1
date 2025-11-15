import asyncio
import json
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

QUEUE_FILE = Path('.ops_event_queue.jsonl')
OPS_WEBHOOK_URL = os.getenv('OPS_WEBHOOK_URL')


async def log_ops_event(
    event: str,
    guild_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    stacktrace: Optional[str] = None
) -> None:
    payload = {
        'event': event,
        'guild_id': guild_id,
        'user_id': user_id,
        'details': details or {},
        'stacktrace': stacktrace,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ack': 'Responder com ✅ no canal de incidentes'
    }
    logger = OpsLogger()
    await logger.send(payload)


class OpsLogger:
    def __init__(self) -> None:
        self.webhook_url = OPS_WEBHOOK_URL
        self.queue_file = QUEUE_FILE

    async def send(self, payload: Dict[str, Any]) -> None:
        self._append_metric('ops_events_total')
        if self.webhook_url:
            if await self._flush_queue():
                pass
            if await self._post(payload):
                return
        self._write_queue(payload)

    async def _flush_queue(self) -> bool:
        if not self.queue_file.exists():
            return True
        try:
            lines = self.queue_file.read_text(encoding='utf-8').splitlines()
            remaining = []
            for line in lines:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not await self._post(data):
                    remaining.append(json.dumps(data, ensure_ascii=False))
                    break
            if remaining:
                self.queue_file.write_text("\n".join(remaining) + "\n", encoding='utf-8')
                return False
            self.queue_file.unlink(missing_ok=True)
            return True
        except Exception:
            return False

    async def _post(self, payload: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload, timeout=15) as resp:
                    success = resp.status < 300
                    if success:
                        self._append_metric('ops_events_sent')
                    else:
                        self._append_metric('ops_events_failed')
                    return success
        except Exception:
            self._append_metric('ops_events_failed')
            return False

    def _write_queue(self, payload: Dict[str, Any]) -> None:
        with self.queue_file.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _append_metric(self, key: str) -> None:
        try:
            from utils.database_manager import db_manager
            loop = asyncio.get_running_loop()
            loop.create_task(db_manager.increment_metadata_counter(key))
        except RuntimeError:
            pass
        except Exception:
            pass


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))


if __name__ == '__main__':
    async def _test():
        try:
            raise RuntimeError('Teste de observabilidade')
        except RuntimeError as exc:
            await log_ops_event(
                event='teste.manual',
                details={'mensagem': 'Simulação via script'},
                stacktrace=format_exception(exc)
            )
            print('Evento de teste registrado. Verifique o webhook ou o arquivo de fila.')

    asyncio.run(_test())
