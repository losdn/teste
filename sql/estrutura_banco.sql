CREATE TABLE IF NOT EXISTS produtos (
    "Cód. Produto (SKU)" text PRIMARY KEY,
    "Descrição" text,
    "Fornecedor" text,
    "Categoria" text,
    "Peso (kg)" double precision,
    "Volume (m³)" double precision,
    "Valor Unitário" NUMERIC(15,2),
    "Class. ABC Item" text
);

CREATE TABLE IF NOT EXISTS pedidos (
    "Data" timestamp without time zone,
    "Nº Ordem de Venda (OV)" bigint,
    "Cód. Produto (SKU)" text,
    "Quantidade Solicitada" bigint,
    "Quantidade Vendida" bigint,
    "Valor Total (R$)" NUMERIC(15,2),
    PRIMARY KEY ("Nº Ordem de Venda (OV)", "Cód. Produto (SKU)")
);

CREATE TABLE IF NOT EXISTS estoque (
    "Carimbo de Data" timestamp without time zone,
    "Cód. Produto (SKU)" text,
    "Posição Armazenagem" bigint,
    "Descrição" text,
    "Qtd. de Estoque Atual" bigint,
    "Valor Total" NUMERIC(15,2),
    PRIMARY KEY ("Carimbo de Data", "Cód. Produto (SKU)", "Posição Armazenagem")
);

CREATE TABLE IF NOT EXISTS kpi_snapshot (
    id SERIAL PRIMARY KEY,
    capturado_em TIMESTAMP DEFAULT NOW(),
    faturamento_total NUMERIC(15,2),
    valor_em_estoque NUMERIC(15,2),
    total_pedidos INTEGER,
    qtd_skus_com_ruptura INTEGER,
    qtd_skus_total INTEGER,
    taxa_ruptura NUMERIC(5,2),
    ticket_medio NUMERIC(14,2),
    giro_estoque NUMERIC(10,2),
    cobertura_dias NUMERIC(10,1),
    ruptura_classe_a INTEGER
);