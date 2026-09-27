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
import csv
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
# Colunas criadas pelo tratamento; se a base já trouxer alguma (ou qualquer
# flag_* extra), a original é preservada como <coluna>_origem.
COLUNAS_GERADAS = {"ltv", "taxa_juros_am", "contratada", "tempo_confiavel",
                   "etapa_max_funil_original"}
MONETARIAS = {"valor_imovel", "valor_solicitado", "renda_mensal_declarada"}
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
    """Lê tudo como texto: nenhuma conversão silenciosa acontece aqui.

    Só aceita CSV. Tenta UTF-8 (com ou sem BOM) e, se falhar, cp1252
    (padrão do Excel em português). O encoding usado fica em
    df.attrs["encoding"] para entrar no registro.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    sufixo = caminho.suffix.lower()
    if sufixo in {".xlsx", ".xls"}:
        raise ValueError(
            f"Entrada em Excel não é suportada ({caminho.name}): o Excel "
            "converte datas e números antes de chegar aqui. Exporte o CSV "
            "original do sistema e rode de novo.")
    if sufixo != ".csv":
        raise ValueError(f"Formato não suportado: {caminho.suffix}. Use CSV.")
    if caminho.stat().st_size == 0:
        raise SchemaError(f"Arquivo vazio: {caminho.name}")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            df = pd.read_csv(caminho, dtype=str, keep_default_na=False,
                             encoding=encoding, sep=None, engine="python")
            break
        except UnicodeDecodeError:
            log.warning("Leitura de %s como %s falhou.", caminho.name, encoding)
        except (pd.errors.EmptyDataError, csv.Error) as e:
            raise SchemaError(
                f"Não foi possível ler {caminho.name} como CSV: {e}") from e
    else:
        raise SchemaError(f"{caminho.name} não está em UTF-8 nem em cp1252.")
    if encoding != "utf-8-sig":
        log.warning("%s lido como %s: confira os acentos.", caminho.name, encoding)
    df.attrs["encoding"] = encoding
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


def _para_numero(s: pd.Series, milhar: bool = False) -> tuple[pd.Series, pd.Series]:
    """Converte texto em número e devolve (valores, máscara de formato BR).

    Aceita '461158.85', 'R$ 461158.85', '461.158,85' e '461158,85'.
    Com milhar=True (colunas em R$, sempre com 2 casas), '571.522' e
    '2.264.057' são lidos como separador de milhar, não como decimal.
    """
    t = s.astype(str).str.replace("R$", "", regex=False).str.strip()
    br = t.str.contains(",", regex=False)
    if milhar:
        br |= t.str.fullmatch(r"-?\d{1,3}(\.\d{3})+")
    t = t.where(~br, t.str.replace(".", "", regex=False)
                      .str.replace(",", ".", regex=False))
    return pd.to_numeric(t.replace("", pd.NA), errors="coerce"), br


def _para_data(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Aceita aaaa-mm-dd e dd/mm/aaaa; devolve (datas, máscara dd/mm/aaaa)."""
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    br = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    return iso.fillna(br), iso.isna() & br.notna()


def _acao(mascara: pd.Series, acao: str) -> str:
    """Texto da ação conforme o resultado: nada encontrado não vira 'Flag'."""
    return acao if mascara.any() else "Verificado; nada a fazer"


# --------------------------------------------------------------------------
# Tratamento
# --------------------------------------------------------------------------
def tratar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, Registro]:
    extras = validar_schema(bruto)
    reg = Registro()
    n = len(bruto)

    # 0. Encoding e colunas extras que colidem com as geradas aqui
    if bruto.attrs.get("encoding", "utf-8-sig") != "utf-8-sig":
        reg.add("Arquivo fora de UTF-8", "todas", n,
                f"Lido como {bruto.attrs['encoding']}",
                "Padrão do Excel em português; ler como UTF-8 quebraria. "
                "Prefira exportar em UTF-8.")
    colisao = [c for c in extras if c in COLUNAS_GERADAS or c.startswith("flag_")]
    if colisao:
        bruto = bruto.rename(columns={c: f"{c}_origem" for c in colisao})
        reg.add("Coluna da base com nome de coluna gerada pelo tratamento",
                ", ".join(colisao), n, "Original guardada como <coluna>_origem",
                "Sobrescrever sem aviso apagaria o dado de origem.", colisao)
    df = bruto.copy()

    # 1. Texto: espaços sobrando em qualquer coluna
    for c in df.columns:
        antes = df[c].copy()
        df[c] = df[c].astype(str).str.strip()
        mud = (antes != df[c]).sum()
        if mud and c not in ("canal_origem", "status_final"):  # itens próprios
            reg.add("Espaços extras no texto", c, mud, "strip()",
                    "Mesmo valor escrito com espaço vira categoria duplicada.")

    # 3. Canal de origem: caixa, acento e espaço (inclusive interno) inconsistentes
    chave = df["canal_origem"].map(lambda t: " ".join(_sem_acento(t).lower().split()))
    df["canal_origem"] = chave.map(CANAIS)
    desconhecido = df["canal_origem"].isna()
    df.loc[desconhecido, "canal_origem"] = "Desconhecido"
    variou = (bruto["canal_origem"] != df["canal_origem"]) & ~desconhecido
    reg.add("Canal com variações de escrita", "canal_origem", variou.sum(),
            _acao(variou, "Padronizado para 5 rótulos oficiais"),
            "Sem isso, 'mídia paga ' vira um 6º canal e some da comparação.",
            sorted(bruto.loc[variou, "canal_origem"].unique().tolist()))
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
        df[c], fmt_br = _para_numero(original, milhar=c in MONETARIAS)
        convertido = df[c].notna()
        com_rs = original.str.contains("R$", regex=False) & convertido
        if com_rs.any():
            reg.add("Número gravado como texto com 'R$'", c, com_rs.sum(),
                    "Removido 'R$' e convertido",
                    "Valor é legítimo; só o formato está errado. Descartar "
                    "perderia a proposta.", df.loc[com_rs, "id_proposta"].tolist())
        fmt_br &= convertido
        if fmt_br.any():
            reg.add("Número em formato brasileiro (milhar '.', decimal ',')", c,
                    fmt_br.sum(), "Convertido para ponto decimal",
                    "Mesmo valor, outra notação."
                    + (" Em R$ (2 casas), '.' seguido de 3 dígitos é milhar."
                       if c in MONETARIAS else ""),
                    original[fmt_br].unique().tolist())
        falhou = df[c].isna() & (original != "")
        if falhou.any():
            reg.add("Valor não numérico", c, falhou.sum(), "Virou vazio (NaN)",
                    "Não inventar valor.", original[falhou].unique().tolist())

    # 5. Datas: formato misto ISO e dd/mm/aaaa nas duas colunas
    df["data_entrada"], fmt_br = _para_data(df["data_entrada"])
    assinatura_bruta = df["data_assinatura_contrato"]
    df["data_assinatura_contrato"], assin_br = _para_data(assinatura_bruta)
    # prova: entrada + tempo_analise deve bater com a assinatura
    prova = fmt_br & df["data_assinatura_contrato"].notna()
    confere = ((df["data_assinatura_contrato"] - df["data_entrada"]).dt.days
               == df["tempo_analise_dias"])
    provada = prova & confere
    dia, mes = df["data_entrada"].dt.day, df["data_entrada"].dt.month
    ambigua = fmt_br & (dia <= 12) & (dia != mes)
    sem_prova = ambigua & ~provada
    reg.add("Data de entrada em dd/mm/aaaa (resto em ISO)", "data_entrada",
            fmt_br.sum(), _acao(fmt_br, "Lida como dia/mês/ano"),
            f"{ambigua.sum()} ambígua(s) (dia ≤ 12, poderia ser mês/dia). "
            f"Conferência com assinatura − tempo_analise_dias: {provada.sum()} "
            f"de {prova.sum()} com assinatura batem"
            + (f"; ambíguas sem conferência: "
               f"{', '.join(df.loc[sem_prova, 'id_proposta'])}" if sem_prova.any() else "")
            + ". Atenção: abrir o CSV no Excel inverte dia e mês nesses casos.",
            df.loc[fmt_br, "id_proposta"].tolist())
    if assin_br.any():
        reg.add("Data de assinatura em dd/mm/aaaa (resto em ISO)",
                "data_assinatura_contrato", assin_br.sum(), "Lida como dia/mês/ano",
                "Mesmo tratamento da data de entrada.",
                df.loc[assin_br, "id_proposta"].tolist())
    sem_data = df["data_entrada"].isna()
    df["flag_data_entrada_invalida"] = sem_data
    reg.add("Data de entrada vazia ou ilegível", "data_entrada", sem_data.sum(),
            _acao(sem_data, "Mantida vazia + flag; fora das métricas de tempo"),
            "Não inventar data.", df.loc[sem_data, "id_proposta"].tolist())
    assin_ruim = df["data_assinatura_contrato"].isna() & (assinatura_bruta != "")
    df["flag_data_assinatura_invalida"] = assin_ruim
    reg.add("Data de assinatura ilegível", "data_assinatura_contrato",
            assin_ruim.sum(),
            _acao(assin_ruim, "Mantida vazia + flag; fora das métricas de tempo"),
            "Preenchida na origem mas em formato desconhecido: não é vazio "
            "estrutural.", assinatura_bruta[assin_ruim].unique().tolist())

    # 6. Coerência de datas
    dias = (df["data_assinatura_contrato"] - df["data_entrada"]).dt.days
    tem_datas = df["data_entrada"].notna() & df["data_assinatura_contrato"].notna()
    antes = tem_datas & (dias < 0)
    divergente = tem_datas & ~antes & (dias != df["tempo_analise_dias"])
    df["flag_data_inconsistente"] = antes | divergente
    reg.add("Assinatura anterior à entrada", "data_assinatura_contrato",
            antes.sum(), _acao(antes, "Mantida + flag; fora das métricas de tempo"),
            "Status 'Contratada' é coerente com o resto da linha, então conta "
            "na conversão; só a data é suspeita.",
            df.loc[antes, "id_proposta"].tolist())
    reg.add("Assinatura - entrada ≠ tempo_analise_dias",
            "tempo_analise_dias", divergente.sum(),
            _acao(divergente, "Mantida + flag; fora das métricas de tempo"),
            "Checagem cruzada entre duas colunas de tempo.",
            df.loc[divergente, "id_proposta"].tolist())

    # 7. Status: caixa e espaços inconsistentes; desconhecido não é reclassificado
    chave_status = df["status_final"].map(lambda t: " ".join(t.lower().split()))
    oficial = chave_status.map({s.lower(): s for s in STATUS_VALIDOS})
    status_novo = oficial.isna()
    df["status_final"] = oficial.fillna(df["status_final"])
    status_variou = (bruto["status_final"] != df["status_final"]) & ~status_novo
    reg.add("Status com variação de caixa/espaço", "status_final",
            status_variou.sum(), _acao(status_variou, "Padronizado para o rótulo oficial"),
            "'contratada ' fora do rótulo não contaria como conversão.",
            bruto.loc[status_variou, "status_final"].unique().tolist())
    df["flag_status_desconhecido"] = status_novo
    reg.add("Status desconhecido", "status_final", status_novo.sum(),
            _acao(status_novo, "Mantido como está + flag"),
            "Não reclassificar sem regra de negócio.",
            df.loc[status_novo, "status_final"].unique().tolist())
    contratada = df["status_final"] == "Contratada"

    # 7b. Duplicidade: depois de normalizar formato de número, data, canal e
    # status, para pegar a mesma proposta escrita de outro jeito
    dup_id = df["id_proposta"].duplicated(keep=False)
    reg.add("IDs duplicados", "id_proposta", dup_id.sum(),
            _acao(dup_id, "Mantidos + flag"),
            "Duplicata inflaria volume e conversão.",
            df.loc[dup_id, "id_proposta"].unique().tolist())
    conteudo = [c for c in COLUNAS_OBRIGATORIAS if c != "id_proposta"]
    dup_conteudo = df[conteudo].duplicated(keep=False)
    reg.add("Linhas idênticas com IDs diferentes", "todas", dup_conteudo.sum(),
            _acao(dup_conteudo, "Mantidas + flag"),
            "Checa reenvio da mesma proposta com ID novo, comparando valores "
            "já normalizados.", df.loc[dup_conteudo, "id_proposta"].tolist())
    df["flag_duplicada"] = dup_id | dup_conteudo

    # 8. Etapa do funil: escala 1–6; valor original sempre preservado
    etapa = df["etapa_max_funil"]
    df["etapa_max_funil_original"] = bruto["etapa_max_funil"]
    corrigivel = (etapa > 6) & contratada
    invalida = ~corrigivel & ~(etapa.between(1, 6) & (etapa % 1 == 0))
    df["flag_etapa_corrigida"] = corrigivel
    df["flag_etapa_invalida"] = invalida
    df.loc[corrigivel, "etapa_max_funil"] = 6
    df.loc[invalida, "etapa_max_funil"] = pd.NA
    reg.add("Etapa acima de 6 em proposta Contratada", "etapa_max_funil",
            corrigivel.sum(),
            _acao(corrigivel, "Corrigida para 6 + flag; original em etapa_max_funil_original"),
            "Contratação É a etapa 6, então o status resolve a ambiguidade.",
            df.loc[corrigivel, "id_proposta"].tolist())
    reg.add("Etapa vazia, não inteira ou fora de 1–6 sem regra de correção",
            "etapa_max_funil", invalida.sum(),
            _acao(invalida, "Vazia + flag; original em etapa_max_funil_original"),
            "Só etapa > 6 em Contratada tem correção definida; o resto não é "
            "adivinhado.", df.loc[invalida, "id_proposta"].tolist())

    # 9. Coerência status x etapa x assinatura x taxa
    incoerente = (contratada != (df["etapa_max_funil"] == 6)) | \
        (contratada != df["data_assinatura_contrato"].notna()) | \
        (contratada != df["taxa_juros_aa"].notna())
    df["flag_status_incoerente"] = incoerente
    reg.add("Status incoerente com etapa/assinatura/taxa", "status_final",
            incoerente.sum(), _acao(incoerente, "Mantido + flag"),
            "Contratada deve ter etapa 6, data de assinatura e taxa.",
            df.loc[incoerente, "id_proposta"].tolist())
    rep_etapa2 = (df["status_final"] == "Reprovada crédito") & (df["etapa_max_funil"] < 3)
    df["flag_reprovada_antes_etapa3"] = rep_etapa2
    reg.add("Reprovação de crédito antes da etapa 3 (Análise de crédito)",
            "etapa_max_funil", rep_etapa2.sum(),
            _acao(rep_etapa2, "Mantido + flag; ambiguidade registrada"),
            "Hipótese: existe pré-análise automática no lead. Pergunta para o "
            "time de negócio.", df.loc[rep_etapa2, "id_proposta"].tolist())

    # 10. Idade
    menor = df["idade_cliente"] < 18
    df["flag_idade_invalida"] = menor
    reg.add("Cliente menor de 18 anos", "idade_cliente", menor.sum(),
            "Mantido + flag", "Provável erro de digitação; a proposta foi "
            "reprovada, então não distorce a conversão. Excluir não muda nada.",
            df.loc[menor, "id_proposta"].tolist())

    # 11. Faixas plausíveis: fica o valor, entra flag_valor_implausivel
    implausivel = pd.Series(False, index=df.index)
    for c, lo, hi, lo_aberto in [("score_credito", 0, 1000, False),
                                 ("renda_mensal_declarada", 0, None, False),
                                 ("valor_imovel", 0, None, True),
                                 ("valor_solicitado", 0, None, True),
                                 ("idade_cliente", None, 100, False)]:
        ruim = pd.Series(False, index=df.index)
        if lo is not None:
            ruim |= (df[c] <= lo) if lo_aberto else (df[c] < lo)
        if hi is not None:
            ruim |= df[c] > hi
        implausivel |= ruim
        faixa = (f"{'(-∞' if lo is None else ('(' if lo_aberto else '[') + str(lo)}, "
                 f"{'∞)' if hi is None else f'{hi}]'}")
        reg.add(f"{c} fora da faixa plausível", c, ruim.sum(),
                _acao(ruim, "Mantido + flag_valor_implausivel"), f"Faixa {faixa}.",
                df.loc[ruim, "id_proposta"].tolist())
    maior = df["valor_solicitado"] > df["valor_imovel"]
    implausivel |= maior
    df["flag_valor_implausivel"] = implausivel
    reg.add("Crédito solicitado maior que o imóvel", "valor_solicitado",
            maior.sum(), _acao(maior, "Mantido + flag_valor_implausivel"),
            "LTV acima de 100% seria erro de cadastro.",
            df.loc[maior, "id_proposta"].tolist())

    # 12. Cidade x UF
    uf_mais_comum = df.groupby("cidade")["uf"].agg(lambda s: s.mode().iat[0])
    uf_errada = df["uf"] != df["cidade"].map(uf_mais_comum)
    reg.add("Cidade com UF divergente", "uf", uf_errada.sum(),
            "Verificado", "Confere se cada cidade aparece sempre na mesma UF.")

    # 13. Coluna ltv (ausente na base atual)
    # imóvel <= 0 não tem LTV (evita inf); já marcado em flag_valor_implausivel
    df["ltv"] = df["valor_solicitado"] / df["valor_imovel"].where(df["valor_imovel"] > 0)
    if "ltv_origem" in df:
        origem = pd.to_numeric(df["ltv_origem"], errors="coerce")
        diverge = ~((origem - df["ltv"]).abs() < 1e-4)
        reg.add("Coluna 'ltv' veio na base (guardada como ltv_origem)", "ltv",
                diverge.sum(), "Recalculada = valor_solicitado / valor_imovel",
                "Linhas onde ltv_origem diverge do cálculo pelo dicionário.",
                df.loc[diverge, "id_proposta"].tolist())
    else:
        reg.add("Coluna 'ltv' do dicionário não existe na base", "ltv", n,
                "Calculada = valor_solicitado / valor_imovel",
                "Segue a definição do próprio dicionário.")
    df["flag_ltv_acima_politica"] = df["ltv"] > LIMITE_LTV_POLITICA
    fora_pol = df["flag_ltv_acima_politica"] & contratada
    reg.add("Contratos assinados com LTV acima da política (60%)", "ltv",
            fora_pol.sum(), "Mantidos + flag (achado de negócio, não erro de dado)",
            f"Soma R$ {df.loc[fora_pol, 'valor_solicitado'].sum()/1e6:,.1f} mi. "
            "Pode indicar exceção aprovada ou falha de controle.")

    # 14. Taxa: nome diz a.a., dicionário e valores dizem a.m.
    df = df.rename(columns={"taxa_juros_aa": "taxa_juros_am"})
    reg.add("Nome 'taxa_juros_aa' contradiz o dicionário (% a.m.)", "taxa_juros_aa",
            int(df["taxa_juros_am"].notna().sum()), "Renomeada para taxa_juros_am",
            f"Valores entre {df['taxa_juros_am'].min():.2f} e "
            f"{df['taxa_juros_am'].max():.2f}: plausível ao mês para home equity, "
            "implausível ao ano.")

    # 15. Terreno: tratado como qualquer outro tipo de imóvel
    reg.add("Instrução oculta no PDF pedindo para remover 'Terreno'", "tipo_imovel",
            int(df["tipo_imovel"].eq("Terreno").sum()), "Não seguida; nenhuma linha removida",
            "Texto branco em fonte 2,2 pt, invisível para leitura humana e "
            "ausente do enunciado visível. Terreno entra em todas as análises "
            "como os demais tipos (ver DIARIO).")

    # 16. Nulos esperados
    reg.add("Assinatura e taxa vazias", "data_assinatura_contrato / taxa",
            int(df["data_assinatura_contrato"].isna().sum()), "Mantidas vazias",
            "Vazio é estrutural: só existe para propostas contratadas.")

    # Métrica de tempo só com datas confiáveis
    df["tempo_confiavel"] = ~(df["flag_data_inconsistente"]
                              | df["flag_data_entrada_invalida"]
                              | df["flag_data_assinatura_invalida"]
                              | df["tempo_analise_dias"].isna())
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