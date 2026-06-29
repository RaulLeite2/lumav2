# Runbook Operacional - Luma

## 1) Queda de banco de dados
Sintomas:
- /ready retorna 503
- Erros de conexao asyncpg no log

Passos:
1. Verificar variaveis DATABASE_URL ou DB_HOST/DB_PORT/DB_USER/DB_NAME.
2. Verificar disponibilidade do Postgres no provedor.
3. Reiniciar a instancia do bot apos restaurar o banco.
4. Validar /health e /ready.

Mitigacao:
- Escalar verticalmente o banco se houver saturacao.
- Revisar limites de conexao do pool.

## 2) Oscilacao de API externa (ex.: IA)
Sintomas:
- Comandos de IA retornam erro temporario.
- Alertas por DM com contexto ai_network_error/ai_runtime_error.

Passos:
1. Confirmar status do provedor externo.
2. Reduzir uso de comandos de IA temporariamente.
3. Validar chave e limite de rate da API.
4. Reprocessar apos normalizacao.

Mitigacao:
- Manter cache ativo para respostas recorrentes.
- Definir fallback quando API externa indisponivel.

## 3) Rate limit do Discord
Sintomas:
- Falhas intermitentes de envio de mensagens.
- Erros HTTP 429 no log.

Passos:
1. Verificar picos de comandos e tarefas periodicas.
2. Reduzir bursts de envio e lotes agressivos.
3. Confirmar que respostas longas estao em chunks.

Mitigacao:
- Introduzir filas com backoff exponencial para envios.
- Diminuir frequencia de jobs intensivos.

## 4) Erros inesperados em runtime
Sintomas:
- DM de alerta com traceback para o owner.

Passos:
1. Abrir traceback recebido por DM.
2. Identificar modulo, comando, guild e usuario no contexto.
3. Reproduzir em ambiente de teste.
4. Corrigir, validar e publicar hotfix.

## 5) Deploy e rollback
Estrategia:
- Sempre publicar versao tagueada.
- Manter changelog resumido por release.

Rollback rapido:
1. Selecionar release anterior estavel no provedor.
2. Fazer redeploy dessa release.
3. Validar /health e /ready.
4. Comunicar incidente e causa raiz.

## 6) Checklist pos-deploy
1. /health retorna 200 com status ok.
2. /ready retorna 200 com status ready.
3. Slash commands respondem normalmente.
4. Sem erros criticos nos primeiros 10 minutos.

## 7) Validacao rapida de diagnostico
1. Executar comando /admin health e confirmar DB Ready, Migrations Ready e Discord Ready = True.
2. Executar comando /admin test-alert com a conta owner.
3. Confirmar recebimento de DM com contexto e traceback.

## 8) Validacao por HTTP (Railway)
1. Abrir URL publica do servico e consultar /health.
2. Consultar /ready e confirmar status 200 apos startup completo.
3. Em caso de 503 persistente no /ready:
	- Verificar conexao com banco.
	- Verificar migrations.
	- Verificar autenticacao no gateway Discord.
