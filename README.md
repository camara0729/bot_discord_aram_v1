# Bot Discord ARAM Scrim Master

## Comandos principais
- `/registrar` – registra o Riot ID do jogador.
- `/times` – cria painel para montar times com balanceamento automático.
- `/ranking` – mostra o Top 20 por PDL.
- `/fila criar` – administradores criam filas inteligentes (Queue+). Jogadores usam os botões **Entrar/Sair** para participar e, quando a fila completa, os times são montados automaticamente e um snapshot é salvo para `/resultado_rapido`.
- `/fila status` – consulta filas abertas no servidor.
- `/fila cancelar` – encerra filas em andamento.
- `/historico` – mostra histórico dos últimos N dias com streak, média de PDL e destaques.
- `/historico_configurar_cartao` / `/historico_enviar_cartao` – comandos administrativos para definir o canal e disparar o cartão semanal de destaques.
- `/temporada_iniciar` / `/temporada_finalizar` – comandos administrativos para resetar o ranking com snapshots e bloquear partidas entre temporadas.

## Permissões
- Comandos `/fila criar` e `/fila cancelar` exigem permissão de administrador na guild (verificado antes de criar a fila).
- O bot precisa de permissão para enviar mensagens e usar componentes no canal configurado.

## Variáveis de ambiente relevantes
- `DISCORD_TOKEN`
- `RIOT_API_KEY`
- `DATABASE_PATH` (ex.: `/app/data/bot_database.db`)
- `BACKUP_WEBHOOK_URL`
- (Opcional) `RENDER_EXTERNAL_URL` – usado pelo keep-alive

## Observações Queue+
- Cada guild pode manter múltiplas filas simultâneas.
- O bot registra métricas de filas concluídas em `metadata.queues_completed` (visível nos logs).
- Snapshot das últimas equipes é enviado para o mecanismo já utilizado por `/resultado_rapido`.

## Histórico & Destaques
- Cada partida registrada agora gera entradas completas em `matches` e `match_participants`, permitindo agregações detalhadas.
- `/historico` aceita o período (1 a 90 dias) e, se nenhum jogador for informado, usa o autor.
- Configure o canal para os cartões semanais com `/historico_configurar_cartao canal:#destaques`. O bot envia automaticamente (no máximo uma vez por semana) ou sob demanda via `/historico_enviar_cartao`.
- Métricas de uso (`metadata.historico_used`, `metadata.matches_registered`) são incrementadas automaticamente e podem ser inspecionadas via consultas diretas ao banco.

## Temporadas Automatizadas
- Antes de um reset, use `/temporada_iniciar nome:"Split X" canal:#anuncios`. O bot gera snapshot JSON (enviado ao webhook de backup), exporta os dados para `season_history`, faz backup adicional e reseta PDL/W-L/MVP/Bagre para o valor padrão.
- `/temporada_finalizar` congela o ranking, gera um segundo snapshot e define a flag `season_locked`. Enquanto `season_locked=1`, comandos de registro de partida retornam aviso até nova temporada começar.
- Os metadados (`season_active`, `season_name`, `season_started_at`, `season_last_finished`) ficam na tabela `metadata`. Métricas `seasons_started`/`seasons_finished` ajudam a medir recorrência.
- Recomenda-se verificar o webhook de backup (`BACKUP_WEBHOOK_URL`) antes de executar os resets. Sem ele, os snapshots ficam apenas no sistema de arquivos.
