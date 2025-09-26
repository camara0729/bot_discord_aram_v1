# 🚀 Sistema Keep-Alive 24/7

Este bot implementa um sistema completo para evitar a hibernação no plano gratuito do Render.

## 🔧 Como Funciona

### 1. **Servidor HTTP Interno**
- Bot roda um servidor web na porta definida pelo Render
- Endpoints disponíveis: `/`, `/health`, `/ping`
- Responde com status do bot em JSON

### 2. **Auto-Ping Interno**
- Bot faz ping em si mesmo a cada 10 minutos
- Evita hibernação do plano gratuito (15 min)
- Logs automáticos de keep-alive

### 3. **Pinger Externo (Opcional)**
- Script separado (`external_pinger.py`) 
- Pode rodar em outro servidor/computador
- Pinga o bot a cada 12 minutos

## 📋 Configuração no Render

### Variáveis de Ambiente Necessárias:
```
DISCORD_BOT_TOKEN=seu_token_aqui
RIOT_API_KEY=sua_chave_aqui
PORT=10000  # Automático no Render
RENDER_EXTERNAL_URL=https://seu-bot.onrender.com  # Automático
```

### Configurações do Serviço:
```
Build Command: pip install -r requirements.txt
Start Command: python main.py
Port: 10000 (ou a porta que o Render definir)
```

## 🌐 Endpoints do Bot

Após deploy, seu bot terá os endpoints:

- `https://seu-bot.onrender.com/` - Status geral
- `https://seu-bot.onrender.com/health` - Health check
- `https://seu-bot.onrender.com/ping` - Keep-alive ping

### Exemplo de resposta:
```json
{
  "status": "alive",
  "bot": "ARAM Bot",
  "timestamp": "2025-09-26T14:30:00",
  "guilds": 1,
  "uptime": "online"
}
```

## 🤖 Uso do Pinger Externo

### 1. Configure a URL do bot:
```bash
# No arquivo .env
BOT_URL=https://seu-bot.onrender.com
```

### 2. Execute o pinger:
```bash
python external_pinger.py
```

### 3. Logs do pinger:
```
🚀 Iniciando pinger externo do bot...
🎯 URL do bot: https://seu-bot.onrender.com
✅ Bot ativo - ARAM Bot - 14:30:15
💓 Bot mantido ativo
```

## 📊 Monitoramento

### Logs do Bot:
```
🌐 Servidor web iniciado na porta 10000
🚀 Sistema keep-alive iniciado
✅ Keep-alive ping successful - 14:20:00
✅ Keep-alive ping successful - 14:30:00
```

### Status no Render:
- Aba "Logs": Acompanhe pings em tempo real
- Aba "Metrics": CPU/RAM sempre ativo
- Status: "Live" (verde) continuamente

## ⚠️ Importante

### Plano Gratuito:
- ✅ **Funciona** mas tem limitações de CPU
- ✅ **Keep-alive** evita hibernação
- ⚠️ **500 horas/mês** de uso gratuito

### Plano Pago ($7/mês):
- ✅ **Sem hibernação** nativa
- ✅ **Melhor performance**
- ✅ **Keep-alive** como backup

## 🔍 Troubleshooting

### Bot hibernando mesmo assim:
1. Verifique logs do keep-alive
2. Confirme se endpoints respondem
3. Use pinger externo como backup

### Erro de porta:
```python
# O Render define PORT automaticamente
PORT = int(os.getenv('PORT', 10000))
```

### Erro de URL:
```python
# URL é definida automaticamente pelo Render
RENDER_URL = os.getenv('RENDER_EXTERNAL_URL')
```

## 🎯 Resultado

Com este sistema implementado:
- ✅ **Bot ativo 24/7** no plano gratuito
- ✅ **Ping automático** a cada 10 minutos  
- ✅ **Servidor web** respondendo sempre
- ✅ **Logs detalhados** de monitoramento
- ✅ **Backup externo** opcional

Seu bot Discord ARAM ficará online continuamente! 🎮✨