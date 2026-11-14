# Protocolo mínimo dos quatro pilares — Editor

Protocolo definido antes da nova execução pontuada. Esta etapa mede uma tarefa delimitada de perguntas factuais sobre o Editor e requisitos controlados de pesquisa. Não mede alucinação em prosa livre, qualidade de migração completa ou estabilidade geral em fluxos longos. TTFT foi excluído a pedido do autor.

## Corpus e procedimento

- Fonte: submódulo Editor, commit `cd588660d6f30fefbf1ba030e6890f93279dddf1`. Funções de `main.py`, `merge.py` e `upstream.py`, com hashes também de `contracts.py`. O arquivo `protocol.json` preserva trechos exatos, linhas, perguntas, gabarito e relevância. O gabarito não entra nos prompts dos agentes.
- Relações: pequeno manifesto de dependências revisadas no código, compartilhado pelos dois braços. Não é extração por Cognee. Os rótulos foram revisados por assistentes; não houve anotação humana independente.
- Doze tarefas por braço: seis relacionais entre módulos, duas locais, duas sem resposta no corpus e duas de visibilidade de requisito atualizado. O requisito controlado de timeout começa em 6 segundos, muda para 9 antes da nona tarefa e preserva a versão antiga. Isso é uma intervenção de pesquisa, não uma alteração no Editor original. A ancoragem da versão ativa facilita a tarefa; não comprova memória de longa duração.
- Quatro pares, com ordem vetor/grafo alternada, mais uma execução diagnóstica sem contexto. As repetições usam as mesmas perguntas e não são observações independentes de repositórios diferentes.
- Analista responde; Revisor recebe a mesma evidência e deve verificar ou corrigir o candidato. O gabarito só é usado pelo avaliador externo. Respostas revisadas acumulam na memória, mas não são promovidas a fatos de referência.
- Qdrant: similaridade mais seguimento genérico de referências por busca exata de IDs, até dois saltos. FalkorDB: travessia até dois saltos. Mesmos registros, embeddings compartilhados, IDs de entrada, prompts e empacotador final. A comparação inclui representação e estratégia de recuperação.
- Contexto máximo: 1.400 tokens de `o200k_base`, tiktoken 0.12.0, aplicado ao texto serializado com IDs e separadores. Saída máxima de cada chamada: 220 tokens. Duas chamadas por tarefa, sem reparos automáticos; até 216 chamadas de chat no desenho completo.

## Definições e denominadores

| Pilar | Definição operacional |
| --- | --- |
| Taxa de alucinação factual restrita | Respostas escalares assertivas incompatíveis com o gabarito da fonte/estado vigente, divididas pelas respostas assertivas avaliáveis. `UNKNOWN` é abstenção; reportar cobertura, abstenções e respostas não avaliáveis. Não equivale à avaliação de todas as afirmações de uma resposta livre. |
| Acurácia | Tarefas concluídas corretamente / 12 tarefas planejadas. Falhas e tarefas não tentadas permanecem no denominador. Informar também acurácia nas seis questões relacionais. |
| Latência de execução | Tempo monotônico do início de cada braço até o resultado final, incluindo indexação, recuperação, chamadas, persistência e avaliação determinística local. Preparação compartilhada fora dos braços; tempo por tarefa e indexação são registrados separadamente. |
| Eficiência de contexto | Tokens em registros previamente rotulados como relevantes / tokens do contexto injetado nas tarefas com rótulos. Contagem exata do tokenizer; utilidade anotada no nível de função/registro, e não por avaliação semântica de cada token. O numerador pode incluir tokens não essenciais dentro de uma função relevante. |
| Eficiência operacional complementar | Tokens de chat / tarefas corretamente concluídas; embeddings e USD apresentados separadamente. Denominador zero gera `null`. |

Cada contexto é enviado ao Analista e ao Revisor. Os totais de contexto agregados contam cada chamada registrada. O cálculo de relevância exclui as duas questões sem resposta, para as quais não há rótulos defensáveis de evidência positiva. Um token é relevante se seus bytes intersectam um registro rotulado como relevante; IDs e separadores desse registro seguem o mesmo rótulo.

Respostas são escalares curtas. Normalização predefinida: caixa, espaços e aspas externas; prefixo `HTTP`, sufixo de segundos/vezes/percentual para números. Texto fora do formato atômico é não avaliável para alucinação e não é transformado automaticamente em uma afirmação falsa. Citações e cobertura da evidência são indicadores separados: uma resposta correta por palpite continua correta, mas não demonstra fundamentação.

## Controles e critérios de entrega

Testes prévios verificam resposta falsa, resposta correta sem suporte recuperado, abstenção, tokenização exata, falha após uma chamada paga e falha durante indexação. O controle sem contexto revela acertos por conhecimento prévio ou palpite. O problema de comportamento sem alteração (`no-op`) foi excluído por divergência verificada entre código e contrato do Editor.

Preservar todos os braços e chamadas, inclusive falhas, custo parcial observado e uso desconhecido como `null`. O gate valida disponibilidade das quatro medidas nesta definição operacional; ele não atesta superioridade do grafo ou validação humana dos rótulos. Comparações são descritivas por par. Empate e vantagem vetorial são resultados válidos.

Arquivar protocolo, configuração sem credenciais, snapshot comum, prompts/respostas completos, contextos, tempos, uso de tokens, saídas do avaliador, código executado e hashes. Os resultados anteriores continuam separados. Os quatro pilares ficam operacionalizados neste estudo delimitado; alegações sobre prosa livre, muitos agentes, diferentes repositórios e longa duração exigem estudos adicionais.
