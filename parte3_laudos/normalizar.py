"""
normalizar.py — Converte o texto literal devolvido pelo LLM no formato final.

Tudo aqui é determinístico e testável. Se um valor não normaliza, a função
levanta ValueError e o campo é rebaixado para "nao_verificado": melhor não
saber do que chutar.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from schema import CAMPOS, SITUACOES_ONUS, TIPOS_IMOVEL, CampoFinal, CampoLLM, RespostaLLM

CAMPOS_AREA = {"area_privativa_m2", "area_total_m2", "area_construida_m2", "area_terreno_m2"}
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


# ----------------------------------------------------------------------------
# Texto
# ----------------------------------------------------------------------------
def sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c))


def compactar(txt: str) -> str:
    """Minúsculas, sem acento e com espaços colapsados: base da checagem de evidência."""
    return " ".join(sem_acento(txt).lower().split())


def evidencia_existe(trecho: str | None, documento: str) -> bool:
    """O trecho citado pelo LLM precisa existir no laudo (ignorando caixa, acento e espaços)."""
    return bool(trecho) and compactar(trecho) in compactar(documento)


# ----------------------------------------------------------------------------
# Números, datas, anos
# ----------------------------------------------------------------------------
def numero_br(txt: str) -> float:
    """'78,40 m²' -> 78.4 | 'R$ 3.900.000' -> 3900000 | '4,8 ha' -> 48000 (m²)."""
    alvo = txt.split("R$", 1)[1] if "R$" in txt else txt  # valor por extenso + (R$ ...)
    m = re.search(r"\d[\d.,]*", alvo)
    if not m:
        raise ValueError(f"sem número em {txt!r}")
    bruto = m.group().rstrip(".,")
    if "," in bruto:
        n = float(bruto.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", bruto):
        n = float(bruto.replace(".", ""))
    else:
        n = float(bruto)
    if re.search(r"\bha\b|hectare", alvo, flags=re.I):
        n *= 10_000
    return n


def data_iso(txt: str) -> str:
    """'12/03/2025', '20-04-2025', '22 de março de 2025', '2025-03-12' -> '2025-03-12'."""
    t = compactar(txt)
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", t):
        a, mes, d = map(int, m.groups())
    elif m := re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", t):
        d, mes, a = map(int, m.groups())
    elif m := re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", t):
        d, mes, a = int(m.group(1)), MESES.get(m.group(2)), int(m.group(3))
        if mes is None:
            raise ValueError(f"mês desconhecido em {txt!r}")
    else:
        raise ValueError(f"data não reconhecida em {txt!r}")
    return date(a, mes, d).isoformat()  # date() rejeita 31/02 etc.


def ano(txt: str, status: str, ano_vistoria: int | None) -> int:
    """Ano explícito ('2014') ou, se inferido, ano da vistoria menos a idade ('11 anos')."""
    if status == "inferido" and re.search(r"\banos?\b", txt, flags=re.I):
        if ano_vistoria is None:
            raise ValueError("idade informada, mas sem data de vistoria para calcular o ano")
        idade = re.search(r"\d+", txt)
        if not idade:
            raise ValueError(f"idade sem número em {txt!r}")
        return ano_vistoria - int(idade.group())
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", txt)
    if not m:
        raise ValueError(f"ano não reconhecido em {txt!r}")
    return int(m.group())


def matricula(txt: str) -> str:
    """'184.772 do 14º CRI' -> '184772' (só o primeiro número)."""
    m = re.search(r"\d[\d.]*", txt)
    if not m:
        raise ValueError(f"matrícula sem número em {txt!r}")
    return m.group().rstrip(".").replace(".", "")


def categoria(txt: str, permitidas: list[str]) -> str:
    c = compactar(txt).replace(" ", "_")
    if c not in permitidas:
        raise ValueError(f"categoria {txt!r} fora de {permitidas}")
    return c


# ----------------------------------------------------------------------------
# Campo a campo
# ----------------------------------------------------------------------------
def _converter(nome: str, txt: str, status: str, ano_vistoria: int | None):
    if nome in CAMPOS_AREA or nome == "valor_avaliacao":
        return numero_br(txt)
    if nome == "ano_construcao":
        return ano(txt, status, ano_vistoria)
    if nome == "data_vistoria":
        return data_iso(txt)
    if nome == "matricula":
        return matricula(txt)
    if nome == "uf":
        uf = txt.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", uf):
            raise ValueError(f"UF inválida {txt!r}")
        return uf
    if nome == "tipo_imovel":
        return categoria(txt, TIPOS_IMOVEL)
    if nome == "onus_situacao":
        return categoria(txt, SITUACOES_ONUS)
    return " ".join(txt.split())  # textos livres


def normalizar_campo(nome: str, c: CampoLLM, documento: str,
                     ano_vistoria: int | None) -> CampoFinal:
    # onus_situacao é uma classificação sempre preenchida (regra do gabarito)
    if nome == "onus_situacao" and c.status in ("nao_informado", "nao_aplicavel"):
        return CampoFinal(valor="nao_informado", status="encontrado", trecho_fonte=c.trecho_fonte)

    if c.status in ("nao_informado", "nao_aplicavel"):
        return CampoFinal(valor=None, status=c.status, trecho_fonte=c.trecho_fonte)

    # A partir daqui o campo TEM valor: exige evidência literal no laudo
    if nome != "onus_situacao" and not evidencia_existe(c.trecho_fonte, documento):
        return CampoFinal(status="nao_verificado", trecho_fonte=c.trecho_fonte,
                          motivo="trecho_fonte não encontrado no laudo")
    try:
        if c.status == "contraditorio":
            brutos = c.valores_conflitantes or []
            if len(brutos) < 2:
                raise ValueError("contraditório com menos de dois valores")
            valor = [_converter(nome, v, "encontrado", ano_vistoria) for v in brutos]
        else:
            if not c.valor_texto:
                raise ValueError("status com valor, mas valor_texto vazio")
            valor = _converter(nome, c.valor_texto, c.status, ano_vistoria)
    except ValueError as e:
        return CampoFinal(status="nao_verificado", trecho_fonte=c.trecho_fonte, motivo=str(e))
    return CampoFinal(valor=valor, status=c.status, trecho_fonte=c.trecho_fonte)


def normalizar_resposta(r: RespostaLLM, documento: str) -> dict[str, CampoFinal]:
    # a data da vistoria vem primeiro: o ano inferido depende dela
    data = normalizar_campo("data_vistoria", r.data_vistoria, documento, None)
    ano_vist = int(data.valor[:4]) if isinstance(data.valor, str) else None
    campos = {n: normalizar_campo(n, getattr(r, n), documento, ano_vist) for n in CAMPOS}
    campos["data_vistoria"] = data
    return campos
