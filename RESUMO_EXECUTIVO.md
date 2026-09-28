# Resumo executivo — Diagnóstico do funil de propostas

**Base:** 6.400 propostas de crédito com garantia de imóvel, de jan/2024 a dez/2025 (dados sintéticos do desafio). **Dinheiro potencial** = receita de juros que cada proposta geraria se fosse contratada (estimativa bruta, Tabela Price).

## A percepção da liderança está parcialmente certa, mas olha para o problema menor

- **A conversão caiu, sim:** de 21,3% (2º sem. 2024) para 16,9% (2º sem. 2025). A queda é estatisticamente real.
- **Mas o que mais derrubou o resultado foi o volume de entrada:** de 2.064 para 978 propostas por semestre. Na queda de **R$ 112 mi em receita contratada**, o volume explica cerca de 85%, a conversão cerca de 27%, e o ticket médio maior compensou cerca de 12%.
- **O canal correspondente converte menos**, 14,3% contra 20,7% a 22,3% dos demais canais, e isso vale para clientes com o mesmo score. **Mas ele não explica a queda:** mesmo com a participação de canais de 2024, a conversão de 2025 quase não mudaria (16,9% → 17,1%).

## Onde se perde dinheiro

- **O cliente que some ou desiste custa mais do que a reprovação de crédito:** cerca de 61% da receita potencial perdida em 24 meses.
- **A perda mais recuperável é na formalização:** 836 propostas com crédito e imóvel já aprovados morreram por documentação ou desistência. São cerca de R$ 384 mi de receita potencial, com análise e laudo já pagos.
- **O que mais se associa à contratação:** score de crédito, depois LTV, depois canal. Região, prazo e tipo de imóvel não fazem diferença estatística.

## Alerta de risco

**124 contratos (10% do total, R$ 65,8 mi de crédito) foram assinados com LTV acima do limite de 60% da política.** É preciso confirmar se foram exceções aprovadas ou falha de controle.

## Três recomendações, em ordem de prioridade

Estimativas por ano, no ritmo de 2025, que é o semestre de menor volume; portanto, conservadoras.

| # | Recomendação | Impacto estimado | Premissa |
|---|---|---|---|
| 1 | **Resgatar a formalização:** checklist de documentos na aprovação, régua de follow-up e um responsável por proposta. | ≈ R$ 22 mi/ano de receita (+50 contratos) | Recuperar 20% das perdas dessa etapa (faixa de 10% a 30%: R$ 11 a 34 mi) |
| 2 | **Requalificar o correspondente:** pré-qualificação de score e LTV antes do envio, e comissão atrelada à conversão, não ao volume. | R$ 7 a 14 mi/ano (+16 a +31 contratos) | Fechar de metade a todo o gap de conversão que sobra depois de ajustar pelo score |
| 3 | **Trava de LTV de 60% na simulação**, oferecendo o valor máximo dentro da política. | Evita ≈ 106 laudos e 42 contratos fora da política por ano | Custo: se a trava só recusar, perde-se ≈ R$ 33 mi/ano de receita. Oferecer o valor ajustado reduz esse custo |

A recomendação 1 tem o maior valor e depende só de processo interno. A 2 tem a evidência estatística mais forte. A 3 é a mais urgente do ponto de vista de risco.

## O que pedimos à liderança

1. Aprovar um piloto de resgate da formalização, medindo o resultado em 90 dias.
2. Abrir a renegociação do modelo de comissão com os correspondentes.
3. Explicar os 124 contratos acima da política e decidir se a trava entra na simulação.
4. Investigar a queda de volume de entrada, que é o maior fator: o que mudou na geração de leads no 2º semestre de 2025?

*Limitações: as associações não provam causa; a receita é bruta (não desconta pré-pagamento nem inadimplência); o custo de cada etapa não está na base. Detalhes e código em `parte1_analise.ipynb`.*
