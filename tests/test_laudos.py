"""Testes da Parte 3 sem chamar a API: o LLM é simulado com respostas fixas."""
import copy
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "parte3_laudos"))

import avaliar as av  # noqa: E402
import normalizar as nz  # noqa: E402
from schema import CAMPOS, LaudoExtraido, RespostaLLM  # noqa: E402

LAUDOS = RAIZ / "data/raw/laudos"
GABARITO = json.loads((RAIZ / "parte3_laudos/gabarito.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- normalizadores
@pytest.mark.parametrize("txt, esperado", [
    ("78,40 m²", 78.4), ("R$ 642.000,00", 642000), ("R$ 3.900.000", 3900000),
    ("1.020 m2", 1020), ("4,8 ha", 48000), ("146,00 m2", 146),
    ("seiscentos e oitenta mil reais (R$ 680.000)", 680000), ("96,3 m²", 96.3),
])
def test_numero_br(txt, esperado):
    assert nz.numero_br(txt) == pytest.approx(esperado)


@pytest.mark.parametrize("txt, esperado", [
    ("12/03/2025", "2025-03-12"), ("20-04-2025", "2025-04-20"),
    ("22 de março de 2025", "2025-03-22"), ("2025-06-05", "2025-06-05"),
])
def test_data_iso(txt, esperado):
    assert nz.data_iso(txt) == esperado


def test_data_invalida_falha():
    with pytest.raises(ValueError):
        nz.data_iso("31/02/2025")


def test_ano_inferido_da_idade():
    assert nz.ano("11 anos", "inferido", 2025) == 2014
    assert nz.ano("aproximadamente 18 anos", "inferido", 2025) == 2007
    assert nz.ano("2014", "encontrado", 2025) == 2014
    with pytest.raises(ValueError):
        nz.ano("11 anos", "inferido", None)  # sem vistoria não dá para calcular


def test_matricula_pega_so_o_primeiro_numero():
    assert nz.matricula("184.772 do 14º CRI de São Paulo") == "184772"


def test_categoria_fora_da_lista_falha():
    with pytest.raises(ValueError):
        nz.categoria("chácara", ["casa", "rural"])


def test_evidencia_ignora_caixa_acento_e_espaco():
    doc = "Área privativa: 78,40 m²  | área total"
    assert nz.evidencia_existe("area PRIVATIVA: 78,40 m²", doc)
    assert not nz.evidencia_existe("Área privativa: 80 m²", doc)
    assert not nz.evidencia_existe(None, doc)


# ---------------------------------------------------------------- pipeline com LLM falso
def _resposta(**campos):
    base = {c: {"valor_texto": None, "status": "nao_informado", "trecho_fonte": None} for c in CAMPOS}
    base.update(campos)
    return RespostaLLM.model_validate(base)


def test_valor_sem_evidencia_e_rebaixado():
    doc = (LAUDOS / "laudo_01.txt").read_text(encoding="utf-8")
    r = _resposta(valor_avaliacao={"valor_texto": "R$ 700.000,00", "status": "encontrado",
                                   "trecho_fonte": "Valor de avaliação: R$ 700.000,00"})
    campos = nz.normalizar_resposta(r, doc)
    assert campos["valor_avaliacao"].status == "nao_verificado"
    assert campos["valor_avaliacao"].valor is None


def test_laudo_17_contraditorio_e_laudo_03_inferido():
    doc17 = (LAUDOS / "laudo_17.txt").read_text(encoding="utf-8")
    r = _resposta(area_total_m2={"valor_texto": None, "status": "contraditorio",
                                 "trecho_fonte": "No cabeçalho consta área total 95 m², porém a tabela interna registra 92 m²",
                                 "valores_conflitantes": ["95 m²", "92 m²"]})
    assert nz.normalizar_resposta(r, doc17)["area_total_m2"].valor == [95.0, 92.0]

    doc03 = (LAUDOS / "laudo_03.txt").read_text(encoding="utf-8")
    r = _resposta(
        data_vistoria={"valor_texto": "22 de março de 2025", "status": "encontrado",
                       "trecho_fonte": "Em 22 de março de 2025 vistoriamos"},
        ano_construcao={"valor_texto": "11 anos", "status": "inferido",
                        "trecho_fonte": "Idade aparente: 11 anos"})
    c = nz.normalizar_resposta(r, doc03)
    assert c["ano_construcao"].valor == 2014 and c["ano_construcao"].status == "inferido"


def test_onus_silencioso_vira_nao_informado_e_nunca_sem_onus():
    doc = (LAUDOS / "laudo_14.txt").read_text(encoding="utf-8")
    r = _resposta(onus_situacao={"valor_texto": None, "status": "nao_informado", "trecho_fonte": None})
    c = nz.normalizar_resposta(r, doc)["onus_situacao"]
    assert (c.valor, c.status) == ("nao_informado", "encontrado")


def test_laudo_com_falha_mantem_o_formato():
    x = LaudoExtraido.vazio("laudo_99.txt", "modelo", "TimeoutError")
    assert set(x.campos) == set(CAMPOS)
    assert all(c.status == "nao_verificado" for c in x.campos.values())


# ---------------------------------------------------------------- avaliação
def _extracao_perfeita():
    return {k: {"campos": {c: {"valor": v[c]["valor"], "status": v[c]["status"]} for c in CAMPOS}}
            for k, v in GABARITO["laudos"].items()}


def test_extracao_igual_ao_gabarito_da_100():
    r = av.resumo(av.avaliar(GABARITO, _extracao_perfeita()))
    assert r["acurácia estrita (valor + status)"] == 1.0
    assert r["alucinações (valor onde não existe)"] == 0


def test_alucinacao_e_abstencao_sao_contadas_separadamente():
    ext = copy.deepcopy(_extracao_perfeita())
    ext["laudo_08"]["campos"]["matricula"] = {"valor": "12345", "status": "encontrado"}  # não existe
    ext["laudo_01"]["campos"]["valor_avaliacao"] = {"valor": None, "status": "nao_verificado"}
    df = av.avaliar(GABARITO, ext)
    assert df.query("laudo == 'laudo_08' and campo == 'matricula'")["resultado"].item() == "alucinacao"
    assert df.query("laudo == 'laudo_01' and campo == 'valor_avaliacao'")["resultado"].item() == "abstencao"


def test_laudo_ausente_conta_como_abstencao_e_nao_quebra():
    ext = _extracao_perfeita()
    del ext["laudo_05"]
    df = av.avaliar(GABARITO, ext)
    assert (df.query("laudo == 'laudo_05'")["resultado"] != "alucinacao").all()


@pytest.mark.parametrize("campo, esperado, obtido, ok", [
    ("valor_avaliacao", 642000, 642500, True),     # 0,08%
    ("valor_avaliacao", 642000, 700000, False),
    ("endereco", "Rua das Acácias, 145, ap. 82 - Vila Mariana",
                 "Rua das Acacias 145 ap 82 Vila Mariana", True),
    ("uf", "SP", "sp", True),
    ("area_total_m2", [95.0, 92.0], [92.0, 95.0], True),
    ("area_total_m2", [95.0, 92.0], 95.0, False),
])
def test_equivalencia(campo, esperado, obtido, ok):
    assert av.equivale(campo, esperado, obtido) is ok
