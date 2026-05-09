import psycopg2
import random
import os
from dotenv import load_dotenv

# Carrega as configurações do seu arquivo .env
load_dotenv('config/.env')

def simular_crise_geral():
    conn = None
    try:
        # Conectando ao banco oficial (Porta 5432)
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        
        cur = conn.cursor()
        print("🛠️  Iniciando simulação de alteração de KPIs...\n")

        # 1. Redução de Pedidos (Afeta Faturamento, Ticket Médio e Total de Pedidos)
        fator_pedidos = 0.70 # Queda de 30%
        cur.execute("""
            UPDATE pedidos 
            SET "Quantidade Vendida" = ROUND("Quantidade Vendida" * %s)
            WHERE "Quantidade Vendida" > 0
        """, (fator_pedidos,))
        print(f"Pedidos reduzidos: {cur.rowcount} registros (fator {fator_pedidos:.3f})")

        # 2. Redução de Estoque (Afeta Cobertura e Giro)
        fator_estoque = 0.40 # Queda de 60% para forçar cobertura baixa
        cur.execute("""
            UPDATE estoque 
            SET "Qtd. de Estoque Atual" = ROUND("Qtd. de Estoque Atual" * %s)
            WHERE "Qtd. de Estoque Atual" > 0
        """, (fator_estoque,))
        print(f"Estoque reduzido: {cur.rowcount} registros (fator {fator_estoque:.3f})")

        # 3. Ruptura de Itens Classe A (Gatilho Crítico específico)
        cur.execute("""
            UPDATE estoque 
            SET "Qtd. de Estoque Atual" = 0 
            WHERE "Cód. Produto (SKU)" IN (
                SELECT e."Cód. Produto (SKU)" 
                FROM estoque e
                JOIN produtos p ON e."Cód. Produto (SKU)" = p."Cód. Produto (SKU)"
                WHERE p."Class. ABC Item" = 'A'
                LIMIT 2
            )
        """)
        print(f"SKUs Classe A zerados: {cur.rowcount}")

        # 4. Outros SKUs zerados (Aumentar a Taxa de Ruptura Geral)
        cur.execute("""
            UPDATE estoque 
            SET "Qtd. de Estoque Atual" = 0 
            WHERE "Cód. Produto (SKU)" IN (
                SELECT "Cód. Produto (SKU)" FROM estoque 
                WHERE "Qtd. de Estoque Atual" > 0 
                ORDER BY RANDOM() 
                LIMIT 5
            )
        """)
        print(f"Outros SKUs zerados: {cur.rowcount}")

        conn.commit()
        print("\n🚀 Simulação completa! Rode o monitor para disparar os alertas.")

    except Exception as e:
        print(f"\n❌ Erro durante a simulação: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    simular_crise_geral()