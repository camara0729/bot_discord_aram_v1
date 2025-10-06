# Sistema de Backup Git para Render Free Tier

## Problema Resolvido

O Render Free Tier não possui armazenamento persistente em disco, fazendo com que o banco de dados SQLite seja perdido a cada deploy. Este sistema resolve isso automaticamente usando o Git como mecanismo de backup/restore.

## Como Funciona

### 1. Backup Automático
- **Frequência**: A cada 6 horas (configurável via `BACKUP_FREQUENCY_HOURS`)
- **Trigger**: Executado junto com o keep-alive ping (a cada 10 minutos, mas só faz backup quando necessário)
- **Processo**:
  1. Verifica se há dados novos no banco
  2. Cria backup em JSON (`auto_backup_render.json`)
  3. Faz commit e push automático para o Git
  4. Registra timestamp do último backup

### 2. Restore Automático
- **Trigger**: No startup do bot
- **Processo**:
  1. Verifica se o banco está vazio
  2. Procura por arquivos de backup disponíveis
  3. Restaura automaticamente os dados
  4. Preserva histórico de jogadores e ranking

### 3. Comandos Manuais de Administração

#### `/fazer_backup`
- Cria backup manual imediato
- Envia automaticamente para Git
- Útil antes de alterações importantes

#### `/restaurar_backup arquivo:nome.json`
- Restaura dados de backup específico
- Pede confirmação se há dados existentes
- Seguro contra perda acidental

#### `/confirmar_restore arquivo:nome.json`
- Confirma restauração (substitui todos os dados)
- Usado após `/restaurar_backup` quando há dados existentes

#### `/status_backup`
- Mostra status completo do sistema
- Lista arquivos de backup disponíveis
- Informações do último backup automático
- Status do repositório Git

#### `/listar_backups`
- Lista todos os arquivos de backup
- Mostra tamanhos, datas e número de jogadores
- Ordenados por data (mais recentes primeiro)

## Configuração no Render

### 1. Variáveis de Ambiente
```bash
DISCORD_TOKEN=seu_token_discord
RIOT_API_KEY=sua_chave_riot_api
RENDER_EXTERNAL_URL=https://seu-app.onrender.com
BACKUP_FREQUENCY_HOURS=6
```

### 2. Deploy Command
No Render, usar como build command:
```bash
pip install -r requirements.txt
```

E como start command:
```bash
python main.py
```

### 3. Git Configuration
O sistema configura automaticamente:
- `user.email`: "render-bot@noreply.com" (automático) ou "admin-bot@noreply.com" (manual)  
- `user.name`: "Render Auto Backup" (automático) ou "Admin Manual Backup" (manual)

## Arquivos de Backup

### Tipos de Arquivo
- `auto_backup_render.json`: Backups automáticos
- `manual_backup_YYYYMMDD_HHMMSS.json`: Backups manuais
- `render_migration_backup.json`: Backup de migração inicial (legado)

### Estrutura do Backup
```json
{
  "backup_date": "2024-01-01T12:00:00",
  "version": "1.0",
  "total_players": 25,
  "total_matches": 150,
  "data": {
    "players": [...],
    "matches": [...],
    "match_participants": [...]
  }
}
```

## Fluxo de Deploy

1. **Novo Deploy**:
   - Sistema inicia → `restore_from_git_backup()`
   - Verifica se banco está vazio
   - Se vazio, procura backup mais recente
   - Restaura dados automaticamente

2. **Durante Execução**:
   - Keep-alive a cada 10 minutos
   - Backup automático a cada 6 horas (se houver dados novos)
   - Commit e push automático para Git

3. **Administração**:
   - Admins podem fazer backup manual
   - Possibilidade de restaurar backups específicos
   - Monitoramento via `/status_backup`

## Vantagens

✅ **Zero configuração**: Funciona automaticamente no primeiro deploy  
✅ **Persistência garantida**: Dados nunca são perdidos  
✅ **Backup incremental**: Só faz backup quando há dados novos  
✅ **Controle manual**: Comandos admin para situações especiais  
✅ **Monitoramento**: Status completo do sistema  
✅ **Segurança**: Confirmações antes de substituir dados  
✅ **Histórico**: Múltiplos backups preservados  

## Solução de Problemas

### Backup não está funcionando
1. Verificar `/status_backup`
2. Confirmar variáveis de ambiente
3. Verificar logs do Render

### Dados não foram restaurados no deploy
1. Verificar se existe arquivo de backup no repositório
2. Executar `/listar_backups` para ver arquivos
3. Usar `/restaurar_backup` manualmente se necessário

### Git push falha
- Backups locais ainda são criados
- Sistema continua funcionando
- Verificar permissões do repositório no Render

## Importante

⚠️ **Render Free Tier**: Este sistema é especificamente para o free tier sem persistent disk  
⚠️ **Git como Storage**: O repositório Git funciona como storage de backup  
⚠️ **Automatic**: Funciona sem intervenção manual, mas comandos admin estão disponíveis  
⚠️ **Safe**: Sempre pede confirmação antes de substituir dados existentes  