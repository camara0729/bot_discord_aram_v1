# Sistema de Backup para Render Free Tier

O armazenamento local do Render é efêmero, mas agora usamos dois mecanismos complementares:

1. **Banco em disco persistente** – `DATABASE_PATH=/app/data/bot_database.db` fica em um volume que sobrevive a deploys/restarts.
2. **Backup remoto automático** – os dados são exportados periodicamente para um webhook (Discord, Supabase Storage ou qualquer endpoint HTTP compatível).

## Como Funciona

### 1. Disco Persistente
- Configure `DATABASE_PATH=/app/data/bot_database.db` (já definido em `render.yaml`).
- O arquivo do banco fica no volume `bot-data`, evitando perda em redeploys.

### 2. Backup Automático via Webhook
- Variável obrigatória: `BACKUP_WEBHOOK_URL` (ex.: webhook privado do Discord).
- Job `periodic_backup_task` roda a cada hora e, se o último backup tiver mais de `BACKUP_FREQUENCY_HOURS` (default 6), cria um JSON via `backup_restore_db.py` e envia para o webhook.
- Após envio bem-sucedido, a data do backup é registrada em `.last_backup_time`.

### 3. Comandos Manuais
- `/fazer_backup`: força a criação do arquivo JSON e o envio para o webhook.
- `/listar_backups`: lista arquivos `.json` presentes no repositório/volume (útil para inspeções).
- `/restaurar_backup` e `/confirmar_restore`: restauram qualquer arquivo local (inclusive backups baixados do webhook e enviados de volta para o servidor).

## Fluxo de Recuperação
1. Baixe o arquivo JSON do canal/webhook.
2. Faça upload para o repositório (ou para o volume montado no Render).
3. Execute `/restaurar_backup arquivo:nome.json` ou deixe o arquivo como `render_migration_backup.json` para restauração automática no próximo deploy.

## Monitoramento
- `/status_backup` mostra:
  - Se o webhook está configurado.
  - Caminho atual do banco (`DATABASE_PATH`).
  - Último backup automático registrado.
  - Principais arquivos `.json` existentes.
- Logs do Render exibem mensagens `📤 Preparando backup remoto...` e `✅ Backup enviado...` confirmando a rotina.

## Variáveis Relevantes
| Variável | Descrição |
|----------|-----------|
| `DATABASE_PATH` | Caminho absoluto do arquivo SQLite (ex.: `/app/data/bot_database.db`). |
| `BACKUP_WEBHOOK_URL` | URL usada para receber os backups JSON. |
| `BACKUP_FREQUENCY_HOURS` | Intervalo mínimo entre backups automáticos (padrão 6h). |

Com esses ajustes, o bot mantém os dados mesmo no plano gratuito e ainda exporta cópias off-site para recuperação rápida. 🚀
