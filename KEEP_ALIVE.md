# 🚀 Sistema Keep-Alive para Render Free Tier

Como o plano gratuito do Render só oferece Web Services, o bot expõe um pequeno servidor HTTP e se mantém ativo pingando a própria URL.

## Como funciona
1. **Servidor HTTP interno** (`aiohttp`)
   - Endpoints `/`, `/health` e `/ping` respondem com o status do bot.
   - Necessário para o Render detectar que o processo está ouvindo a porta definida em `PORT`.
2. **Loop de keep-alive**
   - A cada 8 minutos o bot faz `GET` em `RENDER_EXTERNAL_URL/ping` (ou `localhost:PORT` em desenvolvimento).
   - Isso evita que o Render hiberne o serviço por inatividade.
3. **Monitor externo (recomendado)**
   - Configure algo como UptimeRobot para bater em `/health` a cada 5 minutos. Assim você recebe alertas caso o serviço caia e reforça o keep-alive.

## Configuração no Render
1. Serviço do tipo **Web**.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python main.py`
4. Variáveis obrigatórias:
   - `DISCORD_TOKEN`
   - `RIOT_API_KEY`
   - `DATABASE_PATH=/app/data/bot_database.db`
   - `BACKUP_WEBHOOK_URL`
   - O Render preenche `PORT` automaticamente; após o primeiro deploy copie a URL e defina `RENDER_EXTERNAL_URL` para ela.

## Testando
- Abra `https://seu-app.onrender.com/health` no navegador; você deve ver o JSON de status.
- Verifique os logs: `🌐 Servidor web iniciado...` e `✅ Keep-alive ping successful ...` indicam que o loop está rodando.

## Scripts externos
O `external_pinger.py` permanece opcional. Use-o apenas se quiser um segundo ping rodando fora do Render (por exemplo, em outra VPS).

Com esse setup o bot continua compatível com o plano gratuito, mantém a porta obrigatória aberta e reduz o risco de hibernação inesperada. ✅
