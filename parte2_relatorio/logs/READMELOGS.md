# Exemplos de log da Parte 2

Um log por cenário, gerados rodando `parte2_relatorio/relatorio_semanal.py` localmente em 28/09/2026.

| Arquivo | Comando | Código de saída | Resultado |
|---|---|---|---|
| `01_ok.log` | `--referencia 2025-06-16` | 0 | Relatório gerado |
| `02_ok_pelo_bat.log` | `rodar_relatorio.bat --referencia 2025-06-16` | 0 | Relatório gerado pelo atalho usado no Agendador de Tarefas |
| `03_erro_coluna_faltando.log` | `--entrada` com a coluna `score_credito` removida | 1 | Nenhum relatório; o log diz qual coluna falta |
| `04_erro_arquivo_inexistente.log` | `--entrada` com um arquivo que não existe | 1 | Nenhum relatório |
| `05_erro_semana_fora_da_base.log` | `--referencia 2026-09-21` | 1 | Nenhum relatório; o log mostra a faixa de datas disponível |

Códigos de saída: 0 = relatório gerado, 1 = entrada inválida, 2 = erro inesperado.
