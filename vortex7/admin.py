"""Painel administrativo da VORTEX 7 (montado em /vortex7/admin)."""

import csv
import io
import os
import time
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import payments
from .common import (BRT, PHOTO_EXTS, PRODUCT_IMG_DIR, admin_required, current_admin, fmt_datetime, get_db,
                     load_settings, now_iso, only_digits, safe_next_url, save_setting, slugify, to_brt)
from .orders import (OrderError, PAYMENT_LABELS, STATUS_LABELS, get_order_events, get_order_items, log_event,
                     mark_paid, set_payment_status, set_status, set_tracking, sync_with_mercadopago)
from .payments import PaymentError

admin_bp = Blueprint("admin", __name__)

PER_PAGE = 20
LOW_STOCK = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# Contexto comum dos templates do painel
# ---------------------------------------------------------------------------

@admin_bp.app_context_processor
def _admin_ctx():
    if not request.endpoint or not request.endpoint.startswith("vortex7.admin."):
        return {}
    admin = current_admin()
    if not admin:
        return {"admin": None}
    db = get_db()
    return {
        "admin": admin,
        "adm_pending_orders": db.execute(
            "SELECT COUNT(*) FROM orders WHERE status IN ('aguardando_pagamento','pago')").fetchone()[0],
        "adm_unread": db.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0").fetchone()[0],
        "adm_test_mode": load_settings(db).get("test_mode") == "1",
    }


def _actor():
    admin = current_admin()
    return f"admin:{admin['email']}" if admin else "admin"


def _page():
    try:
        return max(1, int(request.args.get("p", 1)))
    except ValueError:
        return 1


def _money(text):
    """Converte '1.299,90' / '299,90' / '299.90' em float; None se vazio/inválido."""
    text = (text or "").strip().replace("R$", "").replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return round(value, 2)


# ---------------------------------------------------------------------------
# Login / logout (com bloqueio simples contra força bruta)
# ---------------------------------------------------------------------------

_FAILS = {}  # ip -> [tentativas, primeiro_timestamp]
MAX_FAILS = 5
LOCK_SECONDS = 300


def _locked(ip):
    entry = _FAILS.get(ip)
    if not entry:
        return False
    if time.time() - entry[1] > LOCK_SECONDS:
        _FAILS.pop(ip, None)
        return False
    return entry[0] >= MAX_FAILS


def _register_fail(ip):
    entry = _FAILS.get(ip)
    if not entry or time.time() - entry[1] > LOCK_SECONDS:
        _FAILS[ip] = [1, time.time()]
    else:
        entry[0] += 1


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_admin():
        return redirect(url_for("vortex7.admin.dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _locked(ip):
            flash("Muitas tentativas. Aguarde alguns minutos e tente novamente.", "error")
            return render_template("vortex7/admin/login.html"), 429
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        row = get_db().execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password"], password):
            _FAILS.pop(ip, None)
            session.pop("_csrf", None)  # novo token após autenticar
            session["admin_id"] = row["id"]
            session["admin_at"] = datetime.now(timezone.utc).isoformat()
            return redirect(safe_next_url(request.args.get("next"), url_for("vortex7.admin.dashboard")))
        _register_fail(ip)
        flash("E-mail ou senha inválidos.", "error")
    return render_template("vortex7/admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("admin_id", None)
    session.pop("admin_at", None)
    flash("Você saiu do painel.", "success")
    return redirect(url_for("vortex7.admin.login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    now_brt = datetime.now(BRT)
    start_today = now_brt.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = start_today.replace(day=1)
    utc = lambda d: d.astimezone(timezone.utc).isoformat(timespec="seconds")

    def one(sql, *args):
        return db.execute(sql, args).fetchone()[0] or 0

    stats = {
        "orders_today": one("SELECT COUNT(*) FROM orders WHERE created_at >= ? AND status != 'cancelado'", utc(start_today)),
        "awaiting_payment": one("SELECT COUNT(*) FROM orders WHERE status = 'aguardando_pagamento'"),
        "to_ship": one("SELECT COUNT(*) FROM orders WHERE status IN ('pago','em_separacao')"),
        "revenue_month": one("SELECT SUM(total) FROM orders WHERE payment_status='pago' AND status!='cancelado' AND paid_at >= ?", utc(start_month)),
        "revenue_total": one("SELECT SUM(total) FROM orders WHERE payment_status='pago' AND status!='cancelado'"),
        "paid_count": one("SELECT COUNT(*) FROM orders WHERE payment_status='pago' AND status!='cancelado'"),
    }
    stats["avg_ticket"] = stats["revenue_total"] / stats["paid_count"] if stats["paid_count"] else 0

    # faturamento dos últimos 7 dias (por dia de Brasília)
    days = [(start_today - timedelta(days=i)) for i in range(6, -1, -1)]
    since = utc(days[0])
    per_day = {d.date(): 0.0 for d in days}
    for row in db.execute(
            "SELECT paid_at, total FROM orders WHERE payment_status='pago' AND status!='cancelado' AND paid_at >= ?", (since,)):
        dt = to_brt(row["paid_at"])
        if dt and dt.date() in per_day:
            per_day[dt.date()] += row["total"]
    max_val = max(per_day.values()) or 1
    chart = [{"label": d.strftime("%d/%m"), "value": v, "pct": round(v / max_val * 100)} for d, v in per_day.items()]

    recent = db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 8").fetchall()
    low_stock = db.execute(
        "SELECT id, name, stock FROM products WHERE stock <= ? ORDER BY stock, name LIMIT 8", (LOW_STOCK,)).fetchall()
    return render_template("vortex7/admin/dashboard.html", stats=stats, chart=chart, recent=recent,
                           low_stock=low_stock, low=LOW_STOCK)


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------

def _orders_filter():
    status = request.args.get("status", "")
    pay = request.args.get("pagamento", "")
    q = request.args.get("q", "").strip()
    where, params = ["1=1"], []
    if status in STATUS_LABELS:
        where.append("status = ?")
        params.append(status)
    if pay in PAYMENT_LABELS:
        where.append("payment_status = ?")
        params.append(pay)
    if q:
        where.append("(number LIKE ? OR customer_name LIKE ? OR customer_email LIKE ? OR customer_phone LIKE ?)")
        params += [f"%{q}%"] * 4
    return " AND ".join(where), params, status, pay, q


@admin_bp.route("/pedidos")
@admin_required
def orders():
    db = get_db()
    where, params, status, pay, q = _orders_filter()
    total = db.execute(f"SELECT COUNT(*) FROM orders WHERE {where}", params).fetchone()[0]
    page = _page()
    rows = db.execute(
        f"SELECT * FROM orders WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [PER_PAGE, (page - 1) * PER_PAGE]).fetchall()
    counts = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")}
    pages = max(1, -(-total // PER_PAGE))
    return render_template("vortex7/admin/pedidos.html", orders=rows, total=total, page=page, pages=pages,
                           status=status, pay=pay, q=q, counts=counts)


def _csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@admin_bp.route("/pedidos/exportar.csv")
@admin_required
def orders_export():
    db = get_db()
    where, params, *_ = _orders_filter()
    rows = db.execute(f"SELECT * FROM orders WHERE {where} ORDER BY id DESC", params).fetchall()
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM: o Excel abre com acentos corretos
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Pedido", "Data", "Cliente", "E-mail", "Telefone", "Cidade/UF", "Envio", "Subtotal", "Frete",
                "Desconto", "Total", "Pagamento", "Situação pgto", "Status", "Rastreio"])
    for o in rows:
        w.writerow([_csv_safe(x) for x in (
            o["number"], fmt_datetime(o["created_at"]), o["customer_name"], o["customer_email"],
            o["customer_phone"], f"{o['ship_city']}/{o['ship_state']}", o["shipping_method"].upper(),
            f"{o['subtotal']:.2f}".replace(".", ","), f"{o['shipping_price']:.2f}".replace(".", ","),
            f"{o['discount']:.2f}".replace(".", ","), f"{o['total']:.2f}".replace(".", ","),
            payments.METHOD_LABELS.get(o["payment_method"], o["payment_method"]),
            PAYMENT_LABELS.get(o["payment_status"]), STATUS_LABELS.get(o["status"]), o["tracking_code"] or "")])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=pedidos-vortex7.csv"})


def _order_or_404(oid):
    order = get_db().execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
    if not order:
        abort(404)
    return order


@admin_bp.route("/pedidos/<int:oid>")
@admin_required
def order_detail(oid):
    db = get_db()
    order = _order_or_404(oid)
    settings = load_settings(db)
    phone = only_digits(order["customer_phone"])
    if len(phone) in (10, 11):
        phone = "55" + phone
    return render_template(
        "vortex7/admin/pedido.html", order=order, items=get_order_items(db, oid),
        events=get_order_events(db, oid), whatsapp=phone,
        mp_ready=bool(settings.get("mp_access_token", "").strip()) and order["payment_method"] in ("cartao", "boleto"),
    )


def _back(oid):
    return redirect(url_for("vortex7.admin.order_detail", oid=oid))


@admin_bp.route("/pedidos/<int:oid>/status", methods=["POST"])
@admin_required
def order_status(oid):
    order = _order_or_404(oid)
    try:
        changed = set_status(get_db(), order, request.form.get("status", ""), _actor(),
                             request.form.get("note", "").strip()[:200] or None)
        if changed:
            flash("Status atualizado.", "success")
            if request.form.get("status") == "cancelado" and order["payment_status"] == "pago":
                flash("Este pedido já estava PAGO. Faça o reembolso ao cliente e depois marque o pagamento como Reembolsado.", "error")
    except OrderError as exc:
        flash(str(exc), "error")
    return _back(oid)


@admin_bp.route("/pedidos/<int:oid>/pagamento", methods=["POST"])
@admin_required
def order_payment(oid):
    order = _order_or_404(oid)
    try:
        if set_payment_status(get_db(), order, request.form.get("payment_status", ""), _actor()):
            flash("Pagamento atualizado.", "success")
    except OrderError as exc:
        flash(str(exc), "error")
    return _back(oid)


@admin_bp.route("/pedidos/<int:oid>/rastreio", methods=["POST"])
@admin_required
def order_tracking(oid):
    order = _order_or_404(oid)
    set_tracking(get_db(), order, request.form.get("tracking_code", ""), _actor(),
                 mark_shipped=bool(request.form.get("mark_shipped")))
    flash("Código de rastreio salvo.", "success")
    return _back(oid)


@admin_bp.route("/pedidos/<int:oid>/nota", methods=["POST"])
@admin_required
def order_note(oid):
    _order_or_404(oid)
    db = get_db()
    db.execute("UPDATE orders SET admin_notes=?, updated_at=? WHERE id=?",
               (request.form.get("admin_notes", "").strip()[:2000] or None, now_iso(), oid))
    db.commit()
    flash("Observação interna salva.", "success")
    return _back(oid)


@admin_bp.route("/pedidos/<int:oid>/verificar-mp", methods=["POST"])
@admin_required
def order_check_mp(oid):
    db = get_db()
    order = _order_or_404(oid)
    token = load_settings(db).get("mp_access_token", "").strip()
    if not token:
        flash("Configure o token do Mercado Pago em Configurações.", "error")
        return _back(oid)
    try:
        result = sync_with_mercadopago(db, order, token)
    except PaymentError as exc:
        flash(str(exc), "error")
        return _back(oid)
    messages = {
        "pago": ("Pagamento aprovado e confirmado!", "success"),
        "ja_pago": ("O pedido já constava como pago.", "success"),
        "sem_pagamento": ("O Mercado Pago ainda não registrou nenhum pagamento para este pedido.", "error"),
        "pendente": ("Pagamento ainda pendente no Mercado Pago.", "error"),
        "recusado": ("O pagamento foi recusado/cancelado no Mercado Pago.", "error"),
        "divergente": ("Pagamento aprovado, mas com valor diferente do pedido. Confira manualmente.", "error"),
        "reembolsado": ("Pagamento consta como reembolsado.", "success"),
    }
    text, cat = messages.get(result, ("Nada a atualizar.", "success"))
    flash(text, cat)
    return _back(oid)


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------

def _sniff_image(head):
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def _save_product_image(file_storage, base):
    """Valida (pelo conteúdo, não pelo nome) e salva a foto. Retorna o nome do arquivo."""
    data = file_storage.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("A foto é maior que 5 MB.")
    ext = _sniff_image(data[:16])
    if not ext:
        raise ValueError("Formato de imagem inválido. Use JPG, PNG ou WEBP.")
    os.makedirs(PRODUCT_IMG_DIR, exist_ok=True)
    for old_ext in PHOTO_EXTS:  # remove versões antigas para a nova foto valer
        old = os.path.join(PRODUCT_IMG_DIR, f"{base}.{old_ext}")
        if os.path.exists(old):
            os.remove(old)
    fname = f"{base}.{ext}"
    with open(os.path.join(PRODUCT_IMG_DIR, fname), "wb") as fh:
        fh.write(data)
    return fname


@admin_bp.route("/produtos")
@admin_required
def products():
    db = get_db()
    q = request.args.get("q", "").strip()
    only_low = request.args.get("estoque") == "baixo"
    where, params = ["1=1"], []
    if q:
        where.append("p.name LIKE ?")
        params.append(f"%{q}%")
    if only_low:
        where.append("p.stock <= ?")
        params.append(LOW_STOCK)
    rows = db.execute(
        "SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON c.id = p.category_id "
        f"WHERE {' AND '.join(where)} ORDER BY p.id DESC", params).fetchall()
    return render_template("vortex7/admin/produtos.html", products=rows, q=q, only_low=only_low, low=LOW_STOCK)


def _product_form_data():
    f = request.form
    data = {
        "name": f.get("name", "").strip()[:150],
        "description": f.get("description", "").strip()[:2000],
        "price": _money(f.get("price")),
        "promo_price": _money(f.get("promo_price")),
        "category_id": f.get("category_id", ""),
        "stock": f.get("stock", "0").strip(),
        "sizes": ",".join(s.strip() for s in f.get("sizes", "").split(",") if s.strip())[:200],
        "colors": ",".join(s.strip() for s in f.get("colors", "").split(",") if s.strip())[:200],
        "featured": 1 if f.get("featured") else 0,
    }
    errors = []
    if not data["name"]:
        errors.append("Informe o nome do produto.")
    if not data["price"] or data["price"] <= 0:
        errors.append("Informe um preço válido.")
    if data["promo_price"] is not None and (data["promo_price"] <= 0 or (data["price"] and data["promo_price"] >= data["price"])):
        errors.append("O preço promocional deve ser menor que o preço normal (ou deixe em branco).")
    try:
        data["stock"] = int(data["stock"])
        if data["stock"] < 0:
            raise ValueError
    except ValueError:
        errors.append("Estoque deve ser um número inteiro (0 ou mais).")
    if not get_db().execute("SELECT 1 FROM categories WHERE id = ?", (data["category_id"],)).fetchone():
        errors.append("Escolha uma categoria.")
    return data, errors


def _form_view(product, form=None):
    """Renderiza o formulário; `v` guarda os valores já prontos para exibir."""
    def br(value):
        return f"{value:.2f}".replace(".", ",") if value else ""

    if form is not None:
        v = form.to_dict()
        v["featured"] = bool(form.get("featured"))
    elif product is not None:
        v = dict(product)
        v["price"], v["promo_price"] = br(product["price"]), br(product["promo_price"])
        v["featured"] = bool(product["featured"])
    else:
        v = {"stock": 0}
    cats = get_db().execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template("vortex7/admin/produto_form.html", product=product, categories=cats, v=v)


@admin_bp.route("/produtos/novo", methods=["GET", "POST"])
@admin_required
def product_new():
    if request.method == "POST":
        data, errors = _product_form_data()
        if errors:
            for e in errors:
                flash(e, "error")
            return _form_view(None, request.form)
        db = get_db()
        cur = db.execute(
            """INSERT INTO products (name, description, price, promo_price, category_id, image, stock,
                                     rating, reviews_count, sizes, colors, featured)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["description"], data["price"], data["promo_price"], data["category_id"], "",
             data["stock"], 4.5, 0, data["sizes"], data["colors"], data["featured"]))
        pid = cur.lastrowid
        photo = request.files.get("image")
        if photo and photo.filename:
            try:
                fname = _save_product_image(photo, f"{slugify(data['name'])}-{pid}")
                db.execute("UPDATE products SET image=? WHERE id=?", (fname, pid))
            except ValueError as exc:
                flash(f"Produto criado, mas a foto não foi salva: {exc}", "error")
        db.commit()
        flash("Produto criado.", "success")
        return redirect(url_for("vortex7.admin.products"))
    return _form_view(None)


@admin_bp.route("/produtos/<int:pid>/editar", methods=["GET", "POST"])
@admin_required
def product_edit(pid):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not product:
        abort(404)
    if request.method == "POST":
        data, errors = _product_form_data()
        if errors:
            for e in errors:
                flash(e, "error")
            return _form_view(product, request.form)
        image = product["image"] or ""
        photo = request.files.get("image")
        if photo and photo.filename:
            base = os.path.splitext(image)[0] if image else f"{slugify(data['name'])}-{pid}"
            try:
                fname = _save_product_image(photo, base)
                image = image or fname
            except ValueError as exc:
                flash(str(exc), "error")
                return _form_view(product, request.form)
        db.execute(
            """UPDATE products SET name=?, description=?, price=?, promo_price=?, category_id=?, image=?,
                                   stock=?, sizes=?, colors=?, featured=? WHERE id=?""",
            (data["name"], data["description"], data["price"], data["promo_price"], data["category_id"], image,
             data["stock"], data["sizes"], data["colors"], data["featured"], pid))
        db.commit()
        flash("Produto atualizado.", "success")
        return redirect(url_for("vortex7.admin.products"))
    return _form_view(product)


@admin_bp.route("/produtos/<int:pid>/estoque", methods=["POST"])
@admin_required
def product_stock(pid):
    try:
        stock = int(request.form.get("stock", ""))
        if stock < 0:
            raise ValueError
    except ValueError:
        flash("Estoque inválido.", "error")
        return redirect(url_for("vortex7.admin.products"))
    db = get_db()
    db.execute("UPDATE products SET stock=? WHERE id=?", (stock, pid))
    db.commit()
    flash("Estoque atualizado.", "success")
    return redirect(request.referrer or url_for("vortex7.admin.products"))


@admin_bp.route("/produtos/<int:pid>/excluir", methods=["POST"])
@admin_required
def product_delete(pid):
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (pid,))  # itens de pedidos antigos guardam cópia do nome/preço
    db.commit()
    flash("Produto excluído.", "success")
    return redirect(url_for("vortex7.admin.products"))


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

@admin_bp.route("/categorias", methods=["GET", "POST"])
@admin_required
def categories():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:60]
        if not name:
            flash("Informe o nome da categoria.", "error")
        else:
            slug = slugify(name)
            if db.execute("SELECT 1 FROM categories WHERE name = ? OR slug = ?", (name, slug)).fetchone():
                flash("Já existe uma categoria com esse nome.", "error")
            else:
                db.execute("INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug))
                db.commit()
                flash("Categoria criada.", "success")
        return redirect(url_for("vortex7.admin.categories"))
    rows = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) AS n FROM categories c ORDER BY c.name"
    ).fetchall()
    return render_template("vortex7/admin/categorias.html", categories=rows)


@admin_bp.route("/categorias/<int:cid>/excluir", methods=["POST"])
@admin_required
def category_delete(cid):
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM products WHERE category_id = ?", (cid,)).fetchone()[0]:
        flash("Não é possível excluir: há produtos nesta categoria.", "error")
    else:
        db.execute("DELETE FROM categories WHERE id = ?", (cid,))
        db.commit()
        flash("Categoria excluída.", "success")
    return redirect(url_for("vortex7.admin.categories"))


# ---------------------------------------------------------------------------
# Clientes e mensagens
# ---------------------------------------------------------------------------

@admin_bp.route("/clientes")
@admin_required
def customers():
    rows = get_db().execute(
        """SELECT u.*, COUNT(o.id) AS orders_n,
                  COALESCE(SUM(CASE WHEN o.payment_status='pago' THEN o.total END), 0) AS spent
           FROM users u LEFT JOIN orders o ON o.user_id = u.id
           GROUP BY u.id ORDER BY u.id DESC""").fetchall()
    return render_template("vortex7/admin/clientes.html", customers=rows)


@admin_bp.route("/mensagens")
@admin_required
def messages():
    rows = get_db().execute("SELECT * FROM messages ORDER BY is_read, id DESC LIMIT 200").fetchall()
    return render_template("vortex7/admin/mensagens.html", messages=rows)


@admin_bp.route("/mensagens/<int:mid>/lida", methods=["POST"])
@admin_required
def message_read(mid):
    db = get_db()
    db.execute("UPDATE messages SET is_read = 1 - is_read WHERE id = ?", (mid,))
    db.commit()
    return redirect(url_for("vortex7.admin.messages"))


@admin_bp.route("/mensagens/<int:mid>/excluir", methods=["POST"])
@admin_required
def message_delete(mid):
    db = get_db()
    db.execute("DELETE FROM messages WHERE id = ?", (mid,))
    db.commit()
    return redirect(url_for("vortex7.admin.messages"))


# ---------------------------------------------------------------------------
# Configurações (loja, pagamentos, senha)
# ---------------------------------------------------------------------------

TEXT_SETTINGS = ("store_name", "store_legal_name", "store_cnpj", "store_email", "store_phone", "store_whatsapp",
                 "store_address", "pix_key", "pix_receiver_name", "pix_city")


@admin_bp.route("/configuracoes", methods=["GET", "POST"])
@admin_required
def settings():
    db = get_db()
    if request.method == "POST":
        f = request.form
        for key in TEXT_SETTINGS:
            save_setting(db, key, f.get(key, "").strip()[:200])
        try:
            pct = float(f.get("pix_discount_percent", "0").replace(",", "."))
            if not 0 <= pct <= 50:
                raise ValueError
        except ValueError:
            flash("Desconto Pix deve estar entre 0 e 50.", "error")
            return redirect(url_for("vortex7.admin.settings"))
        save_setting(db, "pix_discount_percent", f"{pct:g}")

        base = f.get("public_base_url", "").strip().rstrip("/")
        if base and not base.startswith(("http://", "https://")):
            flash("O endereço público do site deve começar com http:// ou https://", "error")
            return redirect(url_for("vortex7.admin.settings"))
        save_setting(db, "public_base_url", base)

        token = f.get("mp_access_token", "").strip()
        if f.get("mp_clear"):
            save_setting(db, "mp_access_token", "")
        elif token:
            save_setting(db, "mp_access_token", token)
        save_setting(db, "test_mode", "1" if f.get("test_mode") else "0")
        db.commit()

        cfg = load_settings(db)
        if cfg["test_mode"] != "1" and not cfg["pix_key"].strip() and not cfg["mp_access_token"].strip():
            flash("Atenção: modo teste desligado e nenhum meio de pagamento configurado — os clientes não conseguirão pagar.", "error")
        else:
            flash("Configurações salvas.", "success")
        return redirect(url_for("vortex7.admin.settings"))

    cfg = load_settings(db)
    token = cfg.get("mp_access_token", "")
    pix_preview = pix_qr = None
    if cfg.get("pix_key", "").strip():
        try:
            pix_preview = payments.build_pix_payload(cfg["pix_key"], cfg["pix_receiver_name"], cfg["pix_city"],
                                                     amount=1.00, txid="TESTE")
            pix_qr = payments.qr_svg(pix_preview)
        except PaymentError:
            pass
    return render_template("vortex7/admin/configuracoes.html", cfg=cfg,
                           mp_masked=("••••" + token[-4:]) if token else "", pix_preview=pix_preview, pix_qr=pix_qr)


@admin_bp.route("/senha", methods=["POST"])
@admin_required
def change_password():
    admin = current_admin()
    current, new, confirm = (request.form.get(k, "") for k in ("current", "new", "confirm"))
    if not check_password_hash(admin["password"], current):
        flash("Senha atual incorreta.", "error")
    elif len(new) < 8:
        flash("A nova senha deve ter pelo menos 8 caracteres.", "error")
    elif new != confirm:
        flash("A confirmação não coincide com a nova senha.", "error")
    else:
        db = get_db()
        db.execute("UPDATE admins SET password=? WHERE id=?", (generate_password_hash(new), admin["id"]))
        db.commit()
        flash("Senha alterada com sucesso.", "success")
    return redirect(url_for("vortex7.admin.settings"))
