# Avaliação da extração de laudos

Critério de acerto: ver docstring de `avaliar.py`. Alucinação é o erro mais grave.

## Resumo

| Métrica | Valor |
|---|---|
| campos avaliados | 272 |
| laudos com falha na extração | 0 |
| acurácia (valor) | 98.5% |
| acurácia nos laudos extraídos | 98.5% |
| acurácia estrita (valor + status) | 98.5% |
| cobertura (acertos onde o gabarito tem valor) | 98.2% |
| abstenção correta (onde o gabarito não tem valor) | 100.0% |
| alucinações (valor onde não existe) | 0 |
| erros de valor | 2 |
| abstenções (não sabia, errou para o lado seguro) | 2 |
| campos aceitos com evidência localizada pelo código | 0 |

## Por campo

| campo | abstencao | acerto | erro_valor | acurácia |
|---|---|---|---|---|
| tipo_imovel | 0 | 17 | 0 | 100% |
| endereco | 1 | 15 | 1 | 88% |
| cidade | 0 | 17 | 0 | 100% |
| uf | 0 | 17 | 0 | 100% |
| area_privativa_m2 | 0 | 17 | 0 | 100% |
| area_total_m2 | 0 | 17 | 0 | 100% |
| area_construida_m2 | 0 | 17 | 0 | 100% |
| area_terreno_m2 | 0 | 17 | 0 | 100% |
| ano_construcao | 1 | 16 | 0 | 94% |
| valor_avaliacao | 0 | 17 | 0 | 100% |
| matricula | 0 | 17 | 0 | 100% |
| onus_situacao | 0 | 17 | 0 | 100% |
| onus_descricao | 0 | 16 | 1 | 94% |
| data_vistoria | 0 | 17 | 0 | 100% |
| responsavel_nome | 0 | 17 | 0 | 100% |
| responsavel_registro | 0 | 17 | 0 | 100% |

## Evidência localizada pelo código

O LLM citou só o valor; o código achou a única linha do laudo que contém o valor e fala do campo. Contam como acerto ou erro normalmente.

Nenhum.

## Campos que não bateram

| laudo | campo | resultado | status_gabarito | status_extrator | esperado | obtido | motivo |
|---|---|---|---|---|---|---|---|
| laudo_02 | onus_descricao | erro_valor | encontrado | encontrado | "Certidão: sem gravames conhecidos" | "sem gravames conhecidos" |  |
| laudo_05 | endereco | abstencao | encontrado | nao_informado | "Sítio Boa Vista" | null |  |
| laudo_08 | ano_construcao | abstencao | inferido | nao_informado | 2005 | null |  |
| laudo_10 | endereco | erro_valor | encontrado | encontrado | "SQN 214, bloco C, apto 407 - Condomínio Parque Norte" | "SQN 214, bloco C, apto 407" |  |
