# bari_desafio

## Estrutura

```
bari_desafio/
├── data/raw/                  # dados brutos (entrada)
├── src/tratamento.py          # funções de leitura e tratamento
├── parte1_analise.ipynb       # Parte 1 — análise exploratória
├── parte2_relatorio/
│   ├── relatorio_semanal.py   # gera o relatório semanal
│   ├── rodar_relatorio.bat    # atalho de execução (Windows / agendador)
│   ├── logs/                  # logs de execução
│   └── output/                # relatórios gerados
├── parte3_laudos/
│   ├── extrator.py            # extrai campos dos laudos
│   ├── schema.py              # schema dos campos extraídos
│   ├── gabarito.json          # respostas esperadas
│   └── avaliar.py             # compara extração x gabarito
├── RESUMO_EXECUTIVO.md
├── README.md
└── DIARIO.md
```

## Como executar

- **Parte 1:** `jupyter notebook parte1_analise.ipynb` (a partir da raiz do projeto)
- **Parte 2:** `python parte2_relatorio/relatorio_semanal.py` ou `parte2_relatorio\rodar_relatorio.bat`
- **Parte 3:**
  ```
  cd parte3_laudos
  python extrator.py <pasta_dos_laudos>
  python avaliar.py
  ```
