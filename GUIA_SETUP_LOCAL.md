# Guia de Setup Local — Squad 2
## Visual Law & IA | Backend e Segurança

---

## Pré-requisitos

- Python 3.10 ou superior instalado → [python.org/downloads](https://python.org/downloads)
- VSCode instalado → [code.visualstudio.com](https://code.visualstudio.com)

---

## PASSO 1 — Abrir a pasta no VSCode

Extraia o ZIP do projeto e abra a pasta `squad2_backend` no VSCode:

```
Arquivo → Abrir Pasta → seleciona squad2_backend
```

---

## PASSO 2 — Abrir o terminal

```
Ctrl + ` (acento grave)
```

Confirme que está na pasta certa:

```bash
ls
```

Deve aparecer: `anonimizador.py`, `api_backend.py`, `banco_dados.py`, etc.

---

## PASSO 3 — Criar o ambiente virtual

```bash
python -m venv .venv
```

---

## PASSO 4 — Ativar o ambiente virtual

**Windows (PowerShell):**
```bash
.\.venv\Scripts\activate
```

Se der erro de permissão, rode antes:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
E depois ative novamente:
```bash
.\.venv\Scripts\activate
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

✅ Quando ativar, aparece `(.venv)` no início da linha do terminal.

---

## PASSO 5 — Instalar o PyMuPDF (separado)

```bash
pip install pymupdf --prefer-binary
```

---

## PASSO 6 — Instalar as demais dependências

```bash
pip install flask==3.0.3 flask-cors==4.0.0 cryptography==42.0.8 pymongo==4.7.3 mongomock==4.1.2 python-dotenv==1.0.1 gunicorn==22.0.0
```

---

## PASSO 7 — Criar o arquivo .env

```bash
copy .env.example .env
```

> **Mac/Linux:** `cp .env.example .env`

Abra o `.env` no VSCode e confirme que está assim:

```env
ENCRYPTION_KEY=
SECRET_SALT=visuallaw_squad2_2026
MONGO_URI=
DB_PATH=visuallaw.db
PORT=5000
FLASK_ENV=development
SESSAO_TTL_HORAS=8
PASTA_TEMP=/tmp/visuallaw_uploads
```

> `ENCRYPTION_KEY` e `MONGO_URI` podem ficar em branco em desenvolvimento.

---

## PASSO 8 — Testar os módulos individualmente

```bash
python anonimizador.py
```
```bash
python banco_dados.py
```
```bash
python seguranca.py
```
```bash
python mongo_service.py
```

✅ Cada um deve mostrar resultados sem erros em vermelho.

---

## PASSO 9 — Iniciar a API

```bash
python api_backend.py
```

**Saída esperada:**
```
[INFO] Banco de dados inicializado em: visuallaw.db
[INFO] Iniciando Visual Law Backend na porta 5000
 * Running on http://127.0.0.1:5000
```

---

## PASSO 10 — Abrir o frontend de testes

Abra um **segundo terminal** (clique no `+` no terminal do VSCode) e rode:

```bash
python -m http.server 8080
```

Acesse no navegador:
```
http://localhost:8080/visuallaw_tester.html
```

✅ O indicador no canto superior direito deve aparecer **verde (online)**.

---

## Resumo — dois terminais rodando ao mesmo tempo

| Terminal | Comando | Porta |
|---|---|---|
| Terminal 1 | `python api_backend.py` | 5000 (API) |
| Terminal 2 | `python -m http.server 8080` | 8080 (Frontend) |

---

## Para parar

```bash
Ctrl + C
```

---

## Para rodar novamente (próxima vez)

```bash
cd squad2_backend
.\.venv\Scripts\activate
python api_backend.py
```

E no segundo terminal:
```bash
python -m http.server 8080
```

---

## Endpoints disponíveis para teste

| Método | Endpoint | Descrição |
|---|---|---|
| POST | /auth/cadastro | Criar conta |
| POST | /auth/login | Login → gera token |
| POST | /auth/logout | Logout |
| POST | /documentos/upload | Upload de PDF com anonimização |
| GET | /documentos/ | Listar documentos |
| PUT | /usuarios/opt-out | Atualizar opt-out LGPD |
| GET | /usuarios/opt-out | Consultar opt-out |
| GET | /logs/auditoria | Ver logs com IP mascarado |
| POST | /alertas/ | Criar alerta de prazo |
| GET | /alertas/ | Listar alertas |
| GET | /health | Verificar se a API está online |

---

## Testado em

- Windows 11 com Python 3.13
- VSCode com PowerShell

*Squad 2 — Backend e Segurança | Visual Law | 2026*
