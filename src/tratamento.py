"""Funções de leitura e tratamento dos dados brutos em data/raw/."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA_RAW = RAIZ / "data" / "raw"


def carregar_dados(nome_arquivo: str):
    """Carrega um arquivo de data/raw/. TODO: implementar."""
    raise NotImplementedError


def tratar(df):
    """Aplica limpeza e padronização nos dados. TODO: implementar."""
    raise NotImplementedError
