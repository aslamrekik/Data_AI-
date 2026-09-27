"""
relatorio_semanal.py — Relatório semanal do funil (Parte 2).

Lê o CSV bruto, aplica o mesmo tratamento da Parte 1 (src/tratamento.py),
calcula as métricas-chave e exporta um HTML autocontido, pronto para enviar.

Uso (da raiz do repositório, ou pelo rodar_relatorio.bat):
    python parte2_relatorio/relatorio_semanal.py
    python parte2_relatorio/relatorio_semanal.py --entrada outro.csv --referencia 2025-12-29

Semana de referência: por padrão, a última semana completa (segunda a domingo)
presente na base. Em produção, com dados do dia, seria a semana passada.

Códigos de saída (o Agendador de Tarefas registra):
    0 = relatório gerado | 1 = entrada inválida (arquivo ausente, vazio, colunas) | 2 = erro inesperado
"""
from __future__ import annotations

import argparse
import csv
import base64
import io
import logging
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # sem janela: roda em servidor e no Agendador
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
import tratamento as t  # noqa: E402

DIR = RAIZ / "parte2_relatorio"
MATURACAO_DIAS = 90   # maior tempo de análise na base é 78 dias: coortes mais novas ainda estão abertas
log = logging.getLogger("relatorio")


# ----------------------------------------------------------------------------
# Log
# ----------------------------------------------------------------------------
def configurar_log() -> Path:
    (DIR / "logs").mkdir(parents=True, exist_ok=True)
    arq = DIR / "logs" / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for h in (logging.FileHandler(arq, encoding="utf-8"), logging.StreamHandler()):
        h.setFormatter(fmt)
        raiz.addHandler(h)
    return arq


# ----------------------------------------------------------------------------
# Métricas
# ----------------------------------------------------------------------------
def semana_referencia(df: pd.DataFrame, referencia: str | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Segunda e domingo da semana de referência."""
    if referencia:
        dia = pd.Timestamp(referencia)
    else:
        ultimo = df["data_entrada"].max()
        dia = ultimo - timedelta(days=7) if ultimo.weekday() < 6 else ultimo  # última semana COMPLETA
    inicio = (dia - timedelta(days=dia.weekday())).normalize()
    fim = inicio + timedelta(days=6)
    primeira, ultima = df["data_entrada"].min(), df["data_entrada"].max()
    if pd.isna(ultima):
        raise ValueError("nenhuma data de entrada válida na base")
    # Semana sem cobertura completa gera KPIs zerados ou quedas falsas: melhor falhar
    if inicio < primeira.normalize() or fim > ultima.normalize():
        raise ValueError(f"semana {inicio:%d/%m/%Y}–{fim:%d/%m/%Y} fora da base ou incompleta "
                         f"(entradas de {primeira:%d/%m/%Y} a {ultima:%d/%m/%Y})")
    return inicio, fim


def calcular(df: pd.DataFrame, inicio: pd.Timestamp, fim: pd.Timestamp) -> dict:
    b = t.base_analise(df).copy()
    fim_dia = fim + timedelta(days=1)
    semana = lambda col: b[(b[col] >= inicio) & (b[col] < fim_dia)]
    # Comparação com até 4 semanas anteriores, só as que a base cobre por inteiro: no início
    # da base, dividir por 4 com uma semana e meia de dados inventa altas de centenas de %.
    primeira = b["data_entrada"].min().normalize()
    n_hist = sum(1 for w in range(1, 5) if inicio - timedelta(weeks=w) >= primeira)
    anteriores = lambda col: b[(b[col] >= inicio - timedelta(weeks=n_hist)) & (b[col] < inicio)]
    media = lambda total: total / n_hist if n_hist else float("nan")

    entradas, entradas_ant = semana("data_entrada"), anteriores("data_entrada")
    assinados, assinados_ant = semana("data_assinatura_contrato"), anteriores("data_assinatura_contrato")

    kpis = {
        "Propostas que entraram": (len(entradas), media(len(entradas_ant)), "{:,.0f}"),
        "Contratos assinados": (len(assinados), media(len(assinados_ant)), "{:,.0f}"),
        "Valor contratado (R$ mi)": (assinados["valor_solicitado"].sum() / 1e6,
                                     media(assinados_ant["valor_solicitado"].sum() / 1e6), "{:,.1f}"),
        "Contratos acima da política de LTV": (int((assinados["ltv"] > t.LIMITE_LTV_POLITICA).sum()),
                                               media((assinados_ant["ltv"] > t.LIMITE_LTV_POLITICA).sum()), "{:,.0f}"),
    }

    # Conversão só em coortes MADURAS: propostas recentes ainda não tiveram tempo de fechar
    corte = fim - timedelta(days=MATURACAO_DIAS)
    madura = b[(b["data_entrada"] <= corte) & (b["data_entrada"] > corte - timedelta(days=90))]
    conv_canal = (madura.groupby("canal_origem")["contratada"].agg(["mean", "size"])
                  .rename(columns={"mean": "conversão", "size": "propostas"})
                  .sort_values("conversão"))
    perdas = (madura[madura["contratada"] == 0].groupby("status_final")
              .agg(propostas=("id_proposta", "size"), valor=("valor_solicitado", "sum"))
              .sort_values("valor", ascending=False))

    semanal = (b.set_index("data_entrada").resample("W-SUN")["id_proposta"].count()
               .loc[:fim].tail(12))
    return dict(kpis=kpis, n_hist=n_hist, conv_canal=conv_canal, perdas=perdas, semanal=semanal,
                janela_madura=(corte - timedelta(days=90), corte),
                conv_madura=madura["contratada"].mean() if len(madura) else float("nan"),
                n_madura=len(madura))


# ----------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------
def _grafico_png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def rotulos_semana(indice: pd.DatetimeIndex) -> list[str]:
    """resample('W-SUN') rotula pelo domingo; o relatório identifica a semana pela segunda."""
    return [(d - timedelta(days=6)).strftime("%d/%m") for d in indice]


def _br(v: float, fmt: str) -> str:
    return fmt.format(v).replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_html(m: dict, reg_df: pd.DataFrame, inicio, fim, arquivo: str, n_linhas: int) -> str:
    cards = []
    for nome, (atual, media, fmt) in m["kpis"].items():
        delta = (atual - media) / media if media else float("nan")
        seta = "" if pd.isna(delta) else ("▲" if delta >= 0 else "▼")
        cor = "#b42318" if "acima da política" in nome and atual > 0 else "#1f4e8c"
        n = m["n_hist"]
        base_cmp = "a semana anterior" if n == 1 else f"a média das {n} semanas anteriores"
        var = "sem semanas anteriores na base para comparar" if pd.isna(delta) and not n else \
            ("" if pd.isna(delta) else f"{seta} {_br(abs(delta) * 100, '{:,.0f}')}% vs {base_cmp}")
        cards.append(f'<div class="card"><div class="rot">{nome}</div>'
                     f'<div class="num" style="color:{cor}">{_br(atual, fmt)}</div>'
                     f'<div class="var">{var}</div></div>')

    fig, ax = plt.subplots(figsize=(8, 3))
    s = m["semanal"]
    ax.bar(rotulos_semana(s.index), s.values,
           color=["#1f4e8c" if d.normalize() == fim.normalize() else "#c7d4e8" for d in s.index])
    ax.set_title("Propostas que entraram por semana (últimas 12, rótulo = segunda-feira)")
    ax.spines[["top", "right"]].set_visible(False)
    graf_volume = _grafico_png(fig)

    cc = m["conv_canal"]
    graf_canal = ""
    if m["n_madura"]:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.barh(cc.index, cc["conversão"] * 100, color="#1f4e8c")
        ax.set_xlabel("Conversão (%)"); ax.spines[["top", "right"]].set_visible(False)
        ax.set_title("Conversão por canal (coortes maduras)")
        graf_canal = _grafico_png(fig)

    perdas = m["perdas"].assign(valor=lambda d: d["valor"].map(lambda v: "R$ " + _br(v / 1e6, "{:,.1f}") + " mi"))
    linhas_perda = "".join(f"<tr><td>{i}</td><td>{r.propostas}</td><td>{r.valor}</td></tr>"
                           for i, r in perdas.iterrows())
    problemas = reg_df[reg_df["linhas_afetadas"] > 0]
    linhas_dq = "".join(f"<tr><td>{r.problema}</td><td>{r.linhas_afetadas}</td><td>{r.acao}</td></tr>"
                        for r in problemas.itertuples())
    j0, j1 = m["janela_madura"]
    if m["n_madura"]:
        bloco_conv = (f'<p class="nota">Coortes que entraram entre {j0:%d/%m/%Y} e {j1:%d/%m/%Y} '
                      f'({_br(m["n_madura"], "{:,.0f}")} propostas, conversão geral de '
                      f'{_br(m["conv_madura"] * 100, "{:,.1f}")}%). Propostas com menos de {MATURACAO_DIAS} '
                      f'dias ainda podem fechar e ficam de fora.</p>\n'
                      f'<img src="data:image/png;base64,{graf_canal}" alt="Conversão por canal">')
        tabela_perda = (f'<table><tr><th>Status final</th><th>Propostas</th><th>Crédito solicitado</th></tr>'
                        f'{linhas_perda}</table>')
    else:
        bloco_conv = (f'<p class="nota">Ainda não há coortes maduras nesta base: a conversão só é medida '
                      f'para propostas com mais de {MATURACAO_DIAS} dias (entrada até {j1:%d/%m/%Y}).</p>')
        tabela_perda = '<p class="nota">Sem coortes maduras para analisar.</p>'

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Funil de propostas — semana {inicio:%d/%m/%Y}</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#1d2939}}
 h1{{font-size:22px;margin-bottom:4px}} h2{{font-size:17px;margin-top:28px;border-bottom:1px solid #e4e7ec;padding-bottom:4px}}
 .sub{{color:#667085;font-size:13px}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:16px}}
 .card{{border:1px solid #e4e7ec;border-radius:8px;padding:12px}} .rot{{font-size:13px;color:#475467}}
 .num{{font-size:28px;font-weight:600;margin:4px 0}} .var{{font-size:12px;color:#667085}}
 table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid #eaecf0;padding:6px;text-align:left}}
 img{{max-width:100%}} .nota{{font-size:12px;color:#667085}}
</style></head><body>
<h1>Relatório semanal do funil de propostas</h1>
<div class="sub">Semana de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} · gerado em {datetime.now():%d/%m/%Y %H:%M} ·
fonte: {arquivo} ({_br(n_linhas, "{:,.0f}")} propostas, nenhuma removida)</div>
<div class="cards">{''.join(cards)}</div>
<h2>Volume de entrada</h2><img src="data:image/png;base64,{graf_volume}" alt="Volume semanal">
<h2>Conversão por canal</h2>
{bloco_conv}
<h2>Onde as propostas se perderam (mesmas coortes)</h2>
{tabela_perda}
<h2>Qualidade dos dados desta execução</h2>
<table><tr><th>Problema</th><th>Linhas</th><th>Ação</th></tr>{linhas_dq}</table>
<p class="nota">Registro completo no log da execução. Nenhuma linha é descartada: problemas viram correção documentada ou sinalização.</p>
</body></html>"""


# ----------------------------------------------------------------------------
# Execução
# ----------------------------------------------------------------------------
def executar(entrada: Path, referencia: str | None) -> Path:
    log.info("Início. Entrada: %s", entrada)
    bruto = t.carregar_bruto(entrada)          # FileNotFoundError / formato não suportado
    df, reg = t.tratar(bruto)                  # SchemaError se faltar coluna ou vier vazio
    reg_df = reg.to_frame()
    log.info("Tratamento: %d linhas, %d checagens com ocorrência",
             len(df), int((reg_df["linhas_afetadas"] > 0).sum()))
    inicio, fim = semana_referencia(df, referencia)
    log.info("Semana de referência: %s a %s", inicio.date(), fim.date())
    m = calcular(df, inicio, fim)
    for nome, (atual, media, _) in m["kpis"].items():
        log.info("KPI %-38s semana=%.1f média_%ds=%.1f", nome, atual, m["n_hist"], media)
    (DIR / "output").mkdir(parents=True, exist_ok=True)
    destino = DIR / "output" / f"relatorio_funil_{inicio:%Y-%m-%d}.html"
    destino.write_text(gerar_html(m, reg_df, inicio, fim, entrada.name, len(df)), encoding="utf-8")
    log.info("Relatório gerado: %s", destino)
    return destino


def main() -> int:
    p = argparse.ArgumentParser(description="Gera o relatório semanal do funil.")
    p.add_argument("--entrada", type=Path, default=RAIZ / "data/raw/propostas_credito.csv")
    p.add_argument("--referencia", help="qualquer dia da semana desejada (AAAA-MM-DD)")
    a = p.parse_args()
    arq_log = configurar_log()
    try:
        executar(a.entrada, a.referencia)
        return 0
    except (FileNotFoundError, t.SchemaError, ValueError, pd.errors.EmptyDataError, csv.Error) as e:
        log.error("Entrada inválida: %s. Nenhum relatório foi gerado.", e)
        return 1
    except Exception:
        log.error("Erro inesperado. Nenhum relatório foi gerado.\n%s", traceback.format_exc())
        return 2
    finally:
        log.info("Log desta execução: %s", arq_log)


if __name__ == "__main__":
    sys.exit(main())
