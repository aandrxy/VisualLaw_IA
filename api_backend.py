"""
=============================================================
SQUAD 2 — Backend e Segurança | Visual Law Project
Módulo: api_backend.py
Tecnologia: Python (Flask) simulando estrutura de API REST
Requisitos: RF-001 a RF-004, RNF-010, RCP-001, RCP-002
=============================================================
Define os endpoints REST que o Frontend (Squad 1) e o motor
de IA (Squad 3) consomem.

Endpoints implementados:
  POST /auth/cadastro          → Criar conta
  POST /auth/login             → Autenticar
  POST /auth/logout            → Encerrar sessão
  POST /documentos/upload      → Upload de PDF (com anonimização)
  GET  /documentos/            → Listar documentos do usuário
  DELETE /documentos/<id>      → Excluir documento
  PUT  /usuarios/opt-out       → Atualizar preferência de opt-out
  GET  /logs/auditoria         → Exportar logs (admin)
  GET  /alertas/               → Listar alertas de prazo
  POST /alertas/               → Criar alerta de prazo
  GET  /health                 → Health check do serviço
"""

import os
import io
import logging
from functools import wraps
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import fitz  # PyMuPDF

from anonimizador import anonimizar_texto
from banco_dados import (
    inicializar_banco, criar_usuario, autenticar_usuario,
    buscar_usuario, atualizar_opt_out, verificar_opt_out,
    registrar_log, exportar_logs_auditoria,
    registrar_documento, marcar_documento_excluido,
    verificar_limite_uploads, criar_alerta_prazo,
    listar_alertas_usuario
)
from seguranca import (
    GerenciadorSessao, GerenciadorArquivosTemporarios,
    CriptografiaArquivo, validar_extensao_arquivo,
    validar_tamanho_arquivo, sanitizar_nome_arquivo
)

# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins="*")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB máximo

# Inicializa banco na startup
inicializar_banco()

gerenciador_arquivos = GerenciadorArquivosTemporarios()


# ─────────────────────────────────────────────
# DECORADORES DE SEGURANÇA
# ─────────────────────────────────────────────

def requer_autenticacao(f):
    """Decorator: exige token de sessão válido no header."""
    @wraps(f)
    def verificar(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"erro": "Token de autenticação ausente."}), 401

        id_usuario = GerenciadorSessao.validar_sessao(token)
        if not id_usuario:
            return jsonify({"erro": "Sessão inválida ou expirada."}), 401

        g.id_usuario = id_usuario
        g.token_sessao = token
        return f(*args, **kwargs)
    return verificar


def obter_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0")


# ─────────────────────────────────────────────
# 1. AUTENTICAÇÃO
# ─────────────────────────────────────────────

@app.route("/auth/cadastro", methods=["POST"])
def cadastro():
    """
    POST /auth/cadastro
    Body: { nome, email, senha }
    """
    dados = request.get_json(force=True) or {}
    nome = dados.get("nome", "").strip()
    email = dados.get("email", "").strip().lower()
    senha = dados.get("senha", "")

    if not all([nome, email, senha]):
        return jsonify({"erro": "Campos obrigatórios: nome, email, senha."}), 400

    if len(senha) < 8:
        return jsonify({"erro": "Senha deve ter no mínimo 8 caracteres."}), 400

    resultado = criar_usuario(nome, email, senha)

    if not resultado["sucesso"]:
        return jsonify({"erro": resultado["erro"]}), 409

    registrar_log(resultado["id_usuario"], "CADASTRO_API", "auth",
                  "SUCESSO", ip=obter_ip())
    return jsonify({
        "mensagem": "Cadastro realizado com sucesso.",
        "id_usuario": resultado["id_usuario"]
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """
    POST /auth/login
    Body: { email, senha }
    """
    dados = request.get_json(force=True) or {}
    email = dados.get("email", "").strip().lower()
    senha = dados.get("senha", "")

    usuario = autenticar_usuario(email, senha)

    if not usuario:
        registrar_log(None, "LOGIN_FALHA", "auth",
                      "FALHA", ip=obter_ip())
        return jsonify({"erro": "Credenciais inválidas."}), 401

    token = GerenciadorSessao.criar_sessao(
        usuario["id_usuario"], ip=obter_ip()
    )

    registrar_log(usuario["id_usuario"], "LOGIN_SUCESSO", "auth",
                  "SUCESSO", ip=obter_ip())

    return jsonify({
        "token": token,
        "usuario": {
            "id": usuario["id_usuario"],
            "nome": usuario["nome"],
            "email": usuario["email"],
            "opt_out_ia": bool(usuario["opt_out_ia"])
        }
    }), 200


@app.route("/auth/logout", methods=["POST"])
@requer_autenticacao
def logout():
    """POST /auth/logout — Encerra sessão e remove arquivos temporários."""
    removidos = gerenciador_arquivos.excluir_sessao(g.token_sessao)
    GerenciadorSessao.encerrar_sessao(g.token_sessao)

    registrar_log(g.id_usuario, "LOGOUT", "auth", "SUCESSO", ip=obter_ip(),
                  detalhes=f"arquivos_removidos:{removidos}")

    return jsonify({
        "mensagem": "Sessão encerrada.",
        "arquivos_temporarios_removidos": removidos
    }), 200


# ─────────────────────────────────────────────
# 2. DOCUMENTOS
# ─────────────────────────────────────────────

@app.route("/documentos/upload", methods=["POST"])
@requer_autenticacao
def upload_documento():
    """
    POST /documentos/upload
    Form-data: arquivo (PDF/Word)

    Pipeline:
      1. Valida extensão e tamanho
      2. Verifica limite de 50 uploads/dia
      3. Extrai texto com PyMuPDF
      4. ANONIMIZA (RCP-001) — antes de qualquer uso
      5. Salva arquivo criptografado (RNF-010)
      6. Registra no banco
      7. Retorna texto anonimizado + relatório
    """
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arquivo = request.files["arquivo"]
    nome = sanitizar_nome_arquivo(arquivo.filename or "documento.pdf")

    # Validações
    if not validar_extensao_arquivo(nome):
        return jsonify({
            "erro": "Formato não permitido. Envie PDF ou DOCX."
        }), 415

    conteudo = arquivo.read()
    if not validar_tamanho_arquivo(len(conteudo)):
        return jsonify({"erro": "Arquivo excede 10MB."}), 413

    # Limite diário
    if not verificar_limite_uploads(g.id_usuario):
        return jsonify({
            "erro": "Limite de 50 uploads diários atingido."
        }), 429

    # Extração de texto (PyMuPDF)
    try:
        doc_pdf = fitz.open(stream=conteudo, filetype="pdf")
        texto_bruto = ""
        for pagina in doc_pdf:
            texto_bruto += pagina.get_text()
        doc_pdf.close()
    except Exception as e:
        logger.error("Erro ao extrair texto do PDF: %s", str(e))
        return jsonify({"erro": "Falha ao processar o PDF."}), 422

    # ANONIMIZAÇÃO OBRIGATÓRIA — RCP-001
    texto_anonimizado, relatorio = anonimizar_texto(texto_bruto)

    # Salva arquivo criptografado
    caminho_enc = gerenciador_arquivos.salvar_temporario(
        g.token_sessao, nome, conteudo, criptografar=True
    )

    # Registra no banco
    id_doc = registrar_documento(
        g.id_usuario, nome, len(conteudo)
    )

    registrar_log(
        g.id_usuario, "UPLOAD_DOCUMENTO", "documentos", "SUCESSO",
        ip=obter_ip(),
        detalhes=f"doc_id:{id_doc}|cpfs:{relatorio['cpfs_encontrados']}"
                 f"|nomes:{relatorio['nomes_encontrados']}"
    )

    return jsonify({
        "id_doc": id_doc,
        "nome_arquivo": nome,
        "texto_anonimizado": texto_anonimizado,
        "relatorio_anonimizacao": relatorio,
        "aviso": (
            "⚠️ Dados sensíveis foram anonimizados antes do processamento. "
            "Nenhum dado pessoal foi enviado à IA."
        )
    }), 201


@app.route("/documentos/", methods=["GET"])
@requer_autenticacao
def listar_documentos():
    """GET /documentos/ — Lista documentos do usuário."""
    from banco_dados import _conexao
    with _conexao() as conn:
        rows = conn.execute("""
            SELECT id_doc, nome_arquivo, tamanho_bytes,
                   data_upload, processado
            FROM documentos
            WHERE id_usuario = ? AND excluido = 0
            ORDER BY data_upload DESC
        """, (g.id_usuario,)).fetchall()

    return jsonify({
        "documentos": [dict(r) for r in rows],
        "total": len(rows)
    }), 200


@app.route("/documentos/<id_doc>", methods=["DELETE"])
@requer_autenticacao
def excluir_documento(id_doc: str):
    """DELETE /documentos/<id_doc> — Exclui documento."""
    marcar_documento_excluido(id_doc)
    registrar_log(g.id_usuario, "EXCLUSAO_DOCUMENTO", "documentos",
                  "SUCESSO", ip=obter_ip(),
                  detalhes=f"doc_id:{id_doc}")
    return jsonify({"mensagem": "Documento excluído."}), 200


# ─────────────────────────────────────────────
# 3. OPT-OUT (RCP-002 / US-13)
# ─────────────────────────────────────────────

@app.route("/usuarios/opt-out", methods=["PUT"])
@requer_autenticacao
def atualizar_preferencia_opt_out():
    """
    PUT /usuarios/opt-out
    Body: { opt_out: true | false }
    """
    dados = request.get_json(force=True) or {}
    opt_out = dados.get("opt_out")

    if not isinstance(opt_out, bool):
        return jsonify({"erro": "Campo 'opt_out' deve ser true ou false."}), 400

    sucesso = atualizar_opt_out(g.id_usuario, opt_out)
    if not sucesso:
        return jsonify({"erro": "Falha ao atualizar preferência."}), 500

    mensagem = (
        "Opt-out ATIVADO. Seus dados NÃO serão usados para treinar modelos de IA."
        if opt_out else
        "Opt-out DESATIVADO. Seus dados PODEM ser usados para melhorar o serviço."
    )

    return jsonify({
        "opt_out_ia": opt_out,
        "mensagem": mensagem
    }), 200


@app.route("/usuarios/opt-out", methods=["GET"])
@requer_autenticacao
def consultar_opt_out():
    """GET /usuarios/opt-out — Consulta status atual do opt-out."""
    opt_out = verificar_opt_out(g.id_usuario)
    return jsonify({"opt_out_ia": opt_out}), 200


# ─────────────────────────────────────────────
# 4. LOGS DE AUDITORIA (RNF-012/013)
# ─────────────────────────────────────────────

@app.route("/logs/auditoria", methods=["GET"])
@requer_autenticacao
def obter_logs():
    """
    GET /logs/auditoria?data_inicio=&data_fim=
    Retorna logs do usuário autenticado.
    """
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    logs = exportar_logs_auditoria(
        id_usuario=g.id_usuario,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    return jsonify({"logs": logs, "total": len(logs)}), 200


# ─────────────────────────────────────────────
# 5. ALERTAS DE PRAZO (RF-012)
# ─────────────────────────────────────────────

@app.route("/alertas/", methods=["GET"])
@requer_autenticacao
def obter_alertas():
    """GET /alertas/ — Lista alertas pendentes do usuário."""
    alertas = listar_alertas_usuario(g.id_usuario)
    return jsonify({"alertas": alertas, "total": len(alertas)}), 200


@app.route("/alertas/", methods=["POST"])
@requer_autenticacao
def novo_alerta():
    """
    POST /alertas/
    Body: { titulo, data_vencimento, prioridade, descricao }
    """
    dados = request.get_json(force=True) or {}
    titulo = dados.get("titulo", "").strip()
    data_venc = dados.get("data_vencimento", "")
    prioridade = dados.get("prioridade", "media")
    descricao = dados.get("descricao", "")

    if not titulo or not data_venc:
        return jsonify({"erro": "Campos obrigatórios: titulo, data_vencimento."}), 400

    try:
        id_alerta = criar_alerta_prazo(
            g.id_usuario, titulo, data_venc, prioridade, descricao
        )
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400

    return jsonify({"id_alerta": id_alerta, "mensagem": "Alerta criado."}), 201


# ─────────────────────────────────────────────
# 6. HEALTH CHECK
# ─────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health_check():
    """GET /health — Verifica disponibilidade do serviço."""
    from datetime import datetime
    return jsonify({
        "status": "ok",
        "servico": "Visual Law Backend — Squad 2",
        "versao": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200


# ─────────────────────────────────────────────
# TRATAMENTO DE ERROS GLOBAIS
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# FRONTEND — serve o tester automaticamente
# ─────────────────────────────────────────────

@app.route("/")
def frontend():
    """Abre o Visual Law Tester direto no navegador."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(pasta, "visuallaw_tester.html")

@app.errorhandler(413)
def arquivo_muito_grande(e):
    return jsonify({"erro": "Arquivo excede o limite de 10MB."}), 413


@app.errorhandler(404)
def nao_encontrado(e):
    return jsonify({"erro": "Endpoint não encontrado."}), 404


@app.errorhandler(500)
def erro_interno(e):
    logger.error("Erro interno: %s", str(e))
    return jsonify({"erro": "Erro interno do servidor."}), 500


# ─────────────────────────────────────────────
# INICIALIZAÇÃO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # DESENVOLVIMENTO: debug=True, host local
    # PRODUÇÃO: usar gunicorn + HTTPS (Streamlit Cloud / Azure)
    porta = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"

    import threading, webbrowser
    logger.info("Iniciando Visual Law Backend na porta %d", porta)
    logger.info("Abrindo frontend em http://localhost:%d", porta)
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{porta}")).start()
    app.run(host="0.0.0.0", port=porta, debug=debug)
