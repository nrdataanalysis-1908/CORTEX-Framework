# Avaliação de qualidade das respostas — protocolo humano

Este protocolo complementa as métricas de recuperação. Ele não executa um LLM judge e não infere factualidade por correspondência lexical: cada afirmação da resposta precisa ser anotada por um revisor, comparando-a com as evidências recuperadas e com a fonte de referência.

## Unidade de avaliação

Uma unidade é uma resposta para uma pergunta do conjunto-ouro. O revisor decompõe a resposta em afirmações atômicas e registra, para cada uma:

- `claim`: afirmação verificável extraída da resposta.
- `status`: um dos rótulos abaixo.
- `evidence`: trecho, localização da fonte ou justificativa explícita da decisão.

Rótulos permitidos:

| Rótulo | Critério |
|---|---|
| `supported` | A evidência recuperada sustenta integralmente a afirmação. |
| `unsupported` | A afirmação não é sustentada pelas evidências disponíveis, sem haver evidência contrária explícita. |
| `contradicted` | A evidência disponível contradiz a afirmação. |
| `unverifiable` | Não é possível decidir com o material disponível; requer revisão ou fonte adicional. |

Também registre `answer_abstained` e `abstention_expected`. O segundo campo deve ser definido pelo revisor antes de avaliar a resposta, com base na suficiência da evidência para responder.

## Formato de entrada

O agregador recebe uma lista JSON. Exemplo ilustrativo, não resultado real:

~~~json
[
  {
    "id": "Q01",
    "answer_abstained": false,
    "abstention_expected": false,
    "claims": [
      {
        "claim": "O prazo de primeira resposta P1 é de 15 minutos.",
        "status": "supported",
        "evidence": "Manual operacional, seção 2.1: prazo P1 de 15 minutos."
      }
    ]
  }
]
~~~

Cada caso exige identificador único, campos booleanos de abstenção e lista de afirmações. Cada afirmação exige texto, rótulo válido e evidência ou justificativa do revisor.

## Métricas agregadas

O módulo `evaluation.answer_quality.evaluate_annotations` calcula:

- `support_rate`: afirmações sustentadas / afirmações decidíveis.
- `unsupported_claim_rate`: afirmações unsupported ou contradicted / afirmações decidíveis.
- `contradiction_rate`: afirmações contradicted / afirmações decidíveis.
- `abstention_accuracy`: casos em que a decisão de abster-se coincide com a expectativa do revisor / casos avaliados.

Afirmações `unverifiable` são contabilizadas, mas excluídas do denominador das taxas de afirmações decidíveis. Os contadores brutos são preservados no relatório. Em conjuntos vazios, as métricas retornam zero; isso não representa qualidade perfeita.

## Execução e interpretação

A função é pura e não realiza chamadas de rede, inferência de modelo ou leitura de banco. Pode ser usada em testes e em um futuro pipeline de anotação. Os resultados só representam a amostra revisada e a consistência dos revisores; não constituem garantia estatística nem prova universal de factualidade.

Recomenda-se revisão independente de uma amostra por dois avaliadores, adjudicação de divergências e versionamento do conjunto de anotações. Não comparar versões do sistema sem manter constantes as perguntas, fontes e critérios de rotulagem.

## Limites explícitos

- Não há classificação automática de afirmações.
- Não há LLM judge nem chamada à OpenAI.
- O módulo não transforma similaridade vetorial em evidência de factualidade.
- As métricas de recuperação (Recall@K, MRR@K e NDCG@K) permanecem separadas das métricas de resposta.
- Nenhum benchmark ou resultado real é incluído nesta entrega.
