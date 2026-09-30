"""Comprovante de pedido em PDF (reportlab, sem dependências nativas)."""

import io

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from . import payments
from .common import format_brl, fmt_datetime
from .orders import PAYMENT_LABELS, SHIPPING_LABELS, STATUS_LABELS

GREEN = colors.HexColor("#0f7a34")
DARK = colors.HexColor("#111511")
GRAY = colors.HexColor("#5f665e")
LINE = colors.HexColor("#d9ded6")
SOFT = colors.HexColor("#f2f5f0")


def _styles():
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=DARK)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=11, textColor=GRAY),
        "brand": ParagraphStyle("brand", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=22, textColor=GREEN),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=13, leading=16, alignment=TA_RIGHT),
        "h": ParagraphStyle("h", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=GREEN),
        "b": ParagraphStyle("b", parent=base, fontName="Helvetica-Bold"),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "rightb": ParagraphStyle("rightb", parent=base, alignment=TA_RIGHT, fontName="Helvetica-Bold"),
        "total": ParagraphStyle("total", parent=base, alignment=TA_RIGHT, fontName="Helvetica-Bold", fontSize=13, leading=16),
        "center": ParagraphStyle("center", parent=base, alignment=TA_CENTER, fontSize=8, leading=11, textColor=GRAY),
        "mono": ParagraphStyle("mono", parent=base, fontName="Courier", fontSize=7, leading=9, wordWrap="CJK"),
    }


def _p(text, style):
    return Paragraph(escape(str(text)) if text is not None else "", style)


def _qr_drawing(payload, size_mm=42):
    matrix = payments.qr_matrix(payload)
    border = 2
    n = len(matrix) + border * 2
    size = size_mm * mm
    cell = size / n
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, fillColor=colors.white, strokeColor=None))
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                d.add(Rect((c + border) * cell, size - (r + border + 1) * cell, cell, cell,
                           fillColor=colors.black, strokeColor=None))
    return d


def build_receipt_pdf(order, items, settings):
    """Retorna os bytes do PDF do comprovante do pedido."""
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Comprovante {order['number']}", author=settings.get("store_name", "VORTEX 7"),
    )
    width = A4[0] - 36 * mm
    story = []

    # --- Cabeçalho ---------------------------------------------------------
    store = settings.get("store_name") or "VORTEX 7"
    legal_lines = []
    if settings.get("store_legal_name"):
        legal_lines.append(settings["store_legal_name"])
    if settings.get("store_cnpj"):
        legal_lines.append(f"CNPJ {settings['store_cnpj']}")
    contact = " · ".join(x for x in (settings.get("store_email"), settings.get("store_phone")) if x)
    if contact:
        legal_lines.append(contact)
    if settings.get("store_address"):
        legal_lines.append(settings["store_address"])

    left = [_p(store, st["brand"])] + [_p(l, st["small"]) for l in legal_lines]
    right = [
        _p("COMPROVANTE DE PEDIDO", st["title"]),
        _p(f"Nº {order['number']}", st["rightb"]),
        _p(f"Emitido em {fmt_datetime(order['created_at'])}", ParagraphStyle("r2", parent=st["small"], alignment=TA_RIGHT)),
    ]
    head = Table([[left, right]], colWidths=[width * 0.55, width * 0.45])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [head, Spacer(1, 4 * mm), HRFlowable(width="100%", thickness=1.2, color=GREEN), Spacer(1, 5 * mm)]

    # --- Status --------------------------------------------------------------
    pay_label = PAYMENT_LABELS.get(order["payment_status"], order["payment_status"])
    status = Table(
        [[_p("Situação do pedido", st["small"]), _p("Pagamento", st["small"]), _p("Forma de pagamento", st["small"])],
         [_p(STATUS_LABELS.get(order["status"], order["status"]), st["b"]), _p(pay_label, st["b"]),
          _p(payments.METHOD_LABELS.get(order["payment_method"], order["payment_method"]), st["b"])]],
        colWidths=[width / 3] * 3,
    )
    status.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [status, Spacer(1, 5 * mm)]

    # --- Cliente / entrega ---------------------------------------------------
    cust = [_p("CLIENTE", st["h"]), _p(order["customer_name"], st["b"]), _p(order["customer_email"], st["base"])]
    if order["customer_phone"]:
        cust.append(_p(order["customer_phone"], st["base"]))
    if order["customer_cpf"]:
        cust.append(_p(f"CPF: {order['customer_cpf']}", st["base"]))

    addr_line2 = " – ".join(x for x in (order["ship_neighborhood"], f"{order['ship_city']}/{order['ship_state']}") if x)
    ship = [_p("ENTREGA", st["h"]),
            _p(order["ship_address"] + (f", {order['ship_complement']}" if order["ship_complement"] else ""), st["base"]),
            _p(addr_line2, st["base"]), _p(f"CEP {order['ship_cep'][:5]}-{order['ship_cep'][5:]}", st["base"]),
            _p(f"{SHIPPING_LABELS.get(order['shipping_method'], order['shipping_method'])} — "
               f"prazo estimado {order['shipping_days']} dias úteis após a postagem", st["small"])]
    if order["tracking_code"]:
        ship.append(_p(f"Rastreio: {order['tracking_code']}", st["b"]))
    two = Table([[cust, ship]], colWidths=[width * 0.48, width * 0.52])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [two, Spacer(1, 5 * mm)]

    # --- Itens ---------------------------------------------------------------
    rows = [[_p("Produto", st["b"]), _p("Qtd", st["rightb"]), _p("Unitário", st["rightb"]), _p("Total", st["rightb"])]]
    for it in items:
        variant = " / ".join(v for v in (it["size"], it["color"]) if v)
        name = escape(it["name"]) + (f'<br/><font size="8" color="#5f665e">{escape(variant)}</font>' if variant else "")
        rows.append([Paragraph(name, st["base"]), _p(it["qty"], st["right"]),
                     _p(f"R$ {format_brl(it['unit_price'])}", st["right"]),
                     _p(f"R$ {format_brl(it['line_total'])}", st["right"])])
    tbl = Table(rows, colWidths=[width * 0.52, width * 0.1, width * 0.19, width * 0.19], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, GREEN),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [tbl, Spacer(1, 3 * mm)]

    # --- Totais --------------------------------------------------------------
    tot = [[_p("Subtotal", st["right"]), _p(f"R$ {format_brl(order['subtotal'])}", st["right"])]]
    if order["discount"]:
        tot.append([_p("Desconto Pix", st["right"]), _p(f"- R$ {format_brl(order['discount'])}", st["right"])])
    ship_txt = "Grátis" if not order["shipping_price"] else f"R$ {format_brl(order['shipping_price'])}"
    tot.append([_p(f"Frete ({SHIPPING_LABELS.get(order['shipping_method'], '')})", st["right"]), _p(ship_txt, st["right"])])
    tot.append([_p("TOTAL", st["total"]), _p(f"R$ {format_brl(order['total'])}", st["total"])])
    t2 = Table(tot, colWidths=[width * 0.75, width * 0.25])
    t2.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.8, GREEN), ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story += [t2, Spacer(1, 6 * mm)]

    # --- Instruções de pagamento (Pix pendente) ------------------------------
    if order["payment_method"] == "pix" and order["payment_status"] == "pendente" and order["pix_payload"]:
        qr = _qr_drawing(order["pix_payload"])
        info = [_p("PAGUE COM PIX", st["h"]),
                _p(f"Valor: R$ {format_brl(order['total'])}", st["b"]),
                Spacer(1, 2 * mm),
                _p("Escaneie o QR Code ou copie o código abaixo (Pix copia e cola) no app do seu banco:", st["small"]),
                Spacer(1, 1.5 * mm), _p(order["pix_payload"], st["mono"])]
        box = Table([[qr, info]], colWidths=[46 * mm, width - 46 * mm])
        box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [box, Spacer(1, 4 * mm)]
    elif order["payment_status"] == "pago":
        story += [_p(f"Pagamento confirmado em {fmt_datetime(order['paid_at'])}.", st["b"]), Spacer(1, 4 * mm)]

    # --- Rodapé --------------------------------------------------------------
    story += [
        HRFlowable(width="100%", thickness=0.5, color=LINE), Spacer(1, 2 * mm),
        _p("Este documento comprova o registro do pedido e não possui valor fiscal. "
           "Guarde-o para acompanhar sua compra ou solicitar troca/devolução em até 30 dias após o recebimento.", st["center"]),
        _p(f"{store} — obrigado pela preferência!", st["center"]),
    ]
    doc.build(story)
    return buf.getvalue()
