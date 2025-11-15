# Deploy Guide - Render Free Tier (Worker)

## Pré-requisitos
1. Repositório GitHub com o bot.
2. Conta no Render (plano gratuito).
3. Discord Bot Token e Riot API Key.
4. Webhook privado (Discord ou outro endpoint HTTP) para receber backups.

## Passo a Passo

### 1. Preparar Repositório
Certifique-se de que o código mais recente está no GitHub.

### 2. Configurar Worker no Render
1. Acesse [render.com](https://render.com).
2. Clique em **New +** → **Worker**.
3. Selecione o repositório do bot.
4. Configure:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Plan**: `Free`

### 3. Variáveis de Ambiente
| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `DISCORD_TOKEN` | Token do bot do Discord | ✅ |
| `RIOT_API_KEY` | Chave da Riot | ✅ |
| `DATABASE_PATH` | Caminho do SQLite (use `/app/data/bot_database.db`) | ✅ |
| `BACKUP_WEBHOOK_URL` | Webhook para receber backups JSON | ✅ |
| `BACKUP_FREQUENCY_HOURS` | Intervalo entre backups automáticos (padrão 6) | ❌ |

O `render.yaml` já define o volume persistente `bot-data` montado em `/app/data`.

### 4. Deploy Inicial
1. Clique em **Create Worker**.
2. Aguarde a instalação e o start.
3. Verifique nos logs:
   - `🤖 Bot ... está online!`
   - `💾 Rotina de backup remoto iniciada`

### 5. Migração de Dados (opcional)
- Coloque um arquivo `render_migration_backup.json` no repositório com o dump desejado.
- O `main.py` detecta banco vazio e restaura automaticamente esse arquivo apenas uma vez.

## Monitoramento
- Use `/status_backup` para confirmar webhook, caminho do banco e horário do último backup.
- Logs do Render mostram cada envio automático de backup.
- Como Worker, não há endpoints HTTP – monitore a presença do bot diretamente pelo Discord.

## Recuperação
1. Baixe o backup JSON do webhook (ex.: canal privado no Discord).
2. Faça upload do arquivo para o repositório/volume.
3. Use `/restaurar_backup arquivo:seuarquivo.json` ou deixe o arquivo como `render_migration_backup.json` para restauração automática.

## Dicas
- Mantenha o `DATABASE_PATH` apontando para o volume persistente para evitar perdas inesperadas.
- Para maior confiabilidade, gere backups manuais antes de grandes alterações usando `/fazer_backup`.
- Caso precise migrar para outra plataforma (Railway, Fly.io, etc.), basta reutilizar o Dockerfile e as mesmas variáveis.
