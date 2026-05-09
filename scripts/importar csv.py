import pandas as pd
from sqlalchemy import create_engine
import os

# 1. Agora com a porta padrão 5432
engine = create_engine('postgresql://postgres:postgres@localhost:5432/estoque')

# Restante do código continua igual...
pasta = r'D:\Projetos\data'
arquivos_tabelas = {
    'produtos.csv': 'produtos',
    'estoque.csv': 'estoque',
    'pedidos.csv': 'pedidos'
}

for arquivo_nome, tabela_nome in arquivos_tabelas.items():
    caminho_completo = os.path.join(pasta, arquivo_nome)
    try:
        df = pd.read_csv(caminho_completo, sep=';', encoding='latin1')
        df.to_sql(tabela_nome, engine, if_exists='replace', index=False)
        print(f"✅ {arquivo_nome} -> Importado para a tabela '{tabela_nome}'")
    except Exception as e:
        print(f"❌ Erro ao importar {arquivo_nome}: {e}")