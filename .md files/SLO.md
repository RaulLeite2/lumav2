# Luma SLO Basico

## Objetivo
Definir metas minimas de confiabilidade para operacao do bot em producao.

## Indicadores (SLI)
- Disponibilidade do bot: percentual de tempo com conexao ativa ao gateway do Discord e comandos respondendo.
- Latencia de comando slash: tempo entre recebimento do comando e primeira resposta/defer.
- Taxa de erro de comandos: percentual de comandos que resultam em falha.

## Metas (SLO)
- Disponibilidade mensal: >= 99.5%
- P95 de primeira resposta de comando: <= 3 segundos
- Taxa de erro mensal em comandos: <= 1.0%

## Orcamento de erro
- Orcamento mensal de indisponibilidade em 99.5%: ~3h39min
- Se consumo > 50% do orcamento antes da metade do mes:
  - Congelar features nao criticas.
  - Priorizar estabilizacao e correcoes.

## Alertas recomendados
- Alerta critico: endpoint /ready retornando 503 por mais de 2 minutos.
- Alerta alto: taxa de erro de comandos > 3% por 10 minutos.
- Alerta medio: p95 de latencia > 5 segundos por 15 minutos.

## Revisao
- Revisao semanal dos indicadores.
- Revisao mensal das metas e ajustes de capacidade.
