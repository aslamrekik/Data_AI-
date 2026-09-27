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
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
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


TRECHO_MIN = 6                                  # "SP" ou "2" existem em qualquer laudo: não provam nada
CATEGORICOS = {"tipo_imovel", "onus_situacao"}  # valor é uma categoria, não um texto copiado
_AREA = r"area|m2|ha|hectares?|lote|terreno|superficie|coberta|benfeitorias?"
# O trecho precisa falar DO CAMPO: "12345" copiado de "CNAI 12345" não é matrícula.
ANCORAS = {
    "matricula": r"matricula|registro|rgi|cri|oficio|cartorio",
    "valor_avaliacao": r"r|valor|avaliacao|preco|mercado",
    "data_vistoria": r"vistori\w*|inspe\w*|visita|levantamento|data",
    "ano_construcao": r"ano|anos|constru\w*|idade|edifica\w*|conclusao",
    "responsavel_registro": r"crea|cau|cnai|registro",
    **{c: _AREA for c in ("area_privativa_m2", "area_total_m2", "area_construida_m2", "area_terreno_m2")},
}


def palavras(txt: str) -> str:
    """compactar() sem pontuação: 'R$ 642.000,00' -> 'r 642 000 00'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", compactar(txt)).split())


def contido(parte: str | None, texto: str | None) -> bool:
    """`parte` aparece em `texto` palavra a palavra ('12345' não casa com '112345')."""
    return bool(parte and texto and palavras(parte)) and f" {palavras(parte)} " in f" {palavras(texto)} "


def ancorado(campo: str, trecho: str | None) -> bool:
    """O trecho contém uma palavra que identifica o campo (quando o campo tem âncora)."""
    padrao = ANCORAS.get(campo)
    return padrao is None or bool(re.search(rf"\b(?:{padrao})\b", palavras(trecho or "")))


TEXTOS_LIVRES = {"endereco", "cidade", "onus_descricao", "responsavel_nome"}


def valor_no_trecho(campo: str, valor: str, trecho: str | None) -> bool:
    """Números, datas e códigos: sequência exata dentro do trecho. Textos livres: toda palavra
    do valor está no trecho (o endereço sem cidade/UF pode não ser contíguo no laudo)."""
    if campo in TEXTOS_LIVRES:
        return bool(palavras(valor)) and set(palavras(valor).split()) <= set(palavras(trecho or "").split())
    return contido(valor, trecho)


def evidencia_existe(trecho: str | None, documento: str) -> bool:
    """O trecho citado pelo LLM precisa existir no laudo (ignorando caixa, acento, espaços e
    pontuação) e ter tamanho mínimo."""
    return bool(trecho) and len(palavras(trecho)) >= TRECHO_MIN and contido(trecho, documento)


# ----------------------------------------------------------------------------
# Números, datas, anos
# ----------------------------------------------------------------------------
def numero_br(txt: str) -> float:
    """'78,40 m²' -> 78.4 | 'R$ 3.900.000' -> 3900000 | '4,8 ha' -> 48000 (m²) | 'R$ 3,9 milhões' -> 3900000.

    Exige exatamente UM número (sem contar o '2' de 'm2'): um texto com dois
    números ('privativa 61 m² e total 84 m²') é ambíguo e falha.
    """
    alvo = txt.split("R$", 1)[1] if "R$" in txt else txt  # valor por extenso + (R$ ...)
    alvo = re.sub(r"(?<=[\d\s])m[2²]", " m² ", alvo)       # o '2' da unidade não é número
    numeros = re.findall(r"\d[\d.,]*", alvo)
    if not numeros:
        raise ValueError(f"sem número em {txt!r}")
    if len(numeros) > 1:
        raise ValueError(f"mais de um número em {txt!r}: ambíguo")
    bruto = numeros[0].rstrip(".,")
    if "," in bruto:
        n = float(bruto.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", bruto):
        n = float(bruto.replace(".", ""))
    else:
        n = float(bruto)
    depois = compactar(alvo[alvo.index(numeros[0]) + len(numeros[0]):])
    if re.match(r"(ha|hectares?)\b", depois):             # só a unidade logo após o número
        n *= 10_000
    elif re.match(r"(milhao|milhoes|mi)\b", depois):
        n *= 1_000_000
    elif re.match(r"mil\b", depois):
        n *= 1_000
    if n <= 0:
        raise ValueError(f"valor não positivo em {txt!r}")
    return n


def data_iso(txt: str) -> str:
    """'12/03/2025', '20-04-2025', '22 de março de 2025', '2025-03-12' -> '2025-03-12'."""
    t = compactar(txt)
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", t):
        a, mes, d = map(int, m.groups())
    elif m := re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b", t):
        d, mes, a = map(int, m.groups())
        a = a + 2000 if a < 100 else a                        # '12/03/25' -> 2025
    elif m := re.search(r"(\d{1,2})o? de ([a-z]+) de (\d{4})", t):   # '1º de abril' vira '1o de abril'
        d, mes, a = int(m.group(1)), MESES.get(m.group(2)), int(m.group(3))
        if mes is None:
            raise ValueError(f"mês desconhecido em {txt!r}")
    else:
        raise ValueError(f"data não reconhecida em {txt!r}")
    return date(a, mes, d).isoformat()  # date() rejeita 31/02 etc.


def ano(txt: str, status: str, ano_vistoria: int | None) -> int:
    """Ano explícito ('2014') ou, se inferido, ano da vistoria menos a idade ('11 anos').

    Idade é número seguido de 'ano(s)'. A palavra 'Ano' em 'Ano de referência: 2005'
    não é idade: ali o valor é o próprio ano.
    """
    idade = re.search(r"\b(\d{1,3})\s*anos?\b", txt, flags=re.I)
    if status == "inferido" and idade:
        if ano_vistoria is None:
            raise ValueError("idade informada, mas sem data de vistoria para calcular o ano")
        return ano_vistoria - int(idade.group(1))
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", txt)
    if not m:
        raise ValueError(f"ano não reconhecido em {txt!r}")
    return int(m.group())


def matricula(txt: str) -> str:
    """'184.772 do 14º CRI' -> '184772' | '3º Ofício, matrícula 45.981' -> '45981'.

    Prefere o número logo depois de 'matrícula', 'nº' ou 'registro'; sem essas
    palavras, o número mais longo (o do cartório, '14º', é curto).
    """
    t = compactar(txt)
    m = re.search(r"(?:matricula|registro|\bn[o°]\.?)[^\d]{0,20}(\d[\d.]*)", t)
    if m:
        return m.group(1).rstrip(".").replace(".", "")
    numeros = [n.rstrip(".").replace(".", "") for n in re.findall(r"\d[\d.]*", t)]
    if not numeros:
        raise ValueError(f"matrícula sem número em {txt!r}")
    return max(numeros, key=len)


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
        if uf not in UFS:
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

    rebaixar = lambda motivo: CampoFinal(status="nao_verificado", trecho_fonte=c.trecho_fonte, motivo=motivo)

    # "inferido" só existe para o ano vindo da idade; em qualquer outro campo é chute
    if c.status == "inferido" and nome != "ano_construcao":
        return rebaixar("inferido só é aceito para ano_construcao (idade -> ano)")

    # onus_situacao: "nao_informado" dispensa trecho; as outras classes precisam dele.
    # Sem trecho, a classificação volta para nao_informado: silêncio nunca é sem_onus.
    if nome == "onus_situacao":
        try:
            classe = categoria(c.valor_texto or "", SITUACOES_ONUS)
        except ValueError as e:
            return rebaixar(str(e))
        if classe != "nao_informado" and not evidencia_existe(c.trecho_fonte, documento):
            return CampoFinal(valor="nao_informado", status="encontrado", trecho_fonte=c.trecho_fonte,
                              motivo=f"'{classe}' sem trecho do laudo que a sustente")
        return CampoFinal(valor=classe, status=c.status, trecho_fonte=c.trecho_fonte)

    # A partir daqui o campo TEM valor: exige evidência literal no laudo
    if not evidencia_existe(c.trecho_fonte, documento):
        return rebaixar("trecho_fonte não encontrado no laudo (ou curto demais)")
    try:
        if c.status == "contraditorio":
            brutos = c.valores_conflitantes or []
            if len({palavras(v) for v in brutos}) < 2:
                raise ValueError("contraditório com menos de dois valores diferentes")
            fora = [v for v in brutos if not contido(v, documento)]
            if fora:
                raise ValueError(f"valores conflitantes que não estão no laudo: {fora}")
            valor = [_converter(nome, v, "encontrado", ano_vistoria) for v in brutos]
        else:
            if not c.valor_texto:
                raise ValueError("status com valor, mas valor_texto vazio")
            # o valor precisa estar DENTRO do trecho citado (categorias são classificações)
            if nome not in CATEGORICOS and not valor_no_trecho(nome, c.valor_texto, c.trecho_fonte):
                raise ValueError("valor_texto não aparece no trecho_fonte citado")
            if not ancorado(nome, c.trecho_fonte):
                raise ValueError(f"trecho_fonte não fala de {nome}")
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
