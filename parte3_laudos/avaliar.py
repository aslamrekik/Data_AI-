"""
avaliar.py — Mede a extração contra o gabarito.

Critério de acerto (por campo):
  - Gabarito SEM valor (nao_informado / nao_aplicavel):
      acerto   se o extrator também não deu valor;
      ALUCINAÇÃO se o extrator deu um valor. É o pior erro.
  - Gabarito COM valor (encontrado / inferido / contraditorio):
      acerto        se o valor equivale (regras abaixo);
      erro_valor    se deu um valor diferente;
      abstencao     se não deu valor (errou para o lado seguro).
  Equivalência de valores:
      números: diferença de até 0,5%;   datas, anos, UF, matrícula, categorias: iguais;
      registro profissional: igual, ignorando espaços e pontuação;
      textos livres: os NÚMEROS têm de ser idênticos (145 != 154) e as palavras
        (sem caixa, acento e pontuação, sem importar a ordem) têm de coincidir em
        pelo menos 80% (palavras em comum / tamanho do maior conjunto);
      contraditório: o mesmo conjunto de valores, cada um com a tolerância de 0,5%.
  Status: reportado à parte ("acerto estrito" = valor certo E status igual).
  Laudo que falhou na extração (campo "erro" preenchido, ou ausente): todos os
  campos contam como "falha_extracao", nunca como acerto.

Uso:
    python parte3_laudos/avaliar.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalizar import MOTIVO_LOCALIZADA, compactar, palavras  # noqa: E402
from schema import CAMPOS  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "parte3_laudos"
SEM_VALOR = {"nao_informado", "nao_aplicavel", "nao_verificado"}
NUMERICOS = {"area_privativa_m2", "area_total_m2", "area_construida_m2", "area_terreno_m2",
             "valor_avaliacao"}
EXATOS = {"ano_construcao", "data_vistoria", "uf", "matricula", "tipo_imovel", "onus_situacao"}
TOLERANCIA = 0.005
SIMILARIDADE_MIN = 0.80


def tabela_md(df: pd.DataFrame, index: bool = True) -> str:
    """Tabela markdown sem depender do pacote tabulate."""
    d = df.reset_index() if index else df
    cab = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "---|" * len(d.columns)
    corpo = ["| " + " | ".join("" if pd.isna(v) else str(v).replace("|", "/") for v in row) + " |"
             for row in d.itertuples(index=False)]
    return "\n".join([cab, sep, *corpo])


def _num_igual(e, o) -> bool:
    try:
        e, o = float(e), float(o)
    except (TypeError, ValueError):
        return False
    return abs(e - o) <= TOLERANCIA * max(abs(e), 1)


def _texto_equivale(esperado: str, obtido: str) -> bool:
    a, b = palavras(esperado).split(), palavras(obtido).split()
    if sorted(t for t in a if t.isdigit()) != sorted(t for t in b if t.isdigit()):
        return False                              # número de endereço/registro errado nunca é acerto
    pa, pb = set(a), set(b)
    return bool(pa or pb) and len(pa & pb) / max(len(pa), len(pb)) >= SIMILARIDADE_MIN


def equivale(campo: str, esperado, obtido) -> bool:
    if isinstance(esperado, list) or isinstance(obtido, list):
        if not (isinstance(esperado, list) and isinstance(obtido, list)) or len(esperado) != len(obtido):
            return False
        if campo in NUMERICOS:
            try:
                pares = zip(sorted(map(float, esperado)), sorted(map(float, obtido)))
            except (TypeError, ValueError):
                return False
            return all(_num_igual(e, o) for e, o in pares)
        return sorted(map(palavras, map(str, esperado))) == sorted(map(palavras, map(str, obtido)))
    if campo in NUMERICOS:
        return _num_igual(esperado, obtido)
    if campo in EXATOS:
        return compactar(str(esperado)) == compactar(str(obtido))
    if campo == "responsavel_registro":
        return palavras(str(esperado)).replace(" ", "") == palavras(str(obtido)).replace(" ", "")
    return _texto_equivale(str(esperado), str(obtido))


def classificar(campo: str, g: dict, x: dict) -> str:
    g_tem = g["status"] not in SEM_VALOR and g["valor"] is not None
    x_tem = x["status"] not in SEM_VALOR and x.get("valor") is not None
    if not g_tem:
        return "acerto" if not x_tem else "alucinacao"
    if not x_tem:
        return "abstencao"
    return "acerto" if equivale(campo, g["valor"], x["valor"]) else "erro_valor"


def avaliar(gabarito: dict, extracoes: dict) -> pd.DataFrame:
    linhas = []
    for laudo, g_campos in gabarito["laudos"].items():
        x_laudo = extracoes.get(laudo)
        falhou = x_laudo is None or bool(x_laudo.get("erro"))
        for campo in CAMPOS:
            g = g_campos[campo]
            x = (x_laudo or {}).get("campos", {}).get(campo) or {"valor": None, "status": "nao_verificado"}
            # laudo que falhou não ganha acerto nos campos vazios do gabarito
            resultado = "falha_extracao" if falhou else classificar(campo, g, x)
            linhas.append(dict(
                laudo=laudo, campo=campo, resultado=resultado,
                status_gabarito=g["status"], status_extrator=x["status"],
                status_igual=g["status"] == x["status"],
                esperado=json.dumps(g["valor"], ensure_ascii=False),
                obtido=json.dumps(x.get("valor"), ensure_ascii=False),
                motivo=x.get("motivo"),
            ))
    return pd.DataFrame(linhas)


def _localizado(df: pd.DataFrame) -> pd.Series:
    """Campos aceitos com evidência localizada pelo código (o LLM citou só o valor)."""
    return df["motivo"].fillna("").str.startswith(MOTIVO_LOCALIZADA) & ~df["status_extrator"].isin(SEM_VALOR)


def resumo(df: pd.DataFrame) -> dict:
    g_sem = df["status_gabarito"].isin(SEM_VALOR)
    extraidos = df[df["resultado"] != "falha_extracao"]
    return {
        "campos avaliados": len(df),
        "laudos com falha na extração": int(df.loc[df["resultado"] == "falha_extracao", "laudo"].nunique()),
        "acurácia (valor)": (df["resultado"] == "acerto").mean(),
        # sem isto, uma rodada interrompida pela cota parece um extrator ruim
        "acurácia nos laudos extraídos": (extraidos["resultado"] == "acerto").mean() if len(extraidos) else float("nan"),
        "acurácia estrita (valor + status)": ((df["resultado"] == "acerto") & df["status_igual"]).mean(),
        "cobertura (acertos onde o gabarito tem valor)": (df.loc[~g_sem, "resultado"] == "acerto").mean(),
        "abstenção correta (onde o gabarito não tem valor)": (df.loc[g_sem, "resultado"] == "acerto").mean(),
        "alucinações (valor onde não existe)": int((df["resultado"] == "alucinacao").sum()),
        "erros de valor": int((df["resultado"] == "erro_valor").sum()),
        "abstenções (não sabia, errou para o lado seguro)": int((df["resultado"] == "abstencao").sum()),
        "campos aceitos com evidência localizada pelo código": int(_localizado(df).sum()),
    }


def _fmt(v) -> str:
    if isinstance(v, float):
        return "n/a" if v != v else f"{v:.1%}"
    return str(v)


def relatorio_md(df: pd.DataFrame, r: dict) -> str:
    fmt = _fmt
    linhas = ["# Avaliação da extração de laudos", "",
              "Critério de acerto: ver docstring de `avaliar.py`. Alucinação é o erro mais grave.", "",
              "## Resumo", "", "| Métrica | Valor |", "|---|---|"]
    linhas += [f"| {k} | {fmt(v)} |" for k, v in r.items()]
    por_campo = df.pivot_table(index="campo", columns="resultado", values="laudo",
                               aggfunc="count", fill_value=0).reindex(CAMPOS)
    por_campo["acurácia"] = (por_campo.get("acerto", 0) / por_campo.sum(axis=1)).map("{:.0%}".format)
    linhas += ["", "## Por campo", "", tabela_md(por_campo)]
    loc = df[_localizado(df)]
    linhas += ["", "## Evidência localizada pelo código", "",
               "O LLM citou só o valor; o código achou a única linha do laudo que contém o valor e "
               "fala do campo. Contam como acerto ou erro normalmente.", ""]
    linhas += [tabela_md(loc[["laudo", "campo", "resultado", "obtido", "motivo"]], index=False)
               if len(loc) else "Nenhum."]
    erros = df[df["resultado"] != "acerto"]
    linhas += ["", "## Campos que não bateram", ""]
    linhas += [tabela_md(erros[["laudo", "campo", "resultado", "status_gabarito", "status_extrator",
                               "esperado", "obtido", "motivo"]], index=False)
               if len(erros) else "Nenhum."]
    return "\n".join(linhas) + "\n"


def nomes_saida(extracoes: Path) -> tuple[Path, Path]:
    """extracoes.json -> avaliacao.md; extracoes_<nome>.json -> avaliacao_<nome>.md
    (outro nome de arquivo -> avaliacao_<arquivo>.md). O CSV de detalhe segue o mesmo sufixo."""
    stem = extracoes.stem
    nome = stem.removeprefix("extracoes_") if stem.startswith("extracoes_") else \
        ("" if stem == "extracoes" else stem)
    sufixo = f"_{nome}" if nome else ""
    return (BASE / f"saida/avaliacao{sufixo}.md", BASE / f"saida/avaliacao_detalhe{sufixo}.csv")


def main() -> None:
    p = argparse.ArgumentParser(description="Compara a extração com o gabarito.")
    p.add_argument("--extracoes", type=Path, default=BASE / "saida/extracoes.json",
                   help="JSON do extrator (ex.: parte3_laudos/saida/extracoes_claude.json; "
                        "só o nome procura em parte3_laudos/saida/)")
    a = p.parse_args()
    arq = a.extracoes
    if not arq.exists() and not arq.is_absolute() and (BASE / "saida" / arq).exists():
        arq = BASE / "saida" / arq
    if not arq.exists():
        sys.exit(f"{arq} não existe. Rode antes: python parte3_laudos/extrator.py")
    gab = json.loads((BASE / "gabarito.json").read_text(encoding="utf-8"))
    ext = json.loads(arq.read_text(encoding="utf-8"))
    df = avaliar(gab, ext)
    r = resumo(df)
    md, csv = nomes_saida(arq)
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    md.write_text(relatorio_md(df, r), encoding="utf-8")
    for k, v in r.items():
        print(f"{k:55s} {_fmt(v)}")
    print(f"\nDetalhe: {md}")

if __name__ == "__main__":
    main()
