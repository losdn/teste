# Sistema de Monitoramento de KPI - Estoque

Sistema independente de monitoramento de KPIs e gestão de estoque, sem dependência de Docker ou Dify.

## Pré-requisitos

- Python 3.8+
- PostgreSQL 12+
- pip

## Instalação Rápida

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

```bash
# Criar banco de dados PostgreSQL
createdb -U postgres estoque

# Restaurar schema
psql -U postgres -d estoque -f sql/estrutura_banco.sql
```

### 3. Configurar variáveis de ambiente

```bash
# Copiar arquivo de exemplo
copy config\.env.example config\.env

# Editar config\.env com suas credenciais:
# - DB_HOST: localhost
# - DB_PORT: 5432
# - DB_NAME: estoque
# - DB_USER: postgres
# - DB_PASSWORD: sua_senha
# - EMAIL_USER: seu_email@gmail.com
# - EMAIL_PASSWORD: sua_senha_app_gmail
```

### 4. Importar dados

```bash
python scripts/importar_dados.py
```

### 5. Executar monitoramento

```bash
python scripts/monitorar_kpi.py
```

## Estrutura do Projeto

```
config/          → Variáveis de ambiente (.env, .env.example)
data/           → Arquivos CSV (estoque.csv, pedidos.csv, produtos.csv)
scripts/        → Scripts Python (monitorar_kpi.py, importar_dados.py, forcar_mudanca.py)
sql/            → Schema do banco de dados (estrutura_banco.sql)
```

## Scripts Disponíveis

- **monitorar_kpi.py** → Executa verificações de KPI por hora
- **importar_dados.py** → Importa dados dos CSVs para o banco
- **forcar_mudanca.py** → Simula alterações para testes

## Alertas Configurados

O sistema monitora 11 KPIs com alertas de CRÍTICO e ATENÇÃO:
- Taxa de Ruptura
- Cobertura de Dias
- Giro de Estoque
- Queda de Faturamento
- Queda de Pedidos
- Variação de Ticket Médio
- E mais...

## Suporte

Para dúvidas, verifique os comentários nos scripts ou a documentação do PostgreSQL.
