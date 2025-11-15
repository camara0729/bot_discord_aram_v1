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
- `/sincronizar_elo` – consulta a Riot API e atualiza o rank armazenado no banco.
- `/fairplay registrar/resolver/listar/configurar` – administradores gerenciam incidentes de fair play e bloqueios automáticos.

## Permissões
- Comandos `/fila criar` e `/fila cancelar` exigem permissão de administrador na guild (verificado antes de criar a fila).
- O bot precisa de permissão para enviar mensagens e usar componentes no canal configurado.

## Variáveis de ambiente relevantes
- `DISCORD_TOKEN`
- `RIOT_API_KEY`
- `DATABASE_PATH` (ex.: `/app/data/bot_database.db`)
- `BACKUP_WEBHOOK_URL`
- (Opcional) `RENDER_EXTERNAL_URL` – usado pelo keep-alive
- `OPS_WEBHOOK_URL` – webhook privado que recebe os eventos estruturados de observabilidade.
- `FAIRPLAY_LIMIT` / `FAIRPLAY_TIMEOUT_MINUTES` – valores padrão para incidentes ativos e tempo de bloqueio antes de impedir novas participações.

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

## Observabilidade via Webhook Estruturado
- Configure `OPS_WEBHOOK_URL` com um webhook privado (ex.: canal de incidentes). O bot envia payloads JSON contendo evento, guilda, usuário, detalhes e instrução de ACK (reaja com ✅ para indicar que alguém está cuidando).
- Eventos cobertos: erros de slash (`slash.error`), cooldowns excessivos, falhas no keep-alive (`keepalive.*`) e problemas no backup remoto (`backup.*`).
- Há fallback local (`.ops_event_queue.jsonl`) caso o webhook esteja indisponível; ao restaurar a conectividade, os eventos pendentes são reenviados.
- Métricas `ops_events_total`, `ops_events_sent`, `ops_events_failed` são armazenadas na tabela `metadata` para auditoria.
- Para testar a configuração, execute `python utils/ops_logger.py` após definir `OPS_WEBHOOK_URL`; o script gera um evento de prova e informa se foi enfileirado.

## Integração Riot Elo
- O bot usa `RIOT_API_KEY` para consultar a Riot API (account → summoner → league). A chave pode ser obtida no [Portal do Desenvolvedor Riot](https://developer.riotgames.com/); lembre-se de renovar periodicamente e respeitar os limites (20 req/seg global / 100 req/2min).
- Jogadores usam `/sincronizar_elo` para atualizar o campo `lol_rank`. O comando busca o Riot ID salvo, converte o tier para o formato interno (ex.: `OURO IV`) e registra o momento da sincronização.
- Um job automático (`rank_auto_sync`) roda diariamente e sincroniza até 5 jogadores que estão há mais de 7 dias sem atualizar o elo. Métricas `rank_sync_manual`, `rank_sync_auto` e `rank_sync_percent_30d` ajudam a monitorar a adoção.
- Caso a API esteja indisponível, os erros são reportados no webhook de observabilidade (`riot.sync_failed`) e o bot tenta novamente no próximo ciclo.

## Penalidades & Fair Play
- Use `/fairplay registrar jogador:@nick motivo:"ausencia" descrição:"Não apareceu"` para registrar incidentes. Após atingir o limite (`FAIRPLAY_LIMIT`, padrão 3), o bot aplica bloqueio automático por `FAIRPLAY_TIMEOUT_MINUTES` (padrão 30) em filas e geração de times.
- `/fairplay listar jogador` mostra histórico e `/fairplay resolver incidente_id:123` encerra incidentes em aberto. `/fairplay configurar limite:3 timeout_minutos:45` permite customizar por guild.
- Jogadores bloqueados recebem mensagem no canal público e DM (quando possível), e qualquer tentativa de entrar em filas ou usar `/times` é recusada com aviso.
- Métricas `fairplay_incidents`, `fairplay_penalties_applied` e `fairplay_resolved` são registradas para auditoria.
