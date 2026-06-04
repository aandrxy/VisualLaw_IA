# Visual Law & IA — Squad 2
## Backend, Segurança e Conformidade LGPD

Sistema de backend para a plataforma Visual Law, responsável por infraestrutura,
segurança, banco de dados e conformidade com a Lei Geral de Proteção de Dados
(LGPD — Lei 13.709/2018).

---

## O que foi construído

| Módulo | Responsabilidade |
|---|---|
| `anonimizador.py` | Substitui CPF, CNPJ, RG, e-mail, telefone e nomes antes do envio à IA |
| `banco_dados.py` | SQLite/PostgreSQL: usuários, logs, documentos e alertas |
| `seguranca.py` | Criptografia AES-128, tokens de sessão e exclusão forense |
| `api_backend.py` | 12 endpoints Flask REST com autenticação Bearer Token |
| `mongo_service.py` | MongoDB: histórico de chat e metadados de análise da IA |

---

## Como executar

### 1. Pré-requisitos

- Python 3.11 → [python.org/downloads](https://python.org/downloads)
- VSCode → [code.visualstudio.com](https://code.visualstudio.com)

### 2. Clonar o repositório

```bash
git clone https://github.com/aandrxy/VisualLaw_IA.git
cd Visual-Law---IA
```

### 3. Criar e ativar o ambiente virtual

```bash
python -m venv .venv
```

**Windows:**
```bash
.\.venv\Scripts\activate
```

Se der erro de permissão:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\activate
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

### 4. Instalar o PyMuPDF (separado)

```bash
pip install pymupdf --prefer-binary
```

### 5. Instalar as demais dependências

```bash
pip install flask==3.0.3 flask-cors==4.0.0 cryptography==42.0.8 pymongo==4.7.3 mongomock==4.1.2 python-dotenv==1.0.1 gunicorn==22.0.0
```

### 6. Criar o arquivo .env

```bash
copy .env.example .env
```

> **Mac/Linux:** `cp .env.example .env`

O `.env` não vai para o GitHub — é criado localmente a partir do `.env.example`.

### 7. Testar os módulos individualmente

```bash
python anonimizador.py
python banco_dados.py
python seguranca.py
python mongo_service.py
```

Se o `mongo_service.py` der erro, rode:
```bash
python fix_mongo.py
python mongo_service.py
```

### 8. Iniciar a API

```bash
python api_backend.py
```

O navegador abre automaticamente em `http://localhost:5000` com o frontend de testes.

---

## Endpoints disponíveis

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| POST | /auth/cadastro | Criar conta | ❌ |
| POST | /auth/login | Login → token | ❌ |
| POST | /auth/logout | Encerrar sessão | ✅ |
| POST | /documentos/upload | Upload PDF com anonimização | ✅ |
| GET | /documentos/ | Listar documentos | ✅ |
| DELETE | /documentos/\<id\> | Excluir documento | ✅ |
| PUT | /usuarios/opt-out | Atualizar opt-out LGPD | ✅ |
| GET | /usuarios/opt-out | Consultar opt-out | ✅ |
| GET | /logs/auditoria | Exportar logs | ✅ |
| POST | /alertas/ | Criar alerta de prazo | ✅ |
| GET | /alertas/ | Listar alertas | ✅ |
| GET | /health | Status da API | ❌ |

---

## Requisitos atendidos

| Código | Descrição |
|---|---|
| RCP-001 | Anonimização automática antes do envio à IA |
| RCP-002 | Opt-out de treinamento de IA |
| RNF-010 | Criptografia em trânsito e em repouso |
| RNF-012 | Logs de auditoria com timestamp e IP mascarado |
| RNF-013 | Exportação de relatórios de auditoria |
| RF-001 | Cadastro e login de usuários |
| RF-018 | Limite de 50 uploads diários por usuário |
| RF-012 | Alertas de prazo por prioridade |
| US-09 | Histórico de chat persistente no MongoDB |
| US-13 | Opt-out nas configurações de privacidade |

---

## Tecnologias

- **Python 3.11** — linguagem principal
- **Flask** — framework web para a API REST
- **SQLite / PostgreSQL** — banco relacional
- **MongoDB / mongomock** — banco de documentos
- **Fernet (AES-128)** — criptografia em repouso
- **PyMuPDF** — extração de texto de PDFs
- **cryptography** — biblioteca de criptografia

---

*Squad 2 — Backend e Segurança | Visual Law | 2026*
