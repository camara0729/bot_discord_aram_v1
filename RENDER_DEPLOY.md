# Deploy Guide - Render Free Tier

## Pré-requisitos
1. Conta no GitHub com repositório do bot
2. Conta no Render (gratuita)
3. Discord Bot Token
4. Riot API Key

## Passo a Passo

### 1. Preparar Repositório
```bash
# Adicionar sistema de backup ao Git
git add .
git commit -m "Add Git backup system for Render free tier"
git push origin main
```

### 2. Configurar Render
1. Acesse [render.com](https://render.com)
2. Conecte sua conta GitHub
3. Clique em "New +" → "Web Service"
4. Selecione seu repositório
5. Configure:
   - **Name**: `bot-discord-aram` (ou nome desejado)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Plan**: `Free`

### 3. Variáveis de Ambiente
No painel do Render, adicionar em "Environment":

| Variável | Valor | Obrigatório |
|----------|-------|-------------|
| `DISCORD_TOKEN` | `seu_bot_token_aqui` | ✅ |
| `RIOT_API_KEY` | `sua_riot_api_key_aqui` | ✅ |
| `RENDER_EXTERNAL_URL` | `https://seu-app-nome.onrender.com` | ⚠️ Preencher após deploy |
| `BACKUP_FREQUENCY_HOURS` | `6` | ❌ Opcional |

### 4. Deploy Inicial
1. Clique em "Deploy"
2. Aguarde build completar (3-5 minutos)
3. Bot iniciará automaticamente
4. Logs mostrarão: `📋 Nenhum backup de migração encontrado` (normal para primeiro deploy)

### 5. Configurar URL Externa
1. Após deploy, copiar URL do serviço (ex: `https://seu-bot-nome.onrender.com`)
2. Adicionar em Environment Variables como `RENDER_EXTERNAL_URL`
3. Redeploy para aplicar

### 6. Migrar Dados Existentes (se houver)
Se você tem dados existentes para migrar:

1. **Localmente**:
   ```bash
   python backup_restore_db.py
   # Escolha opção de criar backup
   ```

2. **Renomear arquivo**:
   ```bash
   mv backup_database_*.json render_migration_backup.json
   ```

3. **Commitar**:
   ```bash
   git add render_migration_backup.json
   git commit -m "Add migration backup for Render deploy"
   git push origin main
   ```

4. **Redeploy no Render**:
   - Vai detectar e restaurar automaticamente

## Verificação

### 1. Logs do Deploy
Procurar por mensagens:
```
✅ Migração automática concluída!  # Se houve dados para migrar
🚀 Sistema keep-alive iniciado      # Sistema funcionando
🌐 Servidor web iniciado na porta 10000
```

### 2. Testar Bot
```
/ping              # Verificar se responde
/leaderboard       # Ver se dados foram restaurados (se aplicável)
/status_backup     # Verificar sistema de backup (admin)
```

### 3. Verificar Backup Automático
- Aguardar ~10 minutos
- Verificar logs: `✅ Keep-alive ping successful`
- Após 6 horas com dados: backup automático será criado

## Troubleshooting

### Bot não inicia
- ✅ Verificar `DISCORD_TOKEN` está correto
- ✅ Verificar `requirements.txt` tem todas as dependências
- ✅ Ver logs completos no Render

### Keep-alive não funciona  
- ✅ Configurar `RENDER_EXTERNAL_URL` corretamente
- ✅ Verificar se URL está acessível publicamente

### Backup não funciona
- ✅ Verificar se há dados no banco (`/leaderboard`)
- ✅ Usar `/fazer_backup` manual para testar
- ✅ Verificar `/status_backup` para diagnóstico

### Dados perdidos no redeploy
- ✅ Verificar se backup existe no repositório Git
- ✅ Usar `/restaurar_backup` manual se necessário
- ✅ Verificar logs de startup para erros

## Monitoramento

### Comandos Úteis (Admin)
- `/status_backup` - Status completo do sistema
- `/fazer_backup` - Backup manual imediato  
- `/listar_backups` - Ver todos os backups
- `/restaurar_backup` - Restaurar backup específico

### Logs Importantes
```bash
# Sucesso no keep-alive
✅ Keep-alive ping successful - 14:30:25

# Backup automático criado
✅ Backup enviado para Git com sucesso!

# Restore no startup
🔄 Restaurando dados do backup Git...
✅ Dados restaurados do backup Git!
```

## Custos
- **Render Free Tier**: Gratuito
- **Limitações**: 
  - 750 horas/mês (suficiente para uso pessoal)
  - Hibernação após inatividade (resolvido com keep-alive)
  - Sem persistent disk (resolvido com Git backup)

🎉 **Pronto!** Seu bot agora está executando no Render com backup automático funcionando!