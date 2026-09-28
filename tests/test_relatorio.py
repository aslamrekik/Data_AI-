"""Testes da Parte 2: o relatório roda na base real e falha de forma controlada."""
import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "parte2_relatorio/relatorio_semanal.py"
CSV = RAIZ / "data/raw/propostas_credito.csv"


def rodar(*args, saida):
    """Sempre com --saida: teste nunca grava em parte2_relatorio/output/ (foi o que contaminou o
    HTML de exemplo com o CSV de teste)."""
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--saida", str(saida)],
                          capture_output=True, text=True)


def test_gera_html_na_base_real(tmp_path):
    r = rodar("--referencia", "2025-06-16", saida=tmp_path)
    assert r.returncode == 0, r.stderr
    html = (tmp_path / "relatorio_funil_2025-06-16.html").read_text(encoding="utf-8")
    for trecho in ["Propostas que entraram", "Conversão por canal", "Qualidade dos dados"]:
        assert trecho in html


def test_coluna_faltando_nao_gera_relatorio(tmp_path):
    arq = tmp_path / "sem_coluna.csv"
    pd.read_csv(CSV, dtype=str, encoding="utf-8-sig").drop(columns=["score_credito"]).to_csv(arq, index=False)
    r = rodar("--entrada", str(arq), saida=tmp_path)
    assert r.returncode == 1
    assert "score_credito" in r.stderr


def test_arquivo_inexistente(tmp_path):
    assert rodar("--entrada", str(tmp_path / "nao_existe.csv"), saida=tmp_path).returncode == 1


def test_arquivo_vazio(tmp_path):
    arq = tmp_path / "vazio.csv"
    arq.write_text("", encoding="utf-8")
    assert rodar("--entrada", str(arq), saida=tmp_path).returncode == 1


def test_coluna_extra_e_canal_novo_nao_quebram(tmp_path):
    d = pd.read_csv(CSV, dtype=str, encoding="utf-8-sig")
    d["coluna_nova"] = "x"
    d.loc[0, "canal_origem"] = "TikTok"
    arq = tmp_path / "formato_novo.csv"
    d.to_csv(arq, index=False)
    assert rodar("--entrada", str(arq), "--referencia", "2025-06-16", saida=tmp_path).returncode == 0


# ---------------------------------------------------------------- revisão: relatório com número errado
import pytest  # noqa: E402

sys.path.insert(0, str(RAIZ / "parte2_relatorio"))
import relatorio_semanal as rs  # noqa: E402


@pytest.fixture(scope="module")
def base():
    df, reg = rs.t.tratar(rs.t.carregar_bruto(CSV))
    return df, reg.to_frame()


@pytest.mark.parametrize("referencia", ["2026-03-02", "2025-12-29", "2024-01-01"])
def test_semana_fora_da_base_ou_incompleta_falha(referencia, tmp_path):
    # antes: relatório com KPIs zerados (2026) ou "▼ 85%" numa semana com 1 dia de dados (29/12)
    r = rodar("--referencia", referencia, saida=tmp_path)
    assert r.returncode == 1 and "fora da base ou incompleta" in r.stderr


def test_media_usa_so_semanas_anteriores_que_existem(base):
    df, reg_df = base
    b = rs.t.base_analise(df)
    # base começa em 11/01/2024 (quinta): a semana de 08/01 não está inteira na base
    inicio, fim = rs.semana_referencia(df, "2024-01-22")
    m = rs.calcular(df, inicio, fim)
    assert m["n_hist"] == 1
    _, media, _ = m["kpis"]["Propostas que entraram"]
    assert media == ((b["data_entrada"] >= "2024-01-15") & (b["data_entrada"] < "2024-01-22")).sum()
    # 15/01: nenhuma semana anterior inteira -> sem comparação (antes: "▲ 367%" dividindo por 4)
    inicio, fim = rs.semana_referencia(df, "2024-01-15")
    m = rs.calcular(df, inicio, fim)
    html = rs.gerar_html(m, reg_df, inicio, fim, "x.csv", len(df))
    assert m["n_hist"] == 0 and "sem semanas anteriores na base para comparar" in html and "%" not in \
        html.split('class="cards"')[1].split("</div></div></div>")[0].split("Propostas que entraram")[1][:200]


def test_sem_coorte_madura_nao_mostra_nan(base):
    df, reg_df = base
    inicio, fim = rs.semana_referencia(df, "2024-03-04")
    m = rs.calcular(df, inicio, fim)
    assert m["n_madura"] == 0
    html = rs.gerar_html(m, reg_df, inicio, fim, "x.csv", len(df))
    assert "nan" not in html.lower().replace("nanceir", "") and "Ainda não há coortes maduras" in html


def test_numeros_do_cabecalho_em_pt_br(tmp_path):
    rodar("--referencia", "2025-06-16", saida=tmp_path)
    html = (tmp_path / "relatorio_funil_2025-06-16.html").read_text(encoding="utf-8")
    assert "6.400 propostas" in html and "6,400" not in html


def test_rotulo_do_grafico_e_a_segunda_feira(base):
    df, _ = base
    inicio, fim = rs.semana_referencia(df, "2025-06-16")
    s = rs.calcular(df, inicio, fim)["semanal"]
    assert rs.rotulos_semana(s.index)[-1] == inicio.strftime("%d/%m") == "16/06"


def test_saida_vai_para_a_pasta_pedida(tmp_path):
    destino = tmp_path / "outra" / "pasta"
    assert rodar("--referencia", "2025-06-16", saida=destino).returncode == 0
    assert [p.name for p in destino.iterdir()] == ["relatorio_funil_2025-06-16.html"]


def test_qualidade_dos_dados_mostra_so_problemas(base):
    df, reg_df = base
    inicio, fim = rs.semana_referencia(df, "2025-06-16")
    html = rs.gerar_html(rs.calcular(df, inicio, fim), reg_df, inicio, fim, "x.csv", len(df))
    tabela = html.split("Qualidade dos dados")[1]
    assert "Canal com variações de escrita" in tabela
    for informativo in reg_df.loc[reg_df["tipo"] == "informativo", "problema"]:
        assert informativo not in tabela            # ltv calculada, taxa renomeada, Terreno...
