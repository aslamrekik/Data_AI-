# bari_desafio

## Estrutura

```
bari_desafio/
├── data/raw/                  # dados brutos (entrada)
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
│   ├── extrator.py            # extrai campos dos laudos
│   ├── schema.py              # schema dos campos extraídos
│   ├── gabarito.json          # respostas esperadas
│   └── avaliar.py             # compara extração x gabarito
├── RESUMO_EXECUTIVO.md
├── README.md
└── DIARIO.md
```

## Instalação

Requer Python >= 3.11. Da raiz do repositório:

```
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

O `parte2_relatorio\rodar_relatorio.bat` usa esse `.venv`.

## Como executar

```
pip install -r requirements.txt
python src/tratamento.py   # gera data/processed/ e docs/registro_tratamento.md
pytest                     # testes do tratamento
```

- **Parte 1:** `jupyter notebook parte1_analise.ipynb` (a partir da raiz do projeto)
- **Parte 2:** `python parte2_relatorio/relatorio_semanal.py [--referencia AAAA-MM-DD]` ou `parte2_relatorio\rodar_relatorio.bat` (pode ir no Agendador de Tarefas). Gera `parte2_relatorio/output/relatorio_funil_<segunda>.html` e um log em `parte2_relatorio/logs/`; código de saída 0 = ok, 1 = entrada inválida, 2 = erro inesperado. Exemplo pronto, sem rodar nada: `docs/exemplo_relatorio_funil_2025-06-16.html`.
- **Parte 3:**
  ```
  cd parte3_laudos
  python extrator.py <pasta_dos_laudos>
  python avaliar.py
  ```
