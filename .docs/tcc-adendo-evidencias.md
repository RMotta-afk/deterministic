# Adendo ao TCC: delimitação experimental e resultados observáveis

## Texto sugerido para os resultados finais do estudo de caso

> No estudo adicional com quatro pares de execução sobre perguntas factuais do Project Editor, as quatro dimensões foram mensuradas por um protocolo delimitado e reproduzível. O vetor com seguimento de referências acertou 48 de 48 tarefas e não apresentou erro entre 40 respostas assertivas. O grafo acertou 46 de 48 tarefas e apresentou dois erros entre 40 respostas assertivas. Em contrapartida, o grafo apresentou menor latência média por braço (17,380 s contra 33,458 s), maior proporção de contexto rotulado como relevante (37,57% contra 21,60%) e menor consumo de tokens de chat por tarefa correta (2.093,74 contra 3.043,02). Os erros do grafo ocorreram mesmo com a evidência necessária recuperada, indicando falha de interpretação ou verificação nesse caso.

> Os resultados sustentam uma comparação empírica entre eficiência e qualidade, sem estabelecer superioridade geral de uma representação de memória. A taxa de alucinação foi operacionalizada como erro factual em respostas escalares, e a utilidade do contexto foi rotulada por função ou registro. O pequeno corpus, as repetições das mesmas perguntas, a ausência de anotação humana independente e a curta sequência limitam a generalização. A hipótese de maior estabilidade de grafos em fluxos extensos de múltiplos agentes permanece aberta, enquanto a coleta confirma a viabilidade de medir os quatro pilares de forma rastreável no escopo definido.

Fonte: [relatório PT-BR e pacote de evidências](../metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md), [protocolo](editor-four-pillars-protocol.pt-BR.md) e [gate de medição](../metrics/editor-four-pillars-2026-11-14/measurement_gate.json). Os parágrafos históricos abaixo tratam de experimentos anteriores.

**Atualização de 14/11/2026 UTC:** o [novo par real do Editor](../metrics/editor-live-2026-11-14/) foi executado após a correção do parser, com 12 relações de importação no snapshot. A migração em grafo passou 12/12 verificações comportamentais e a vetorial, 10/12. Foram medidos tempo total (27,407 s / 44,243 s, grafo / vetor) e consumo de tokens de provedor em execução (40.157 / 48.884). O juiz cego de afirmações deu 0/12 contradições nos dois braços, mas sua calibração falhou no vetor com dois falsos suportes; por isso **não há taxa válida de alucinação para este par**. Acurácia relacional em perguntas reais de múltiplos saltos e proporção de contexto útil por token continuam sem medição. O [gate estruturado](../metrics/editor-live-2026-11-14/observability_gate.json) registra essa incompletude. O par novo deve ser citado separadamente dos quatro pares históricos abaixo e do piloto sintético.

> **Errata metodológica (13/11/2026):** O experimento Editor arquivado produziu zero relações de código e seus grafos FalkorDB tinham zero arestas. As comparações numéricas abaixo descrevem braços executados, mas **não testam a hipótese central de vantagem relacional do grafo**. A interpretação válida é viabilidade do pipeline com observabilidade. A correção de parser e vínculos e o novo [protocolo de estudo](long-horizon-protocol.md) são posteriores ao arquivo; seus resultados não devem ser misturados com os quatro pares originais.

**Adendo posterior para a discussão:** no [piloto sintético de relações de dois saltos](../metrics/long-horizon-2026-11-13/), o grafo acertou 36/36 respostas e a busca vetorial de consulta única acertou 9/36 em três pares. Uma estratégia vetorial posterior que seguiu IDs explícitos no texto empatou com o grafo em 12/12; ambos recuperaram o estado do revisor anterior em 33/33 etapas. O grafo consumiu mais tokens de entrada do modelo e teve maior custo estimado que o braço vetorial de consulta única. Assim, o resultado sustenta somente a vantagem do **método de travessia explícita sobre similaridade de consulta única neste cenário construído**. A hipótese geral do TCC continua aberta até replicação em relações verificadas de repositórios reais e tarefas dependentes mais difíceis. O desafio vetorial posterior deve ser identificado como análise de sensibilidade, nunca agregado aos pares predefinidos.

A [proposta revisada para toda a seção 3](tcc-secao-3-metodologia.md) incorpora os quatro indicadores do TCC, os dados do piloto, os controles e as ameaças à validade. O [painel quantitativo em português](observability.pt-BR.md) contém os cálculos diretamente extraídos dos relatórios.

Este adendo foi preparado para apoiar a revisão de [*Estruturando Memória Determinística em Sistemas Não-Determinísticos*](<TCC - Estruturando Memoria Deterministica em Sistemas Nao-Deterministicos.pdf>). As seções históricas abaixo se apoiam na execução arquivada em [`metrics/editor-2026-11-13/`](../metrics/editor-2026-11-13/) e nas definições do [registro de observabilidade em português](observability.pt-BR.md); o piloto sintético posterior é apresentado separadamente no início deste documento. **Não substitui o PDF nem afirma que as hipóteses gerais do trabalho foram comprovadas.** Os números são observações de provas de conceito, não estimativas populacionais. Trechos sugeridos abaixo que atribuem vantagem ao grafo com base nos pares Editor devem ser reescritos à luz da errata, antes de entrar na versão final do TCC.

## 1. Ajustes necessários no texto-base

| Ponto do PDF | Situação após a prova de conceito | Ajuste recomendado |
| --- | --- | --- |
| Resumo, p. 1: resultados esperados e conclusão favorável ao grafo | O sucesso comportamental observado foi 3/4 em cada configuração. | Apresentar a superioridade do grafo como hipótese; substituir a conclusão categórica por resultados preliminares e limites. |
| Introdução, pp. 2–3: degradação de contexto, alucinação e longa duração | O experimento teve uma tarefa de backend e até duas correções, sem acompanhamento de uma sequência longa. | Restringir a conclusão à viabilidade do pipeline; reservar as hipóteses de longa duração para estudo posterior. |
| Metodologia 3.1, p. 5: LangGraph, Cognee e Neo4j | O POC usa fluxo Python direto, FalkorDB e Qdrant. | Descrever a pilha realmente executada e distinguir a arquitetura inicialmente proposta da implementação. |
| Métricas 3.2, p. 5: alucinação por juiz, acurácia multi-salto, razão de tokens úteis | Foram coletados testes de contrato, relevância por caminho, tokens de provedor, correções e latências. | Registrar as métricas propostas como ainda não medidas; não renomear os indicadores coletados como se fossem equivalentes. |
| Desenvolvimento 4 e 4.4, p. 6: projeto sem código e vários ciclos iterativos | Agora existe uma implementação executável, porém para uma tarefa de migração. | Atualizar o capítulo com o experimento; não afirmar avaliação de longa iteração ou reavaliação contínua. |
| Conclusão 5, pp. 6–7: robustez e escalabilidade demonstradas | A amostra tem quatro pares do mesmo repositório e direção. | Tratar robustez, escalabilidade e vantagem geral como trabalho futuro. |

Há ainda uma inconsistência editorial: a introdução promete implementar e avaliar a arquitetura, enquanto o capítulo 4 afirma abster-se de implementação. A revisão deve escolher o escopo atual e datar a transição do projeto conceitual para a prova de conceito. Afirmações gerais do referencial, como um limiar universal de degradação da janela de contexto, exigem fontes verificáveis e condições experimentais explícitas. A lista de referências também deve ser conferida quanto à pertinência e aos dados bibliográficos completos.

## 2. Texto histórico para a metodologia (substituído)

Os parágrafos 3.3 e 3.4 abaixo documentam a proposta anterior, restrita à migração Editor. **Não devem ser inseridos na versão final do TCC sem revisão**, pois foram escritos antes da constatação de que os grafos arquivados não tinham arestas. Use a [seção 3 revisada](tcc-secao-3-metodologia.md) como texto principal.

### 3.3. Delimitação da etapa experimental

> A etapa experimental implementou uma prova de conceito de migração de backend Python para TypeScript. Foi utilizado o repositório Project Editor, fixado no commit `cd588660d6f30fefbf1ba030e6890f93279dddf1`, com frontend e serviço de registros preservados como fronteiras de contrato. A ingestão produziu 132 entidades e um cache de evidências reutilizado nos testes; cada braço construiu sua própria memória. A unidade de comparação foi o par de execuções sobre a mesma tarefa: um braço consultou memória vetorial em Qdrant e o outro consultou memória em grafo no FalkorDB. Foram realizados quatro pares, totalizando oito braços. As configurações compartilharam origem, modelo, versão do prompt, gerador, validador, limite de empacotamento de contexto e limite de correções. Variaram a representação da memória e o método de recuperação do adaptador. O estudo compara essas configurações, não o desempenho intrínseco dos bancos isoladamente.

### 3.4. Instrumentação e critérios de avaliação

> Cada execução registrou manifesto versionado, eventos de telemetria, contexto recuperado, uso de tokens informado pelo provedor, tentativas de correção e resultado de validação. O sucesso comportamental corresponde à aprovação no conjunto predefinido de verificações executáveis do contrato da API, dentro de até duas correções. Todas as falhas permaneceram no denominador. A relevância das evidências foi estimada por revocação e precisão dos caminhos de módulos recuperados em duas etapas, comparados a oito caminhos selecionados do repositório. As latências foram medidas em tempo de relógio. Os custos em USD foram calculados apenas quando as tarifas estavam configuradas no momento da execução. Esse procedimento não mediu diretamente alucinação factual, acurácia em raciocínio de múltiplos saltos, utilidade ponderada por token ou degradação em longa duração.

O identificador do projeto foi `681cbe488a3e94c4`. A versão do prompt (`a972bca2f26282b2`), o modelo (`gpt-5.4-mini`), o snapshot retornado pela API, os limites e as versões de ferramentas constam nos [manifestos de cada braço](../metrics/editor-2026-11-13/arms/). O [relatório JSON](../metrics/editor-2026-11-13/evaluation.json) preserva falhas, deltas por par e dados ausentes. A execução usa código-fonte aberto do submódulo fixado; não arquiva credenciais nem os volumes vivos dos serviços.

## 3. Texto sugerido para os resultados

### 4.5. Resultados preliminares da prova de conceito

> As duas configurações passaram em três dos quatro braços, isto é, 75% de sucesso comportamental observado para cada uma. No primeiro par, o braço vetorial falhou em uma verificação HTTP `422`, enquanto o braço em grafo passou. No quarto par ocorreu o inverso: o braço em grafo falhou em diversas verificações de comportamento da API, enquanto o vetorial passou. Os dois pares restantes passaram em ambas as configurações. Não houve exclusão de pares. Portanto, esta amostra não mostra vantagem de qualidade comportamental para nenhum dos dois braços.

| Resultado descritivo por braço, n = 4 por configuração | Qdrant | FalkorDB |
| --- | ---: | ---: |
| Sucessos comportamentais | 3/4 | 3/4 |
| Média de tokens de entrada | 20.222 | 13.925 |
| Média de tokens de saída | 4.284 | 3.512 |
| Média de tempo de recuperação | 1.732 ms | 39 ms |
| Média de tempo total | 29.048 ms | 19.082 ms |
| Média de correções | 1,0 | 0,5 |
| Média de revocação de evidências | 0,625 | 0,750 |
| Média de precisão de evidências | 0,556 | 0,750 |

> O braço em grafo apresentou média de 6.297 tokens de entrada a menos e aproximadamente 10 segundos a menos no tempo total. As médias incluem execuções com falha e correções, e três dos quatro pares favoreceram o grafo em tokens de entrada; no quarto, ele consumiu 8.603 tokens a mais. A diferença de recuperação também incorpora os algoritmos distintos dos adaptadores. Assim, os números descrevem esta implementação e não isolam um efeito causal do motor de banco de dados. Quatro pares não permitem inferência estatística robusta sobre desempenho geral.

### 4.6. Custos observáveis e dados faltantes

> A ingestão registrou 9.705 tokens de entrada e 2.548 de saída para resumos, além de 2.504 tokens para embeddings, mas não registrou custo em USD. As tarifas somente estavam configuradas no quarto par, que reutilizou o cache da ingestão. Nesse par, a estimativa de custo da execução foi US$ 0,03570386 para o braço vetorial e US$ 0,05295075 para o braço em grafo, totalizando US$ 0,08865461. São estimativas baseadas nos tokens informados pela API e nas tarifas configuradas, sem custo de hospedagem, descontos do provedor ou preço do pré-processamento inicial. Os três pares anteriores têm custo `null`; por isso não se calculou custo comparativo global por sucesso.

As tarifas configuradas nessa execução foram US$ 0,75 por milhão de tokens de entrada e US$ 4,50 por milhão de tokens de saída do [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), e US$ 0,02 por milhão de tokens do [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small), conforme as páginas de preços consultadas em 13/11/2026. O arquivo bruto mantém os valores `null` em vez de preencher custos retrospectivos não medidos.

## 4. Texto sugerido para a discussão e conclusão

> O experimento confirma a viabilidade operacional de ingerir um backend real, recuperar contexto por duas configurações de memória, gerar uma implementação alternativa, testá-la e preservar telemetria por execução. A igualdade na taxa de sucesso observada e a variabilidade entre pares impedem afirmar que a memória em grafo reduza falhas de migração neste caso. As diferenças descritivas de tokens, relevância por caminho e latência motivam estudos adicionais, mas não demonstram menor alucinação, raciocínio relacional superior ou estabilidade semântica em fluxos longos. A implementação testada utiliza FalkorDB e Qdrant em um fluxo Python direto; ela constitui uma etapa experimental mais restrita que a arquitetura conceitual com LangGraph, Cognee e Neo4j descrita inicialmente.

Uma formulação apropriada para o resumo seria: **“Nesta prova de conceito, ambas as configurações passaram em três de quatro execuções. A configuração em grafo apresentou menores médias descritivas de tokens e tempo, com inversão em um dos pares; a amostra não permite concluir superioridade geral. O trabalho estabelece a instrumentação e o protocolo para avaliações posteriores.”**

## 5. Evidência necessária para testar a hipótese central

1. **Longa duração:** executar sequências de tarefas dependentes, com medição por etapa e análise de crescimento de contexto, deriva de contratos e falhas ao longo da sequência.
2. **Raciocínio relacional:** construir perguntas multi-salto com gabarito independente e medir acerto da resposta, não apenas presença de caminhos recuperados.
3. **Alucinação factual:** definir rubrica e conjunto de referência, avaliação cega e procedimento de concordância; manter separadas falhas de contrato e inconsistências factuais.
4. **Eficiência de contexto:** rotular trechos relevantes e calcular a fração de tokens úteis efetivamente injetados, além dos tokens totais de entrada.
5. **Generalização e custo:** repetir em mais de um projeto e na direção TypeScript → Python, registrar preços antes de todas as execuções, separar pré-processamento, inferência, embeddings e infraestrutura, e controlar ordem e variabilidade do modelo.

Até que essas etapas sejam executadas, o TCC pode apresentar esta prova como **resultado preliminar de viabilidade com evidências rastreáveis**, mantendo as afirmações mais amplas no campo das hipóteses e do trabalho futuro.
