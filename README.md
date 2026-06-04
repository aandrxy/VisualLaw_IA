# SQUAD 2 — Backend e Segurança
## Projeto Visual Law & IA no Sistema Jurídico Brasileiro

---

## 📋 ETAPA 1 — ANÁLISE DO DOCUMENTO

### Requisitos mapeados para a Squad 2

| Código | Descrição | Origem |
|--------|-----------|--------|
| RNF-010 | Criptografia em trânsito e em repouso | Requisitos Não Funcionais |
| RNF-012 | Sistema de logs de auditoria com timestamp | Requisitos Não Funcionais |
| RNF-013 | Exportação de relatórios de auditoria | Requisitos Não Funcionais |
| RNF-003 | Respostas em até 5 segundos | Requisitos Não Funcionais |
| RCP-001 | Anonimização automática antes de envio à IA | Conformidade LGPD |
| RCP-002 | Botão de opt-out de treinamento de IA | Conformidade LGPD |
| RF-001 | Cadastro e login de usuários | Requisitos Funcionais |
| RF-018 | Limite de 50 uploads por dia | Requisitos Funcionais |
| RF-012 | Alertas de prazo por prioridade | Requisitos Funcionais |
| US-01 | Cadastro e configuração de conta | Histórias de Usuário |
| US-09 | Histórico de chat persistente | Histórias de Usuário |
| US-13 | Opt-out nas configurações de privacidade | Histórias de Usuário |

### Base legal LGPD aplicada
- **Art. 7º, IX** — Legítimo Interesse como base de tratamento
- **Art. 18, VI** — Direito de exclusão de dados do titular
- **Finalidade**: Democratização da informação jurídica
- **Necessidade**: Coleta mínima, anonimização obrigatória

---

## 🧩 ETAPA 2 — ESCOPO DA SQUAD 2

### ✅ O que a Squad 2 FAZ
- Script de anonimização de CPF, CNPJ, RG, e-mail, telefone e nomes
- Banco relacional (SQLite/PostgreSQL): usuários, logs, documentos, alertas
- Banco NoSQL (MongoDB): histórico de chat, metadados de análises da IA
- Criptografia de arquivos em repouso (Fernet/AES-128)
- Tokens de sessão seguros com expiração
- Exclusão segura de arquivos temporários ao fim da sessão
- API REST (Flask): autenticação, upload, opt-out, logs, alertas
- Validação de entradas (extensão, tamanho, sanitização de nome)
- Controle de limite diário de uploads (50/dia)
- Exportação de logs de auditoria (LGPD RNF-013)
- Direito de exclusão de dados do titular (LGPD Art. 18)

### ❌ O que NÃO faz parte da Squad 2
- Interface visual / Streamlit (Squad 1)
- Motor RAG / FAISS / embeddings (Squad 3)
- Web scraping de leis (Squad 3)
- Engenharia de prompts (Squad 3 + PO)
- Integração com Google Gemini (Squad 3)
- Acessibilidade visual WCAG / dark mode (Squad 1)

### ⚠️ Dependências indiretas
- O texto anonimizado pela Squad 2 **alimenta** o motor RAG da Squad 3
- Os endpoints da Squad 2 **são consumidos** pela interface da Squad 1
- A Squad 2 deve garantir que o campo `opt_out_ia` seja verificado **antes** que a Squad 3 use dados para treinamento

---

## 📋 ETAPA 3 — PLANO DE IMPLEMENTAÇÃO

```
squad2_backend/
├── anonimizador.py      → RCP-001: substituição de dados sensíveis
├── banco_dados.py       → SQLite/PostgreSQL: usuários, logs, documentos
├── seguranca.py         → RNF-010: criptografia, sessões, exclusão segura
├── api_backend.py       → Endpoints REST Flask
├── mongo_service.py     → MongoDB: histórico chat, metadados IA
├── requirements.txt     → Dependências Python
└── README.md            → Esta documentação
```

### Fluxo de dados sensível (pipeline de segurança)
```
[PDF enviado pelo usuário]
        ↓
[Validação: extensão + tamanho + limite diário]
        ↓
[Extração de texto: PyMuPDF]
        ↓
[ANONIMIZAÇÃO OBRIGATÓRIA: CPF, CNPJ, nomes → RCP-001]
        ↓
[Texto anonimizado → Squad 3 (IA / RAG)]
        ↓
[Arquivo PDF → criptografado em repouso: RNF-010]
        ↓
[Metadados → banco relacional (sem dados pessoais)]
        ↓
[Log de auditoria → RNF-012 (IP mascarado, sem dados pessoais)]
        ↓
[Encerramento da sessão → exclusão automática do PDF do servidor]
```

---

## ✅ ETAPA 4 — CHECKLIST DE COBERTURA

### LGPD
- [x] Anonimização de CPF, CNPJ, RG, e-mail, telefone e nomes (RCP-001)
- [x] Opt-out de treinamento de IA (RCP-002)
- [x] Logs de auditoria sem dados pessoais (RNF-012)
- [x] IP mascarado nos logs (hash SHA-256)
- [x] Direito de exclusão de dados do titular (Art. 18)
- [x] Base legal: Legítimo Interesse documentada (Art. 7º, IX)

### Segurança
- [x] Criptografia em repouso: Fernet / AES-128 (RNF-010)
- [x] HTTPS em trânsito: via Streamlit Cloud / Azure (documentado)
- [x] Senhas armazenadas apenas como hash (SHA-256 + salt)
- [x] Tokens de sessão: secrets.token_urlsafe(48) com expiração
- [x] Exclusão segura de arquivos (sobrescrita com zeros antes de deletar)
- [x] Validação de extensão e tamanho de arquivo
- [x] Sanitização de nomes de arquivos

### Backend funcional
- [x] Cadastro e login (RF-001)
- [x] Upload com limite de 50/dia (RF-018)
- [x] Banco relacional: usuários, logs, documentos, alertas
- [x] Banco NoSQL: histórico de chat, análises da IA
- [x] Alertas de prazo por prioridade (RF-012)
- [x] Exportação de logs de auditoria (RNF-013)
- [x] API REST com todos os endpoints necessários

---

## ⚙️ COMO EXECUTAR

### Instalação
```bash
pip install -r requirements.txt
```

### Variáveis de ambiente (.env)
```
ENCRYPTION_KEY=sua_chave_fernet_aqui
SECRET_SALT=seu_salt_secreto
MONGO_URI=mongodb://localhost:27017
DB_PATH=visuallaw.db
PORT=5000
FLASK_ENV=development
SESSAO_TTL_HORAS=8
```

### Iniciar a API
```bash
python api_backend.py
```

### Testar módulos individualmente
```bash
python anonimizador.py    # Testa anonimização
python banco_dados.py     # Testa banco SQLite
python seguranca.py       # Testa criptografia
python mongo_service.py   # Testa MongoDB mock
```

---

## 🔌 ENDPOINTS DA API

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| POST | /auth/cadastro | Criar conta | ❌ |
| POST | /auth/login | Autenticar | ❌ |
| POST | /auth/logout | Encerrar sessão | ✅ |
| POST | /documentos/upload | Upload PDF com anonimização | ✅ |
| GET | /documentos/ | Listar documentos | ✅ |
| DELETE | /documentos/<id> | Excluir documento | ✅ |
| PUT | /usuarios/opt-out | Atualizar opt-out | ✅ |
| GET | /usuarios/opt-out | Consultar opt-out | ✅ |
| GET | /logs/auditoria | Exportar logs | ✅ |
| GET | /alertas/ | Listar alertas | ✅ |
| POST | /alertas/ | Criar alerta | ✅ |
| GET | /health | Health check | ❌ |

---

## 📦 ARQUITETURA DE BANCO DE DADOS

### Banco Relacional (SQLite → PostgreSQL em produção)
```sql
usuarios         → id, nome, email, senha_hash, opt_out_ia
logs_auditoria   → id, acao, modulo, resultado, ip_hash, data_hora
documentos       → id, id_usuario, nome_arquivo, processado, excluido
alertas_prazo    → id, titulo, data_vencimento, prioridade
```

### Banco NoSQL (MongoDB)
```
historico_chat         → conversas do chatbot (US-09)
metadados_documentos   → JSON: direitos, deveres, timeline (Squad 1)
```

---

## 🔒 DECISÕES DE SEGURANÇA

1. **Anonimização antes de tudo**: O texto bruto do PDF **nunca chega à IA**. Passa primeiro pelo `anonimizador.py`.
2. **Logs sem dados pessoais**: Os logs registram ações técnicas. IP é armazenado como hash, nunca o valor real.
3. **Opt-out por padrão seguro**: Se o usuário não for encontrado, o sistema assume `opt_out = True` (proteção máxima).
4. **Exclusão segura**: Arquivos são sobrescritos com zeros (`\x00`) antes de deletados, impedindo recuperação forense.
5. **Sessões com expiração**: Tokens expiram em 8 horas (configurável). Sem refresh token automático.
6. **Senhas com salt**: Não armazenamos senha, apenas `SHA-256(salt + senha)`. Salt definido por variável de ambiente.

---

*Projeto Visual Law | Squad 2 — Backend e Segurança | 2026*
