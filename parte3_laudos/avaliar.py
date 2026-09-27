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
      textos livres: similaridade >= 0,85 depois de tirar caixa, acento e pontuação;
      contraditório: o mesmo conjunto de valores.
  Status: reportado à parte ("acerto estrito" = valor certo E status igual).

Uso:
    python parte3_laudos/avaliar.py
"""
from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalizar import compactar  # noqa: E402
from schema import CAMPOS  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "parte3_laudos"
SEM_VALOR = {"nao_informado", "nao_aplicavel", "nao_verificado"}
NUMERICOS = {"area_privativa_m2", "area_total_m2", "area_construida_m2", "area_terreno_m2",
             "valor_avaliacao"}
EXATOS = {"ano_construcao", "data_vistoria", "uf", "matricula", "tipo_imovel", "onus_situacao"}


def tabela_md(df: pd.DataFrame, index: bool = True) -> str:
    """Tabela markdown sem depender do pacote tabulate."""
    d = df.reset_index() if index else df
    cab = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "---|" * len(d.columns)
    corpo = ["| " + " | ".join("" if pd.isna(v) else str(v).replace("|", "/") for v in row) + " |"
             for row in d.itertuples(index=False)]
    return "\n".join([cab, sep, *corpo])


def equivale(campo: str, esperado, obtido) -> bool:
    if isinstance(esperado, list) or isinstance(obtido, list):
        if not (isinstance(esperado, list) and isinstance(obtido, list)):
            return False
        return sorted(map(float, esperado)) == sorted(map(float, obtido)) if campo in NUMERICOS \
            else sorted(map(str, esperado)) == sorted(map(str, obtido))
    if campo in NUMERICOS:
        try:
            e, o = float(esperado), float(obtido)
        except (TypeError, ValueError):
            return False
        return abs(e - o) <= 0.005 * max(abs(e), 1)
    if campo in EXATOS:
        return compactar(str(esperado)) == compactar(str(obtido))
    a = " ".join(re.sub(r"[^\w ]", " ", compactar(str(esperado))).split())
    b = " ".join(re.sub(r"[^\w ]", " ", compactar(str(obtido))).split())
    return SequenceMatcher(None, a, b).ratio() >= 0.85


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
        for campo in CAMPOS:
            g = g_campos[campo]
            x = (x_laudo or {}).get("campos", {}).get(campo) or {"valor": None, "status": "nao_verificado"}
            resultado = classificar(campo, g, x)
            linhas.append(dict(
                laudo=laudo, campo=campo, resultado=resultado,
                status_gabarito=g["status"], status_extrator=x["status"],
                status_igual=g["status"] == x["status"],
                esperado=json.dumps(g["valor"], ensure_ascii=False),
                obtido=json.dumps(x.get("valor"), ensure_ascii=False),
                motivo=x.get("motivo"),
            ))
    return pd.DataFrame(linhas)


def resumo(df: pd.DataFrame) -> dict:
    g_sem = df["status_gabarito"].isin(SEM_VALOR)
    return {
        "campos avaliados": len(df),
        "acurácia (valor)": (df["resultado"] == "acerto").mean(),
        "acurácia estrita (valor + status)": ((df["resultado"] == "acerto") & df["status_igual"]).mean(),
        "cobertura (acertos onde o gabarito tem valor)": (df.loc[~g_sem, "resultado"] == "acerto").mean(),
        "abstenção correta (onde o gabarito não tem valor)": (df.loc[g_sem, "resultado"] == "acerto").mean(),
        "alucinações (valor onde não existe)": int((df["resultado"] == "alucinacao").sum()),
        "erros de valor": int((df["resultado"] == "erro_valor").sum()),
        "abstenções (não sabia, errou para o lado seguro)": int((df["resultado"] == "abstencao").sum()),
    }


def relatorio_md(df: pd.DataFrame, r: dict) -> str:
    fmt = lambda v: f"{v:.1%}" if isinstance(v, float) else str(v)
    linhas = ["# Avaliação da extração de laudos", "",
              "Critério de acerto: ver docstring de `avaliar.py`. Alucinação é o erro mais grave.", "",
              "## Resumo", "", "| Métrica | Valor |", "|---|---|"]
    linhas += [f"| {k} | {fmt(v)} |" for k, v in r.items()]
    por_campo = df.pivot_table(index="campo", columns="resultado", values="laudo",
                               aggfunc="count", fill_value=0).reindex(CAMPOS)
    por_campo["acurácia"] = (por_campo.get("acerto", 0) / por_campo.sum(axis=1)).map("{:.0%}".format)
    linhas += ["", "## Por campo", "", tabela_md(por_campo)]
    erros = df[df["resultado"] != "acerto"]
    linhas += ["", "## Campos que não bateram", ""]
    linhas += [tabela_md(erros[["laudo", "campo", "resultado", "status_gabarito", "status_extrator",
                               "esperado", "obtido", "motivo"]], index=False)
               if len(erros) else "Nenhum."]
    return "\n".join(linhas) + "\n"


def main() -> None:
    gab = json.loads((BASE / "gabarito.json").read_text(encoding="utf-8"))
    arq = BASE / "saida/extracoes.json"
    if not arq.exists():
        sys.exit("Rode antes: python parte3_laudos/extrator.py")
    ext = json.loads(arq.read_text(encoding="utf-8"))
    df = avaliar(gab, ext)
    r = resumo(df)
    df.to_csv(BASE / "saida/avaliacao_detalhe.csv", index=False, encoding="utf-8-sig")
    (BASE / "saida/avaliacao.md").write_text(relatorio_md(df, r), encoding="utf-8")
    for k, v in r.items():
        print(f"{k:55s} {v:.1%}" if isinstance(v, float) else f"{k:55s} {v}")
    print(f"\nDetalhe: {BASE / 'saida/avaliacao.md'}")


if __name__ == "__main__":
    main()
