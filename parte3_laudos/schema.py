"""Parte 3 — Schema dos campos extraídos dos laudos."""
from dataclasses import dataclass, asdict


@dataclass
class Laudo:
    arquivo: str
    # TODO: definir os campos a extrair

    def to_dict(self) -> dict:
        return asdict(self)
