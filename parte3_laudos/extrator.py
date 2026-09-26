"""Parte 3 — Extração de informações dos laudos."""
import json
import sys
from pathlib import Path

from schema import Laudo

BASE = Path(__file__).resolve().parent


def extrair(caminho: Path) -> Laudo:
    """Extrai os campos de um laudo. TODO: implementar."""
    raise NotImplementedError


def main(pasta: str) -> None:
    resultados = [extrair(p).to_dict() for p in sorted(Path(pasta).iterdir()) if p.is_file()]
    (BASE / "resultado.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
