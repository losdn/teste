import pandas as pd
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv('config/.env')

DB_USER     = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST     = os.getenv('DB_HOST')
DB_PORT     = os.getenv('DB_PORT')
DB_NAME     = os.getenv('DB_NAME')

engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

PASTA = r'D:\Projetos\data'  

def converter_moeda(serie):
    """Converte '1.679,00' → 1679.00"""
    return (
        serie.astype(str)
             .str.replace(r'[R$\s]', '', regex=True)
             .str.replace('.', '', regex=False)
             .str.replace(',', '.', regex=False)
             .pipe(pd.to_numeric, errors='coerce')
    )

def converter_numero(serie):
    """Converte '1,08' → 1.08"""
    return (
        serie.astype(str)
             .str.replace('.', '', regex=False)
             .str.replace(',', '.', regex=False)
             .pipe(pd.to_numeric, errors='coerce')
    )


print("📦 Importando produtos...")
produtos = pd.read_csv(
    fr'{PASTA}\produtos.csv',
    encoding='latin1',
    sep=';',
    engine='python'
)

produtos['Valor Unitário'] = converter_moeda(produtos['Valor Unitário'])
produtos['Peso (kg)']      = converter_numero(produtos['Peso (kg)'])
produtos['Volume (m³)']    = converter_numero(produtos['Volume (m³)'])

produtos.to_sql('produtos', engine, if_exists='replace', index=False)
print(f"   ✅ {len(produtos)} produtos importados")


print("🧾 Importando pedidos...")
pedidos = pd.read_csv(
    fr'{PASTA}\pedidos.csv',
    encoding='latin1',
    sep=';',
    engine='python'
)

pedidos['Valor Total (R$)'] = converter_moeda(pedidos['Valor Total (R$)'])
pedidos['Data']             = pd.to_datetime(pedidos['Data'], dayfirst=True, errors='coerce')

pedidos.to_sql('pedidos', engine, if_exists='replace', index=False)
print(f"   ✅ {len(pedidos)} pedidos importados")


print("🏭 Importando estoque...")
estoque = pd.read_csv(
    fr'{PASTA}\estoque.csv',
    encoding='latin1',
    sep=';',
    engine='python'
)

estoque['Valor Total']       = converter_moeda(estoque['Valor Total'])
estoque['Carimbo de Data']   = pd.to_datetime(estoque['Carimbo de Data'], dayfirst=True, errors='coerce')

estoque.to_sql('estoque', engine, if_exists='replace', index=False)
print(f"   ✅ {len(estoque)} registros de estoque importados")


print("📸 Criando tabela de snapshots de KPI...")
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS kpi_snapshot (
            id                   SERIAL PRIMARY KEY,
            capturado_em         TIMESTAMP DEFAULT NOW(),
            faturamento_total    NUMERIC(15,2),
            valor_em_estoque     NUMERIC(15,2),
            total_pedidos        INTEGER,
            qtd_skus_com_ruptura INTEGER,
            qtd_skus_total       INTEGER,
            taxa_ruptura         NUMERIC(5,2)
        )
    """))
    conn.commit()
print("   ✅ Tabela kpi_snapshot pronta")

print("\n🎉 Importação concluída!")