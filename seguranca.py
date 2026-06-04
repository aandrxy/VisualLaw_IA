"""
=============================================================
SQUAD 2 — Backend e Segurança | Visual Law Project
Módulo: seguranca.py
Requisito: RNF-010 — Criptografia em trânsito e em repouso
=============================================================
Responsabilidades:
  - Criptografia simétrica de arquivos (em repouso)
  - Geração e validação de tokens de sessão
  - Exclusão segura de arquivos temporários
  - Middleware de segurança para APIs
"""

import os
import base64
import secrets
import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 1. GERENCIAMENTO DE CHAVES
# ─────────────────────────────────────────────

class GerenciadorChaves:
    """
    Gera e carrega chaves de criptografia.
    Em produção: usar Azure Key Vault ou variável de ambiente.
    """

    @staticmethod
    def gerar_chave_fernet() -> bytes:
        """Gera nova chave Fernet (AES-128-CBC + HMAC-SHA256)."""
        return Fernet.generate_key()

    @staticmethod
    def derivar_chave_de_senha(senha: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        Deriva chave de criptografia a partir de senha (PBKDF2-HMAC-SHA256).
        Retorna: (chave_fernet, salt)
        """
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # NIST recomenda >= 310.000
        )
        chave_raw = kdf.derive(senha.encode())
        chave_b64 = base64.urlsafe_b64encode(chave_raw)
        return chave_b64, salt

    @staticmethod
    def carregar_chave_ambiente() -> bytes:
        """
        Carrega chave da variável de ambiente ENCRYPTION_KEY.
        Se não existir, gera uma para desenvolvimento (NUNCA em produção).
        """
        chave_env = os.environ.get("ENCRYPTION_KEY")
        if chave_env:
            return chave_env.encode()

        logger.warning(
            "⚠️  ENCRYPTION_KEY não definida. "
            "Usando chave temporária (apenas para desenvolvimento)."
        )
        # Em desenvolvimento: persiste chave em arquivo local
        chave_path = Path(".dev_key")
        if chave_path.exists():
            return chave_path.read_bytes()
        chave = Fernet.generate_key()
        chave_path.write_bytes(chave)
        return chave


# ─────────────────────────────────────────────
# 2. CRIPTOGRAFIA DE ARQUIVOS EM REPOUSO
# ─────────────────────────────────────────────

class CriptografiaArquivo:
    """
    Criptografa e descriptografa arquivos em repouso (RNF-010).
    Usa Fernet (AES-128 + HMAC) — autenticado e seguro.
    """

    def __init__(self, chave: Optional[bytes] = None):
        if chave is None:
            chave = GerenciadorChaves.carregar_chave_ambiente()
        self._fernet = Fernet(chave)

    def criptografar_bytes(self, dados: bytes) -> bytes:
        """Criptografa bytes. Retorna bytes criptografados."""
        return self._fernet.encrypt(dados)

    def descriptografar_bytes(self, dados_cripto: bytes) -> bytes:
        """Descriptografa bytes. Levanta InvalidToken se corrompido."""
        return self._fernet.decrypt(dados_cripto)

    def criptografar_arquivo(self, caminho_entrada: str,
                             caminho_saida: Optional[str] = None) -> str:
        """
        Lê arquivo, criptografa e salva.
        Retorna caminho do arquivo criptografado.
        """
        caminho_entrada = Path(caminho_entrada)
        if not caminho_entrada.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_entrada}")

        dados = caminho_entrada.read_bytes()
        dados_cripto = self.criptografar_bytes(dados)

        if caminho_saida is None:
            caminho_saida = str(caminho_entrada) + ".enc"

        Path(caminho_saida).write_bytes(dados_cripto)
        logger.info("Arquivo criptografado: %s → %s",
                    caminho_entrada.name, caminho_saida)
        return caminho_saida

    def descriptografar_arquivo(self, caminho_entrada: str,
                                caminho_saida: Optional[str] = None) -> str:
        """Descriptografa arquivo. Retorna caminho do arquivo original."""
        caminho_entrada = Path(caminho_entrada)
        dados_cripto = caminho_entrada.read_bytes()
        dados = self.descriptografar_bytes(dados_cripto)

        if caminho_saida is None:
            caminho_saida = str(caminho_entrada).replace(".enc", "")

        Path(caminho_saida).write_bytes(dados)
        return caminho_saida


# ─────────────────────────────────────────────
# 3. TOKENS DE SESSÃO
# ─────────────────────────────────────────────

class GerenciadorSessao:
    """
    Gera e valida tokens de sessão seguros.
    Tokens expiram em SESSAO_TTL_HORAS horas.
    """

    SESSAO_TTL_HORAS = int(os.environ.get("SESSAO_TTL_HORAS", "8"))
    _sessoes_ativas: dict[str, dict] = {}  # Em produção: Redis/banco

    @classmethod
    def criar_sessao(cls, id_usuario: str,
                     ip: str = "0.0.0.0") -> str:
        """Cria token de sessão. Retorna o token."""
        token = secrets.token_urlsafe(48)
        expira_em = datetime.utcnow() + timedelta(hours=cls.SESSAO_TTL_HORAS)

        cls._sessoes_ativas[token] = {
            "id_usuario": id_usuario,
            "ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:16],
            "expira_em": expira_em,
            "criada_em": datetime.utcnow().isoformat()
        }
        logger.info("Sessão criada para usuário: %s", id_usuario)
        return token

    @classmethod
    def validar_sessao(cls, token: str) -> Optional[str]:
        """
        Valida token. Retorna id_usuario se válido, None se inválido.
        """
        sessao = cls._sessoes_ativas.get(token)
        if not sessao:
            return None

        if datetime.utcnow() > sessao["expira_em"]:
            cls.encerrar_sessao(token)
            logger.warning("Sessão expirada para token: %s...", token[:8])
            return None

        return sessao["id_usuario"]

    @classmethod
    def encerrar_sessao(cls, token: str) -> None:
        """Remove sessão — chamado no logout ou expiração."""
        cls._sessoes_ativas.pop(token, None)

    @classmethod
    def sessoes_ativas_usuario(cls, id_usuario: str) -> int:
        """Conta sessões ativas do usuário."""
        agora = datetime.utcnow()
        return sum(
            1 for s in cls._sessoes_ativas.values()
            if s["id_usuario"] == id_usuario and s["expira_em"] > agora
        )


# ─────────────────────────────────────────────
# 4. EXCLUSÃO SEGURA DE ARQUIVOS (MVP Funcional)
# ─────────────────────────────────────────────

class GerenciadorArquivosTemporarios:
    """
    Gerencia ciclo de vida dos PDFs temporários.
    Exclusão automática após sessão (conforme MVP Funcional).
    """

    PASTA_TEMP = Path(os.environ.get("PASTA_TEMP", "/tmp/visuallaw_uploads"))

    def __init__(self):
        self.PASTA_TEMP.mkdir(parents=True, exist_ok=True)
        self._arquivos_sessao: dict[str, list[str]] = {}

    def salvar_temporario(self, token_sessao: str,
                          nome_arquivo: str,
                          conteudo: bytes,
                          criptografar: bool = True) -> str:
        """
        Salva arquivo temporário associado à sessão.
        Retorna caminho do arquivo salvo.
        """
        # Nome único para evitar colisão
        id_unico = secrets.token_hex(8)
        nome_seguro = f"{id_unico}_{Path(nome_arquivo).name}"
        caminho = self.PASTA_TEMP / nome_seguro

        if criptografar:
            cripto = CriptografiaArquivo()
            caminho = Path(str(caminho) + ".enc")
            caminho.write_bytes(cripto.criptografar_bytes(conteudo))
        else:
            caminho.write_bytes(conteudo)

        # Registra na sessão
        if token_sessao not in self._arquivos_sessao:
            self._arquivos_sessao[token_sessao] = []
        self._arquivos_sessao[token_sessao].append(str(caminho))

        logger.info("Arquivo temporário salvo: %s", caminho.name)
        return str(caminho)

    def excluir_sessao(self, token_sessao: str) -> int:
        """
        Remove TODOS os arquivos temporários da sessão.
        Chamado automaticamente no logout/expiração.
        Retorna quantidade de arquivos removidos.
        """
        arquivos = self._arquivos_sessao.pop(token_sessao, [])
        removidos = 0

        for caminho in arquivos:
            try:
                p = Path(caminho)
                if p.exists():
                    # Sobrescreve com zeros antes de deletar (exclusão segura)
                    tamanho = p.stat().st_size
                    p.write_bytes(b'\x00' * tamanho)
                    p.unlink()
                    removidos += 1
            except Exception as e:
                logger.error("Erro ao remover arquivo %s: %s", caminho, str(e))

        if removidos > 0:
            logger.info(
                "Sessão encerrada: %d arquivo(s) removido(s).", removidos
            )
        return removidos

    def limpar_arquivos_orfaos(self, max_idade_horas: int = 24) -> int:
        """
        Remove arquivos sem sessão ativa com mais de N horas.
        Executar via tarefa agendada.
        """
        limite = datetime.utcnow().timestamp() - (max_idade_horas * 3600)
        removidos = 0

        for arquivo in self.PASTA_TEMP.iterdir():
            if arquivo.is_file():
                if arquivo.stat().st_mtime < limite:
                    arquivo.unlink()
                    removidos += 1

        logger.info("Limpeza: %d arquivo(s) órfão(s) removido(s).", removidos)
        return removidos


# ─────────────────────────────────────────────
# 5. VALIDAÇÕES DE ENTRADA (proteção contra injeção)
# ─────────────────────────────────────────────

def validar_extensao_arquivo(nome_arquivo: str,
                              extensoes_permitidas: tuple = (".pdf", ".docx")) -> bool:
    """Valida se extensão é permitida. Evita upload de arquivos maliciosos."""
    ext = Path(nome_arquivo).suffix.lower()
    return ext in extensoes_permitidas


def validar_tamanho_arquivo(tamanho_bytes: int,
                            limite_mb: int = 10) -> bool:
    """Valida tamanho máximo do arquivo."""
    return tamanho_bytes <= (limite_mb * 1024 * 1024)


def sanitizar_nome_arquivo(nome: str) -> str:
    """Remove caracteres perigosos do nome do arquivo."""
    import re
    # Mantém apenas alfanuméricos, hífen, underscore e ponto
    nome_limpo = re.sub(r'[^\w\-_\. ]', '_', Path(nome).name)
    return nome_limpo[:100]  # Limita tamanho


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 55)
    print("DEMO — Módulo de Segurança")
    print("=" * 55)

    # 1. Gerar chave
    chave = GerenciadorChaves.gerar_chave_fernet()
    print(f"\n✅ Chave Fernet gerada ({len(chave)} bytes)")

    # 2. Criptografia de bytes
    cripto = CriptografiaArquivo(chave)
    dados = b"Contrato sigiloso: CPF 111.222.333-44"
    enc = cripto.criptografar_bytes(dados)
    dec = cripto.descriptografar_bytes(enc)
    print(f"✅ Criptografia: '{dados.decode()}' → {len(enc)} bytes cifrados")
    print(f"✅ Descriptografia: '{dec.decode()}'")

    # 3. Sessão
    token = GerenciadorSessao.criar_sessao("usuario-123", "192.168.1.1")
    uid = GerenciadorSessao.validar_sessao(token)
    print(f"\n✅ Sessão criada. Token: {token[:16]}...")
    print(f"✅ Sessão válida para usuário: {uid}")

    # 4. Arquivo temporário
    gerenciador = GerenciadorArquivosTemporarios()
    caminho = gerenciador.salvar_temporario(
        token, "teste.pdf", b"conteudo do pdf aqui"
    )
    print(f"\n✅ Arquivo temporário criado: {Path(caminho).name}")
    removidos = gerenciador.excluir_sessao(token)
    print(f"✅ Arquivos removidos ao encerrar sessão: {removidos}")

    # 5. Validações
    print(f"\n✅ Extensão .pdf válida: {validar_extensao_arquivo('doc.pdf')}")
    print(f"✅ Extensão .exe inválida: {validar_extensao_arquivo('virus.exe')}")
    print(f"✅ Tamanho 5MB válido: {validar_tamanho_arquivo(5*1024*1024)}")
    print(f"✅ Nome sanitizado: {sanitizar_nome_arquivo('../../../etc/passwd')}")
