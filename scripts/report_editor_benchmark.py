"""Render the frozen four-pillar evidence as a PT-BR thesis-ready report."""
# ruff: noqa: E501

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from statistics import mean

from deterministic.study.editor_benchmark import Arm, MeasurementGate, Protocol, Summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive
    Protocol.model_validate_json((archive / "protocol.json").read_text())
    gate = MeasurementGate.model_validate_json((archive / "measurement_gate.json").read_text())
    summaries = [
        Summary.model_validate(s) for s in json.loads((archive / "evaluation.json").read_text())
    ]
    arms = {
        s.run_id: Arm.model_validate_json((archive / s.run_id / "run.json").read_text())
        for s in summaries
    }
    grouped = {
        m: [s for s in summaries if s.memory == m and s.pair >= 0] for m in ("vector", "graph")
    }

    def total(memory, field):
        return sum(getattr(s, field) for s in grouped[memory])

    def ratio(memory, numerator, denominator):
        a, b = total(memory, numerator), total(memory, denominator)
        return f"{a}/{b} ({100 * a / b:.2f}%)" if b else "não estimável"

    rows = [
        ("Alucinação factual restrita", *(ratio(m, "unsupported", "assertions") for m in grouped)),
        ("Acurácia de tarefas", *(ratio(m, "correct", "planned") for m in grouped)),
        (
            "Acurácia relacional",
            *(ratio(m, "relational_correct", "relational_total") for m in grouped),
        ),
        (
            "Latência média por braço, s",
            *(f"{mean(s.latency_ms for s in grouped[m]) / 1000:.3f}" for m in grouped),
        ),
        (
            "Eficiência de contexto rotulado",
            *(ratio(m, "useful_context_tokens", "context_tokens") for m in grouped),
        ),
        (
            "Tokens de chat por tarefa correta",
            *(
                f"{total(m, 'chat_tokens') / total(m, 'correct'):.2f}"
                if total(m, "correct")
                else "null"
                for m in grouped
            ),
        ),
        ("Tokens de chat", *(str(total(m, "chat_tokens")) for m in grouped)),
        ("Tokens de embedding em execução", *(str(total(m, "embedding_tokens")) for m in grouped)),
        ("Abstenções", *(str(total(m, "abstentions")) for m in grouped)),
        (
            "Citações completas entre respostas assertivas",
            *(ratio(m, "citation_complete", "assertions") for m in grouped),
        ),
        ("Custo estimado dos braços, USD", *(f"{total(m, 'cost_usd'):.6f}" for m in grouped)),
    ]
    table = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    pair_rows = []
    for pair in sorted({s.pair for s in summaries if s.pair >= 0}):
        v = next(s for s in grouped["vector"] if s.pair == pair)
        g = next(s for s in grouped["graph"] if s.pair == pair)
        pair_rows.append(
            f"| {pair + 1} | {v.correct}/{v.planned} | {g.correct}/{g.planned} | "
            f"{v.unsupported}/{v.assertions} | {g.unsupported}/{g.assertions} | "
            f"{v.latency_ms / 1000:.3f} | {g.latency_ms / 1000:.3f} |"
        )
    failures = []
    for summary in summaries:
        if summary.pair < 0:
            continue
        for obs in arms[summary.run_id].observations:
            if not obs.correct:
                answer = obs.answer.answer if obs.answer else "sem resposta"
                failures.append(
                    f"- Par {summary.pair + 1}, {summary.memory}, {obs.question_id}: "
                    f"resposta `{answer}`, esperado `{obs.expected}`, "
                    f"evidência necessária recuperada: `{obs.evidence_complete}`."
                )
    control = next((s for s in summaries if s.memory == "none"), None)
    control_text = (
        f"O controle sem contexto acertou {control.correct}/{control.planned}, "
        f"com {control.abstentions} abstenções e {control.unsupported} respostas "
        f"assertivas incompatíveis com o gabarito."
        if control
        else "Controle ausente."
    )
    prep = json.loads((archive / "preparation.json").read_text())
    prep_cost = sum(u["cost_usd"] for u in prep["usage"])
    run_cost = sum(s.cost_usd for s in summaries)
    text = f"""# Observabilidade dos quatro pilares — caso Editor

## Resultado e escopo

Foram executados {len(grouped["vector"])} pares reais no Editor fixado: {sum(s.planned for s in summaries if s.pair >= 0)} tarefas pontuadas, duas chamadas de agentes por tarefa, mais um controle sem contexto. O gate registra **quatro pilares medidos: `{gate.four_pillars_measured}`**, na definição restrita deste experimento. O gate não comprova superioridade geral do grafo e não substitui revisão humana dos rótulos.

Os agentes Analista e Revisor responderam seis questões relacionais, duas locais, duas sem resposta e duas sobre requisito controlado por braço. Qdrant usou similaridade e seguimento genérico de referências; FalkorDB usou travessia limitada. Ambos receberam os mesmos trechos de fonte, relações, embeddings compartilhados, prompts e orçamento exato de 1.400 tokens de contexto. A ordem dos braços alternou entre os pares.

| Indicador | Vetor | Grafo |
| --- | ---: | ---: |
{table}

## Resultados por par

| Par | Acertos vetor | Acertos grafo | Erros factuais/assertivas vetor | Erros factuais/assertivas grafo | Tempo vetor, s | Tempo grafo, s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(pair_rows)}

## Controle e erros

{control_text} As duas questões sem resposta têm `UNKNOWN` como resultado correto; abstenção nas demais conta como erro de tarefa, sem ser transformada em alucinação.

{chr(10).join(failures) if failures else "Nenhuma tarefa pontuada apresentou erro nesta amostra."}

Uma resposta incorreta com evidência necessária presente é uma falha de interpretação ou verificação, não prova de falha de recuperação. Citações completas verificam presença dos IDs necessários; não garantem que a interpretação desses trechos esteja correta.

## Definições para a seção 3

**Alucinação factual restrita:** fração de respostas escalares assertivas incompatíveis com fatos da fonte ou requisito vigente, entre respostas assertivas avaliáveis. É uma operacionalização limitada de erro factual em perguntas com gabarito. Não mede todas as afirmações de prosa ou código gerado. Acurácia e erro factual são relacionados neste formato; as abstenções e os denominadores explicam sua diferença. Respostas fora do formato são registradas separadamente, não classificadas automaticamente como falsas.

**Acurácia:** tarefas corretamente concluídas divididas por todas as tarefas planejadas. A fração relacional usa as seis questões entre módulos de cada execução. Falhas e tarefas não tentadas permanecem no denominador. Os mesmos doze casos foram repetidos; não são novos repositórios independentes.

**Latência:** tempo monotônico do início do braço até seu encerramento, incluindo indexação, recuperação, chamadas, persistência e avaliação determinística local. Preparação compartilhada: {prep["duration_ms"] / 1000:.3f} s, fora dos braços. A diferença observada inclui embeddings e operações distintas dos adaptadores, rede e modelo; não isola velocidade de bancos.

**Eficiência de tokens:** fração de tokens do contexto pertencentes a funções/registros previamente rotulados relevantes. O tokenizer tiktoken 0.12.0, `o200k_base`, conta exatamente o texto enviado, incluindo IDs e separadores; as duas exposições do contexto, ao Analista e ao Revisor, entram no total. O rótulo de utilidade é por registro, não uma anotação semântica de cada token. As duas questões sem resposta são excluídas dessa razão por falta de rótulos positivos defensáveis. Tokens de chat por acerto são um indicador complementar, com embeddings separados.

Preparação estimada: US$ {prep_cost:.6f}. Execuções, incluindo controle: US$ {run_cost:.6f}. Total estimado deste pacote: **US$ {prep_cost + run_cost:.6f}**. São tarifas configuradas sobre uso informado pelo provedor; não incluem infraestrutura nem equivalem à fatura.

## Limites e interpretação para o TCC

Esta execução fornece medidas auditáveis dos quatro pilares em um estudo de caso delimitado. Os rótulos foram revisados por assistentes e congelados antes da coleta; não houve anotação humana independente. A atualização de requisito com ID ativo compartilhado mede visibilidade de estado, não estabilidade de memória de longa duração. O corpus é pequeno, os formatos de resposta são escalares, e o baseline vetorial conhece as mesmas referências disponíveis ao grafo.

Quatro repetições do mesmo corpus permitem comparação descritiva, sem estabelecer superioridade geral ou significância estatística. A tese deve relatar o resultado observado mesmo quando houver empate ou vantagem vetorial. Os resultados da migração de backend e do piloto sintético anterior permanecem separados deste pacote.

## Reprodução e evidências

```powershell
docker compose build cli
docker compose up -d qdrant falkordb
docker compose run --rm -v "${{PWD}}/metrics:/evidence" --entrypoint python cli -m deterministic.study.editor_benchmark /fixtures/project-editor /evidence/editor-four-pillars-repetition --repeat 4 --control
uv run python scripts/report_editor_benchmark.py metrics/editor-four-pillars-repetition
```

Use uma pasta de saída nova. Credenciais vêm do `.env` local e não integram este pacote. [Protocolo completo](../../.docs/editor-four-pillars-protocol.pt-BR.md), [protocolo congelado](protocol.json), [configuração](configuration.json), [resultados](evaluation.json) e [gate](measurement_gate.json). Cada pasta de braço contém contexto, prompts, respostas, tempos e memória. O diretório `implementation` preserva o código utilizado. `SHA256SUMS` verifica os artefatos brutos; textos explicativos são excluídos.
"""
    (archive / "OBSERVABILITY.pt-BR.md").write_text(text, encoding="utf-8")
    (archive / "README.md").write_text(
        "# Editor: four-pillar live study\n\n"
        "See [the PT-BR evidence report](OBSERVABILITY.pt-BR.md) for the scored results, "
        "operational definitions, limitations and reproduction command. "
        "These are bounded source-grounded scalar QA measurements, not proof of general "
        "graph superiority. The older migration and synthetic studies remain separate.\n",
        encoding="utf-8",
    )
    repo = Path(__file__).resolve().parents[1]
    for path in (repo / "src").rglob("*.py"):
        destination = archive / "implementation" / path.relative_to(repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    for name in ("pyproject.toml", "uv.lock", "Dockerfile", "docker-compose.yml"):
        shutil.copy2(repo / name, archive / "implementation" / name)
    shutil.copy2(__file__, archive / "implementation" / "report_editor_benchmark.py")
    raw = sorted(
        p
        for p in archive.rglob("*")
        if p.is_file() and p.name not in {"README.md", "OBSERVABILITY.pt-BR.md", "SHA256SUMS"}
    )
    (archive / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(archive).as_posix()}\n"
            for p in raw
        ),
        encoding="utf-8",
    )
    print(f"Report saved; {len(raw)} hashed evidence files; gate={gate.four_pillars_measured}")


if __name__ == "__main__":
    main()
