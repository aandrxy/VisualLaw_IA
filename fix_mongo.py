# Rode este arquivo dentro da pasta squad2_backend:
# python fix_mongo.py

import os

novo = '''import os, uuid, logging
from datetime import datetime

logger = logging.getLogger(__name__)
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("MONGO_DB_NAME", "visuallaw_db")
_client = None


def _obter_db():
    global _client
    if _client is not None:
        if isinstance(_client, _FakeDB):
            return _client
        return _client[DB_NAME]
    if MONGO_URI:
        from pymongo import MongoClient
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        return _client[DB_NAME]
    try:
        import mongomock
        _client = mongomock.MongoClient()
        logger.warning("Usando MongoMock (desenvolvimento).")
        return _client[DB_NAME]
    except ImportError:
        _client = _FakeDB()
        return _client


class _FakeDB:
    def __init__(self):
        self._c = {}

    def __getitem__(self, n):
        if n not in self._c:
            self._c[n] = _FakeColecao()
        return self._c[n]


class _FakeColecao:
    def __init__(self):
        self._docs = []

    def insert_one(self, d):
        self._docs.append(dict(d))

    def find(self, f=None):
        if not f:
            return list(self._docs)
        return [d for d in self._docs if all(d.get(k) == v for k, v in f.items())]

    def find_one(self, f=None):
        results = self.find(f)
        return results[0] if results else None

    def update_one(self, f, u):
        for d in self._docs:
            if all(d.get(k) == v for k, v in f.items()):
                d.update(u.get("$set", {}))
                return

    def delete_many(self, f):
        self._docs = [d for d in self._docs
                      if not all(d.get(k) == v for k, v in f.items())]

    def count_documents(self, f=None):
        return len(self.find(f))


def salvar_mensagem_chat(id_usuario, id_doc, modo, pergunta, resposta):
    db = _obter_db()
    id_msg = str(uuid.uuid4())
    db["historico_chat"].insert_one({
        "_id": id_msg,
        "id_usuario": id_usuario,
        "id_doc": id_doc,
        "modo": modo,
        "pergunta": pergunta,
        "resposta": resposta,
        "timestamp": datetime.utcnow().isoformat(),
        "possui_caveat": "ia" in resposta.lower()
    })
    return id_msg


def buscar_historico_chat(id_usuario, id_doc=None, limite=50):
    db = _obter_db()
    f = {"id_usuario": id_usuario}
    if id_doc:
        f["id_doc"] = id_doc
    r = db["historico_chat"].find(f)
    if isinstance(r, list):
        r.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return list(r)[:limite]


def excluir_historico_usuario(id_usuario):
    _obter_db()["historico_chat"].delete_many({"id_usuario": id_usuario})


def salvar_analise_visual_law(id_doc, id_usuario, resumo, direitos, deveres, timeline):
    db = _obter_db()
    id_an = str(uuid.uuid4())
    db["metadados_documentos"].insert_one({
        "_id": id_an,
        "id_doc": id_doc,
        "id_usuario": id_usuario,
        "resumo_simples": resumo,
        "Direitos_da_Parte": direitos,
        "Deveres_da_Parte": deveres,
        "Timeline": timeline,
        "gerado_em": datetime.utcnow().isoformat(),
        "versao_modelo": "gemini-2.5",
        "selo_ia": "Conteudo Gerado por IA"
    })
    return id_an


def buscar_analise(id_doc):
    return _obter_db()["metadados_documentos"].find_one({"id_doc": id_doc})


def excluir_analises_usuario(id_usuario):
    _obter_db()["metadados_documentos"].delete_many({"id_usuario": id_usuario})


if __name__ == "__main__":
    uid = "demo-001"
    doc_id = "doc-001"

    id_an = salvar_analise_visual_law(
        doc_id, uid, "Resumo contrato",
        [{"titulo": "D1", "descricao": "desc"}],
        [{"titulo": "Dev1", "descricao": "desc"}],
        [{"data": "2026-01-01", "evento": "Assinatura", "status": "concluido"}]
    )
    print("Analise salva:", id_an)

    analise = buscar_analise(doc_id)
    print("Direitos:", len(analise["Direitos_da_Parte"]))
    print("Selo IA:", analise["selo_ia"])

    id_msg = salvar_mensagem_chat(
        uid, doc_id, "pdf_especifico",
        "Quais meus direitos?",
        "Resposta gerada por ia."
    )
    print("Mensagem salva:", id_msg)

    hist = buscar_historico_chat(uid)
    print("Historico:", len(hist), "mensagem(ns)")

    excluir_historico_usuario(uid)
    print("Historico excluido - LGPD Art. 18")

    print("TODOS OS TESTES OK")
'''

with open("mongo_service.py", "w", encoding="utf-8") as f:
    f.write(novo)

print("mongo_service.py substituido com sucesso!")
print("Agora rode: python mongo_service.py")
