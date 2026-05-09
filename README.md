# 📊 Sistema de Monitoramento de KPIs de Logística & Alertas Automatizados

Desenvolvido para fornecer monitoramento proativo e visibilidade em tempo real sobre indicadores críticos, este sistema utiliza um pipeline automatizado de KPIs para permitir a mitigação de riscos operacionais antes que impactem os resultados da organização.

---

## 🎯 Objetivo do Projeto
O objetivo principal é evitar a **ruptura de estoque** (falta de produto) e monitorar a saúde financeira da operação. Ao centralizar dados de diferentes fontes em um banco de dados PostgreSQL, o sistema permite uma análise preditiva simples, avisando os gestores antes que problemas como o "encalhe" (giro baixo) ou a falta de itens Classe A impactem o faturamento.

---

## 🛠️ Tecnologias Utilizadas
- **Linguagem:** Python 3.12
- **Banco de Dados:** PostgreSQL 18 (Nativo)
- **Bibliotecas:** Pandas, SQLAlchemy, Psycopg2, Dotenv
- **Interface de Dados:** pgAdmin 4
- **Comunicação:** Protocolo SMTP (Gmail)

---

## 📋 Pré-requisitos
- Python 3.8+
- PostgreSQL 12+
- Pip (Gerenciador de pacotes do Python)

---

## 🚀 Instalação Rápida

### 1. Clonar e instalar dependências
```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente (Windows)
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configurar banco de dados
Crie uma instância no PostgreSQL e execute o script para gerar a estrutura das tabelas:

```bash
# Criar banco de dados PostgreSQL
createdb -U postgres estoque

# Restaurar schema (Tabelas e Snapshots)
psql -U postgres -d estoque -f sql/estrutura_banco.sql
```

### 3. Configurar variáveis de ambiente

Crie um arquivo `.env` na pasta `config/` seguindo o modelo abaixo:

```bash
# Copiar arquivo de exemplo
copy config\.env.example config\.env
```

```env
# Edite o arquivo config\.env com suas credenciais:

DB_HOST=localhost
DB_PORT=5432
DB_NAME=estoque
DB_USER=postgres
DB_PASSWORD=sua_senha_do_banco

EMAIL_USER=seu_email@gmail.com
EMAIL_PASSWORD=sua_senha_de_app_gmail
```


---

## ⚙️ Fluxo de Execução

### 1️⃣ Ingestão de Dados

Popula o banco de dados a partir dos arquivos CSV brutos:

```bash
python scripts/importar_dados.py
```

---

### 2️⃣ Simulação de Mercado (Testes)

Gera alterações aleatórias nos dados para validar o disparo dos alertas:

```bash
python scripts/forcar_mudanca.py
```

---

### 3️⃣ Serviço de Monitoramento

Inicia o loop que verifica os KPIs e envia os e-mails formatados em HTML:

```bash
python scripts/monitorar_kpi.py
```


## 📂 Estrutura do Projeto

```text
config/   → Configurações e variáveis de ambiente
data/     → Arquivos CSV (estoque, pedidos e produtos)
scripts/  → Scripts principais do sistema
sql/      → Scripts SQL e estrutura do banco
```

---

## 🚨 Alertas

O sistema monitora **11 indicadores** com dois níveis de severidade:

- 🔴 CRÍTICO
- 🟡 ATENÇÃO
- 🟢 SAUDÁVEL
  

## Indicadores monitorados

### 📦 Taxa de Ruptura
Alerta quando mais de **5% do catálogo** está sem estoque.

### ⭐ Ruptura Classe A
Alerta imediato caso qualquer item de curva A fique zerado.

### 📉 Cobertura de Estoque
Monitora se a quantidade atual suporta o ritmo de vendas até a próxima reposição.

### 🔄 Giro de Estoque
Identifica produtos com baixa rotatividade e risco de obsolescência.

Saúde Financeira: Detecta quedas bruscas (>15%) no faturamento ou no ticket médio em relação ao período anterior.
