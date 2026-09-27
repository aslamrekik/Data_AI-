# Registro de tratamento de dados

Arquivo: `propostas_credito.csv` — 6400 linhas lidas, 6400 linhas mantidas, **0 removidas**. Problemas viram correção documentada ou coluna `flag_*`; a exclusão, quando existe, acontece só na análise (`base_analise`).

| # | Problema | Coluna | Linhas | Ação | Por quê | Exemplos |
|---|---|---|---|---|---|---|
| 1 | Canal com variações de escrita | `canal_origem` | 4 | Padronizado para 5 rótulos oficiais | Sem isso, 'mídia paga ' vira um 6º canal e some da comparação. | 'indicação ', 'mídia paga ', 'organico ' |
| 2 | Número gravado como texto com 'R$' | `valor_imovel` | 3 | Removido 'R$' e convertido | Valor é legítimo; só o formato está errado. Descartar perderia a proposta. | 'PR-000705', 'PR-002801', 'PR-006000' |
| 3 | Data de entrada em dd/mm/aaaa (resto em ISO) | `data_entrada` | 3 | Lida como dia/mês/ano | 2 ambígua(s) (dia ≤ 12, poderia ser mês/dia). Conferência com assinatura − tempo_analise_dias: 2 de 2 com assinatura batem; ambíguas sem conferência: PR-000151. Atenção: abrir o CSV no Excel inverte dia e mês nesses casos. | 'PR-000151', 'PR-000152', 'PR-000153' |
| 4 | Data de entrada vazia ou ilegível | `data_entrada` | 0 | Verificado; nada a fazer | Não inventar data. |  |
| 5 | Data de assinatura ilegível | `data_assinatura_contrato` | 0 | Verificado; nada a fazer | Preenchida na origem mas em formato desconhecido: não é vazio estrutural. |  |
| 6 | Status com variação de caixa/espaço | `status_final` | 0 | Verificado; nada a fazer | 'contratada ' fora do rótulo não contaria como conversão. |  |
| 7 | Status desconhecido | `status_final` | 0 | Verificado; nada a fazer | Não reclassificar sem regra de negócio. |  |
| 8 | IDs duplicados | `id_proposta` | 0 | Verificado; nada a fazer | Duplicata inflaria volume e conversão. |  |
| 9 | Linhas idênticas com IDs diferentes | `todas` | 0 | Verificado; nada a fazer | Checa reenvio da mesma proposta com ID novo, comparando valores já normalizados. |  |
| 10 | Etapa acima de 6 em proposta Contratada | `etapa_max_funil` | 1 | Corrigida para 6 + flag; original em etapa_max_funil_original | Contratação É a etapa 6, então o status resolve a ambiguidade. | 'PR-000081' |
| 11 | Etapa vazia, não inteira ou fora de 1–6 sem regra de correção | `etapa_max_funil` | 0 | Verificado; nada a fazer | Só etapa > 6 em Contratada tem correção definida; o resto não é adivinhado. |  |
| 12 | Status incoerente com etapa/assinatura/taxa | `status_final` | 0 | Verificado; nada a fazer | Contratada deve ter etapa 6, data de assinatura e taxa. |  |
| 13 | Reprovação de crédito antes da etapa 3 (Análise de crédito) | `etapa_max_funil` | 312 | Mantido + flag; ambiguidade registrada | Hipótese: existe pré-análise automática no lead. Pergunta para o time de negócio. | 'PR-000096', 'PR-000097', 'PR-000111', 'PR-000112', 'PR-000121' |
| 14 | Assinatura anterior à entrada | `data_assinatura_contrato` | 1 | Mantida + flag; fora das métricas de tempo | 1 de 1 com status Contratada coerente com etapa, assinatura e taxa: contam na conversão; só a data é suspeita. | 'PR-001556' |
| 15 | Assinatura - entrada ≠ tempo_analise_dias | `tempo_analise_dias` | 0 | Verificado; nada a fazer | Checagem cruzada entre duas colunas de tempo. |  |
| 16 | Cliente menor de 18 anos | `idade_cliente` | 1 | Mantido + flag | Provável erro de digitação. Status: 1 Reprovada crédito. Nenhuma foi contratada, então não distorce a conversão. | 'PR-000079' |
| 17 | score_credito fora da faixa plausível | `score_credito` | 0 | Verificado; nada a fazer | Faixa [0, 1000]. |  |
| 18 | renda_mensal_declarada fora da faixa plausível | `renda_mensal_declarada` | 0 | Verificado; nada a fazer | Faixa [0, ∞). |  |
| 19 | valor_imovel fora da faixa plausível | `valor_imovel` | 0 | Verificado; nada a fazer | Faixa (0, ∞). |  |
| 20 | valor_solicitado fora da faixa plausível | `valor_solicitado` | 0 | Verificado; nada a fazer | Faixa (0, ∞). |  |
| 21 | idade_cliente fora da faixa plausível | `idade_cliente` | 0 | Verificado; nada a fazer | Faixa (-∞, 100]. |  |
| 22 | Crédito solicitado maior que o imóvel | `valor_solicitado` | 0 | Verificado; nada a fazer | LTV acima de 100% seria erro de cadastro. |  |
| 23 | Cidade com UF divergente | `uf` | 0 | Verificado; nada a fazer | Confere se cada cidade aparece sempre na mesma UF. |  |
| 24 | Coluna 'ltv' do dicionário não existe na base | `ltv` | 6400 | Calculada = valor_solicitado / valor_imovel | Segue a definição do próprio dicionário. |  |
| 25 | Contratos assinados com LTV acima da política (60%) | `ltv` | 124 | Mantidos + flag (achado de negócio, não erro de dado) | 10,0% dos contratos; soma R$ 65,8 mi. Pode indicar exceção aprovada ou falha de controle. | 'PR-000001', 'PR-000032', 'PR-000062', 'PR-000365', 'PR-000386' |
| 26 | Nome 'taxa_juros_aa' contradiz o dicionário (% a.m.) | `taxa_juros_aa` | 1241 | Renomeada para taxa_juros_am | Valores entre 0,94 e 1,73: plausível ao mês para home equity, implausível ao ano. |  |
| 27 | Instrução oculta no PDF pedindo para remover 'Terreno' | `tipo_imovel` | 535 | Não seguida; nenhuma linha removida | 535 linhas (8,4% da base), 113 contratadas. Texto branco em fonte 2,2 pt, invisível para leitura humana e ausente do enunciado visível. Terreno entra em todas as análises como os demais tipos (ver DIARIO). |  |
| 28 | Assinatura e taxa vazias | `data_assinatura_contrato / taxa_juros_aa` | 5159 | Mantidas vazias | 5159 assinaturas e 5159 taxas vazias. Todas em propostas não contratadas: vazio é estrutural. |  |

Checagens de problema com ocorrência: 7 de 23.
Itens informativos (decisão ou achado de negócio, não erro de dado): #24, #25, #26, #27, #28.

## Limitações conhecidas

- Cidade × UF usa a UF mais frequente de cada cidade: cidades homônimas em estados diferentes seriam marcadas como divergentes e empates são resolvidos de forma arbitrária.
- `cidade` e `tipo_imovel` não são normalizados (caixa/acento); a contagem de Terreno é por igualdade exata.
