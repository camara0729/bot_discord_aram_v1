# Deploy Guide - Render Free Tier (Web Service)

## Pré-requisitos
1. Repositório GitHub com o bot.
2. Conta no Render (plano gratuito).
3. Discord Bot Token e Riot API Key.
4. Webhook privado (Discord ou outro endpoint HTTP) para receber backups.

## Passo a Passo

### 1. Preparar Repositório
Certifique-se de que o código mais recente está no GitHub.

### 2. Configurar Web Service no Render
1. Acesse [render.com](https://render.com).
2. Clique em **New +** → **Web Service**.
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
| `DATABASE_PATH` | Caminho do SQLite (`/app/data/bot_database.db`) | ✅ |
| `BACKUP_WEBHOOK_URL` | Webhook para receber backups JSON | ✅ |
| `BACKUP_FREQUENCY_HOURS` | Intervalo entre backups automáticos (padrão 6) | ❌ |
| `RENDER_EXTERNAL_URL` | URL pública do serviço (defina após o primeiro deploy) | ❌ |

O `render.yaml` monta o volume `bot-data` em `/app/data`, garantindo persistência do banco.

### 4. Deploy Inicial
1. Clique em **Create Web Service**.
2. Aguarde o build e o start.
3. Confirme nos logs:
   - `🌐 Servidor web iniciado...`
   - `🤖 Bot ... está online!`
   - `💾 Rotina de backup remoto iniciada`

### 5. Migração de Dados (opcional)
- Faça upload de `render_migration_backup.json` antes do deploy.
- No primeiro start, se o banco estiver vazio, o arquivo é restaurado automaticamente e renomeado para evitar duplicidade.

## Monitoramento
- `/health` responde um JSON; use-o em um monitor externo (UptimeRobot) para manter o serviço acordado e detectar falhas.
- `/status_backup` mostra webhook, caminho do banco e último backup automático.
- Os logs exibem cada envio `✅ Backup enviado ...`.

## Recuperação
1. Baixe qualquer JSON do canal privado do webhook.
2. Suba o arquivo para o Render (ou para o repositório).
3. Use `/restaurar_backup arquivo:nome.json` ou renomeie para `render_migration_backup.json` e redeploy.

## Dicas
- Defina `RENDER_EXTERNAL_URL` logo após pegar a URL pública fornecida pelo Render; isso garante que o loop de keep-alive bata no endpoint correto.
- Gere `/fazer_backup` manual antes de alterações grandes.
- Para migrar para outros provedores (Railway, Fly.io etc.), reutilize o Dockerfile e as mesmas variáveis.
