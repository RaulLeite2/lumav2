# Database Migrations - Luma Bot

## Visão Geral

As migrations SQL gerenciam o schema do banco de dados. Todos os arquivos `.sql` no diretório `migrations/` são executados automaticamente quando o bot inicia.

## Estrutura

```
migrations/
├── 001_initial_schema.sql      # Schema inicial com tabelas guilds, user_warnings, moderation_logs
├── 007_add_dashboard_setup_fields.sql
├── 008_add_entry_exit_embeds.sql
└── ...
```

## Execução Automática

Al iniciar o bot (`python main.py`), o método `_run_migrations()` executa todos os `.sql` em ordem alfabética:

```python
# O bot conecta ao banco de dados e roda:
[DB] ✅ Migration executed: 001_initial_schema.sql
```

## Executar Migrations Manualmente

Se você quiser rodar as migrations fora do bot:

```bash
python migrate.py
```

> **Nota:** Edite a `DATABASE_URL` em `migrate.py` com suas credenciais antes de executar.

## Tabelas Criadas

### guilds
- `guild_id` (PK): ID único do servidor Discord
- `log_channel_id`: Canal para logs de moderação
- `modmail_category_id`: Categoria usada como base para o ModMail
- `auto_moderation`: Ativar/desativar AutoMod (boolean)
- `quant_warnings`: Número de avisos antes da ação (int)
- `acao`: Ação a executar (kick/ban/mute)

### user_warnings
- `id` (PK): ID único do registro
- `guild_id` (FK): Referência ao servidor
- `user_id`: ID do usuário
- `warning_count`: Número de avisos atuais
- `warned_at`: Data/hora do último aviso

### moderation_logs
- `id` (PK): ID único do log
- `guild_id` (FK): Referência ao servidor
- `moderator_id`: Quem aplicou a ação
- `user_id`: Quem recebeu a ação
- `action`: Tipo de ação (warn/kick/ban/mute)
- `reason`: Motivo da ação
- `created_at`: Data/hora do evento

## Adicionar Novas Migrations

1. Crie um novo arquivo `002_descricao.sql` em `migrations/`
2. Escreva seus comandos SQL (use `IF NOT EXISTS` para segurança)
3. O bot executará automaticamente na próxima inicialização

Exemplo:
```sql
-- migrations/002_add_user_roles.sql
ALTER TABLE guilds ADD COLUMN IF NOT EXISTS mod_role_id BIGINT;
```

## Rollback Manual

Se precisar reverter mudanças, execute SQL diretamente:

```sql
DROP TABLE IF EXISTS user_warnings CASCADE;
DROP TABLE IF EXISTS moderation_logs CASCADE;
ALTER TABLE guilds DROP COLUMN IF EXISTS auto_moderation;
```

## DBeaver / pgAdmin

Para gerenciar o banco via interface gráfica:

1. **Host:** localhost (ou IP)
2. **Port:** 5432 (padrão)
3. **User:** seu user PostgreSQL
4. **Password:** sua senha
5. **Database:** luma_bot

Então execute as `.sql` manualmente se necessário.
