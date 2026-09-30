"""Regras de negócio dos pedidos da VORTEX 7."""

import secrets

from .common import now_iso
from . import payments

FREE_SHIPPING_MIN = 299.90

STATUS_LABELS = {
    "aguardando_pagamento": "Aguardando pagamento",
    "pago": "Pago",
    "em_separacao": "Em separação",
    "enviado": "Enviado",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}
PAYMENT_LABELS = {
    "pendente": "Pendente",
    "pago": "Pago",
    "reembolsado": "Reembolsado",
    "cancelado": "Cancelado",
}
SHIPPING_LABELS = {"pac": "PAC", "sedex": "SEDEX"}


class OrderError(Exception):
    """Erro de regra de negócio (mensagem pode ser mostrada ao usuário)."""


# ---------------------------------------------------------------------------
# Frete (estimativa determinística por região do CEP)
# ---------------------------------------------------------------------------

def calcular_frete(cep, subtotal, item_count):
    """Estimativa de frete sem API externa: faixas por 1º dígito do CEP."""
    digits = "".join(ch for ch in (cep or "") if ch.isdigit())
    if len(digits) != 8:
        return None

    region = int(digits[0])
    region_base = {
        0: 18.90, 1: 19.90, 2: 22.90, 3: 16.90, 4: 24.90,
        5: 27.90, 6: 32.90, 7: 29.90, 8: 26.90, 9: 25.90,
    }
    base = region_base.get(region, 24.90)
    volume_extra = max(0, item_count - 1) * 3.5

    pac_price = round(base + volume_extra, 2)
    sedex_price = round(pac_price * 1.75, 2)

    frete_gratis = subtotal >= FREE_SHIPPING_MIN
    if frete_gratis:
        pac_price = 0.0

    return {
        "cep": digits,
        "pac_price": pac_price,
        "pac_days": 5 + (region % 4),
        "sedex_price": sedex_price,
        "sedex_days": 2 + (region % 2),
        "frete_gratis": frete_gratis,
    }


# ---------------------------------------------------------------------------
# Carrinho -> linhas com preço atual do banco
# ---------------------------------------------------------------------------

def cart_lines(db, cart):
    lines = []
    for key, data in cart.items():
        p = db.execute("SELECT * FROM products WHERE id = ?", (data["product_id"],)).fetchone()
        if not p:
            continue
        unit = p["promo_price"] if p["promo_price"] else p["price"]
        lines.append({
            "key": key,
            "product": p,
            "qty": int(data["qty"]),
            "size": data.get("size") or "",
            "color": data.get("color") or "",
            "unit_price": round(float(unit), 2),
            "line_total": round(float(unit) * int(data["qty"]), 2),
        })
    return lines


def pix_discount_amount(subtotal, settings):
    try:
        pct = float(settings.get("pix_discount_percent") or 0)
    except ValueError:
        pct = 0.0
    pct = max(0.0, min(pct, 50.0))
    return round(subtotal * pct / 100, 2)


def compute_totals(lines, frete, shipping_method, payment_method, settings):
    subtotal = round(sum(l["line_total"] for l in lines), 2)
    item_count = sum(l["qty"] for l in lines)
    fr = calcular_frete(frete["cep"], subtotal, item_count) if frete else None
    if fr is None:
        raise OrderError("CEP inválido. Calcule o frete novamente no carrinho.")
    if shipping_method == "sedex":
        shipping_price, days = fr["sedex_price"], fr["sedex_days"]
    else:
        shipping_method, shipping_price, days = "pac", fr["pac_price"], fr["pac_days"]
    discount = pix_discount_amount(subtotal, settings) if payment_method == "pix" else 0.0
    total = round(subtotal - discount + shipping_price, 2)
    return {
        "subtotal": subtotal,
        "shipping_method": shipping_method,
        "shipping_price": shipping_price,
        "shipping_days": days,
        "discount": discount,
        "total": total,
        "cep": fr["cep"],
        "frete": fr,
    }


# ---------------------------------------------------------------------------
# Eventos / histórico
# ---------------------------------------------------------------------------

def log_event(db, order_id, message, actor="sistema"):
    db.execute(
        "INSERT INTO order_events (order_id, message, actor, created_at) VALUES (?,?,?,?)",
        (order_id, message, actor, now_iso()),
    )


def _new_number(db):
    for _ in range(20):
        number = f"V7-{secrets.randbelow(900000) + 100000}"
        if not db.execute("SELECT 1 FROM orders WHERE number = ?", (number,)).fetchone():
            return number
    raise OrderError("Não foi possível gerar o número do pedido. Tente novamente.")


# ---------------------------------------------------------------------------
# Criação do pedido
# ---------------------------------------------------------------------------

def create_order(db, cart, customer, shipping_method, payment_method, frete, settings, user_id=None):
    """Cria o pedido de forma atômica: confere estoque, baixa e grava tudo.

    Os preços são SEMPRE recalculados aqui a partir do banco; nada que vem do
    navegador (preço, frete, desconto) é confiado.
    """
    if payment_method not in payments.METHOD_LABELS:
        raise OrderError("Forma de pagamento inválida.")

    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")
    try:
        lines = cart_lines(db, cart)
        if not lines:
            raise OrderError("Seu carrinho está vazio.")

        for l in lines:
            if l["qty"] < 1:
                raise OrderError("Quantidade inválida.")
            cur = db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (l["qty"], l["product"]["id"], l["qty"]),
            )
            if cur.rowcount == 0:
                raise OrderError(f'Estoque insuficiente para "{l["product"]["name"]}".')

        t = compute_totals(lines, frete, shipping_method, payment_method, settings)
        number = _new_number(db)
        token = secrets.token_urlsafe(16)
        pix_payload = None
        if payment_method == "pix":
            pix_payload = payments.pix_for_order(settings, number, t["total"])

        now = now_iso()
        cur = db.execute(
            """INSERT INTO orders (
                number, access_token, user_id,
                customer_name, customer_email, customer_phone, customer_cpf,
                ship_cep, ship_address, ship_complement, ship_neighborhood, ship_city, ship_state,
                shipping_method, shipping_days, subtotal, shipping_price, discount, total,
                payment_method, payment_status, status, pix_payload, customer_notes,
                created_at, updated_at
            ) VALUES (?,?,?, ?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?, ?,?)""",
            (
                number, token, user_id,
                customer["name"], customer["email"], customer["phone"], customer.get("cpf") or None,
                t["cep"], customer["address"], customer.get("complement") or None,
                customer["neighborhood"], customer["city"], customer["state"],
                t["shipping_method"], t["shipping_days"], t["subtotal"], t["shipping_price"],
                t["discount"], t["total"],
                payment_method, "pendente", "aguardando_pagamento", pix_payload,
                customer.get("notes") or None,
                now, now,
            ),
        )
        order_id = cur.lastrowid
        for l in lines:
            db.execute(
                """INSERT INTO order_items
                   (order_id, product_id, name, size, color, qty, unit_price, line_total)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (order_id, l["product"]["id"], l["product"]["name"], l["size"], l["color"],
                 l["qty"], l["unit_price"], l["line_total"]),
            )
        log_event(db, order_id, f"Pedido criado ({payments.METHOD_LABELS[payment_method]}).", "cliente")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"id": order_id, "number": number, "token": token, "total": t["total"]}


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def get_order_by_number(db, number):
    return db.execute("SELECT * FROM orders WHERE number = ?", (number,)).fetchone()


def get_order_items(db, order_id):
    return db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()


def get_order_events(db, order_id):
    return db.execute(
        "SELECT * FROM order_events WHERE order_id = ? ORDER BY id DESC", (order_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Mudanças de estado
# ---------------------------------------------------------------------------

def _restore_stock(db, order_id):
    for it in get_order_items(db, order_id):
        if it["product_id"]:
            db.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (it["qty"], it["product_id"]))


def mark_paid(db, order, actor="sistema", note=None, mp_payment_id=None):
    """Marca o pedido como pago. Retorna True se houve mudança."""
    if order["payment_status"] == "pago":
        return False
    now = now_iso()
    new_status = order["status"]
    if order["status"] == "aguardando_pagamento":
        new_status = "pago"
    db.execute(
        "UPDATE orders SET payment_status='pago', paid_at=?, status=?, updated_at=?, "
        "mp_payment_id=COALESCE(?, mp_payment_id) WHERE id=?",
        (now, new_status, now, str(mp_payment_id) if mp_payment_id else None, order["id"]),
    )
    msg = "Pagamento confirmado."
    if note:
        msg += f" {note}"
    if order["status"] == "cancelado":
        msg += " ATENÇÃO: o pedido já estava cancelado — verifique o reembolso."
    log_event(db, order["id"], msg, actor)
    db.commit()
    return True


def set_payment_status(db, order, new_status, actor="admin"):
    if new_status not in PAYMENT_LABELS:
        raise OrderError("Status de pagamento inválido.")
    if new_status == order["payment_status"]:
        return False
    if new_status == "pago":
        return mark_paid(db, order, actor)
    db.execute(
        "UPDATE orders SET payment_status=?, updated_at=? WHERE id=?",
        (new_status, now_iso(), order["id"]),
    )
    log_event(db, order["id"], f"Pagamento alterado para: {PAYMENT_LABELS[new_status]}.", actor)
    db.commit()
    return True


def set_status(db, order, new_status, actor="admin", note=None):
    """Altera o status do pedido. Cancelar devolve o estoque."""
    if new_status not in STATUS_LABELS:
        raise OrderError("Status inválido.")
    old = order["status"]
    if new_status == old:
        return False
    if old == "cancelado":
        raise OrderError("Pedido cancelado não pode ser reaberto. Crie um novo pedido.")

    if new_status == "cancelado":
        _restore_stock(db, order["id"])
        pay = order["payment_status"]
        if pay == "pendente":
            pay = "cancelado"
        db.execute(
            "UPDATE orders SET status='cancelado', payment_status=?, updated_at=? WHERE id=?",
            (pay, now_iso(), order["id"]),
        )
        msg = "Pedido cancelado; estoque devolvido."
    else:
        db.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, now_iso(), order["id"]))
        msg = f"Status alterado: {STATUS_LABELS[old]} → {STATUS_LABELS[new_status]}."
    if note:
        msg += f" Obs.: {note}"
    log_event(db, order["id"], msg, actor)
    db.commit()
    return True


def set_tracking(db, order, code, actor="admin", mark_shipped=True):
    code = (code or "").strip()[:60]
    db.execute("UPDATE orders SET tracking_code=?, updated_at=? WHERE id=?", (code or None, now_iso(), order["id"]))
    log_event(db, order["id"], f"Código de rastreio {'definido: ' + code if code else 'removido'}.", actor)
    db.commit()
    if code and mark_shipped and order["status"] in ("pago", "em_separacao"):
        fresh = db.execute("SELECT * FROM orders WHERE id=?", (order["id"],)).fetchone()
        set_status(db, fresh, "enviado", actor)


# ---------------------------------------------------------------------------
# Mercado Pago -> pedido
# ---------------------------------------------------------------------------

def apply_mp_payment(db, order, payment):
    """Aplica ao pedido o resultado de um pagamento do Mercado Pago.

    Retorna uma string curta com o que aconteceu (útil para mensagens/log).
    """
    if not payment or payment.get("external_reference") != order["number"]:
        return "ignorado"
    status = payment.get("status")
    pid = payment.get("id")
    amount = float(payment.get("transaction_amount") or 0)

    if status == "approved":
        if abs(amount - float(order["total"])) > 0.01:
            log_event(db, order["id"],
                      f"Pagamento MP #{pid} aprovado com valor divergente "
                      f"(R$ {amount:.2f} x pedido R$ {order['total']:.2f}). Verifique manualmente.", "mercadopago")
            db.commit()
            return "divergente"
        return "pago" if mark_paid(db, order, "mercadopago", f"(Mercado Pago #{pid})", pid) else "ja_pago"
    if status in ("refunded", "charged_back"):
        if order["payment_status"] != "reembolsado":
            set_payment_status(db, order, "reembolsado", "mercadopago")
        return "reembolsado"
    if status in ("rejected", "cancelled"):
        log_event(db, order["id"], f"Pagamento MP #{pid} {status}. O cliente pode tentar novamente.", "mercadopago")
        db.commit()
        return "recusado"
    return "pendente"


def sync_with_mercadopago(db, order, token):
    """Consulta o Mercado Pago e atualiza o pedido. Retorna o resultado."""
    if order["mp_payment_id"]:
        payment = payments.mp_get_payment(order["mp_payment_id"], token)
    else:
        payment = payments.mp_find_payment_for_order(order["number"], token)
    if not payment:
        return "sem_pagamento"
    return apply_mp_payment(db, order, payment)
