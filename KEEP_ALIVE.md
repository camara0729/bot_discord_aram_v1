# 🚀 Execução Contínua sem Keep-Alive

O bot agora roda como **Worker** no Render, portanto não depende mais de endpoints HTTP ou scripts externos para se manter acordado. O processo principal permanece ativo 24/7 enquanto houver horas disponíveis no plano gratuito.

## ✔️ O que mudou
- `render.yaml` e `Procfile` usam `type: worker`, eliminando o servidor web/`/health`.
- O loop de keep-alive/AioHTTP foi removido do `main.py`; apenas o Discord bot é iniciado.
- Nenhuma chamada externa periódica é necessária para evitar hibernação.

## 📦 Como configurar no Render
1. Crie um serviço **Worker** apontando para este repositório.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python main.py`
4. Configure as variáveis obrigatórias:
   - `DISCORD_TOKEN`
   - `RIOT_API_KEY`
   - `DATABASE_PATH=/app/data/bot_database.db` (usa o disco persistente)
   - `BACKUP_WEBHOOK_URL` (para envio automático dos backups JSON)

O Worker não expõe portas, portanto nenhum health-check HTTP é necessário.

## 🔎 Monitoramento opcional
Se quiser visibilidade adicional:
- Use um canal privado do Discord para receber logs do Render (Streaming logs).
- Configure alertas do próprio Discord (Status > Incident) ou monitores que chequem a presença do bot via API (`discord.py` já loga reconexões).

## 🧹 E o antigo `external_pinger.py`?
Esse script tornou-se opcional e pode ser removido. Ele só faz sentido se você hospedar o bot como Web Service em outro provedor.

Com esse ajuste, o bot permanece on-line continuamente sem depender de gambiarras de keep-alive. 🎉
