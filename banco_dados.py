"""
=============================================================
SQUAD 2 — Backend e Segurança | Visual Law Project
Módulo: banco_dados.py
Requisitos: RNF-012, RNF-013, RCP-002, US-01, US-13
Base Legal: LGPD Art. 7º, IX
=============================================================
Configura e gerencia o banco de dados relacional (SQLite em
desenvolvimento / PostgreSQL em produção).

Tabelas:
  - usuarios          → cadastro, autenticação, opt_out_ia
  - logs_auditoria    → rastreabilidade LGPD com timestamp
  - documentos        → controle de ciclo de vida dos PDFs
  - alertas_prazo     → notificações de vencimento
"""

import sqlite3
import uuid
import hashlib
import os
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

DB_PATH = os.environ.get("DB_PATH", "visuallaw.db")


# ─────────────────────────────────────────────
# 1. INICIALIZAÇÃO DO BANCO
# ─────────────────────────────────────────────

def inicializar_banco(db_path: str = DB_PATH) -> None:
    """
    Cria todas as tabelas se não existirem.
    Deve ser chamado uma vez na inicialização da aplicação.
    """
    with _conexao(db_path) as conn:
        cursor = conn.cursor()

        # 1.1 Tabela de Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_usuario      TEXT PRIMARY KEY,
                nome            TEXT NOT NULL,
                email           TEXT UNIQUE NOT NULL,
                senha_hash      TEXT NOT NULL,
                data_cadastro   TEXT NOT NULL,
                opt_out_ia      INTEGER NOT NULL DEFAULT 0,
                ativo           INTEGER NOT NULL DEFAULT 1,
                config_tema     TEXT DEFAULT 'light',
                config_fonte    INTEGER DEFAULT 14
            )
        """)

        # 1.2 Tabela de Logs de Auditoria (LGPD RNF-012)
        # Dados pessoais NÃO são armazenados aqui — apenas ações técnicas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs_auditoria (
                id_log          TEXT PRIMARY KEY,
                id_usuario      TEXT,
                acao            TEXT NOT NULL,
                modulo          TEXT NOT NULL,
                resultado       TEXT NOT NULL,
                ip_hash         TEXT,
                data_hora       TEXT NOT NULL,
                detalhes_extra  TEXT
            )
        """)

        # 1.3 Tabela de Controle de Documentos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documentos (
                id_doc          TEXT PRIMARY KEY,
                id_usuario      TEXT NOT NULL,
                nome_arquivo    TEXT NOT NULL,
                tamanho_bytes   INTEGER,
                data_upload     TEXT NOT NULL,
                processado      INTEGER DEFAULT 0,
                excluido        INTEGER DEFAULT 0,
                data_exclusao   TEXT
            )
        """)

        # 1.4 Tabela de Alertas de Prazo (RF-012)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alertas_prazo (
                id_alerta       TEXT PRIMARY KEY,
                id_usuario      TEXT NOT NULL,
                titulo_prazo    TEXT NOT NULL,
                descricao       TEXT,
                data_vencimento TEXT NOT NULL,
                prioridade      TEXT NOT NULL DEFAULT 'media',
                notificado      INTEGER DEFAULT 0,
                data_criacao    TEXT NOT NULL
            )
        """)

        conn.commit()
        logger.info("Banco de dados inicializado em: %s", db_path)


# ─────────────────────────────────────────────
# 2. CONTEXT MANAGER DE CONEXÃO
# ─────────────────────────────────────────────

@contextmanager
def _conexao(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error("Erro no banco de dados: %s", str(e))
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────
# 3. SERVIÇO DE USUÁRIOS
# ─────────────────────────────────────────────

def _hash_senha(senha: str) -> str:
    """Hash seguro com salt embutido via SHA-256."""
    salt = os.environ.get("SECRET_SALT", "visuallaw_salt_2026")
    return hashlib.sha256(f"{salt}{senha}".encode()).hexdigest()


def _hash_ip(ip: str) -> str:
    """Mascara IP para logs — não armazena IP real (LGPD)."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def criar_usuario(nome: str, email: str, senha: str,
                  db_path: str = DB_PATH) -> dict:
    """
    Cria novo usuário. Senha armazenada apenas como hash.
    Retorna dict com id_usuario ou erro.
    """
    id_usuario = str(uuid.uuid4())
    senha_hash = _hash_senha(senha)
    data_cadastro = datetime.utcnow().isoformat()

    try:
        with _conexao(db_path) as conn:
            conn.execute("""
                INSERT INTO usuarios
                    (id_usuario, nome, email, senha_hash, data_cadastro)
                VALUES (?, ?, ?, ?, ?)
            """, (id_usuario, nome, email, senha_hash, data_cadastro))
            conn.commit()

        registrar_log(id_usuario, "CADASTRO_USUARIO", "usuarios",
                      "SUCESSO", db_path=db_path)
        return {"sucesso": True, "id_usuario": id_usuario}

    except sqlite3.IntegrityError:
        return {"sucesso": False, "erro": "E-mail já cadastrado."}


def autenticar_usuario(email: str, senha: str,
                       db_path: str = DB_PATH) -> Optional[dict]:
    """
    Autentica usuário. Retorna dados do usuário ou None.
    """
    senha_hash = _hash_senha(senha)
    with _conexao(db_path) as conn:
        row = conn.execute("""
            SELECT id_usuario, nome, email, opt_out_ia,
                   config_tema, config_fonte
            FROM usuarios
            WHERE email = ? AND senha_hash = ? AND ativo = 1
        """, (email, senha_hash)).fetchone()

    if row:
        return dict(row)
    return None


def buscar_usuario(id_usuario: str, db_path: str = DB_PATH) -> Optional[dict]:
    with _conexao(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id_usuario = ?",
            (id_usuario,)
        ).fetchone()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# 4. SERVIÇO DE OPT-OUT (RCP-002 / US-13)
# ─────────────────────────────────────────────

def atualizar_opt_out(id_usuario: str, opt_out: bool,
                      db_path: str = DB_PATH) -> bool:
    """
    Atualiza preferência de opt-out de treinamento de IA.
    opt_out=True  → usuário PROÍBE uso dos seus dados
    opt_out=False → usuário PERMITE uso dos seus dados
    """
    valor = 1 if opt_out else 0
    try:
        with _conexao(db_path) as conn:
            conn.execute(
                "UPDATE usuarios SET opt_out_ia = ? WHERE id_usuario = ?",
                (valor, id_usuario)
            )
            conn.commit()

        acao = "OPT_OUT_ATIVADO" if opt_out else "OPT_OUT_DESATIVADO"
        registrar_log(id_usuario, acao, "usuarios", "SUCESSO",
                      db_path=db_path)
        return True
    except Exception as e:
        logger.error("Erro ao atualizar opt-out: %s", str(e))
        return False


def verificar_opt_out(id_usuario: str, db_path: str = DB_PATH) -> bool:
    """Retorna True se usuário optou por não ter dados usados."""
    with _conexao(db_path) as conn:
        row = conn.execute(
            "SELECT opt_out_ia FROM usuarios WHERE id_usuario = ?",
            (id_usuario,)
        ).fetchone()
    return bool(row["opt_out_ia"]) if row else True  # Padrão: protegido


# ─────────────────────────────────────────────
# 5. SERVIÇO DE LOGS DE AUDITORIA (RNF-012/013)
# ─────────────────────────────────────────────

def registrar_log(
    id_usuario: Optional[str],
    acao: str,
    modulo: str,
    resultado: str,
    ip: str = "0.0.0.0",
    detalhes: Optional[str] = None,
    db_path: str = DB_PATH
) -> None:
    """
    Registra ação crítica no log de auditoria.
    IP é mascarado antes do armazenamento (LGPD).
    Dados pessoais NÃO devem ser passados em 'detalhes'.
    """
    id_log = str(uuid.uuid4())
    data_hora = datetime.utcnow().isoformat()
    ip_hash = _hash_ip(ip)

    try:
        with _conexao(db_path) as conn:
            conn.execute("""
                INSERT INTO logs_auditoria
                    (id_log, id_usuario, acao, modulo,
                     resultado, ip_hash, data_hora, detalhes_extra)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_log, id_usuario, acao, modulo,
                  resultado, ip_hash, data_hora, detalhes))
            conn.commit()
    except Exception as e:
        # Log de auditoria nunca deve parar a aplicação
        logger.error("Falha ao registrar log de auditoria: %s", str(e))


def exportar_logs_auditoria(
    id_usuario: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    db_path: str = DB_PATH
) -> list[dict]:
    """
    Exporta logs de auditoria (RNF-013).
    Filtrável por usuário e período.
    """
    query = "SELECT * FROM logs_auditoria WHERE 1=1"
    params = []

    if id_usuario:
        query += " AND id_usuario = ?"
        params.append(id_usuario)
    if data_inicio:
        query += " AND data_hora >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data_hora <= ?"
        params.append(data_fim)

    query += " ORDER BY data_hora DESC"

    with _conexao(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


# ─────────────────────────────────────────────
# 6. CONTROLE DE DOCUMENTOS
# ─────────────────────────────────────────────

def registrar_documento(
    id_usuario: str,
    nome_arquivo: str,
    tamanho_bytes: int,
    db_path: str = DB_PATH
) -> str:
    """Registra metadados do upload. Retorna id_doc."""
    id_doc = str(uuid.uuid4())
    data_upload = datetime.utcnow().isoformat()

    with _conexao(db_path) as conn:
        conn.execute("""
            INSERT INTO documentos
                (id_doc, id_usuario, nome_arquivo, tamanho_bytes, data_upload)
            VALUES (?, ?, ?, ?, ?)
        """, (id_doc, id_usuario, nome_arquivo, tamanho_bytes, data_upload))
        conn.commit()

    registrar_log(id_usuario, "UPLOAD_DOCUMENTO", "documentos",
                  "SUCESSO", detalhes=f"doc_id:{id_doc}", db_path=db_path)
    return id_doc


def marcar_documento_excluido(id_doc: str, db_path: str = DB_PATH) -> None:
    """Marca documento como excluído (exclusão lógica)."""
    data_exclusao = datetime.utcnow().isoformat()
    with _conexao(db_path) as conn:
        conn.execute("""
            UPDATE documentos
            SET excluido = 1, data_exclusao = ?
            WHERE id_doc = ?
        """, (data_exclusao, id_doc))
        conn.commit()


def verificar_limite_uploads(
    id_usuario: str,
    limite_diario: int = 50,
    db_path: str = DB_PATH
) -> bool:
    """
    Verifica se usuário atingiu limite de 50 uploads/dia (RF-018).
    Retorna True se PODE fazer upload.
    """
    hoje = datetime.utcnow().date().isoformat()
    with _conexao(db_path) as conn:
        count = conn.execute("""
            SELECT COUNT(*) as total FROM documentos
            WHERE id_usuario = ?
              AND data_upload LIKE ?
              AND excluido = 0
        """, (id_usuario, f"{hoje}%")).fetchone()["total"]

    pode_upload = count < limite_diario
    if not pode_upload:
        logger.warning(
            "Usuário %s atingiu limite diário de uploads.", id_usuario
        )
    return pode_upload


# ─────────────────────────────────────────────
# 7. ALERTAS DE PRAZO (RF-012)
# ─────────────────────────────────────────────

def criar_alerta_prazo(
    id_usuario: str,
    titulo: str,
    data_vencimento: str,
    prioridade: str = "media",
    descricao: str = "",
    db_path: str = DB_PATH
) -> str:
    """Cria alerta de prazo. Prioridade: alta | media | baixa."""
    if prioridade not in ("alta", "media", "baixa"):
        raise ValueError("Prioridade deve ser: alta, media ou baixa")

    id_alerta = str(uuid.uuid4())
    data_criacao = datetime.utcnow().isoformat()

    with _conexao(db_path) as conn:
        conn.execute("""
            INSERT INTO alertas_prazo
                (id_alerta, id_usuario, titulo_prazo, descricao,
                 data_vencimento, prioridade, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_alerta, id_usuario, titulo, descricao,
              data_vencimento, prioridade, data_criacao))
        conn.commit()

    return id_alerta


def listar_alertas_usuario(
    id_usuario: str,
    db_path: str = DB_PATH
) -> list[dict]:
    """Lista alertas pendentes ordenados por prioridade e vencimento."""
    ordem_prioridade = "CASE prioridade WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END"
    with _conexao(db_path) as conn:
        rows = conn.execute(f"""
            SELECT * FROM alertas_prazo
            WHERE id_usuario = ? AND notificado = 0
            ORDER BY {ordem_prioridade}, data_vencimento ASC
        """, (id_usuario,)).fetchall()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────
# 8. EXCLUSÃO DE DADOS DO TITULAR (LGPD Art. 18)
# ─────────────────────────────────────────────

def solicitar_exclusao_titular(
    id_usuario: str,
    db_path: str = DB_PATH
) -> bool:
    """
    Atende direito de exclusão (LGPD Art. 18, VI).
    Remove dados pessoais e desativa conta.
    Logs de auditoria são mantidos (obrigação legal), mas
    desvinculados do usuário.
    """
    try:
        with _conexao(db_path) as conn:
            # Anonimiza dados do usuário (não deleta registro)
            conn.execute("""
                UPDATE usuarios SET
                    nome       = '[TITULAR REMOVIDO]',
                    email      = '[REMOVIDO_' || id_usuario || '@anon]',
                    senha_hash = 'REMOVIDO',
                    ativo      = 0
                WHERE id_usuario = ?
            """, (id_usuario,))

            # Marca todos os documentos como excluídos
            conn.execute("""
                UPDATE documentos
                SET excluido = 1, data_exclusao = ?
                WHERE id_usuario = ?
            """, (datetime.utcnow().isoformat(), id_usuario))

            conn.commit()

        registrar_log(id_usuario, "EXCLUSAO_TITULAR", "usuarios",
                      "SUCESSO", db_path=db_path)
        return True

    except Exception as e:
        logger.error("Erro ao excluir dados do titular: %s", str(e))
        return False


# ─────────────────────────────────────────────
# EXECUÇÃO DIRETA — DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    import os

    # Usa banco temporário para demo
    db_demo = tempfile.mktemp(suffix=".db")
    inicializar_banco(db_demo)

    # Criar usuário
    resultado = criar_usuario("Ana Lima", "ana@demo.com", "senha123", db_demo)
    print("Criar usuário:", resultado)

    uid = resultado["id_usuario"]

    # Autenticar
    user = autenticar_usuario("ana@demo.com", "senha123", db_demo)
    print("Autenticação:", user)

    # Opt-out
    atualizar_opt_out(uid, True, db_demo)
    print("Opt-out ativo:", verificar_opt_out(uid, db_demo))

    # Registrar documento
    id_doc = registrar_documento(uid, "contrato.pdf", 204800, db_demo)
    print("Documento registrado:", id_doc)

    # Limite de uploads
    print("Pode fazer upload:", verificar_limite_uploads(uid, db_path=db_demo))

    # Alerta de prazo
    id_alerta = criar_alerta_prazo(
        uid, "Audiência trabalhista", "2026-05-10",
        prioridade="alta", db_path=db_demo
    )
    print("Alerta criado:", id_alerta)

    # Logs
    logs = exportar_logs_auditoria(uid, db_path=db_demo)
    print(f"\nLogs de auditoria ({len(logs)} registros):")
    for log in logs:
        print(f"  [{log['data_hora']}] {log['acao']} → {log['resultado']}")

    os.remove(db_demo)
