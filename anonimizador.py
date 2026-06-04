"""
=============================================================
SQUAD 2 — Backend e Segurança | Visual Law Project
Módulo: anonimizador.py
Requisito: RCP-001 — Anonimização automática de dados sensíveis
Base Legal: LGPD Art. 7º, IX — Legítimo Interesse
=============================================================
Substitui CPFs por [DADO PROTEGIDO] e nomes por Parte A, Parte B...
ANTES de qualquer envio para a API de IA ou armazenamento.
"""

import re
import unicodedata
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. PADRÕES REGEX
# ─────────────────────────────────────────────

# CPF: 000.000.000-00 ou 00000000000
CPF_PATTERN = re.compile(
    r'\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?\d{2}\b'
)

# CNPJ: 00.000.000/0000-00 ou 00000000000000
CNPJ_PATTERN = re.compile(
    r'\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}\b'
)

# RG: formatos variados — ex: 12.345.678-9 ou 123456789
RG_PATTERN = re.compile(
    r'\b\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}[-\s]?[\dxX]\b'
)

# E-mail
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

# Telefone: (00) 00000-0000 ou 0000000000
TELEFONE_PATTERN = re.compile(
    r'\(?\d{2}\)?[\s\-]?\d{4,5}[\-\s]?\d{4}\b'
)

# Nomes próprios — heurística: 2+ palavras capitalizadas consecutivas
# Captura padrões como "João da Silva" ou "Maria Aparecida Santos"
NOME_PATTERN = re.compile(
    r'\b([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][a-záéíóúàâêôãõç]+(?:\s+(?:da|de|do|das|dos|e|'
    r'[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][a-záéíóúàâêôãõç]+)){1,5})\b'
)


# ─────────────────────────────────────────────
# 2. CLASSE PRINCIPAL
# ─────────────────────────────────────────────

class Anonimizador:
    """
    Anonimiza dados sensíveis de um texto jurídico.
    Mantém mapeamento interno para rastreabilidade auditável
    (nunca exposto ao usuário ou à IA).
    """

    def __init__(self):
        self._mapa_nomes: dict[str, str] = {}   # {nome_real: "Parte X"}
        self._contador_partes = 0
        self._letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def _proxima_parte(self) -> str:
        idx = self._contador_partes
        self._contador_partes += 1
        if idx < 26:
            return f"Parte {self._letras[idx]}"
        return f"Parte {idx + 1}"

    def _substituir_nome(self, match: re.Match) -> str:
        nome = match.group(0)
        # Ignora nomes muito curtos (artigos, preposições soltas)
        if len(nome) < 6:
            return nome
        if nome not in self._mapa_nomes:
            self._mapa_nomes[nome] = self._proxima_parte()
        return self._mapa_nomes[nome]

    def anonimizar(self, texto: str) -> tuple[str, dict]:
        """
        Parâmetros:
            texto: texto bruto extraído do PDF
        Retorna:
            (texto_anonimizado, relatorio_substituicoes)
        """
        if not texto or not isinstance(texto, str):
            raise ValueError("Texto inválido ou vazio.")

        original = texto
        substituicoes = {
            "cpfs_encontrados": 0,
            "cnpjs_encontrados": 0,
            "rgs_encontrados": 0,
            "emails_encontrados": 0,
            "telefones_encontrados": 0,
            "nomes_encontrados": 0,
        }

        # 2.1 CPF
        cpfs = CPF_PATTERN.findall(texto)
        substituicoes["cpfs_encontrados"] = len(cpfs)
        texto = CPF_PATTERN.sub("[DADO PROTEGIDO - CPF]", texto)

        # 2.2 CNPJ
        cnpjs = CNPJ_PATTERN.findall(texto)
        substituicoes["cnpjs_encontrados"] = len(cnpjs)
        texto = CNPJ_PATTERN.sub("[DADO PROTEGIDO - CNPJ]", texto)

        # 2.3 RG
        rgs = RG_PATTERN.findall(texto)
        substituicoes["rgs_encontrados"] = len(rgs)
        texto = RG_PATTERN.sub("[DADO PROTEGIDO - RG]", texto)

        # 2.4 E-mail
        emails = EMAIL_PATTERN.findall(texto)
        substituicoes["emails_encontrados"] = len(emails)
        texto = EMAIL_PATTERN.sub("[DADO PROTEGIDO - EMAIL]", texto)

        # 2.5 Telefone
        fones = TELEFONE_PATTERN.findall(texto)
        substituicoes["telefones_encontrados"] = len(fones)
        texto = TELEFONE_PATTERN.sub("[DADO PROTEGIDO - TEL]", texto)

        # 2.6 Nomes próprios (último — após remover CPF/e-mail que possam
        #     conter partes de palavras capitalizadas)
        nomes_encontrados = set(NOME_PATTERN.findall(texto))
        substituicoes["nomes_encontrados"] = len(nomes_encontrados)
        texto = NOME_PATTERN.sub(self._substituir_nome, texto)

        logger.info(
            "Anonimização concluída. Substituições: %s", substituicoes
        )

        return texto, substituicoes

    def relatorio_mapa(self) -> dict:
        """
        Retorna o mapa interno (para auditoria interna apenas).
        NUNCA deve ser enviado ao usuário ou à IA.
        """
        return dict(self._mapa_nomes)


# ─────────────────────────────────────────────
# 3. FUNÇÃO UTILITÁRIA DE ALTO NÍVEL
# ─────────────────────────────────────────────

def anonimizar_texto(texto: str) -> tuple[str, dict]:
    """
    Função de conveniência. Cria instância isolada por chamada.
    Uso: texto_limpo, relatorio = anonimizar_texto(texto_bruto)
    """
    anon = Anonimizador()
    return anon.anonimizar(texto)


# ─────────────────────────────────────────────
# 4. TESTES RÁPIDOS (executar diretamente)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    texto_exemplo = """
    Contrato celebrado entre João da Silva, CPF 123.456.789-00,
    residente à Rua das Flores, e Maria Aparecida Santos,
    CPF 987.654.321-00, e-mail maria@email.com,
    telefone (11) 98765-4321, CNPJ 12.345.678/0001-90.
    O contratante Carlos Eduardo Ferreira assume as obrigações descritas.
    """

    texto_limpo, relatorio = anonimizar_texto(texto_exemplo)
    print("=" * 60)
    print("TEXTO ANONIMIZADO:")
    print(texto_limpo)
    print("\nRELATÓRIO DE SUBSTITUIÇÕES:")
    for k, v in relatorio.items():
        print(f"  {k}: {v}")
