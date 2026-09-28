"""
schema.py — Contratos de dados da extração de laudos (Parte 3).

Dois níveis:
1. RespostaLLM: o que o Gemini devolve. Só texto literal do laudo + status +
   trecho de evidência. O LLM NÃO converte números nem datas.
2. LaudoExtraido: a saída final, sempre no mesmo formato, já normalizada
   pelo código (normalizar.py). É o que vai para extracoes.json.
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

CAMPOS = [
    "tipo_imovel", "endereco", "cidade", "uf",
    "area_privativa_m2", "area_total_m2", "area_construida_m2", "area_terreno_m2",
    "ano_construcao", "valor_avaliacao", "matricula",
    "onus_situacao", "onus_descricao", "data_vistoria",
    "responsavel_nome", "responsavel_registro",
]

TIPOS_IMOVEL = ["apartamento", "casa", "comercial", "galpao", "terreno", "rural"]
SITUACOES_ONUS = ["sem_onus", "com_onus", "nao_verificado", "nao_informado"]

StatusLLM = Literal["encontrado", "nao_informado", "nao_aplicavel", "contraditorio", "inferido"]
# O código pode rebaixar um campo para "nao_verificado" (evidência ausente ou
# valor que não normaliza). Esse status nunca vem do LLM.
StatusFinal = Literal["encontrado", "nao_informado", "nao_aplicavel",
                      "contraditorio", "inferido", "nao_verificado"]

Valor = Union[float, int, str, list, None]


# ----------------------------------------------------------------------------
# 1. O que o LLM devolve
# ----------------------------------------------------------------------------
class CampoLLM(BaseModel):
    valor_texto: Optional[str] = Field(
        None, description="Valor copiado do laudo como está escrito. Null se não houver.")
    status: StatusLLM
    trecho_fonte: Optional[str] = Field(
        None, description="Trecho LITERAL do laudo que sustenta o valor.")
    valores_conflitantes: Optional[list[str]] = Field(
        None, description="Só quando status = contraditorio: cada valor como está escrito.")


class RespostaLLM(BaseModel):
    tipo_imovel: CampoLLM
    endereco: CampoLLM
    cidade: CampoLLM
    uf: CampoLLM
    area_privativa_m2: CampoLLM
    area_total_m2: CampoLLM
    area_construida_m2: CampoLLM
    area_terreno_m2: CampoLLM
    ano_construcao: CampoLLM
    valor_avaliacao: CampoLLM
    matricula: CampoLLM
    onus_situacao: CampoLLM
    onus_descricao: CampoLLM
    data_vistoria: CampoLLM
    responsavel_nome: CampoLLM
    responsavel_registro: CampoLLM


# ----------------------------------------------------------------------------
# 2. Saída final (formato fixo)
# ----------------------------------------------------------------------------
class CampoFinal(BaseModel):
    valor: Valor = None
    status: StatusFinal
    trecho_fonte: Optional[str] = None
    motivo: Optional[str] = Field(
        None, description="Por que o código rebaixou ou ajustou o campo.")


class LaudoExtraido(BaseModel):
    arquivo: str
    modelo: str
    erro: Optional[str] = None
    campos: dict[str, CampoFinal]

    @classmethod
    def vazio(cls, arquivo: str, modelo: str, erro: str) -> "LaudoExtraido":
        """Laudo que falhou: mesmo formato, todos os campos como não verificados."""
        return cls(arquivo=arquivo, modelo=modelo, erro=erro,
                   campos={c: CampoFinal(status="nao_verificado", motivo=erro) for c in CAMPOS})
