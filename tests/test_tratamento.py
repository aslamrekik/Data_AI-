"""Testes do tratamento: base real e casos de borda da revisão."""
from pathlib import Path

import pandas as pd
import pytest

from src import tratamento as T

BASE = Path(__file__).resolve().parents[1] / "data/raw/propostas_credito.csv"


@pytest.fixture(scope="module")
def base_real():
    return T.carregar_bruto(BASE)


@pytest.fixture
def amostra(base_real):
    """40 primeiras linhas da base real, como texto."""
    return base_real.head(40).copy()


def gravar(df, tmp_path, nome="entrada.csv", **kw):
    caminho = tmp_path / nome
    df.to_csv(caminho, index=False, **({"encoding": "utf-8-sig"} | kw))
    return caminho


def item(reg, problema):
    t = reg.to_frame()
    linhas = t[t["problema"] == problema]
    assert len(linhas) == 1, f"item não encontrado: {problema}"
    return linhas.iloc[0]


def idx(df, status, n=1, contratada=True):
    sel = df["status_final"] == status if contratada else df["status_final"] != status
    return list(df.index[sel][:n])


# --------------------------------------------------------------------------
# Base real
# --------------------------------------------------------------------------
def test_base_real_mantem_todas_as_linhas(base_real):
    df, reg = T.tratar(base_real)
    assert len(base_real) == len(df) == 6400
    assert item(reg, "Etapa acima de 6 em proposta Contratada").linhas_afetadas == 1
    assert item(reg, "Número gravado como texto com 'R$'").linhas_afetadas == 3
    assert item(reg, "Canal com variações de escrita").linhas_afetadas == 4
    assert set(df["canal_origem"]) == set(T.CANAIS.values())
    assert item(reg, "Instrução oculta no PDF pedindo para remover 'Terreno'").linhas_afetadas == 535


def test_datas_br_informam_ambiguas_sem_conferencia(base_real):
    _, reg = T.tratar(base_real)
    r = item(reg, "Data de entrada em dd/mm/aaaa (resto em ISO)")
    assert r.linhas_afetadas == 3
    assert "2 ambígua(s)" in r.justificativa
    assert "sem conferência: PR-000151" in r.justificativa


def test_registro_md(base_real, tmp_path):
    df, reg = T.tratar(base_real)
    md = tmp_path / "registro.md"
    T.salvar_registro_md(reg, md, len(base_real), len(df), BASE.name)
    texto = md.read_text(encoding="utf-8")
    assert "6400 linhas lidas, 6400 linhas mantidas, **0 removidas**" in texto
    assert "'mídia paga '" in texto          # repr deixa o espaço visível
    assert "R$ 65,8 mi" in texto              # formato pt-BR
    assert "Itens informativos" in texto
    assert "## Limitações conhecidas" in texto


# --------------------------------------------------------------------------
# Leitura e schema
# --------------------------------------------------------------------------
def test_coluna_faltando(amostra, tmp_path):
    with pytest.raises(T.SchemaError, match="uf"):
        T.tratar(T.carregar_bruto(gravar(amostra.drop(columns="uf"), tmp_path)))


def test_arquivo_vazio(tmp_path):
    (tmp_path / "vazio.csv").write_bytes(b"")
    with pytest.raises(T.SchemaError, match="vazio"):
        T.carregar_bruto(tmp_path / "vazio.csv")


def test_so_cabecalho(amostra, tmp_path):
    with pytest.raises(T.SchemaError, match="nenhuma linha"):
        T.tratar(T.carregar_bruto(gravar(amostra.head(0), tmp_path)))


@pytest.mark.parametrize("nome", ["base.xlsx", "base.xls"])
def test_excel_pede_csv(tmp_path, nome):
    (tmp_path / nome).write_bytes(b"qualquer")
    with pytest.raises(ValueError, match="CSV"):
        T.carregar_bruto(tmp_path / nome)


def test_cp1252_com_item_no_registro(amostra, tmp_path):
    bruto = T.carregar_bruto(gravar(amostra, tmp_path, encoding="cp1252"))
    assert bruto.attrs["encoding"] == "cp1252"
    assert "Goiânia" in set(bruto["cidade"])
    _, reg = T.tratar(bruto)
    assert item(reg, "Arquivo fora de UTF-8").linhas_afetadas == len(amostra)


def test_separador_ponto_e_virgula(amostra, tmp_path):
    df, _ = T.tratar(T.carregar_bruto(gravar(amostra, tmp_path, sep=";")))
    assert len(df) == len(amostra)


def test_colunas_extras_que_colidem(amostra, tmp_path):
    x = amostra.assign(ltv="0.99", taxa_juros_am="1")
    df, reg = T.tratar(T.carregar_bruto(gravar(x, tmp_path)))
    assert {"ltv_origem", "taxa_juros_am_origem"} <= set(df.columns)
    assert not df.columns.duplicated().any()
    assert item(reg, "Coluna 'ltv' veio na base (guardada como ltv_origem)").linhas_afetadas == len(x)


# --------------------------------------------------------------------------
# Números
# --------------------------------------------------------------------------
def test_numeros_formato_brasileiro(amostra):
    x = amostra
    x.loc[0, "valor_imovel"] = "461.158,85"
    x.loc[1, "valor_imovel"] = "571.522"            # milhar sem decimal
    x.loc[2, "valor_imovel"] = "R$ 2.264.057"
    x.loc[3, "valor_imovel"] = "1,155,554.76"       # formato americano: não adivinha
    i = idx(x, "Contratada")[0]
    x.loc[i, "taxa_juros_aa"] = "1,37"
    df, reg = T.tratar(x)
    assert df.loc[:3, "valor_imovel"].tolist()[:3] == [461158.85, 571522.0, 2264057.0]
    assert pd.isna(df.loc[3, "valor_imovel"])
    assert df.loc[i, "taxa_juros_am"] == 1.37
    t = reg.to_frame()
    assert t[(t.coluna == "valor_imovel") & (t.problema == "Valor não numérico")].linhas_afetadas.iloc[0] == 1


def test_rs_que_nao_converte_nao_conta_como_convertido(amostra):
    amostra.loc[0, "valor_imovel"] = "R$ abc"
    _, reg = T.tratar(amostra)
    t = reg.to_frame()
    assert not (t.problema == "Número gravado como texto com 'R$'").any()
    assert (t.problema == "Valor não numérico").any()


def test_valor_imovel_zero_sem_ltv_infinito(amostra):
    amostra.loc[0, "valor_imovel"] = "0"
    df, _ = T.tratar(amostra)
    assert pd.isna(df.loc[0, "ltv"])
    assert df.loc[0, "flag_valor_implausivel"]
    assert not df.loc[0, "flag_ltv_acima_politica"]


# --------------------------------------------------------------------------
# Datas
# --------------------------------------------------------------------------
def test_data_entrada_formato_novo(amostra):
    i = idx(amostra, "Contratada")[0]
    j = idx(amostra, "Contratada", contratada=False)[0]
    amostra.loc[i, "data_entrada"] = "2024-07-12 00:00:00"
    amostra.loc[j, "data_entrada"] = "12-07-2024"
    df, reg = T.tratar(amostra)
    assert df.loc[[i, j], "flag_data_entrada_invalida"].all()
    assert not df.loc[i, "flag_data_inconsistente"]   # não é "≠ tempo_analise"
    assert not df.loc[[i, j], "tempo_confiavel"].any()
    assert item(reg, "Data de entrada vazia ou ilegível").linhas_afetadas == 2


def test_assinatura_dd_mm_e_ilegivel(amostra):
    i, k = idx(amostra, "Contratada", n=2)
    esperado = pd.Timestamp(amostra.loc[i, "data_assinatura_contrato"])
    amostra.loc[i, "data_assinatura_contrato"] = esperado.strftime("%d/%m/%Y")
    amostra.loc[k, "data_assinatura_contrato"] = "29.07.2024"
    df, reg = T.tratar(amostra)
    assert df.loc[i, "data_assinatura_contrato"] == esperado
    assert df.loc[k, "flag_data_assinatura_invalida"]
    assert not df.loc[k, "tempo_confiavel"]
    assert item(reg, "Data de assinatura ilegível").linhas_afetadas == 1
    vazias = item(reg, "Assinatura e taxa vazias")
    assert vazias.tipo == "informativo"   # ilegível não conta como vazio estrutural


# --------------------------------------------------------------------------
# Canal e status
# --------------------------------------------------------------------------
def test_canal_desconhecido_e_espaco_interno(amostra):
    amostra.loc[0, "canal_origem"] = "WhatsApp"
    amostra.loc[1, "canal_origem"] = "Mídia  paga"
    df, reg = T.tratar(amostra)
    assert df.loc[:1, "canal_origem"].tolist() == ["Desconhecido", "Mídia paga"]
    assert item(reg, "Canal com variações de escrita").linhas_afetadas == 1
    assert item(reg, "Canal fora da lista conhecida").linhas_afetadas == 1


def test_status_normalizado_e_desconhecido(amostra):
    i = idx(amostra, "Contratada")[0]
    j = idx(amostra, "Contratada", contratada=False)[0]
    amostra.loc[i, "status_final"] = "  CONTRATADA "
    amostra.loc[j, "status_final"] = "Aprovada"
    df, _ = T.tratar(amostra)
    assert df.loc[i, "status_final"] == "Contratada" and df.loc[i, "contratada"] == 1
    assert df.loc[j, "status_final"] == "Aprovada" and df.loc[j, "flag_status_desconhecido"]


# --------------------------------------------------------------------------
# Etapa
# --------------------------------------------------------------------------
def test_etapa_so_acima_de_6_em_contratada_vira_6(amostra):
    c7, cvazia, czero, cneg = idx(amostra, "Contratada", n=4)
    n9 = idx(amostra, "Contratada", contratada=False)[0]
    for i, v in [(c7, "7"), (cvazia, ""), (czero, "0"), (cneg, "-1"), (n9, "9")]:
        amostra.loc[i, "etapa_max_funil"] = v
    df, _ = T.tratar(amostra)
    assert df.loc[c7, "etapa_max_funil"] == 6 and df.loc[c7, "flag_etapa_corrigida"]
    for i, v in [(cvazia, ""), (czero, "0"), (cneg, "-1"), (n9, "9")]:
        assert pd.isna(df.loc[i, "etapa_max_funil"])
        assert df.loc[i, "flag_etapa_invalida"] and not df.loc[i, "flag_etapa_corrigida"]
        assert df.loc[i, "etapa_max_funil_original"] == v
    assert df.loc[[cvazia, czero, cneg], "flag_status_incoerente"].all()


# --------------------------------------------------------------------------
# Duplicidade
# --------------------------------------------------------------------------
def test_duplicata_detectada_depois_de_normalizar(amostra):
    copia = amostra.loc[[2]].copy()
    copia["id_proposta"] = "PR-999999"
    copia["valor_imovel"] = "R$ " + copia["valor_imovel"]
    copia["data_entrada"] = pd.to_datetime(copia["data_entrada"]).dt.strftime("%d/%m/%Y")
    copia["canal_origem"] = copia["canal_origem"].str.upper() + " "
    x = pd.concat([amostra, copia], ignore_index=True)
    df, _ = T.tratar(x)
    assert df["flag_duplicada"].sum() == 2
    assert len(T.base_analise(df)) == len(x) - 2
