# Bot Discord ARAM Scrim Master

## Comandos principais
- `/registrar` – registra o Riot ID do jogador.
- `/times` – cria painel para montar times com balanceamento automático.
- `/ranking` – mostra o Top 20 por PDL.
- `/fila criar` – administradores criam filas inteligentes (Queue+). Jogadores usam os botões **Entrar/Sair** para participar e, quando a fila completa, os times são montados automaticamente e um snapshot é salvo para `/resultado_rapido`.
- `/fila status` – consulta filas abertas no servidor.
- `/fila cancelar` – encerra filas em andamento.

## Permissões
- Comandos `/fila criar` e `/fila cancelar` exigem permissão de administrador na guild (verificado antes de criar a fila).
- O bot precisa de permissão para enviar mensagens e usar componentes no canal configurado.

## Variáveis de ambiente relevantes
- `DISCORD_TOKEN`
- `RIOT_API_KEY`
- `DATABASE_PATH` (ex.: `/app/data/bot_database.db`)
- `BACKUP_WEBHOOK_URL`

## Observações Queue+
- Cada guild pode manter múltiplas filas simultâneas.
- O bot registra métricas de filas concluídas em `metadata.queues_completed` (visível nos logs).
- Snapshot das últimas equipes é enviado para o mecanismo já utilizado por `/resultado_rapido`.
