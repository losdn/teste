import os
import psycopg2
import smtplib
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('config/.env')

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "127.0.0.1"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "estoque"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres")
}

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "")
EMAIL_SENHA     = os.getenv("EMAIL_SENHA", "")
EMAIL_DESTINO   = os.getenv("EMAIL_DESTINO", "")
SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))

INTERVALO = 3600

REGRAS = [
    {   "campo": "taxa_ruptura",      "op": ">",  "threshold": 5.0,
        "severidade": "CRÍTICO",
        "nome": "Taxa de Ruptura",    "unidade": "%",
        "descricao": "Mais de 5% dos SKUs sem estoque — risco alto de perda de vendas para concorrentes." },
    {   "campo": "taxa_ruptura",      "op": ">",  "threshold": 2.0,
        "severidade": "ATENÇÃO",
        "nome": "Taxa de Ruptura",    "unidade": "%",
        "descricao": "Ruptura acima de 2% — iniciar revisão de reposição imediatamente." },
    {   "campo": "ruptura_classe_a",  "op": ">",  "threshold": 0,
        "severidade": "CRÍTICO",
        "nome": "Ruptura Classe A",   "unidade": "",
        "descricao": "Item Classe A sem estoque — perda direta e imediata de receita." },
    {   "campo": "cobertura_dias",    "op": "<",  "threshold": 30.0,
        "severidade": "CRÍTICO",
        "nome": "Cobertura de Estoque", "unidade": "dias",
        "descricao": "Cobertura abaixo de 30 dias — inferior ao lead time de reposição. Pedido urgente." },
    {   "campo": "cobertura_dias",    "op": "<",  "threshold": 45.0,
        "severidade": "ATENÇÃO",
        "nome": "Cobertura de Estoque", "unidade": "dias",
        "descricao": "Cobertura abaixo de 45 dias — acione reposição preventiva considerando lead time." },
    {   "campo": "giro_estoque",      "op": "<",  "threshold": 6.0,
        "severidade": "CRÍTICO",
        "nome": "Giro de Estoque",    "unidade": "x",
        "descricao": "Giro abaixo de 6x — estoque parado por mais de 2 meses. Risco de obsolescência." },
    {   "campo": "giro_estoque",      "op": "<",  "threshold": 12.0,
        "severidade": "ATENÇÃO",
        "nome": "Giro de Estoque",    "unidade": "x",
        "descricao": "Giro abaixo de 12x — desempenho abaixo do padrão histórico do negócio." },
    {   "campo": "_fat_queda",        "op": "queda_brusca", "threshold": 10.0,
        "severidade": "CRÍTICO",
        "nome": "Faturamento",        "unidade": "R$",
        "descricao": "Faturamento caiu mais de 10% — investigar causa imediatamente." },
    {   "campo": "_fat_queda",        "op": "queda_brusca", "threshold": 5.0,
        "severidade": "ATENÇÃO",
        "nome": "Faturamento",        "unidade": "R$",
        "descricao": "Faturamento caiu mais de 5% — monitorar tendência e verificar canal de vendas." },
    {   "campo": "_ped_queda",        "op": "queda_brusca", "threshold": 8.0,
        "severidade": "ATENÇÃO",
        "nome": "Total de Pedidos",   "unidade": "",
        "descricao": "Volume de pedidos caiu mais de 8% — verificar disponibilidade de SKUs e canal." },
    {   "campo": "_ticket_queda",     "op": "queda_brusca", "threshold": 5.0,
        "severidade": "ATENÇÃO",
        "nome": "Ticket Médio",       "unidade": "R$",
        "descricao": "Ticket médio caiu mais de 5% — verificar mix de produtos e política de descontos." },
]

FAIXAS_RUPTURA = [
    (2.0,  "Saudável", "#16a34a"),
    (5.0,  "Atenção",  "#d97706"),
    (999,  "Crítico",  "#dc2626"),
]

def severidade_ruptura(taxa):
    for limite, label, cor in FAIXAS_RUPTURA:
        if taxa <= limite:
            return label, cor
    return "Crítico", "#dc2626"


def conectar_banco():
    conn = psycopg2.connect(**DB_CONFIG)
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE kpi_snapshot ADD COLUMN IF NOT EXISTS ticket_medio NUMERIC(14,2) DEFAULT 0")
        cur.execute("ALTER TABLE kpi_snapshot ADD COLUMN IF NOT EXISTS giro_estoque NUMERIC(10,2) DEFAULT 0")
        cur.execute("ALTER TABLE kpi_snapshot ADD COLUMN IF NOT EXISTS cobertura_dias NUMERIC(10,1) DEFAULT 0")
        cur.execute("ALTER TABLE kpi_snapshot ADD COLUMN IF NOT EXISTS ruptura_classe_a INTEGER DEFAULT 0")
    conn.commit()
    return conn


def buscar_kpis_atuais(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                ROUND(SUM(p."Quantidade Vendida" * pr."Valor Unitário")::numeric, 2) AS faturamento_total,
                (SELECT ROUND(SUM(e."Qtd. de Estoque Atual" * pr2."Valor Unitário")::numeric, 2)
                 FROM estoque e JOIN produtos pr2 ON e."Cód. Produto (SKU)" = pr2."Cód. Produto (SKU)"
                ) AS valor_em_estoque,
                COUNT(DISTINCT p."Nº Ordem de Venda (OV)") AS total_pedidos,
                (SELECT COUNT(*) FROM estoque WHERE "Qtd. de Estoque Atual" = 0) AS qtd_skus_com_ruptura,
                (SELECT COUNT(DISTINCT "Cód. Produto (SKU)") FROM estoque) AS qtd_skus_total,
                ROUND(
                    (SELECT COUNT(*) FROM estoque WHERE "Qtd. de Estoque Atual" = 0)::numeric /
                    NULLIF((SELECT COUNT(DISTINCT "Cód. Produto (SKU)") FROM estoque), 0) * 100
                , 2) AS taxa_ruptura,
                ROUND(
                    NULLIF(SUM(p."Quantidade Vendida" * pr."Valor Unitário"), 0)::numeric /
                    NULLIF(COUNT(DISTINCT p."Nº Ordem de Venda (OV)"), 0)
                , 2) AS ticket_medio,
                ROUND(
                    (NULLIF(SUM(p."Quantidade Vendida" * pr."Valor Unitário"), 0)::numeric /
                    NULLIF((SELECT SUM(e2."Qtd. de Estoque Atual" * pr2."Valor Unitário")::numeric
                            FROM estoque e2 JOIN produtos pr2 ON e2."Cód. Produto (SKU)" = pr2."Cód. Produto (SKU)"), 0))::numeric
                , 2) AS giro_estoque,
                ROUND(
                    (NULLIF((SELECT SUM("Qtd. de Estoque Atual") FROM estoque), 0)::numeric /
                    NULLIF(
                        SUM(p."Quantidade Vendida")::numeric /
                        NULLIF((MAX(p."Data"::date) - MIN(p."Data"::date))::numeric, 0)
                    , 0))::numeric
                , 1) AS cobertura_dias,
                (SELECT COUNT(*) FROM estoque e2
                 JOIN produtos pr3 ON e2."Cód. Produto (SKU)" = pr3."Cód. Produto (SKU)"
                 WHERE e2."Qtd. de Estoque Atual" = 0 AND pr3."Class. ABC Item" = 'A'
                ) AS ruptura_classe_a
            FROM pedidos p
            JOIN produtos pr ON p."Cód. Produto (SKU)" = pr."Cód. Produto (SKU)"
        """)
        row = cur.fetchone()
        return {
            "faturamento_total":    float(row[0] or 0),
            "valor_em_estoque":     float(row[1] or 0),
            "total_pedidos":        int(row[2] or 0),
            "qtd_skus_com_ruptura": int(row[3] or 0),
            "qtd_skus_total":       int(row[4] or 0),
            "taxa_ruptura":         float(row[5] or 0),
            "ticket_medio":         float(row[6] or 0),
            "giro_estoque":         float(row[7] or 0),
            "cobertura_dias":       float(row[8] or 0),
            "ruptura_classe_a":     int(row[9] or 0),
        }


def buscar_snapshot_anterior(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT faturamento_total, valor_em_estoque, total_pedidos,
                   qtd_skus_com_ruptura, qtd_skus_total, taxa_ruptura,
                   COALESCE(ticket_medio, 0), COALESCE(giro_estoque, 0),
                   COALESCE(cobertura_dias, 0), COALESCE(ruptura_classe_a, 0)
            FROM kpi_snapshot ORDER BY capturado_em DESC LIMIT 1
        """)
        row = cur.fetchone()
        if not row:
            return None
        return {
            "faturamento_total":    float(row[0] or 0),
            "valor_em_estoque":     float(row[1] or 0),
            "total_pedidos":        int(row[2] or 0),
            "qtd_skus_com_ruptura": int(row[3] or 0),
            "qtd_skus_total":       int(row[4] or 0),
            "taxa_ruptura":         float(row[5] or 0),
            "ticket_medio":         float(row[6] or 0),
            "giro_estoque":         float(row[7] or 0),
            "cobertura_dias":       float(row[8] or 0),
            "ruptura_classe_a":     int(row[9] or 0),
        }


def salvar_snapshot(conn, kpis):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO kpi_snapshot
                (faturamento_total, valor_em_estoque, total_pedidos,
                 qtd_skus_com_ruptura, qtd_skus_total, taxa_ruptura,
                 ticket_medio, giro_estoque, cobertura_dias, ruptura_classe_a)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            kpis["faturamento_total"], kpis["valor_em_estoque"], kpis["total_pedidos"],
            kpis["qtd_skus_com_ruptura"], kpis["qtd_skus_total"], kpis["taxa_ruptura"],
            kpis["ticket_medio"], kpis["giro_estoque"], kpis["cobertura_dias"], kpis["ruptura_classe_a"],
        ))
        conn.commit()


def verificar_limites(kpis, kpis_anteriores):
    CAMPO_REAL = {
        "_fat_queda":    "faturamento_total",
        "_ped_queda":    "total_pedidos",
        "_ticket_queda": "ticket_medio",
    }

    alertas = []
    campos_ja_alertados = {}

    for regra in REGRAS:
        campo = regra["campo"]
        op    = regra["op"]
        thr   = regra["threshold"]
        sev   = regra["severidade"]

        if op == "queda_brusca":
            campo_real = CAMPO_REAL.get(campo)
            if not campo_real or not kpis_anteriores:
                continue
            v_ant = kpis_anteriores.get(campo_real, 0)
            if v_ant == 0:
                continue
            delta_pct = ((kpis[campo_real] - v_ant) / v_ant) * 100
            if delta_pct > -thr:
                continue
            if campos_ja_alertados.get(campo) == "CRÍTICO":
                continue
            campos_ja_alertados[campo] = sev
            alertas.append({
                **regra,
                "valor_atual":    kpis[campo_real],
                "valor_anterior": v_ant,
                "delta_pct":      delta_pct,
                "extra":          f"Queda de {abs(delta_pct):.1f}% em relação a anteriormente.",
            })
            continue

        valor = kpis.get(campo)
        if valor is None:
            continue

        disparou = (op == ">" and valor > thr) or (op == "<" and valor < thr)
        if not disparou:
            continue

        if campos_ja_alertados.get(campo) == "CRÍTICO":
            continue

        campos_ja_alertados[campo] = sev
        alertas.append({
            **regra,
            "valor_atual":    valor,
            "valor_anterior": kpis_anteriores.get(campo) if kpis_anteriores else None,
            "delta_pct":      None,
            "extra":          None,
        })

    return alertas


def gerar_insight(alerta):
    campo = alerta["campo"]
    sev   = alerta["severidade"]
    va    = alerta["valor_atual"]
    thr   = alerta["threshold"]
    v_ant = alerta.get("valor_anterior")

    if campo == "taxa_ruptura":
        if sev == "CRÍTICO":
            return (f"Taxa de ruptura em {va:.1f}% — acima do limite crítico de {thr:.0f}%. "
                    "Risco alto de perda de vendas para concorrentes. Acione reposição imediata.")
        else:
            return (f"Taxa de ruptura em {va:.1f}% — ultrapassou o limite de atenção de {thr:.0f}%. "
                    "Inicie revisão de reposição antes que o quadro piore.")

    if campo == "ruptura_classe_a":
        return (f"{int(va)} SKU{'s' if va > 1 else ''} Classe A sem estoque. "
                "Cada ruptura de item A representa perda direta e imediata de receita.")

    if campo == "cobertura_dias":
        if sev == "CRÍTICO":
            return (f"Cobertura de estoque em {va:.0f} dias — abaixo do lead time de reposição de {thr:.0f} dias. "
                    "No ritmo atual de vendas, o estoque se esgota antes da reposição chegar. Pedido urgente.")
        else:
            return (f"Cobertura de estoque em {va:.0f} dias — abaixo de {thr:.0f} dias. "
                    "Acione reposição preventiva considerando o lead time de importação.")

    if campo == "giro_estoque":
        if sev == "CRÍTICO":
            return (f"Giro de estoque em {va:.2f}x — abaixo de {thr:.0f}x. "
                    "Estoque parado por mais de 2 meses. Verifique itens encalhados e risco de obsolescência tecnológica.")
        else:
            return (f"Giro de estoque em {va:.2f}x — abaixo do padrão histórico de {thr:.0f}x. "
                    "Desempenho abaixo do esperado. Monitore itens com baixa saída.")

    if campo == "_fat_queda":
        extra = alerta.get("extra", "")
        return (f"Faturamento caiu para R$ {va:,.2f} (era R$ {v_ant:,.2f}). {extra} "
                "Verifique se há problema operacional, queda de demanda ou perda de pedidos.")

    if campo == "_ped_queda":
        extra = alerta.get("extra", "")
        return (f"Volume de pedidos caiu para {int(va)} (era {int(v_ant)}). {extra} "
                "Queda expressiva no número de ordens — verifique canal de vendas e disponibilidade de SKUs.")

    if campo == "_ticket_queda":
        extra = alerta.get("extra", "")
        return (f"Ticket médio caiu para R$ {va:,.2f} (era R$ {v_ant:,.2f}). {extra} "
                "Verifique troca de mix para produtos mais baratos ou aumento de descontos não aprovados.")

    return alerta["descricao"]


def formatar_valor(v, unidade):
    if v is None:
        return "—"
    if unidade == "R$":
        return f"R$ {v:,.2f}"
    if unidade == "%":
        return f"{v:.2f}%"
    if unidade == "x":
        return f"{v:.2f}x"
    if unidade == "dias":
        return f"{v:.0f} dias"
    return str(int(v))


def formatar_limite(alerta):
    if alerta["op"] == "queda_brusca":
        return f"{alerta['threshold']:.0f}%"
    return formatar_valor(alerta["threshold"], alerta["unidade"])

def cv():  return "#f4ecff"
def cb():  return "#ece7f8"
def ca():  return "#8b5cf6"
def cn():  return "#6b7280"
def cor_sev(sev):   return "#dc2626" if sev == "CRÍTICO" else "#d97706"
def icone_sev(sev): return "&#9888;" if sev == "CRÍTICO" else ""
def er():    return f"font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{cn()};"
def ets():   return f"font-size:13px;line-height:1.6;color:{cn()};"
def sec():   return f"font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:{cn()};font-weight:700;"
def pill(cor): return (
    "display:inline-flex;align-items:center;gap:6px;padding:6px 10px;"
    f"border-radius:9999px;background:{cor}14;color:{cor};font-size:12px;font-weight:700;"
)


def render_badge_ruptura(taxa):
    label, cor = severidade_ruptura(taxa)
    faixas_html = ""
    for limite, flabel, fcor in FAIXAS_RUPTURA:
        peso = "800" if flabel == label else "600"
        fundo = f"{fcor}18" if flabel == label else "#ffffff"
        borda = cb()
        lim_txt = "≤2" if flabel == "Saudável" else ("≤5" if flabel == "Atenção" else ">5")
        faixas_html += (
            f'<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 10px;'
            f'border-radius:9999px;background:{fundo};border:1px solid {borda};'
            f'font-size:12px;font-weight:{peso};color:{fcor};line-height:1.2;">'
            f'{flabel} ({lim_txt}%)</span> '
        )
    return f"""
    <div style="margin-top:10px;padding:14px 14px 12px;background:#faf7ff;border:1px solid {cb()};border-radius:14px;box-shadow:0 1px 3px rgba(17,24,39,0.05);">
      <div style="{er()};margin-bottom:8px;color:{ca()};font-size:13px;">Nível de Ruptura</div>
      <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-start;">{faixas_html}</div>
    </div>"""


def render_comparacao(alerta):
    campo   = alerta["campo"]
    unidade = alerta["unidade"]
    va      = alerta["valor_atual"]
    v_ant   = alerta.get("valor_anterior")

    if v_ant is None:
        return ""

    def fmt(v):
        if unidade == "R$":   return f"R$ {v:,.2f}"
        if unidade == "%":    return f"{v:.2f}%"
        if unidade == "x":    return f"{v:.2f}x"
        if unidade == "dias": return f"{v:.0f} dias"
        return str(int(v))

    ant_fmt = fmt(v_ant)
    atu_fmt = fmt(va)

    if v_ant != 0 and va != v_ant:
        delta     = va - v_ant
        delta_pct = (delta / abs(v_ant)) * 100
        ruim_se_sobe = {"taxa_ruptura", "qtd_skus_com_ruptura", "ruptura_classe_a"}
        ruim_se_cai  = {"cobertura_dias", "giro_estoque", "_fat_queda", "_ped_queda", "_ticket_queda"}

        if campo in ruim_se_sobe:
            cor_var = "#dc2626" if delta > 0 else "#16a34a"
        elif campo in ruim_se_cai:
            cor_var = "#dc2626" if delta < 0 else "#16a34a"
        else:
            cor_var = "#16a34a" if delta > 0 else "#dc2626"

        seta = "&#9650;" if delta > 0 else "&#9660;"

        if campo == "ruptura_classe_a":
            diff_txt = f"{seta} {abs(int(delta))} SKU{'s' if abs(delta) > 1 else ''}"
        elif unidade in ("%", "x", "dias"):
            diff_txt = f"{seta} {fmt(abs(delta))}"
        elif unidade == "":
            diff_txt = f"{seta} {abs(int(delta))}"
        else:
            diff_txt = f"{seta} {abs(delta_pct):.1f}%"

        variacao_html = f'<span style="font-weight:500;color:{cor_var};">{diff_txt}</span>'
    else:
        variacao_html = ""

    return f"""
    <div style="margin-top:14px;padding-top:12px;border-top:0.5px solid #ece7f8;
                font-size:13px;color:#6b7280;display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span>Antes: <strong style="color:#111827;">{ant_fmt}</strong></span>
      {f'<span style="color:#c4b5fd;">&#183;</span> {variacao_html}' if variacao_html else ""}
    </div>"""


def build_html(alertas, kpis):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    tem_critico = any(a["severidade"] == "CRÍTICO" for a in alertas)
    if not alertas:
        status_texto, status_cor = "Tudo dentro do normal", ca()
        resumo = "Nenhum limite crítico ou de atenção foi ultrapassado nesta verificação."
    elif tem_critico:
        status_texto, status_cor = "Ação necessária", "#dc2626"
        n_crit = sum(1 for a in alertas if a["severidade"] == "CRÍTICO")
        resumo = f"{n_crit} alerta{'s' if n_crit > 1 else ''} crítico{'s' if n_crit > 1 else ''} detectado{'s' if n_crit > 1 else ''}."
    else:
        status_texto, status_cor = "Atenção", "#d97706"
        resumo = f"{len(alertas)} indicador{'es' if len(alertas) > 1 else ''} fora da faixa de atenção."

    badge_ruptura_html = ""
    if any(a["campo"] in ("taxa_ruptura", "qtd_skus_com_ruptura", "ruptura_classe_a") for a in alertas):
        badge_ruptura_html = f"""
        <tr><td style="padding:4px 24px 8px;">
          <div style="{sec()};margin-bottom:12px;">Ruptura de Estoque</div>
          {render_badge_ruptura(kpis["taxa_ruptura"])}
        </td></tr>"""

    blocos = []
    for a in alertas:
        insight    = gerar_insight(a)
        comparacao = render_comparacao(a)
        cor        = cor_sev(a["severidade"])
        sev        = a["severidade"]
        icone      = icone_sev(sev)
        v_atual    = formatar_valor(a["valor_atual"], a["unidade"])
        thr_fmt    = formatar_limite(a)
        card_border = (
            f"background:#ffffff;border:1px solid #ece7f8;border-radius:16px;"
            f"box-shadow:0 1px 3px rgba(17,24,39,0.06);padding:18px;"
            f"margin-bottom:14px;border-left:4px solid {cor};"
        )

        blocos.append(f"""
        <div style="{card_border}">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:top;">
                <div style="{er()};margin-bottom:8px;">{a['nome']}</div>
                <div style="font-size:26px;font-weight:800;color:{cor};">{f'{icone} ' if icone else ''}{v_atual}</div>
                <div style="margin-top:6px;{ets()}">{insight}</div>
              </td>
              <td align="right" style="vertical-align:top;white-space:nowrap;">
                <span style="{pill(cor)}">{sev}</span>
              </td>
            </tr>
          </table>
          <div style="margin-top:10px;font-size:12px;color:{cn()};">
            Limite: <strong style="color:#111827;">{thr_fmt}</strong>
          </div>
          {comparacao}
        </div>""")

    blocos_html = "".join(blocos) if blocos else f"""
        <div style="background:#faf7ff;border:1px solid {cb()};border-radius:16px;padding:24px;text-align:center;">
          <div style="font-size:18px;font-weight:700;color:{ca()};">&#10003; Todos os indicadores dentro dos limites</div>
          <div style="margin-top:8px;font-size:13px;color:{cn()};">Próxima verificação em 1 hora.</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#ffffff;font-family:Inter,Roboto,'Segoe UI',Arial,sans-serif;color:#111827;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;padding:28px 14px;">
    <tr><td align="center">
      <table width="680" cellpadding="0" cellspacing="0" style="width:100%;max-width:680px;background:#ffffff;border:1px solid {cb()};border-radius:24px;overflow:hidden;box-shadow:0 10px 28px rgba(17,24,39,0.06);">

        <tr><td style="background:{cv()};padding:18px 24px;border-bottom:1px solid {cb()};">
          <div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:{ca()};font-weight:700;">Monitor de KPIs</div>
          <div style="margin-top:6px;font-size:24px;font-weight:800;color:#111827;">Alerta de Estoque — Limites Atingidos</div>
          <div style="margin-top:4px;font-size:13px;color:{cn()};">{agora}</div>
        </td></tr>

        <tr><td style="padding:18px 24px 10px;">
          <div style="background:#faf7ff;border:1px solid {cb()};border-radius:18px;padding:14px 18px;">
            <span style="font-weight:700;color:{status_cor};font-size:15px;">{status_texto}</span>
            <span style="color:{cn()};font-size:13px;"> — {resumo}</span>
          </div>
        </td></tr>

        {badge_ruptura_html}

        <tr><td style="padding:4px 24px 22px;">
          <div style="{sec()};margin-bottom:12px;">Alertas ativos</div>
          {blocos_html}
        </td></tr>

        <tr><td style="background:#faf7ff;padding:14px 24px;border-top:1px solid {cb()};">
          <div style="font-size:12px;line-height:1.7;color:{cn()};">
            Gerado automaticamente pelo Monitor KPI &mdash; {agora}<br>
            E-mails enviados apenas quando um limite fixo é ultrapassado. Verificação a cada hora.
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def enviar_email(alertas, kpis_atuais):
    agora    = datetime.now().strftime("%d/%m/%Y %H:%M")
    html     = build_html(alertas, kpis_atuais)
    tem_crit = any(a["severidade"] == "CRÍTICO" for a in alertas)
    prefixo  = "🚨 CRÍTICO" if tem_crit else "⚠️ Atenção"
    msg      = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINO
    msg["Subject"] = f"{prefixo} — KPI Estoque {agora} ({len(alertas)} alerta{'s' if len(alertas) > 1 else ''})"
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINO, msg.as_string())
    print(f"[{agora}] E-mail enviado! ({len(alertas)} alerta(s))")


def monitorar():
    print("Monitor KPI iniciado — verificando a cada hora...")
    print("Alertas disparados por limites fixos (não por qualquer variação).")
    print("Pressione Ctrl+C para parar.\n")

    print("Limites configurados:")
    for r in REGRAS:
        if r["op"] == "queda_brusca":
            print(f"  [{r['severidade']:8s}] {r['nome']:25s} queda >= {r['threshold']:.0f}%")
        else:
            op_txt  = "acima de" if r["op"] == ">" else "abaixo de"
            unidade = r.get("unidade", "")
            print(f"  [{r['severidade']:8s}] {r['nome']:25s} {op_txt} {r['threshold']}{unidade}")
    print()

    while True:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            conn            = conectar_banco()
            kpis_atuais     = buscar_kpis_atuais(conn)
            kpis_anteriores = buscar_snapshot_anterior(conn)

            if kpis_anteriores is None:
                print(f"[{agora}] Primeiro snapshot salvo — aguardando próxima verificação")
                salvar_snapshot(conn, kpis_atuais)
            else:
                alertas = verificar_limites(kpis_atuais, kpis_anteriores)
                if alertas:
                    crit  = [a for a in alertas if a["severidade"] == "CRÍTICO"]
                    atenc = [a for a in alertas if a["severidade"] == "ATENÇÃO"]
                    print(f"[{agora}] {len(crit)} crítico(s), {len(atenc)} atenção — enviando email...")
                    enviar_email(alertas, kpis_atuais)
                else:
                    print(f"[{agora}] Todos os KPIs dentro dos limites — nenhum email enviado")
                    salvar_snapshot(conn, kpis_atuais)

            conn.close()
        except Exception as e:
            print(f"[{agora}] ERRO: {e}")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    monitorar()