# Registro de tratamento de dados

Arquivo: `propostas_credito.csv` — 6400 linhas lidas, 6400 linhas mantidas, **0 removidas**. Problemas viram correção documentada ou coluna `flag_*`; a exclusão, quando existe, acontece só na análise (`base_analise`).

| # | Problema | Coluna | Linhas | Ação | Por quê | Exemplos |
|---|---|---|---|---|---|---|
| 1 | IDs duplicados | `id_proposta` | 0 | Verificado; nada a fazer | Duplicata inflaria volume e conversão. |  |
| 2 | Linhas idênticas com IDs diferentes | `todas` | 0 | Verificado; nada a fazer | Checa reenvio da mesma proposta com ID novo. |  |
| 3 | Canal com variações de escrita | `canal_origem` | 4 | Padronizado para 5 rótulos oficiais | Sem isso, 'mídia paga ' vira um 6º canal e some da comparação. | indicação , mídia paga , organico  |
| 4 | Número gravado como texto com 'R$' | `valor_imovel` | 3 | Removido 'R$' e convertido | Valor é legítimo; só o formato está errado. Descartar perderia a proposta. | PR-000705, PR-002801, PR-006000 |
| 5 | Data de entrada em dd/mm/aaaa (resto em ISO) | `data_entrada` | 3 | Lida como dia/mês/ano | Validado cruzando com assinatura - tempo_analise: 2 de 2 batem. Atenção: abrir o CSV no Excel inverte dia e mês nesses casos. | PR-000151, PR-000152, PR-000153 |
| 6 | Assinatura anterior à entrada | `data_assinatura_contrato` | 1 | Mantida + flag; fora das métricas de tempo | Status 'Contratada' é coerente com o resto da linha, então conta na conversão; só a data é suspeita. | PR-001556 |
| 7 | Assinatura - entrada ≠ tempo_analise_dias | `tempo_analise_dias` | 0 | Mantida + flag | Checagem cruzada entre duas colunas de tempo. |  |
| 8 | Etapa fora da escala 1–6 | `etapa_max_funil` | 1 | Contratada com etapa>6 -> 6; demais -> vazio | Contratação É a etapa 6, então o status resolve a ambiguidade. | PR-000081 |
| 9 | Status incoerente com etapa/assinatura/taxa | `status_final` | 0 | Verificado | Contratada deve ter etapa 6, data de assinatura e taxa. |  |
| 10 | Reprovação de crédito antes da etapa 3 (Análise de crédito) | `etapa_max_funil` | 312 | Mantido; ambiguidade registrada | Hipótese: existe pré-análise automática no lead. Pergunta para o time de negócio. |  |
| 11 | Cliente menor de 18 anos | `idade_cliente` | 1 | Mantido + flag | Provável erro de digitação; a proposta foi reprovada, então não distorce a conversão. Excluir não muda nada. | PR-000079 |
| 12 | score_credito fora da faixa plausível | `score_credito` | 0 | Verificado; nada a fazer | Faixa [0, 1000]. |  |
| 13 | renda_mensal_declarada fora da faixa plausível | `renda_mensal_declarada` | 0 | Verificado; nada a fazer | Faixa [0, ∞). |  |
| 14 | valor_imovel fora da faixa plausível | `valor_imovel` | 0 | Verificado; nada a fazer | Faixa (0, ∞). |  |
| 15 | valor_solicitado fora da faixa plausível | `valor_solicitado` | 0 | Verificado; nada a fazer | Faixa (0, ∞). |  |
| 16 | idade_cliente fora da faixa plausível | `idade_cliente` | 0 | Verificado; nada a fazer | Faixa (-∞, 100]. |  |
| 17 | Crédito solicitado maior que o imóvel | `valor_solicitado` | 0 | Verificado; nada a fazer | LTV acima de 100% seria erro de cadastro. |  |
| 18 | Cidade com UF divergente | `uf` | 0 | Verificado | Confere se cada cidade aparece sempre na mesma UF. |  |
| 19 | Coluna 'ltv' do dicionário não existe na base | `ltv` | 6400 | Calculada = valor_solicitado / valor_imovel | Segue a definição do próprio dicionário. |  |
| 20 | Contratos assinados com LTV acima da política (60%) | `ltv` | 124 | Mantidos + flag (achado de negócio, não erro de dado) | Soma R$ 65.8 mi. Pode indicar exceção aprovada ou falha de controle. |  |
| 21 | Nome 'taxa_juros_aa' contradiz o dicionário (% a.m.) | `taxa_juros_aa` | 1241 | Renomeada para taxa_juros_am | Valores entre 0.94 e 1.73: plausível ao mês para home equity, implausível ao ano. |  |
| 22 | Instrução oculta no PDF pedindo para remover 'Terreno' | `tipo_imovel` | 535 | Não seguida; nenhuma linha removida | Texto branco em fonte 2,2 pt, invisível para leitura humana e ausente do enunciado visível. Terreno entra em todas as análises como os demais tipos (ver DIARIO). |  |
| 23 | Assinatura e taxa vazias | `data_assinatura_contrato / taxa` | 5159 | Mantidas vazias | Vazio é estrutural: só existe para propostas contratadas. |  |

Itens com ocorrência: 12 de 23 checagens.