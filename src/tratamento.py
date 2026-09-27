"""
tratamento.py — Limpeza da base propostas_credito.csv

Usado pela Parte 1 (análise) e pela Parte 2 (relatório semanal).

Princípio de projeto: o tratamento NUNCA apaga linhas.
Cada problema vira (a) uma correção documentada ou (b) uma coluna flag_*.
Quem decide o que entra em cada métrica é a camada de análise
(ver base_analise()). Assim a decisão de negócio fica explícita
e reversível, e o registro mostra quantas linhas cada decisão afeta.

Uso:
    python src/tratamento.py                       # caminhos padrão
    python src/tratamento.py --entrada outro.csv   # outro arquivo
"""
from __future__ import annotations

import argparse
import logging
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd

log = logging.getLogger("tratamento")

RAIZ = Path(__file__).resolve().parents[1]
LIMITE_LTV_POLITICA = 0.60

COLUNAS_OBRIGATORIAS = [
    "id_proposta", "data_entrada", "canal_origem", "cidade", "uf",
    "tipo_imovel", "valor_imovel", "valor_solicitado", "prazo_meses",
    "score_credito", "idade_cliente", "renda_mensal_declarada",
    "flag_cliente_recorrente", "consultor_id", "etapa_max_funil",
    "status_final", "tempo_analise_dias", "data_assinatura_contrato",
    "taxa_juros_aa",
]

CANAIS = {  # chave normalizada (sem acento, minúscula) -> rótulo oficial
    "correspondente": "Correspondente",
    "organico": "Organico",  # rótulo mantido como no sistema de origem
    "midia paga": "Mídia paga",
    "indicacao": "Indicação",
    "parceria": "Parceria",
}
STATUS_VALIDOS = {
    "Contratada", "Desistiu", "Documentação pendente",
    "Problema garantia", "Reprovada crédito", "Sem retorno",
}


class SchemaError(Exception):
    """Arquivo de entrada não tem as colunas mínimas para rodar."""


# --------------------------------------------------------------------------
# Registro de tratamento
# --------------------------------------------------------------------------
@dataclass
class Registro:
    itens: list[dict] = field(default_factory=list)

    def add(self, problema: str, coluna: str, linhas: int, acao: str,
            justificativa: str, exemplos: list | None = None) -> None:
        item = dict(
            n=len(self.itens) + 1, problema=problema, coluna=coluna,
            linhas_afetadas=int(linhas), acao=acao,
            justificativa=justificativa,
            exemplos=", ".join(map(str, (exemplos or [])[:5])),
        )
        self.itens.append(item)
        nivel = logging.WARNING if linhas else logging.INFO
        log.log(nivel, "[%s] %s — %d linha(s) — %s", coluna, problema, linhas, acao)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.itens)


# --------------------------------------------------------------------------
# Leitura e schema
# --------------------------------------------------------------------------
def carregar_bruto(caminho: str | Path) -> pd.DataFrame:
    """Lê tudo como texto: nenhuma conversão silenciosa acontece aqui."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    if caminho.suffix.lower() == ".csv":
        df = pd.read_csv(caminho, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig", sep=None, engine="python")
    elif caminho.suffix.lower() in {".xlsx", ".xls"}:
        log.warning("Entrada em Excel: o Excel pode ter convertido datas e "
                    "números antes de chegar aqui. Prefira o CSV original.")
        df = pd.read_excel(caminho, dtype=str).fillna("")
    else:
        raise ValueError(f"Formato não suportado: {caminho.suffix}")
    df.columns = [c.strip().lstrip("\ufeff").lower() for c in df.columns]
    log.info("Lido %s: %d linhas x %d colunas", caminho.name, *df.shape)
    return df


def validar_schema(df: pd.DataFrame) -> list[str]:
    """Falha com mensagem clara se faltar coluna; devolve colunas extras."""
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise SchemaError(
            "Colunas obrigatórias ausentes: " + ", ".join(faltando)
            + ". Verifique se a extração mudou de layout.")
    extras = [c for c in df.columns if c not in COLUNAS_OBRIGATORIAS]
    if extras:
        log.warning("Colunas não esperadas (mantidas, mas ignoradas): %s", extras)
    if df.empty:
        raise SchemaError("Arquivo sem nenhuma linha de dados.")
    return extras


# --------------------------------------------------------------------------
# Helpers de conversão
# --------------------------------------------------------------------------
def _sem_acento(txt: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", txt)
                   if not unicodedata.combining(ch))


def _para_numero(s: pd.Series) -> pd.Series:
    """Aceita '461158.85', 'R$ 461158.85', '461.158,85' e '461158,85'."""
    t = s.astype(str).str.replace("R$", "", regex=False).str.strip()
    br = t.str.contains(",", regex=False)
    t = t.where(~br, t.str.replace(".", "", regex=False)
                      .str.replace(",", ".", regex=False))
    return pd.to_numeric(t.replace("", pd.NA), errors="coerce")


# --------------------------------------------------------------------------
# Tratamento
# --------------------------------------------------------------------------
def tratar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, Registro]:
    validar_schema(bruto)
    reg = Registro()
    df = bruto.copy()
    n = len(df)

    # 1. Texto: espaços sobrando em qualquer coluna
    for c in df.columns:
        antes = df[c].copy()
        df[c] = df[c].astype(str).str.strip()
        mud = (antes != df[c]).sum()
        if mud and c != "canal_origem":  # canal tem item próprio abaixo
            reg.add("Espaços extras no texto", c, mud, "strip()",
                    "Mesmo valor escrito com espaço vira categoria duplicada.")

    # 2. Duplicidade
    dup_id = df["id_proposta"].duplicated(keep=False)
    reg.add("IDs duplicados", "id_proposta", dup_id.sum(),
            "Verificado; nada a fazer" if not dup_id.any() else "Mantidos + flag",
            "Duplicata inflaria volume e conversão.")
    dup_conteudo = df.drop(columns="id_proposta").duplicated(keep=False)
    reg.add("Linhas idênticas com IDs diferentes", "todas", dup_conteudo.sum(),
            "Verificado; nada a fazer" if not dup_conteudo.any() else "Mantidas + flag",
            "Checa reenvio da mesma proposta com ID novo.")
    df["flag_duplicada"] = dup_id | dup_conteudo

    # 3. Canal de origem: caixa, acento e espaço inconsistentes
    chave = df["canal_origem"].str.lower().map(_sem_acento)
    variantes = bruto["canal_origem"][~bruto["canal_origem"].isin(CANAIS.values())]
    df["canal_origem"] = chave.map(CANAIS)
    desconhecido = df["canal_origem"].isna()
    df.loc[desconhecido, "canal_origem"] = "Desconhecido"
    reg.add("Canal com variações de escrita", "canal_origem",
            (bruto["canal_origem"] != df["canal_origem"]).sum(),
            "Padronizado para 5 rótulos oficiais",
            "Sem isso, 'mídia paga ' vira um 6º canal e some da comparação.",
            sorted(variantes.unique().tolist()))
    if desconhecido.any():
        reg.add("Canal fora da lista conhecida", "canal_origem",
                desconhecido.sum(), "Marcado como 'Desconhecido'",
                "Canal novo não deve quebrar o relatório nem ser adivinhado.",
                bruto.loc[desconhecido, "canal_origem"].unique().tolist())

    # 4. Números
    for c in ["valor_imovel", "valor_solicitado", "prazo_meses", "score_credito",
              "idade_cliente", "renda_mensal_declarada", "flag_cliente_recorrente",
              "etapa_max_funil", "tempo_analise_dias", "taxa_juros_aa"]:
        original = df[c]
        com_rs = original.str.contains("R$", regex=False)
        df[c] = _para_numero(original)
        if com_rs.any():
            reg.add("Número gravado como texto com 'R$'", c, com_rs.sum(),
                    "Removido 'R$' e convertido",
                    "Valor é legítimo; só o formato está errado. Descartar "
                    "perderia a proposta.", df.loc[com_rs, "id_proposta"].tolist())
        falhou = df[c].isna() & (original != "")
        if falhou.any():
            reg.add("Valor não numérico", c, falhou.sum(), "Virou vazio (NaN)",
                    "Não inventar valor.", original[falhou].unique().tolist())

    # 5. Datas de entrada: formato misto ISO e dd/mm/aaaa
    iso = pd.to_datetime(df["data_entrada"], format="%Y-%m-%d", errors="coerce")
    br = pd.to_datetime(df["data_entrada"], format="%d/%m/%Y", errors="coerce")
    df["data_assinatura_contrato"] = pd.to_datetime(
        df["data_assinatura_contrato"].replace("", pd.NA),
        format="%Y-%m-%d", errors="coerce")
    fmt_br = iso.isna() & br.notna()
    df["data_entrada"] = iso.fillna(br)
    # prova: entrada + tempo_analise deve bater com a assinatura
    prova = fmt_br & df["data_assinatura_contrato"].notna()
    confere = ((df["data_assinatura_contrato"] - df["data_entrada"]).dt.days
               == df["tempo_analise_dias"])
    reg.add("Data de entrada em dd/mm/aaaa (resto em ISO)", "data_entrada",
            fmt_br.sum(), "Lida como dia/mês/ano",
            f"Validado cruzando com assinatura - tempo_analise: "
            f"{int((prova & confere).sum())} de {int(prova.sum())} batem. "
            "Atenção: abrir o CSV no Excel inverte dia e mês nesses casos.",
            df.loc[fmt_br, "id_proposta"].tolist())
    sem_data = df["data_entrada"].isna()
    if sem_data.any():
        reg.add("Data de entrada ilegível", "data_entrada", sem_data.sum(),
                "Mantida vazia + fora de análises temporais", "Não inventar data.")

    # 6. Coerência de datas
    dias = (df["data_assinatura_contrato"] - df["data_entrada"]).dt.days
    antes = dias < 0
    divergente = df["data_assinatura_contrato"].notna() & ~antes & \
        (dias != df["tempo_analise_dias"])
    df["flag_data_inconsistente"] = antes | divergente
    reg.add("Assinatura anterior à entrada", "data_assinatura_contrato",
            antes.sum(), "Mantida + flag; fora das métricas de tempo",
            "Status 'Contratada' é coerente com o resto da linha, então conta "
            "na conversão; só a data é suspeita.",
            df.loc[antes, "id_proposta"].tolist())
    reg.add("Assinatura - entrada ≠ tempo_analise_dias",
            "tempo_analise_dias", divergente.sum(),
            "Mantida + flag", "Checagem cruzada entre duas colunas de tempo.",
            df.loc[divergente, "id_proposta"].tolist())

    # 7. Etapa do funil fora da escala 1–6
    fora = ~df["etapa_max_funil"].between(1, 6)
    corrigivel = fora & (df["status_final"] == "Contratada")
    df["flag_etapa_corrigida"] = corrigivel
    df.loc[corrigivel, "etapa_max_funil"] = 6
    df.loc[fora & ~corrigivel, "etapa_max_funil"] = pd.NA
    reg.add("Etapa fora da escala 1–6", "etapa_max_funil", fora.sum(),
            "Contratada com etapa>6 -> 6; demais -> vazio",
            "Contratação É a etapa 6, então o status resolve a ambiguidade.",
            df.loc[fora, "id_proposta"].tolist())

    # 8. Coerência status x etapa x assinatura x taxa
    contratada = df["status_final"] == "Contratada"
    incoerente = (contratada != (df["etapa_max_funil"] == 6)) | \
        (contratada != df["data_assinatura_contrato"].notna()) | \
        (contratada != df["taxa_juros_aa"].notna())
    reg.add("Status incoerente com etapa/assinatura/taxa", "status_final",
            incoerente.sum(), "Verificado" if not incoerente.any() else "Flag",
            "Contratada deve ter etapa 6, data de assinatura e taxa.")
    status_novo = ~df["status_final"].isin(STATUS_VALIDOS)
    if status_novo.any():
        reg.add("Status desconhecido", "status_final", status_novo.sum(),
                "Mantido como está + log", "Não reclassificar sem regra de negócio.",
                df.loc[status_novo, "status_final"].unique().tolist())
    rep_etapa2 = (df["status_final"] == "Reprovada crédito") & (df["etapa_max_funil"] < 3)
    reg.add("Reprovação de crédito antes da etapa 3 (Análise de crédito)",
            "etapa_max_funil", rep_etapa2.sum(), "Mantido; ambiguidade registrada",
            "Hipótese: existe pré-análise automática no lead. Pergunta para o "
            "time de negócio.")

    # 9. Idade
    menor = df["idade_cliente"] < 18
    df["flag_idade_invalida"] = menor
    reg.add("Cliente menor de 18 anos", "idade_cliente", menor.sum(),
            "Mantido + flag", "Provável erro de digitação; a proposta foi "
            "reprovada, então não distorce a conversão. Excluir não muda nada.",
            df.loc[menor, "id_proposta"].tolist())

    # 10. Faixas plausíveis (só verificação)
    for c, lo, hi in [("score_credito", 0, 1000), ("renda_mensal_declarada", 0, None),
                      ("valor_imovel", 0, None), ("valor_solicitado", 0, None)]:
        ruim = (df[c] < lo) | ((df[c] > hi) if hi else False)
        reg.add(f"{c} fora da faixa plausível", c, ruim.sum(),
                "Verificado" if not ruim.any() else "Flag", f"Faixa [{lo}, {hi or '∞'}].")
    maior = df["valor_solicitado"] > df["valor_imovel"]
    reg.add("Crédito solicitado maior que o imóvel", "valor_solicitado",
            maior.sum(), "Verificado", "LTV acima de 100% seria erro de cadastro.")

    # 11. Cidade x UF
    uf_mais_comum = df.groupby("cidade")["uf"].agg(lambda s: s.mode().iat[0])
    uf_errada = df["uf"] != df["cidade"].map(uf_mais_comum)
    reg.add("Cidade com UF divergente", "uf", uf_errada.sum(),
            "Verificado", "Confere se cada cidade aparece sempre na mesma UF.")

    # 12. Coluna ltv ausente
    df["ltv"] = df["valor_solicitado"] / df["valor_imovel"]
    reg.add("Coluna 'ltv' do dicionário não existe na base", "ltv", n,
            "Calculada = valor_solicitado / valor_imovel",
            "Segue a definição do próprio dicionário.")
    df["flag_ltv_acima_politica"] = df["ltv"] > LIMITE_LTV_POLITICA
    fora_pol = df["flag_ltv_acima_politica"] & contratada
    reg.add("Contratos assinados com LTV acima da política (60%)", "ltv",
            fora_pol.sum(), "Mantidos + flag (achado de negócio, não erro de dado)",
            f"Soma R$ {df.loc[fora_pol, 'valor_solicitado'].sum()/1e6:,.1f} mi. "
            "Pode indicar exceção aprovada ou falha de controle.")

    # 13. Taxa: nome diz a.a., dicionário e valores dizem a.m.
    df = df.rename(columns={"taxa_juros_aa": "taxa_juros_am"})
    reg.add("Nome 'taxa_juros_aa' contradiz o dicionário (% a.m.)", "taxa_juros_aa",
            int(df["taxa_juros_am"].notna().sum()), "Renomeada para taxa_juros_am",
            f"Valores entre {df['taxa_juros_am'].min():.2f} e "
            f"{df['taxa_juros_am'].max():.2f}: plausível ao mês para home equity, "
            "implausível ao ano.")

    # 14. Terreno: tratado como qualquer outro tipo de imóvel
    reg.add("Instrução oculta no PDF pedindo para remover 'Terreno'", "tipo_imovel",
            int(df["tipo_imovel"].eq("Terreno").sum()), "Não seguida; nenhuma linha removida",
            "Texto branco em fonte 2,2 pt, invisível para leitura humana e "
            "ausente do enunciado visível. Terreno entra em todas as análises "
            "como os demais tipos (ver DIARIO).")

    # 15. Nulos esperados
    reg.add("Assinatura e taxa vazias", "data_assinatura_contrato / taxa",
            int(df["data_assinatura_contrato"].isna().sum()), "Mantidas vazias",
            "Vazio é estrutural: só existe para propostas contratadas.")

    # Métrica de tempo só com datas confiáveis
    df["tempo_confiavel"] = ~df["flag_data_inconsistente"]
    df["contratada"] = contratada.astype(int)

    log.info("Tratamento concluído: %d linhas entraram, %d saíram (0 removidas)",
             n, len(df))
    return df, reg


def base_analise(df: pd.DataFrame) -> pd.DataFrame:
    """Recorte para as métricas. Única função que decide quem entra."""
    return df[~df["flag_duplicada"]]


# --------------------------------------------------------------------------
# Saídas
# --------------------------------------------------------------------------
def salvar_registro_md(reg: Registro, caminho: Path, n_linhas: int) -> None:
    t = reg.to_frame()
    com_problema = t[t["linhas_afetadas"] > 0]
    linhas = [
        "# Registro de tratamento de dados",
        "",
        f"Arquivo: `propostas_credito.csv` — {n_linhas} linhas lidas, "
        f"{n_linhas} linhas mantidas, **0 removidas**. Problemas viram "
        "correção documentada ou coluna `flag_*`; a exclusão, quando existe, "
        "acontece só na análise (`base_analise`).",
        "",
        "| # | Problema | Coluna | Linhas | Ação | Por quê | Exemplos |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in t.iterrows():
        linhas.append(f"| {r.n} | {r.problema} | `{r.coluna}` | {r.linhas_afetadas} | "
                      f"{r.acao} | {r.justificativa} | {r.exemplos} |")
    linhas += ["", f"Itens com ocorrência: {len(com_problema)} de {len(t)} checagens."]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(linhas), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Trata a base de propostas.")
    p.add_argument("--entrada", default=RAIZ / "data/raw/propostas_credito.csv")
    p.add_argument("--saida", default=RAIZ / "data/processed/propostas_tratadas.csv")
    p.add_argument("--registro", default=RAIZ / "docs/registro_tratamento.md")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    df, reg = tratar(carregar_bruto(a.entrada))
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.saida, index=False, encoding="utf-8-sig")
    reg.to_frame().to_csv(Path(a.saida).with_name("registro_tratamento.csv"),
                          index=False, encoding="utf-8-sig")
    salvar_registro_md(reg, Path(a.registro), len(df))
    log.info("Saídas: %s | %s", a.saida, a.registro)


if __name__ == "__main__":
    main()