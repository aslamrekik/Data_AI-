"""Testes da Parte 2: o relatório roda na base real e falha de forma controlada."""
import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "parte2_relatorio/relatorio_semanal.py"
CSV = RAIZ / "data/raw/propostas_credito.csv"


def rodar(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_gera_html_na_base_real():
    r = rodar("--referencia", "2025-06-16")
    assert r.returncode == 0, r.stderr
    html = (RAIZ / "parte2_relatorio/output/relatorio_funil_2025-06-16.html").read_text(encoding="utf-8")
    for trecho in ["Propostas que entraram", "Conversão por canal", "Qualidade dos dados"]:
        assert trecho in html


def test_coluna_faltando_nao_gera_relatorio(tmp_path):
    arq = tmp_path / "sem_coluna.csv"
    pd.read_csv(CSV, dtype=str, encoding="utf-8-sig").drop(columns=["score_credito"]).to_csv(arq, index=False)
    r = rodar("--entrada", str(arq))
    assert r.returncode == 1
    assert "score_credito" in r.stderr


def test_arquivo_inexistente(tmp_path):
    assert rodar("--entrada", str(tmp_path / "nao_existe.csv")).returncode == 1


def test_arquivo_vazio(tmp_path):
    arq = tmp_path / "vazio.csv"
    arq.write_text("", encoding="utf-8")
    assert rodar("--entrada", str(arq)).returncode == 1


def test_coluna_extra_e_canal_novo_nao_quebram(tmp_path):
    d = pd.read_csv(CSV, dtype=str, encoding="utf-8-sig")
    d["coluna_nova"] = "x"
    d.loc[0, "canal_origem"] = "TikTok"
    arq = tmp_path / "formato_novo.csv"
    d.to_csv(arq, index=False)
    assert rodar("--entrada", str(arq), "--referencia", "2025-06-16").returncode == 0
