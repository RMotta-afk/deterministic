# deterministic

[Português (Brasil)](#portugues-brasil) | [English](#english)

<a id="portugues-brasil"></a>
## Português (Brasil)

Este repositório reúne a implementação e as evidências experimentais de um Trabalho de Conclusão de Curso (TCC) sobre memória para sistemas multiagentes. O objetivo é investigar como a memória em grafos se compara à memória vetorial na recuperação de contexto e de relações em tarefas de programação, considerando alucinação, acurácia, latência de execução e eficiência de tokens.

O [estudo mais recente dos quatro pilares](metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md), realizado com chamadas reais ao modelo, mediu alucinação factual restrita, acurácia de tarefas, latência de execução e eficiência de tokens de contexto rotulado em quatro pares de execuções do Editor e um controle sem memória. A abordagem vetorial acertou 48/48 tarefas; a abordagem em grafo acertou 46/48, utilizando menos tempo e menos tokens. Os [critérios de medição foram atendidos](metrics/editor-four-pillars-2026-11-14/measurement_gate.json) para esse protocolo restrito; o resultado não estabelece superioridade geral dos grafos. Consulte o [protocolo](.docs/editor-four-pillars-protocol.pt-BR.md) e o relatório arquivado para os comandos de reprodução e as limitações da pesquisa.

Esta prova de conceito compara a memória vetorial no Qdrant com a memória em grafo no FalkorDB durante a migração do backend Python, fixado em uma revisão específica em `fixtures/project-editor`, para uma API executável em TypeScript. O frontend React/Vite e o serviço original de registros permanecem inalterados. O documento-base é [.docs/base.md](.docs/base.md); as tarefas ordenadas estão em [.context/decomposition.json](.context/decomposition.json). O `project-intaker` está reservado para uma replicação futura.

### Executar a prova de conceito do Editor

1. Inicie o Docker Desktop, inicialize o submódulo na revisão fixada e copie [.env.example](.env.example) para `.env`. Configure um endpoint acessível, compatível com a API da OpenAI para chat e embeddings, os identificadores dos modelos e uma chave. O endpoint deve retornar texto e uso de tokens para chat, além de vetores e uso de tokens para embeddings. Mantenha as mesmas configurações na ingestão e na migração.

2. Construa a imagem e inicie os serviços:

```sh
git submodule update --init --recursive
docker compose build cli
docker compose up -d qdrant falkordb
```

3. Execute a ingestão do caso fixado. Essa etapa grava o snapshot do código-fonte, os resumos em linguagem natural e embeddings em cache, além de registrar o projeto como pronto no DuckDB:

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
```

Para baixar e ingerir o projeto em um único comando da CLI, substitua o caminho local por `https://github.com/RMotta-afk/project-editor`; o perfil de escopo fixa e verifica o commit e o conteúdo. O comando local acima utiliza o submódulo já inicializado e evita outro download.

4. Copie o valor `Ready: <project-id>` exibido pela ingestão. Execute novas tentativas pareadas e avalie todos os resultados:

```sh
docker compose run --rm cli migrate --project <project-id> --target typescript --memory both --repeat 3
docker compose run --rm cli evaluate --project <project-id>
```

O resultado fica em `/data/runs/evaluation/evaluation.json`, no volume persistente `runs`. Cada execução possui manifesto, rastros de contexto, métricas em JSONL, resultado da validação, respostas do modelo e código gerado. Uma condição experimental que falha permanece no relatório e no denominador da taxa de sucesso. O arquivo gerado `server.ts` é compilado e testado com um serviço controlado para casos de borda e, depois, com o serviço de registros preservado do Editor para verificar a conectividade real de GET/PUT. A validação também verifica o destino do proxy `/api` do frontend preservado.

O primeiro estudo real do Editor e suas evidências estão em [.docs/observability.md](.docs/observability.md), no [registro de observabilidade em português](.docs/observability.pt-BR.md), no adendo ao TCC (arquivo local, fora do reposit?rio) e em [metrics/](metrics/README.md). O acervo inclui execuções com falha e uma lista de checksums; `.env` e os volumes dos serviços ficam excluídos do versionamento.

A primeira prova de conceito utiliza uma tarefa de geração de backend e uma estimativa de empacotamento do contexto baseada em palavras separadas por espaços. Os tokens de entrada e saída do provedor vêm do uso informado pela API. O custo do pré-processamento compartilhado é apresentado separadamente; os custos de execução do provedor em dólares dependem das tarifas opcionais em `.env`. Não se atribui um preço fictício à infraestrutura dos bancos executados localmente. Um repositório e uma direção de migração demonstram viabilidade, sem estabelecer resultados gerais para contextos de longa duração ou diferentes linguagens.

O [protocolo de estudo de contexto de longa duração](.docs/long-horizon-protocol.md) acrescenta um experimento controlado de dependências recuperadas em etapas posteriores, com dois papéis apoiados por modelos, controles locais e uma condição sem memória. Execute primeiro os comandos com respostas simuladas: suas pontuações verificam a orquestração e não constituem resultados de pesquisa. O comando com modelo real descrito no protocolo grava um relatório separado por etapa em `/data/runs/study-<session-id>/`.

Os pares do estudo inicial do Editor arquivados tinham zero arestas no grafo e demonstram somente a viabilidade do pipeline. O [plano de estudo](.docs/study-plan.md) registra as evidências necessárias ao TCC. O estudo controlado compara recuperação vetorial em uma única etapa, travessia limitada em grafo e uma avaliação adicional, identificada separadamente, de recuperação vetorial com seguimento de referências por metadados. Sua massa de dados sintética não estabelece superioridade geral em código real.

Um [novo par de execuções reais do Editor com relações extraídas do código-fonte](metrics/editor-live-2026-11-14/) passou em 12/12 verificações da API com memória em grafo e em 10/12 com memória vetorial. Seu [registro de critérios de observabilidade](metrics/editor-live-2026-11-14/observability_gate.json) informa latência e consumo de tokens medidos, mas rejeita o avaliador de alucinação não calibrado e registra como não medidas a acurácia relacional das respostas sobre código real e a proporção de tokens de contexto útil. Trata-se de um resultado operacional, não de uma validação completa das quatro métricas do TCC.

A [comparação de observabilidade em português](.docs/observability.pt-BR.md) relaciona as quatro métricas propostas no TCC ao que as execuções efetivamente mediram. A proposta revisada de metodologia para a Seção 3 (local document, excluded from the repository) pode ser incorporada ao trabalho; o PDF original permanece inalterado.

O par final da prova de conceito controlada acrescenta um veredito de fundamentação baseado exclusivamente em evidências para cada resposta e apresenta afirmações sem suporte separadamente das abstenções. Ele valida afirmações sobre rotas e contratos de identificadores opacos dessa massa de dados; a avaliação de alucinação em texto livre permanece fora do escopo medido. O estudo mais recente dos quatro pilares, indicado no início desta seção, apresenta seus próprios resultados e limites.

### Verificar o pipeline sem gastos com o modelo

Os testes com dados controlados e um par completo de execuções no Docker, com uma resposta fixa e simulada do modelo, verificam a orquestração. O resultado com resposta fixa **não constitui evidência de pesquisa**:

```sh
uv sync --group dev
uv run pytest -q
docker compose run --rm -v "${PWD}/tests/support:/support:ro" --entrypoint python cli /support/run_editor_smoke.py
```

O comando de verificação no Docker acima utiliza a sintaxe de variável do PowerShell. Em um shell POSIX, substitua `"${PWD}/tests/support:/support:ro"` por `"$PWD/tests/support:/support:ro"`.

Instale a verificação de commits com `uv run pre-commit install`; `uv run pre-commit run --all-files` executa Ruff e pytest. Mantenha as credenciais do modelo no arquivo `.env`, não versionado, ou em uma fonte segura de segredos em tempo de execução; elas não são incorporadas à imagem.

---

<a id="english"></a>
## English

This repository contains the implementation and experimental evidence for a Brazilian undergraduate thesis (Trabalho de Conclusão de Curso, TCC) on memory for multi-agent systems. It investigates graph and vector memory for retrieving context and relationships in programming tasks, considering hallucination, accuracy, execution latency, and token efficiency.

The latest [four-pillar live study](metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md) measured bounded factual hallucination, task accuracy, execution latency, and labelled context-token efficiency across four Editor pairs and a no-memory control. Vector scored 48/48 tasks; graph scored 46/48 while using less time and fewer tokens. The [measurement gate passes](metrics/editor-four-pillars-2026-11-14/measurement_gate.json) for this restricted protocol; it does not establish general graph superiority. See the [protocol](.docs/editor-four-pillars-protocol.pt-BR.md) and archived report for reproduction commands and thesis limitations.

This proof of concept compares Qdrant vector memory with FalkorDB graph memory while migrating the pinned Python backend in `fixtures/project-editor` to a runnable TypeScript API. The React/Vite frontend and upstream records service remain untouched. The blueprint is [.docs/base.md](.docs/base.md); ordered tasks are in [.context/decomposition.json](.context/decomposition.json). `project-intaker` is reserved for later replication.

### Run the Editor proof of concept

1. Start Docker Desktop, initialize the pinned submodule, and copy [.env.example](.env.example) to `.env`. Set a reachable OpenAI-compatible chat and embeddings endpoint, its model IDs, and a key. The endpoint must return chat text and token usage, plus embedding vectors and token usage. Keep the same settings for ingestion and migration.

2. Build and start the services:

```sh
git submodule update --init --recursive
docker compose build cli
docker compose up -d qdrant falkordb
```

3. Ingest the pinned case. This writes the source snapshot, cached natural-language summaries and embeddings, and a ready project in DuckDB:

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
```

To download and ingest in one CLI command, replace the local source with `https://github.com/RMotta-afk/project-editor`; the scope profile pins and checks its commit and content. The local command above uses the already initialized submodule and avoids another download.

4. Copy the `Ready: <project-id>` value from ingestion. Run fresh paired attempts and evaluate all outcomes:

```sh
docker compose run --rm cli migrate --project <project-id> --target typescript --memory both --repeat 3
docker compose run --rm cli evaluate --project <project-id>
```

The result is `/data/runs/evaluation/evaluation.json` in the persistent `runs` volume. Each run has its own manifest, context traces, metrics JSONL, validation result, model responses, and generated code. A failed arm remains in the report and in the success-rate denominator. The generated `server.ts` is compiled and tested against a controlled upstream for edge cases, then against Editor's preserved records service for live GET/PUT connectivity. Validation also checks the unchanged frontend's `/api` proxy target.

The first live Editor study and its retained evidence are in [.docs/observability.md](.docs/observability.md), the [PT-BR observability record](.docs/observability.pt-BR.md), the TCC supplement (local document, excluded from the repository), and [metrics/](metrics/README.md). The archive includes failed arms and a checksum list; `.env` and service volumes are excluded.

The first POC uses one backend generation task and a whitespace-word context packing estimate. Provider prompt and completion tokens come from API usage. Shared preprocessing cost is reported separately; runtime provider USD costs require the optional rates in `.env`. No USD price is invented for self-hosted database infrastructure. One repository and one migration direction establish feasibility, not broad long-horizon or language-general results.

The [long-horizon study protocol](.docs/long-horizon-protocol.md) adds a controlled delayed-dependency experiment with two model-backed roles, local controls, and a no-memory ablation. Run its mock commands first; mock scores verify orchestration and are not research results. The live command in that protocol writes a separate per-step report under `/data/runs/study-<session-id>/`.

The archived Editor pairs had zero graph edges and establish pipeline feasibility only. The separate [study plan](.docs/study-plan.md) tracks the remaining evidence needed for the TCC. The controlled study compares one-shot vector retrieval, bounded graph traversal, and a separately labeled metadata-aware vector follow-up challenge; its synthetic fixture cannot establish general superiority on real code.

A [new live Editor pair with real source relations](metrics/editor-live-2026-11-14/) passed 12/12 API checks with graph memory and 10/12 with vector memory. Its [observability gate](metrics/editor-live-2026-11-14/observability_gate.json) reports measured latency and token consumption, while rejecting the uncalibrated hallucination judge and marking real-code relational answer accuracy and the useful-context-token ratio as unmeasured. It is an operational result, not a complete validation of the TCC's four metrics.

The [PT-BR observability comparison](.docs/observability.pt-BR.md) maps the TCC's four proposed metrics to what the runs actually measured. A revised Section 3 methodology draft (local document, excluded from the repository) is ready to incorporate into the thesis; the source PDF remains unchanged.

The final POC pair adds an evidence-only grounding verdict for each answer and reports unsupported assertions alongside abstentions. It validates opaque route and contract claims in this fixture; free-form hallucination assessment remains outside the measured scope.

### Verify the pipeline without model spending

The controlled fixture tests and a full Docker pair using a fixed mock model response check orchestration. The fixed-response result is **not research evidence**:

```sh
uv sync --group dev
uv run pytest -q
docker compose run --rm -v "${PWD}/tests/support:/support:ro" --entrypoint python cli /support/run_editor_smoke.py
```

The Docker smoke command above uses PowerShell variable syntax. On a POSIX shell, replace `"${PWD}/tests/support:/support:ro"` with `"$PWD/tests/support:/support:ro"`.

Install the commit gate with `uv run pre-commit install`; `uv run pre-commit run --all-files` runs Ruff and pytest. Keep model credentials in the untracked `.env` or a secure runtime secret source; they are not baked into the image.
