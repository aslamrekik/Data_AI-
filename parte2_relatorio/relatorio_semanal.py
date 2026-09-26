"""Parte 2 — Geração do relatório semanal.

Grava logs em parte2_relatorio/logs/ e o relatório em parte2_relatorio/output/.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAIZ = BASE.parent
LOGS = BASE / "logs"
OUTPUT = BASE / "output"

sys.path.insert(0, str(RAIZ))


def configurar_log() -> logging.Logger:
    LOGS.mkdir(exist_ok=True)
    arquivo = LOGS / f"relatorio_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(arquivo, encoding="utf-8"), logging.StreamHandler()],
    )
    return logging.getLogger("relatorio_semanal")


def main() -> int:
    log = configurar_log()
    OUTPUT.mkdir(exist_ok=True)
    log.info("Iniciando relatório semanal")
    # TODO: carregar dados, calcular indicadores e salvar em OUTPUT
    log.info("Relatório finalizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
