# Registro de observabilidade: prova de conceito do Project Editor

## Resultado mais recente: quatro pilares medidos

O [estudo mínimo dos quatro pilares](../metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md) executou quatro pares reais, com 12 tarefas por braço e um controle sem contexto. Este é um experimento de perguntas factuais delimitadas sobre fonte real, distinto das migrações e do cenário sintético anteriores. O [gate](../metrics/editor-four-pillars-2026-11-14/measurement_gate.json) registra `four_pillars_measured: true` para as definições do [protocolo congelado](editor-four-pillars-protocol.pt-BR.md).

| Pilar | Vetor com seguimento de referências | Grafo |
| --- | ---: | ---: |
| Alucinação factual restrita: erros / respostas assertivas | 0/40 (0%) | 2/40 (5%) |
| Acurácia: tarefas corretas / planejadas | 48/48 (100%) | 46/48 (95,83%) |
| Acurácia relacional | 24/24 (100%) | 22/24 (91,67%) |
| Latência média por braço | 33,458 s | 17,380 s |
| Eficiência de contexto rotulado | 21,60% | 37,57% |
| Tokens de chat por tarefa correta | 3.043,02 | 2.093,74 |

Houve oito abstenções por braço, todas nas questões sem resposta. O controle sem contexto absteve-se nas 12 questões e acertou apenas as duas cujo gabarito era `UNKNOWN`. O custo estimado completo foi US$ 0,197055, incluindo preparação e controle. Os dois erros do grafo ocorreram na questão de conflito de edição: Analista e Revisor responderam `200` quando a fonte determina `409`, apesar de todos os trechos necessários terem sido recuperados.

**Interpretação:** neste caso, o grafo apresentou menor latência e consumo de tokens, enquanto o vetor apresentou maior acurácia e menor erro factual. Isso documenta uma troca entre desempenho e qualidade, sem comprovar superioridade geral do grafo. A alucinação foi operacionalizada como erro factual de resposta escalar; utilidade de tokens foi rotulada por função/registro e contada com tokenizer exato. Os rótulos foram revisados por assistentes, sem anotação humana independente. Esses limites devem acompanhar os números no TCC. A atualização controlada de requisito verifica visibilidade da versão ativa; não demonstra estabilidade em longa duração. TTFT foi excluído a pedido do autor.

As seções abaixo preservam experimentos anteriores e suas definições; não se devem agregar seus números ao estudo mais recente.

## Nova execução real: 14/11/2026 UTC

O [novo pacote de evidências](../metrics/editor-live-2026-11-14/) contém **um par** de migração Python → TypeScript no Editor fixado. Esta execução é separada dos quatro pares Editor antigos e do piloto sintético descritos abaixo. A nova ingestão produziu 132 entidades e **12 relações `IMPORTS`**; o braço em grafo agora armazenou relações reais. Os dois braços usaram a mesma revisão e configuração. O vetor falhou em duas verificações do contrato (10/12); o grafo passou em 12/12. Ambos esgotaram duas tentativas de correção. Isso demonstra viabilidade operacional com arestas, mas um par não comprova superioridade geral.

| Campo da seção 3.2 do TCC | Vetor (Qdrant) | Grafo (FalkorDB) | Validade nesta execução |
| --- | ---: | ---: | --- |
| **Taxa de alucinação** | Juiz: 0/12 contraditas; calibração falhou em 2 das 6 afirmações confrontadas com testes, além de 1 citação inexata | Juiz: 0/12 contraditas; 6/6 confrontos concordaram | **Não validada.** O juiz chamou de suportados `validation_422` e `unchanged_no_put` no vetor, embora os testes executáveis tenham falhado. A taxa 0% do juiz não deve ser usada como resultado do TCC. Falha comportamental não equivale automaticamente a alucinação. |
| **Acurácia relacional** | 10/12 verificações comportamentais; revocação de caminhos 0,625 | 12/12; revocação de caminhos 0,750 | **Não medida** como acerto de perguntas relacionais de múltiplos saltos em código real. Extração de arestas, revocação e contrato são indicadores diferentes. |
| **Latência de execução** | 44,243 s total; 1,934 s em recuperação | 27,407 s total; 0,084 s em recuperação | **Medida** neste par, incluindo modelo, persistência, validação e correções; preparação compartilhada de 23,941 s é separada. Não isola a velocidade dos bancos. |
| **Eficiência de tokens** | 34.938 entrada + 6.443 saída de chat + 7.503 embedding = **48.884** tokens de provedor em execução | 33.288 + 6.869 + 0 = **40.157** | **Consumo medido; razão de contexto útil/injetado não medida.** Faltam rótulos de relevância por trecho e contagem exata de tokens do contexto. |

Os custos estimados da migração foram US$ 0,05534706 (vetor) e US$ 0,05587650 (grafo). A preparação custou US$ 0,01860039, uma vez, e as duas chamadas adicionais do juiz, US$ 0,01230075 no total. Menos tokens de provedor não implicaram menor custo do grafo, pois as modalidades têm preços diferentes. Os rastros mostram 11/12 relações `IMPORTS` recuperadas pelo grafo e 12/12 pelo vetor em cada contexto; portanto, a aprovação do grafo não pode ser atribuída simplesmente a maior exposição às relações. O [gate de observabilidade](../metrics/editor-live-2026-11-14/observability_gate.json) registra `all_four_tcc_metrics_validated: false`. O resultado relacional sintético anterior continua válido para seu cenário estreito e não preenche automaticamente as lacunas desta migração real.

> **Correção de validade (13/11/2026):** A ingestão arquivada gerou 132 entidades, mas **zero relações entre fontes**. A inspeção dos grafos FalkorDB das execuções arquivadas também encontrou **zero arestas**. Portanto, o braço chamado “grafo” não exercitou travessia de relações. Os quatro pares comprovam a execução do pipeline e a coleta de dados, mas suas diferenças de qualidade, tokens e latência **não sustentam** uma vantagem da memória em grafo para contexto relacional ou de longa duração. Os defeitos de extração e vínculo foram corrigidos depois; o [novo par real](../metrics/editor-live-2026-11-14/) e o [piloto sintético](long-horizon-protocol.md) são relatados separadamente. As métricas e os hashes arquivados não foram alterados.

O [piloto controlado de recuperação de 13/11/2026](../metrics/long-horizon-2026-11-13/) é um experimento distinto: em três pares, o grafo acertou 36/36 respostas e a similaridade vetorial de consulta única acertou 9/36. Em um desafio posterior, consultas ao Qdrant por IDs encontrados no texto empataram com o grafo em 12/12. Ambos os braços recuperaram corretamente o estado do revisor anterior nas 33 etapas avaliáveis. O cenário é sintético e direcionado a relações de dois saltos; não demonstra superioridade geral nem estabilidade de longo prazo. Seus dados não são combinados com os números da migração Editor abaixo.

Este documento apresenta, em português, duas etapas experimentais distintas de 13/11/2026 (UTC): a [migração Editor arquivada](../metrics/editor-2026-11-13/) e o [piloto sintético de memória](../metrics/long-horizon-2026-11-13/). Corresponde ao [registro em inglês da migração](observability.md) e ao [adendo para o TCC](tcc-adendo-evidencias.md). O [texto original do TCC](<TCC - Estruturando Memoria Deterministica em Sistemas Nao-Deterministicos.pdf>) propõe uma investigação mais ampla. Os testes com respostas fixas usados para verificar a infraestrutura não integram as amostras avaliadas.

## Painel comparativo das quatro métricas da seção 3.2 do TCC

Os números desta seção foram recalculados a partir de [`study_evaluation.json` dos três pares predefinidos](../metrics/long-horizon-2026-11-13/scored-one-shot/study_evaluation.json), do [controle sem memória](../metrics/long-horizon-2026-11-13/no-memory/study_evaluation.json) e do [par vetorial reforçado, posterior à análise principal](../metrics/long-horizon-2026-11-13/posthoc-strong-vector/study_evaluation.json). A unidade de repetição são **três pares de execução das mesmas 12 perguntas** (nove relacionais e três locais), e não 36 perguntas independentes. O desafio reforçado tem apenas um par e não entra nas médias dos três pares predefinidos.

| Campo proposto no TCC | Operacionalização disponível | Vetor, consulta única (3 execuções) | Grafo (3 execuções) | Desafio posterior: vetor com seguimento de IDs / grafo (1 par) |
| --- | --- | ---: | ---: | ---: |
| **Taxa de alucinação** | **Não estimável** pela definição do PDF: não houve juiz factual independente. Indicador auxiliar: respostas assertivas erradas e abstenções (`UNKNOWN`). | 0 erradas entre 9 assertivas; 27/36 abstenções | 0 erradas entre 36 assertivas; 0/36 abstenções | 0 erradas entre 12 assertivas em cada braço; 0 abstenções |
| **Acurácia relacional** | Igualdade exata com o gabarito oculto nas nove perguntas de dois saltos por execução. | 0/27 (0%) | 27/27 (100%) | 9/9 (100%) em ambos |
| **Latência de execução** | Média de `end_to_end_ms` por braço, incluindo construção da memória, recuperação e chamadas ao modelo; pré-processamento compartilhado fora do tempo do braço. | 87,141 s | 22,947 s | 92,160 s / 24,241 s |
| **Eficiência de tokens** | Indicador derivado: tokens de **chat** de entrada mais saída por resposta correta; menor é melhor. Embeddings de consulta são mostrados à parte. | 16.086 tokens / 9 acertos = **1.787,3** | 22.010 tokens / 36 acertos = **611,4** | 6.320 / 12 = **526,7**; 7.317 / 12 = **609,8** |

**Alucinação.** Uma resposta `UNKNOWN` é uma abstenção, não uma afirmação falsa. O zero de respostas assertivas erradas **não equivale a taxa de alucinação de 0%**: a cobertura foi 9/36 no vetor de consulta única e 36/36 no grafo. Mesmo uma resposta exata correta poderia ter sido produzida sem suporte recuperado; igualdade com o gabarito não prova fundamentação. A migração Editor também não teve juiz factual; falha em contrato HTTP não deve ser renomeada como alucinação. Para medir a taxa proposta, é necessário um conjunto de afirmações verificáveis, rótulos independentes, rubrica de suporte na fonte e revisão cega dos julgamentos.

**Verificação final de fundamentação (14/11/2026 UTC; par adicional, não agregado aos três pares):** um verificador determinístico examinou a resposta **somente contra o contexto recuperado antes da resposta**, sem consultar o gabarito. Para respostas locais, exigiu a declaração da rota; para respostas relacionais, exigiu rota, duas relações, handler, contrato e token. O [relatório final](../metrics/long-horizon-2026-11-13/final-grounding-pair/study_evaluation.json) registrou:

| Braço | Respostas assertivas | Suportadas pelo contexto | Sem suporte | Abstenções | Taxa operacional sem suporte |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vetor de consulta única | 3/12 | 3 | 0 | 9/12 | 0/3 = 0% |
| Grafo | 12/12 | 12 | 0 | 0/12 | 0/12 = 0% |

O denominador da taxa é o número de respostas assertivas; se ele for zero, a taxa deve ser `null`. O teste confirmou que o verificador detecta uma resposta deliberadamente falsa e uma resposta correta sem a aresta necessária no contexto. **Este par não mostra redução de alucinação pelo grafo**: a taxa operacional empatou, enquanto a cobertura diferiu. A verificação é exata e auditável para IDs opacos; ainda não substitui o juiz factual cego necessário para respostas livres de código ou prosa descrito no TCC. O par adicional usou o mesmo cenário e não é uma nova amostra independente.

**Acurácia relacional.** A vantagem sobre a consulta vetorial única vale para este cenário de IDs opacos, criado para exigir rota → handler → contrato. Os três controles locais passaram nos dois braços em cada execução, e o controle sem memória acertou 0/12. O seguimento explícito de IDs no Qdrant empatou com o grafo no par posterior. A recuperação do estado do revisor anterior também empatou em 33/33 etapas por braço; esses resultados impedem extrapolar a vantagem relacional para toda forma de memória vetorial ou para estabilidade em fluxos longos.

**Latência.** A diferença média descritiva foi de 64,194 s por execução a favor do braço em grafo nos três pares. Ela inclui indexação, embeddings de consulta, operações dos adaptadores e inferência; não isola a velocidade intrínseca de FalkorDB e Qdrant. O par posterior é análise de sensibilidade, sem estimativa de variabilidade. A amostra de três pares não sustenta teste de significância ou generalização de desempenho.

**Tokens.** O grafo consumiu **mais tokens de chat por execução** que o vetor de consulta única (médias de 7.336,7 contra 5.362,0); seu número de tokens de chat por acerto foi menor porque acertou mais respostas. No par posterior, o vetor com seguimento de IDs teve menor consumo de *chat* por acerto que o grafo. A consulta vetorial também gastou **6.111 tokens de embedding em tempo de execução** nos três pares (2.037 por braço), contra zero no grafo; no par posterior, gastou 2.141. Se esses tokens forem somados aos tokens de chat, o consumo operacional por acerto é **2.466,3 contra 611,4** nos três pares e **705,1 contra 609,8** no desafio posterior (vetor / grafo). Tipos de token têm preços diferentes; não se deve converter essa soma diretamente em custo monetário. Os **1.302 tokens de embedding da preparação compartilhada** ficam fora dos dois braços. A razão originalmente proposta no PDF — *tokens de contexto úteis / tokens de contexto injetados* — **não foi medida**: faltam rótulos de utilidade por trecho e contagem pelo tokenizer do contexto isolado. Os limites de 100 palavras aproximadas e 12 registros por passo não substituem essa medida.

O texto pronto para complementar a metodologia da seção 3, com perguntas de pesquisa, controles, fórmulas, plano analítico e ameaças à validade, está em [Metodologia complementar para a seção 3](tcc-secao-3-metodologia.md). As seções numeradas abaixo preservam a descrição da **migração Editor**, cujo grafo arquivado não continha arestas.

## 1. Objeto e procedimento

O repositório de origem foi o submódulo `fixtures/project-editor`, fixado no commit `cd588660d6f30fefbf1ba030e6890f93279dddf1`. A tarefa consistiu em migrar o backend Python para uma API TypeScript. O frontend React/Vite e o serviço de registros original foram preservados para testar contratos e conectividade. A ingestão gerou o projeto `681cbe488a3e94c4`, com 132 entidades e cache inicialmente vazio. O identificador composto de revisão consta em [`ingest/manifest.json`](../metrics/editor-2026-11-13/ingest/manifest.json).

Foram executados **quatro pares**: em cada par, um braço usou memória vetorial em Qdrant e o outro, memória em grafo no FalkorDB. Três pares vieram da primeira execução; um par adicional foi solicitado como teste de baixo custo. Os braços de cada par compartilharam código-fonte, tarefa, modelo, versão do prompt (`a972bca2f26282b2`), gerador, validador, limite de empacotamento de contexto de 4.000 palavras aproximadas, máximo de 6.000 tokens de conclusão e até duas tentativas de correção. A representação da memória **e seu algoritmo de recuperação** variaram. A ordem dos braços está registrada nos manifestos.

Foram usados `gpt-5.4-mini` para geração e resumos e `text-embedding-3-small` para embeddings. A API informou o snapshot `gpt-5.4-mini-2026-03-17` nas migrações. Os manifestos registram Node `v22.23.5`, TypeScript `7.0.2` e Python `3.13.18`.

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 3
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 1
docker compose run --rm cli evaluate --project 681cbe488a3e94c4
```

## 2. Correspondência com o TCC

As seções 3 e 4 do PDF descrevem uma arquitetura conceitual com LangGraph, Cognee, Neo4j, execução assíncrona, reavaliação contínua do conhecimento e vários ciclos de desenvolvimento. Esta implementação usa um fluxo direto em Python de **compreensão → planejamento → construção → validação**, com Qdrant e FalkorDB. Ela persiste tarefas, artefatos e feedback de validação, porém executa uma tarefa de geração de backend com até duas correções. Não há poda contínua do grafo nem experimento de longa duração. A comparação realizada é entre **configurações de memória**, e não entre os motores dos bancos isoladamente.

A seção 3.2 do PDF propõe taxa de alucinação avaliada por juiz, acurácia relacional em consultas de múltiplos saltos e razão entre tokens úteis e tokens injetados. Na **migração Editor arquivada**, essas três grandezas **não foram medidas diretamente**. O piloto sintético posterior mediu acurácia relacional de resposta exata, mas não as outras duas grandezas na definição do PDF. A validação executável da migração fornece evidência de comportamento da API; uma falha de contrato não equivale automaticamente a uma alucinação. As afirmações sobre redução de alucinações e estabilidade semântica permanecem hipóteses para estudos posteriores.

## 3. Definições operacionais

| Indicador | Como foi medido | Limite da interpretação |
| --- | --- | --- |
| Sucesso comportamental | Aprovação em verificações executáveis do contrato da API dentro do limite de correções. Falhas permanecem no denominador. | Um backend e uma direção de migração. |
| Revocação e precisão de evidências | Comparação dos caminhos de módulos recuperados nas etapas `understand_plan` e primeiro `build` com oito caminhos selecionados do Editor; média das duas recuperações. | Indicador de relevância por caminho, não acurácia relacional em múltiplos saltos nem anotação independente. |
| Tokens de entrada e saída | Uso informado pela API nas gerações, inclusive nas correções. | O limite de contexto usa uma estimativa por palavras; não mede a proporção de tokens úteis proposta no PDF. |
| Latência de recuperação e total | Tempo de relógio dos eventos de recuperação e do início ao fim de cada braço. | Inclui métodos diferentes dos adaptadores; não isola a velocidade interna dos bancos. |
| Custo operacional em USD | Tokens informados multiplicados pelas tarifas configuradas quando disponíveis. | Estimativa de provedor, sem fatura, infraestrutura ou pré-processamento não precificado. |

A validação verifica compilação TypeScript, respostas da API diante de um serviço de registros controlado, conexão com o serviço original e configuração de proxy do frontend preservado. A avaliação completa por execução está em [`evaluation.json`](../metrics/editor-2026-11-13/evaluation.json).

## 4. Resultados observados

| Par | Qdrant | FalkorDB | Diferença de tokens de entrada: grafo − vetor | Observação |
| --- | --- | --- | ---: | --- |
| `c74c5d210afb412985e55d26078cc92e` | Falhou, 11/12 verificações | Passou, 12/12 | −21.737 | O braço vetorial falhou no comportamento HTTP `422` após duas correções. |
| `cdab9466f8c84d3bbf248938a499f6d1` | Passou, 12/12 | Passou, 12/12 | −11.131 | Ambos passaram. |
| `5c64e5993d924b3abd06f9fb89fe1f64` | Passou, 12/12 | Passou, 12/12 | −921 | Ambos passaram. |
| `40c5029b0632448ea3a2c428b906a7df` | Passou, 12/12 | Falhou, 3/12 | +8.603 | O braço em grafo falhou em vários comportamentos da API após duas correções; este foi o par precificado. |

Cada configuração passou em **3 de 4 braços (75%)**. Nenhum par foi excluído. As médias aritméticas abaixo incluem falhas e correções; com quatro pares, são apenas descritivas.

| Indicador médio por braço | Qdrant | FalkorDB |
| --- | ---: | ---: |
| Tokens de entrada | 20.222 | 13.925 |
| Tokens de saída | 4.284 | 3.512 |
| Recuperação, ms | 1.732 | 39 |
| Execução total, ms | 29.048 | 19.082 |
| Correções | 1,0 | 0,5 |
| Revocação de evidências | 0,625 | 0,750 |
| Precisão de evidências | 0,556 | 0,750 |

Nesta amostra, o braço em grafo consumiu, em média, cerca de 6.297 tokens de entrada a menos e terminou aproximadamente 10 segundos antes. O quarto par inverteu a direção da diferença de tokens. O número de correções e a variabilidade do código gerado afetam esses totais. A diferença de tempo de recuperação também reflete métodos de consulta distintos, inclusive a geração de embedding para a consulta vetorial; não se pode atribuí-la apenas ao motor do banco.

## 5. Custos e dados ausentes

A ingestão registrou 9.705 tokens de entrada para resumos, 2.548 de saída para resumos e 2.504 de entrada para embeddings. Seu custo em USD permaneceu `null`. As tarifas foram configuradas somente antes do quarto par: US$ 0,75 por milhão de tokens de entrada do GPT-5.4 mini, US$ 4,50 por milhão de saída e US$ 0,02 por milhão de tokens do text-embedding-3-small, conforme as páginas de [preço do modelo de geração](https://developers.openai.com/api/docs/models/gpt-5.4-mini) e [embeddings](https://developers.openai.com/api/docs/models/text-embedding-3-small) consultadas na data da execução.

No quarto par, as **estimativas de custo da execução** foram US$ 0,03570386 para Qdrant e US$ 0,05295075 para FalkorDB, somando **US$ 0,08865461**. Esse par reutilizou o cache de pré-processamento. Os três pares anteriores e o pré-processamento não têm preço registrado. As estimativas usam tarifas padrão e não equivalem à fatura; descontos de cache e hospedagem dos bancos estão fora do cálculo. O custo global por sucesso no relatório é `null`, e não há base para uma conclusão geral de custo.

## 6. Conclusão restrita e preservação

A prova de conceito mostra que o pipeline consegue ingerir o backend fixado, executar pares reais, preservar falhas e emitir telemetria comparável. O sucesso comportamental foi igual nas duas configurações. Quatro pares de um repositório e de uma direção não demonstram superioridade geral, degradação de contexto em longa duração, raciocínio relacional de múltiplos saltos ou redução de alucinações.

O arquivo de evidências inclui `evaluation.json`, manifesto e eventos da ingestão, além de manifesto, `metrics.jsonl`, validação, rastros de contexto, evidências recuperadas, respostas do modelo e `server.ts` final de cada braço. [`SHA256SUMS`](../metrics/editor-2026-11-13/SHA256SUMS) verifica os 59 arquivos brutos. `.env`, credenciais, catálogo DuckDB, volumes dos serviços e índices completos não foram arquivados. Uma repetição exige o submódulo fixado e acesso ao modelo e pode gerar código diferente. O código arquivado é evidência experimental, não uma migração pronta para produção.
