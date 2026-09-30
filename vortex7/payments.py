"""Pagamentos da VORTEX 7.

* Pix  -> gera o "Pix copia e cola" (BR Code EMV, padrão do Banco Central) e o
          QR Code. O dinheiro cai direto na chave Pix da loja. Como é Pix
          estático, não existe callback do banco: o admin confirma o
          recebimento no painel.
* Cartão e Boleto -> Mercado Pago Checkout Pro (o cliente paga na página
          segura do Mercado Pago; nenhum dado de cartão passa pelo nosso
          servidor). O status volta por webhook e/ou verificação ativa.
"""

import json
import re
import unicodedata
import urllib.error
import urllib.request

import segno

MP_API = "https://api.mercadopago.com"


class PaymentError(Exception):
    """Falha ao falar com o provedor de pagamento."""


# ---------------------------------------------------------------------------
# Disponibilidade dos meios de pagamento
# ---------------------------------------------------------------------------

METHOD_LABELS = {"pix": "Pix", "cartao": "Cartão de Crédito", "boleto": "Boleto Bancário"}

# chave usada só em modo teste (não pertence a ninguém)
TEST_PIX_KEY = "teste@vortex7.com.br"


def available_methods(settings):
    """Retorna {metodo: (disponivel, observacao)} conforme as configurações."""
    test_mode = settings.get("test_mode") == "1"
    has_pix = bool(settings.get("pix_key", "").strip())
    has_mp = bool(settings.get("mp_access_token", "").strip())

    def entry(ok_real, missing_msg):
        if test_mode:
            return True, "Modo teste: pagamento simulado"
        if ok_real:
            return True, ""
        return False, missing_msg

    return {
        "pix": entry(has_pix, "Indisponível no momento"),
        "cartao": entry(has_mp, "Indisponível no momento"),
        "boleto": entry(has_mp, "Indisponível no momento"),
    }


# ---------------------------------------------------------------------------
# Pix — BR Code (EMV QRCPS-MPM)
# ---------------------------------------------------------------------------

def crc16_ccitt(text):
    """CRC16/CCITT-FALSE (poly 0x1021, init 0xFFFF), exigido pelo BR Code."""
    crc = 0xFFFF
    for byte in text.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _emv(field_id, value):
    return f"{field_id}{len(value):02d}{value}"


def _ascii(text, max_len, fallback):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9 .\-]", "", text).strip()
    return (text or fallback)[:max_len]


def build_pix_payload(key, receiver_name, city, amount=None, txid="***", point_of_initiation="11"):
    """Monta o Pix copia e cola.

    key: chave Pix como cadastrada no banco (telefone com +55, e-mail, CPF/CNPJ
         só dígitos ou chave aleatória).
    txid: identificador (1–25 letras/números) — usamos o número do pedido.
    """
    key = (key or "").strip()
    if not key or len(key) > 77:
        raise PaymentError("Chave Pix inválida.")
    txid = re.sub(r"[^A-Za-z0-9]", "", txid or "")[:25] or "***"

    merchant_account = _emv("00", "br.gov.bcb.pix") + _emv("01", key)
    payload = _emv("00", "01")
    if point_of_initiation:
        payload += _emv("01", point_of_initiation)
    payload += _emv("26", merchant_account)
    payload += _emv("52", "0000") + _emv("53", "986")
    if amount and amount > 0:
        payload += _emv("54", f"{amount:.2f}")
    payload += _emv("58", "BR")
    payload += _emv("59", _ascii(receiver_name, 25, "LOJA"))
    payload += _emv("60", _ascii(city, 15, "BRASIL"))
    payload += _emv("62", _emv("05", txid))
    payload += "6304"
    return payload + crc16_ccitt(payload)


def pix_for_order(settings, number, total):
    """Payload Pix de um pedido (usa a chave de teste se estiver em modo teste)."""
    key = settings.get("pix_key", "").strip()
    if not key and settings.get("test_mode") == "1":
        key = TEST_PIX_KEY
    return build_pix_payload(
        key,
        settings.get("pix_receiver_name") or settings.get("store_name") or "VORTEX 7",
        settings.get("pix_city") or "FORTALEZA",
        amount=total,
        txid=number,
    )


def qr_svg(payload, scale=5):
    """QR Code como <svg> inline (sem imagem externa)."""
    svg = segno.make(payload, error="m").svg_inline(scale=scale, border=2, dark="#000", light="#fff")
    # troca width/height fixos por viewBox, para o CSS poder redimensionar
    return re.sub(
        r'<svg width="(\d+)" height="(\d+)"',
        r'<svg viewBox="0 0 \1 \2" role="img" aria-label="QR Code Pix"',
        svg,
        count=1,
    )


def qr_matrix(payload):
    """Matriz booleana do QR (usada para desenhar no PDF)."""
    qr = segno.make(payload, error="m")
    return [[bool(cell) for cell in row] for row in qr.matrix]


# ---------------------------------------------------------------------------
# Mercado Pago (Checkout Pro)
# ---------------------------------------------------------------------------

def _mp(method, path, token, payload=None):
    """Chamada HTTP à API do Mercado Pago (isolada para facilitar testes)."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        MP_API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise PaymentError(f"Mercado Pago respondeu {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PaymentError(f"Não foi possível falar com o Mercado Pago: {exc}") from exc


_EXCLUDED_TYPES = {
    # cartão: tira boleto, Pix/transferência e lotérica
    "cartao": ["ticket", "bank_transfer", "atm"],
    # boleto: só deixa "ticket"
    "boleto": ["credit_card", "debit_card", "prepaid_card", "bank_transfer", "atm"],
}


def mp_create_preference(order, items, token, success_url, notification_url=None):
    """Cria a preferência de pagamento e devolve (preference_id, init_point)."""
    pref_items = []
    for it in items:
        title = it["name"]
        variant = " / ".join(v for v in (it["size"], it["color"]) if v)
        if variant:
            title += f" ({variant})"
        pref_items.append({
            "id": str(it["product_id"] or it["id"]),
            "title": title[:250],
            "quantity": int(it["qty"]),
            "unit_price": round(float(it["unit_price"]), 2),
            "currency_id": "BRL",
        })
    if order["shipping_price"] and order["shipping_price"] > 0:
        pref_items.append({
            "id": "frete",
            "title": f"Frete {order['shipping_method'].upper()}",
            "quantity": 1,
            "unit_price": round(float(order["shipping_price"]), 2),
            "currency_id": "BRL",
        })

    name_parts = (order["customer_name"] or "").split(None, 1)
    payer = {"name": name_parts[0] if name_parts else "", "email": order["customer_email"]}
    if len(name_parts) > 1:
        payer["surname"] = name_parts[1]
    phone = "".join(ch for ch in (order["customer_phone"] or "") if ch.isdigit())
    if len(phone) >= 10:
        payer["phone"] = {"area_code": phone[:2], "number": phone[2:]}
    cpf = "".join(ch for ch in (order["customer_cpf"] or "") if ch.isdigit())
    if len(cpf) == 11:
        payer["identification"] = {"type": "CPF", "number": cpf}

    body = {
        "items": pref_items,
        "payer": payer,
        "external_reference": order["number"],
        "statement_descriptor": "VORTEX7",
        "back_urls": {"success": success_url, "pending": success_url, "failure": success_url},
        "payment_methods": {
            "installments": 3,
            "excluded_payment_types": [{"id": t} for t in _EXCLUDED_TYPES.get(order["payment_method"], [])],
        },
    }
    # O Mercado Pago só aceita auto_return / notification_url com HTTPS público.
    if success_url.startswith("https://"):
        body["auto_return"] = "approved"
    if notification_url and notification_url.startswith("https://"):
        body["notification_url"] = notification_url

    pref = _mp("POST", "/checkout/preferences", token, body)
    if not pref.get("id") or not pref.get("init_point"):
        raise PaymentError("Resposta inesperada do Mercado Pago ao criar o pagamento.")
    return pref["id"], pref["init_point"]


def mp_get_payment(payment_id, token):
    return _mp("GET", f"/v1/payments/{int(payment_id)}", token)


def mp_find_payment_for_order(number, token):
    """Procura pagamentos pelo external_reference; prefere o aprovado."""
    from urllib.parse import quote
    result = _mp(
        "GET",
        f"/v1/payments/search?external_reference={quote(number)}&sort=date_created&criteria=desc",
        token,
    )
    payments = result.get("results") or []
    for p in payments:
        if p.get("status") == "approved":
            return p
    return payments[0] if payments else None
