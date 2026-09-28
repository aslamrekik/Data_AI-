# bari_desafio

## Estrutura

```
bari_desafio/
├── data/raw/                  # dados brutos (entrada); laudos em data/raw/laudos/
├── src/tratamento.py          # funções de leitura e tratamento
├── tests/                     # testes do tratamento (pytest)
├── docs/registro_tratamento.md  # registro gerado pelo tratamento
├── parte1_analise.ipynb       # Parte 1 — análise exploratória
├── parte2_relatorio/
│   ├── relatorio_semanal.py   # gera o relatório semanal
│   ├── rodar_relatorio.bat    # atalho de execução (Windows / agendador)
│   ├── logs/                  # logs de execução
│   └── output/                # relatórios gerados
├── parte3_laudos/
│   ├── extrator.py            # extrai campos dos laudos (Gemini ou Claude)
│   ├── normalizar.py          # converte o texto literal do LLM no formato final
│   ├── schema.py              # contratos de dados (Pydantic)
│   ├── gabarito.json          # respostas esperadas
│   ├── avaliar.py             # compara extração x gabarito
│   └── saida/                 # extrações (ignoradas no Git, exceto avaliacao.md)
├── RESUMO_EXECUTIVO.md
├── README.md
└── DIARIO.md
```

## Como executar

Requer Python >= 3.11.

```
pip install -r requirements.txt
python src/tratamento.py   # gera data/processed/ e docs/registro_tratamento.md
pytest                     # testes do tratamento
```

- **Parte 1:** `jupyter notebook parte1_analise.ipynb` (a partir da raiz do projeto)
- **Parte 2:** `python parte2_relatorio/relatorio_semanal.py` ou `parte2_relatorio\rodar_relatorio.bat`
- **Parte 3:** copie `.env.example` para `.env` e preencha `GEMINI_API_KEY` (ou `ANTHROPIC_API_KEY` com `PROVEDOR=claude`; o `.env` nunca vai para o Git). Da raiz do projeto:
  ```
  python parte3_laudos/extrator.py            # todos os laudos (ou --laudo laudo_17)
  python parte3_laudos/extrator.py --renormalizar   # refaz a saída a partir de saida/brutas/, sem API
  python parte3_laudos/avaliar.py             # gera parte3_laudos/saida/avaliacao.md
  # Claude: PROVEDOR=claude no .env (ou --provedor claude) -> saida/extracoes_claude.json
  python parte3_laudos/avaliar.py --extracoes parte3_laudos/saida/extracoes_claude.json  # -> avaliacao_claude.md
  ```
