"""Parte 3 — Compara a saída do extrator com o gabarito."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent


def carregar(nome: str) -> list[dict]:
    return json.loads((BASE / nome).read_text(encoding="utf-8"))


def avaliar(previsto: list[dict], gabarito: list[dict]) -> dict:
    """Calcula a acurácia por campo, casando registros pela chave 'arquivo'."""
    por_arquivo = {r["arquivo"]: r for r in previsto}
    acertos, total = {}, {}
    for esperado in gabarito:
        obtido = por_arquivo.get(esperado["arquivo"], {})
        for campo, valor in esperado.items():
            if campo == "arquivo":
                continue
            total[campo] = total.get(campo, 0) + 1
            acertos[campo] = acertos.get(campo, 0) + (obtido.get(campo) == valor)
    return {c: acertos[c] / total[c] for c in total}


if __name__ == "__main__":
    for campo, acc in avaliar(carregar("resultado.json"), carregar("gabarito.json")).items():
        print(f"{campo}: {acc:.1%}")
