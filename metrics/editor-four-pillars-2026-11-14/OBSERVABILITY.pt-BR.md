# Observabilidade dos quatro pilares — caso Editor

## Resultado e escopo

Foram executados 4 pares reais no Editor fixado: 96 tarefas pontuadas, duas chamadas de agentes por tarefa, mais um controle sem contexto. O gate registra **quatro pilares medidos: `True`**, na definição restrita deste experimento. O gate não comprova superioridade geral do grafo e não substitui revisão humana dos rótulos.

Os agentes Analista e Revisor responderam seis questões relacionais, duas locais, duas sem resposta e duas sobre requisito controlado por braço. Qdrant usou similaridade e seguimento genérico de referências; FalkorDB usou travessia limitada. Ambos receberam os mesmos trechos de fonte, relações, embeddings compartilhados, prompts e orçamento exato de 1.400 tokens de contexto. A ordem dos braços alternou entre os pares.

| Indicador | Vetor | Grafo |
| --- | ---: | ---: |
| Alucinação factual restrita | 0/40 (0.00%) | 2/40 (5.00%) |
| Acurácia de tarefas | 48/48 (100.00%) | 46/48 (95.83%) |
| Acurácia relacional | 24/24 (100.00%) | 22/24 (91.67%) |
| Latência média por braço, s | 33.458 | 17.380 |
| Eficiência de contexto rotulado | 23540/108996 (21.60%) | 23904/63632 (37.57%) |
| Tokens de chat por tarefa correta | 3043.02 | 2093.74 |
| Tokens de chat | 146065 | 96312 |
| Tokens de embedding em execução | 3351 | 0 |
| Abstenções | 8 | 8 |
| Citações completas entre respostas assertivas | 36/40 (90.00%) | 33/40 (82.50%) |
| Custo estimado dos braços, USD | 0.115286 | 0.077949 |

## Resultados por par

| Par | Acertos vetor | Acertos grafo | Erros factuais/assertivas vetor | Erros factuais/assertivas grafo | Tempo vetor, s | Tempo grafo, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 12/12 | 12/12 | 0/10 | 0/10 | 34.458 | 17.578 |
| 2 | 12/12 | 11/12 | 0/10 | 1/10 | 36.742 | 14.563 |
| 3 | 12/12 | 12/12 | 0/10 | 0/10 | 30.222 | 17.311 |
| 4 | 12/12 | 11/12 | 0/10 | 1/10 | 32.411 | 20.068 |

## Controle e erros

O controle sem contexto acertou 2/12, com 12 abstenções e 0 respostas assertivas incompatíveis com o gabarito. As duas questões sem resposta têm `UNKNOWN` como resultado correto; abstenção nas demais conta como erro de tarefa, sem ser transformada em alucinação.

- Par 2, graph, E07: resposta `200`, esperado `409`, evidência necessária recuperada: `True`.
- Par 4, graph, E07: resposta `200`, esperado `409`, evidência necessária recuperada: `True`.

Uma resposta incorreta com evidência necessária presente é uma falha de interpretação ou verificação, não prova de falha de recuperação. Citações completas verificam presença dos IDs necessários; não garantem que a interpretação desses trechos esteja correta.

## Definições para a seção 3

**Alucinação factual restrita:** fração de respostas escalares assertivas incompatíveis com fatos da fonte ou requisito vigente, entre respostas assertivas avaliáveis. É uma operacionalização limitada de erro factual em perguntas com gabarito. Não mede todas as afirmações de prosa ou código gerado. Acurácia e erro factual são relacionados neste formato; as abstenções e os denominadores explicam sua diferença. Respostas fora do formato são registradas separadamente, não classificadas automaticamente como falsas.

**Acurácia:** tarefas corretamente concluídas divididas por todas as tarefas planejadas. A fração relacional usa as seis questões entre módulos de cada execução. Falhas e tarefas não tentadas permanecem no denominador. Os mesmos doze casos foram repetidos; não são novos repositórios independentes.

**Latência:** tempo monotônico do início do braço até seu encerramento, incluindo indexação, recuperação, chamadas, persistência e avaliação determinística local. Preparação compartilhada: 12.272 s, fora dos braços. A diferença observada inclui embeddings e operações distintas dos adaptadores, rede e modelo; não isola velocidade de bancos.

**Eficiência de tokens:** fração de tokens do contexto pertencentes a funções/registros previamente rotulados relevantes. O tokenizer tiktoken 0.12.0, `o200k_base`, conta exatamente o texto enviado, incluindo IDs e separadores; as duas exposições do contexto, ao Analista e ao Revisor, entram no total. O rótulo de utilidade é por registro, não uma anotação semântica de cada token. As duas questões sem resposta são excluídas dessa razão por falta de rótulos positivos defensáveis. Tokens de chat por acerto são um indicador complementar, com embeddings separados.

Preparação estimada: US$ 0.000023. Execuções, incluindo controle: US$ 0.197033. Total estimado deste pacote: **US$ 0.197055**. São tarifas configuradas sobre uso informado pelo provedor; não incluem infraestrutura nem equivalem à fatura.

## Limites e interpretação para o TCC

Esta execução fornece medidas auditáveis dos quatro pilares em um estudo de caso delimitado. Os rótulos foram revisados por assistentes e congelados antes da coleta; não houve anotação humana independente. A atualização de requisito com ID ativo compartilhado mede visibilidade de estado, não estabilidade de memória de longa duração. O corpus é pequeno, os formatos de resposta são escalares, e o baseline vetorial conhece as mesmas referências disponíveis ao grafo.

Quatro repetições do mesmo corpus permitem comparação descritiva, sem estabelecer superioridade geral ou significância estatística. A tese deve relatar o resultado observado mesmo quando houver empate ou vantagem vetorial. Os resultados da migração de backend e do piloto sintético anterior permanecem separados deste pacote.

## Reprodução e evidências

```powershell
docker compose build cli
docker compose up -d qdrant falkordb
docker compose run --rm -v "${PWD}/metrics:/evidence" --entrypoint python cli -m deterministic.study.editor_benchmark /fixtures/project-editor /evidence/editor-four-pillars-repetition --repeat 4 --control
uv run python scripts/report_editor_benchmark.py metrics/editor-four-pillars-repetition
```

Use uma pasta de saída nova. Credenciais vêm do `.env` local e não integram este pacote. [Protocolo completo](../../.docs/editor-four-pillars-protocol.pt-BR.md), [protocolo congelado](protocol.json), [configuração](configuration.json), [resultados](evaluation.json) e [gate](measurement_gate.json). Cada pasta de braço contém contexto, prompts, respostas, tempos e memória. O diretório `implementation` preserva o código utilizado. `SHA256SUMS` verifica os artefatos brutos; textos explicativos são excluídos.
