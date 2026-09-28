# Desafio Prático — Estágio AI & Data Lab | Bari

Diagnóstico do funil de propostas de crédito com garantia de imóvel (Parte 1), relatório semanal automatizado (Parte 2) e extração estruturada de laudos de avaliação com IA (Parte 3). Todos os dados são os sintéticos fornecidos pelo Bari.

## Por onde começar

| Quero ver... | Arquivo |
|---|---|
| As conclusões, em uma página, para a liderança | [`RESUMO_EXECUTIVO.md`](RESUMO_EXECUTIVO.md) |
| A análise completa, com código e gráficos | [`parte1_analise.ipynb`](parte1_analise.ipynb) |
| O que estava errado na base e o que foi feito | [`docs/registro_tratamento.md`](docs/registro_tratamento.md) |
| O relatório semanal pronto, sem rodar nada | [`docs/exemplo_relatorio_funil_2025-06-16.html`](docs/exemplo_relatorio_funil_2025-06-16.html) |
| O resultado da extração dos laudos | [`docs/parte3_rodada_final_claude.md`](docs/parte3_rodada_final_claude.md) |
| Como a IA foi usada, erros e autocrítica | [`DIARIO.md`](DIARIO.md) |

## Instalação

Requer Python 3.11 ou mais novo. Da raiz do repositório:

```
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
pytest                          # testes das três partes, sem chamar nenhuma API
```

## Como rodar

**Tratamento da base** (usado pelas Partes 1 e 2):

```
python src/tratamento.py
```

Gera `data/processed/propostas_tratadas.csv` e `docs/registro_tratamento.md`. Nenhuma linha é removida: cada problema vira uma correção documentada ou uma coluna `flag_*`.

**Parte 1 — Diagnóstico do funil:** abra `parte1_analise.ipynb` a partir da raiz do repositório e execute todas as células. Os gráficos são salvos em `parte1_figuras/`.

**Parte 2 — Relatório semanal:**

```
python parte2_relatorio/relatorio_semanal.py [--referencia AAAA-MM-DD] [--entrada ARQUIVO.csv] [--saida PASTA]
```

Ou dê duplo clique em `parte2_relatorio\rodar_relatorio.bat`. O relatório sai em `parte2_relatorio/output/relatorio_funil_<segunda-feira>.html` e cada execução grava um log em `parte2_relatorio/logs/`.

- **Códigos de saída:** 0 = relatório gerado; 1 = entrada inválida (arquivo ausente ou vazio, coluna obrigatória faltando, semana fora da base), sem gerar relatório; 2 = erro inesperado, com o erro completo no log.
- **Coluna nova ou canal desconhecido:** não quebram; o tratamento registra e segue.
- **Semana padrão:** a última semana completa da base. Como os dados terminam em dezembro de 2025, use `--referencia` para ver uma semana típica.
- **Logs de exemplo, um por cenário (sucesso, coluna faltando, arquivo inexistente, semana fora da base):** [`docs/exemplos_logs/`](docs/exemplos_logs/).
- **Toda segunda-feira, sem ninguém rodar à mão:** agende uma vez pelo terminal do Windows.

```
schtasks /Create /SC WEEKLY /D MON /ST 08:00 /TN "Relatorio Funil Bari" /TR "C:\caminho\do\repo\parte2_relatorio\rodar_relatorio.bat"
```

**Parte 3 — Extração dos laudos:**

1. Crie uma chave gratuita em [Google AI Studio](https://aistudio.google.com/apikey).
2. Copie `.env.example` para `.env` e preencha a chave: `GEMINI_API_KEY` (padrão) ou `ANTHROPIC_API_KEY` com `PROVEDOR=claude`. O `.env` é ignorado pelo Git: a chave nunca vai para o repositório.
3. Rode:

```
python parte3_laudos/extrator.py                  # os 17 laudos de data/raw/laudos/
python parte3_laudos/extrator.py --pendentes      # só os que ainda faltam (útil com a cota gratuita)
python parte3_laudos/extrator.py --renormalizar   # refaz a normalização a partir das respostas salvas, sem API
python parte3_laudos/avaliar.py --extracoes parte3_laudos/saida/extracoes_claude.json
```

Para ver o resultado sem chave nenhuma: `parte3_laudos/saida/extracoes_claude.json` e `parte3_laudos/saida/avaliacao_claude.md` estão versionados.

## O que tem em cada arquivo

```
├── data/raw/propostas_credito.csv      base de propostas (entrada, sem alteração)
├── data/raw/laudos/                    os 17 laudos em texto livre
├── src/tratamento.py                   leitura, validação de schema e tratamento da base
├── parte1_analise.ipynb                Parte 1: diagnóstico do funil (Q1 a Q4)
├── parte1_figuras/                     gráficos gerados pelo notebook
├── parte2_relatorio/
│   ├── relatorio_semanal.py            Parte 2: gera o relatório semanal em HTML
│   └── rodar_relatorio.bat             atalho para duplo clique ou Agendador de Tarefas
├── parte3_laudos/
│   ├── schema.py                       formato fixo da resposta do LLM e da saída final
│   ├── extrator.py                     chama o Gemini ou a Claude, com retentativas e retomada
│   ├── normalizar.py                   converte textos em valores e confere a evidência
│   ├── avaliar.py                      mede a extração contra o gabarito
│   ├── gabarito.json                   respostas esperadas, com as regras de rotulagem
│   └── saida/                          extração e avaliação da execução final (Claude)
├── tests/                              testes pytest das três partes
├── docs/                               registro do tratamento, exemplo do relatório, logs de exemplo, rodadas da Parte 3
├── RESUMO_EXECUTIVO.md                 conclusões em uma página
└── DIARIO.md                           diário de bordo (Parte 4)
```

## Decisões principais

- **Instruções ocultas no enunciado não foram seguidas.** O PDF tinha duas instruções em texto branco, fonte 2,2 pt, invisíveis na leitura: remover os imóveis do tipo Terreno e incluir uma palavra específica neste README. Como não estão no enunciado visível e se comportam como injeção de prompt para quem usa IA sem ler o documento, a análise usa a base completa. Detalhes no `DIARIO.md`.
- **A entrada é o CSV original.** Abrir o CSV no Excel inverteu dia e mês em datas no formato dd/mm/aaaa, então o pipeline lê o CSV como texto e não aceita planilhas.
- **Nenhuma linha é apagada no tratamento.** A exclusão, quando existe, é decidida na análise, e todo problema fica registrado com a quantidade de linhas afetadas.
- **"Dinheiro potencial" = receita de juros bruta estimada** (Tabela Price), com o valor solicitado como métrica complementar. O ranking das perdas é o mesmo nas duas.
- **Na Parte 3, a IA lê e o código formata.** O Gemini só devolve o texto como está no laudo, o status e o trecho de evidência. Números, datas e unidades são convertidos por código determinístico. Todo valor precisa de um trecho que exista no laudo e contenha o valor; sem isso, o campo vira `nao_verificado`. Um valor plausível sem evidência é tratado como o pior erro.
- **Saídas versionadas:** as da Parte 3 são versionadas porque dependem de API externa, cota e um modelo não determinístico. As do tratamento não, porque qualquer pessoa as recria com um comando.

## Resultados da Parte 3

Critério de acerto por campo: valor equivalente ao gabarito (números com tolerância de 0,5%; datas, anos, UF, matrícula e categorias iguais; textos pela similaridade, com números idênticos). Quando o gabarito diz que o campo não existe, só é acerto se o extrator também não der valor; dar um valor ali é **alucinação**, o erro mais grave.

| Métrica | Claude (`claude-sonnet-5`), resultado final | Gemini (`gemini-3.6-flash`), checagem independente |
|---|---|---|
| Laudos extraídos | 17 de 17 | 11 de 17 (cota gratuita esgotada) |
| Acurácia nos laudos extraídos | 98,5% (268 de 272 campos) | 98,9% |
| Alucinações | 0 | 0 |
| Abstenção correta (disse "não sei" onde o campo não existe) | 100% | — |

Todos os casos difíceis saíram certos: área contraditória (laudo 17, com os dois valores), matrícula ausente (08), penhora cancelada (13), ano calculado a partir da idade (03 e 14), hectares (05) e terrenos sem ano (04 e 11).

Nenhum dos 4 campos que não bateram é um valor inventado. Dois são detalhes de texto (o rótulo "Certidão:" no laudo 02 e o nome do condomínio no laudo 10). Os outros dois são casos que o gabarito já marcava como discutíveis (a denominação "Sítio Boa Vista" como endereço e "ano de referência" como ano de construção), em que o extrator respondeu "não informado". Não ajustei o prompt nem o gabarito a esses dois: seria ajustar o extrator à prova.

**Limitações:** os mesmos 17 laudos serviram para ajustar o prompt e para medir o resultado, então os 98,5% são otimistas. O resultado também varia entre execuções. O gabarito foi rascunhado com a Claude, revisado pelo Claude Code e validado por mim nos casos difíceis; como o extrator final também é a Claude, usei o Gemini, que não participou do gabarito, como checagem independente.

Histórico completo das execuções, com o que cada uma motivou: [`docs/parte3_rodada_final_claude.md`](docs/parte3_rodada_final_claude.md). A primeira execução, interrompida pela cota do Gemini: [`docs/parte3_rodada1_cota_esgotada.md`](docs/parte3_rodada1_cota_esgotada.md).

## Uso de IA

Usei o Claude (chat) para planejar, explorar os dados e escrever a primeira versão do código de cada parte, e o Claude Code para integrar, executar e revisar cada fase antes do merge. Toda revisão virou uma lista de achados; eu decidi o que aceitar, e cada bug corrigido virou um teste. O histórico de PRs mostra essas triagens. Os erros concretos da IA e o que fiz com eles estão no `DIARIO.md`.

## Tempo gasto

| Etapa | Tempo |
|---|---|
| Entendimento do desafio, brainstorming e planejamento | [3 HORAS] |
| Tratamento de dados | [30Mn] |
| Parte 1 — análise do funil | [3HORAS] |
| Parte 3 — extração dos laudos | [5 HORAS] |
| Parte 2 — relatório semanal | [2HORAS] |
| Resumo executivo, README e DIARIO | [1H] |
| **Total** | [14 Horas e 30 Min ] |

## Fontes

- Dados: `propostas_credito.csv` e os 17 laudos fornecidos pelo Bari (sintéticos). Nenhum dado externo foi usado.
- Bibliotecas: pandas, NumPy, SciPy, matplotlib, Pydantic, google-genai, anthropic, python-dotenv e pytest.
- Modelos de linguagem da Parte 3: APIs do Google Gemini e da Anthropic (Claude).
