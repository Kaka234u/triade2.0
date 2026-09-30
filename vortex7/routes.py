import hmac
import os
import re
import sqlite3
from datetime import datetime, timezone

from flask import (Blueprint, render_template, request, redirect, url_for, session, flash, g,
                   abort, jsonify, send_file, make_response)
from werkzeug.security import generate_password_hash, check_password_hash
import io

from . import payments
from .common import (BASE_DIR, DB_PATH, PRODUCT_IMG_DIR, PHOTO_EXTS, csrf_input, ensure_admin, ensure_schema,
                     external_url, fmt_datetime, format_brl, get_db, is_admin_session, load_settings, now_iso,
                     only_digits, safe_next_url, valid_cpf, verify_csrf)
from .orders import (OrderError, PAYMENT_LABELS, SHIPPING_LABELS, STATUS_LABELS, apply_mp_payment, calcular_frete,
                     cart_lines, compute_totals, create_order, get_order_by_number, get_order_events,
                     get_order_items, mark_paid, sync_with_mercadopago)
from .payments import PaymentError

# Blueprint da VORTEX 7 — montado em /vortex7 pelo app principal do portal.
# template_folder/static_folder apontam para as pastas locais deste módulo.
# static_url_path="/static" é relativo: como o blueprint é registrado com
# url_prefix="/vortex7" no app principal, o resultado final fica em
# /vortex7/static/... — sem colidir com o /static do portal nem com o
# static das outras marcas (cada uma citada com seu próprio url_prefix).
app = Blueprint(
    "vortex7",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

# Proteção CSRF em todos os POSTs do módulo (loja + admin)
app.before_request(verify_csrf)
app.add_app_template_global(csrf_input, name="csrf_input")


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

@app.teardown_app_request
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    is_new = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            phone TEXT,
            cep TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            promo_price REAL,
            category_id INTEGER NOT NULL,
            image TEXT,
            stock INTEGER NOT NULL DEFAULT 0,
            rating REAL DEFAULT 4.5,
            reviews_count INTEGER DEFAULT 0,
            sizes TEXT,
            colors TEXT,
            featured INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        """
    )
    conn.commit()

    # Migração idempotente: adiciona colunas novas em bancos já existentes
    existing_cols = {row[1] for row in cur.execute("PRAGMA table_info(users)")}
    for col in ("phone", "cep", "address", "city", "state"):
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        categorias = [
            ("Futebol", "futebol"),
            ("Academia", "academia"),
            ("Corrida", "corrida"),
            ("Tênis", "tenis"),
            ("Acessórios", "acessorios"),
        ]
        cur.executemany("INSERT INTO categories (name, slug) VALUES (?, ?)", categorias)
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cat = {row[1]: row[0] for row in cur.execute("SELECT id, slug FROM categories")}
        produtos = [
            (
                "Chuteira Vortex Strike Pro",
                "Chuteira de futsal de alta performance, com solado de borracha para quadra e cabedal "
                "texturizado que garante toque preciso na bola. Feita para quem busca velocidade, "
                "controle e firmeza em cada jogada.",
                399.90, 319.90, cat["futebol"], "chuteira_strike.svg", 24, 4.8, 132,
                "38,39,40,41,42,43,44", "Preto/Verde,Preto/Branco", 1,
            ),
            (
                "Camisa Vortex Elite Dry-Fit",
                "Camisa esportiva com tecnologia de secagem rápida e tecido respirável. Corte "
                "atlético para máxima liberdade de movimento dentro e fora de campo.",
                149.90, None, cat["futebol"], "camisa_elite.svg", 48, 4.6, 87,
                "P,M,G,GG,XG", "Preto,Verde,Branco", 0,
            ),
            (
                "Tênis Vortex Runner X1",
                "Tênis de corrida com amortecimento em resposta dupla e cabedal ultraleve. "
                "Projetado para longas distâncias sem abrir mão do conforto.",
                459.90, 399.90, cat["corrida"], "tenis_runner_x1.svg", 18, 4.9, 210,
                "37,38,39,40,41,42,43", "Preto/Verde,Cinza/Verde", 1,
            ),
            (
                "Tênis Vortex Court Flex",
                "Tênis casual e esportivo com entressola flexível e grip multidirecional. "
                "Versátil para o dia a dia e treinos leves.",
                379.90, None, cat["tenis"], "tenis_court_flex.svg", 32, 4.5, 64,
                "37,38,39,40,41,42,43,44", "Preto,Verde,Branco/Preto", 0,
            ),
            (
                "Regata Vortex Training",
                "Regata de treino em tecido leve e elástico, ideal para musculação e treinos "
                "de alta intensidade. Costura reforçada e caimento moderno.",
                99.90, 79.90, cat["academia"], "regata_training.svg", 55, 4.4, 51,
                "P,M,G,GG", "Preto,Verde,Cinza", 0,
            ),
            (
                "Luvas Vortex Grip Power",
                "Luvas de goleiro de futsal com palma de látex texturizado para máxima aderência, "
                "dedos reforçados e munhequeira ajustável em velcro. Firmeza e proteção em cada defesa.",
                89.90, None, cat["futebol"], "luvas_grip_power.svg", 40, 4.3, 39,
                "P,M,G", "Preto/Verde", 0,
            ),
            (
                "Mochila Vortex Trail",
                "Mochila esportiva com compartimento térmico, bolso para calçados e alças "
                "acolchoadas. Resistente à água e feita para o dia a dia intenso.",
                199.90, None, cat["acessorios"], "mochila_trail.svg", 21, 4.7, 45,
                "Único", "Preto,Preto/Verde", 1,
            ),
            (
                "Garrafa Térmica Vortex Hydro",
                "Garrafa térmica de aço inoxidável de 750 ml, mantém a temperatura por até 12 horas. "
                "Tampa com trava e alça de transporte, design ergonômico com acabamento antiderrapante.",
                69.90, 54.90, cat["acessorios"], "garrafa_hydro.svg", 60, 4.6, 98,
                "750ml", "Preto,Verde", 0,
            ),
        ]
        cur.executemany(
            """INSERT INTO products
               (name, description, price, promo_price, category_id, image, stock,
                rating, reviews_count, sizes, colors, featured)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            produtos,
        )
        conn.commit()

    # Migração idempotente: garante que a bola de futsal exista em bancos já criados
    if not cur.execute("SELECT 1 FROM products WHERE name = ?", ("Bola Vortex 7 Futsal Pro",)).fetchone():
        cat_id = cur.execute("SELECT id FROM categories WHERE slug = 'futebol'").fetchone()
        if cat_id:
            cur.execute(
                """INSERT INTO products
                   (name, description, price, promo_price, category_id, image, stock,
                    rating, reviews_count, sizes, colors, featured)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "Bola Vortex 7 Futsal Pro",
                    "Bola de futsal tamanho 4 com cobertura texturizada de alta aderência e "
                    "construção resistente. Trajetória precisa e ótimo controle, do treino ao jogo.",
                    189.90, None, cat_id[0], "bola_futsal_pro.webp", 30, 4.5, 0,
                    "Tamanho 4", "Preto/Verde", 0,
                ),
            )
            conn.commit()

    ensure_schema(conn)
    ensure_admin(conn)
    conn.close()
    return is_new


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_cart():
    return session.get("cart", {})


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_count():
    cart = get_cart()
    return sum(item["qty"] for item in cart.values())


def get_product_or_404(product_id):
    db = get_db()
    return db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


@app.context_processor
def inject_globals():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return {
        "nav_categories": categories,
        "cart_count": cart_count(),
        "current_user": session.get("user_name"),
        "store_test_mode": load_settings(db).get("test_mode") == "1",
    }


# ---------------------------------------------------------------------------
# Fotos dos produtos
# ---------------------------------------------------------------------------
# Regra: o campo `image` do banco (ex.: "chuteira_strike.svg") define o NOME-BASE
# da foto. Se existir um arquivo com esse mesmo nome-base em
# static/images/products/ com extensão de foto (webp/jpg/jpeg/png/avif), ele é
# usado no lugar do SVG. Fotos extras da galeria: <nome-base>_2, _3, ... _6.
# Sem foto na pasta, o SVG placeholder continua aparecendo (nada quebra).

MAX_GALLERY = 6


def _find_photo(base):
    for ext in PHOTO_EXTS:
        fname = f"{base}.{ext}"
        if os.path.exists(os.path.join(PRODUCT_IMG_DIR, fname)):
            return fname
    return None


def _static_url(fname):
    path = os.path.join(PRODUCT_IMG_DIR, fname)
    try:
        version = int(os.path.getmtime(path))  # evita cache ao trocar a foto
    except OSError:
        version = 0
    return url_for("vortex7.static", filename="images/products/" + fname, v=version)


@app.app_template_global("product_img")
def product_img(product):
    """URL da imagem principal (foto real se existir, senão o SVG do banco)."""
    image = product["image"] or ""
    if not image:
        return _static_url("placeholder.svg")
    base = os.path.splitext(image)[0]
    return _static_url(_find_photo(base) or image)


@app.app_template_global("product_gallery")
def product_gallery(product):
    """Lista de URLs para a galeria: principal + fotos _2.._6 que existirem."""
    image = product["image"] or ""
    base = os.path.splitext(image)[0]
    urls = [product_img(product)]
    if not image:
        return urls
    for n in range(2, MAX_GALLERY + 1):
        extra = _find_photo(f"{base}_{n}")
        if extra:
            urls.append(_static_url(extra))
    return urls


@app.app_template_filter("discount")
def discount_percent(price, promo_price):
    if promo_price and price > 0:
        return round((1 - (promo_price / price)) * 100)
    return 0


@app.app_template_filter("brl")
def format_price(value):
    return format_brl(value)


@app.app_template_filter("dt")
def _dt_filter(value, with_time=True):
    return fmt_datetime(value, with_time)


app.add_app_template_global(lambda: STATUS_LABELS, name="STATUS_LABELS")
app.add_app_template_global(lambda: PAYMENT_LABELS, name="PAYMENT_LABELS")
app.add_app_template_global(lambda: payments.METHOD_LABELS, name="METHOD_LABELS")
app.add_app_template_global(lambda: SHIPPING_LABELS, name="SHIPPING_LABELS")


# ---------------------------------------------------------------------------
# Rotas - Páginas principais
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    featured = db.execute(
        "SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id "
        "WHERE p.featured = 1 ORDER BY p.id"
    ).fetchall()
    offers = db.execute(
        "SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id "
        "WHERE p.promo_price IS NOT NULL ORDER BY p.id"
    ).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return render_template(
        "vortex7/index.html", featured=featured, offers=offers, categories=categories
    )


@app.route("/produtos")
def produtos():
    db = get_db()
    query = "SELECT p.*, c.name as category_name, c.slug as category_slug FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1"
    params = []

    busca = request.args.get("q", "").strip()
    if busca:
        query += " AND (p.name LIKE ? OR p.description LIKE ?)"
        params += [f"%{busca}%", f"%{busca}%"]

    categoria = request.args.get("categoria", "").strip()
    if categoria:
        query += " AND c.slug = ?"
        params.append(categoria)

    ordenar = request.args.get("ordenar", "relevancia")
    if ordenar == "menor_preco":
        query += " ORDER BY COALESCE(p.promo_price, p.price) ASC"
    elif ordenar == "maior_preco":
        query += " ORDER BY COALESCE(p.promo_price, p.price) DESC"
    elif ordenar == "avaliacao":
        query += " ORDER BY p.rating DESC"
    elif ordenar == "nome":
        query += " ORDER BY p.name ASC"
    else:
        query += " ORDER BY p.featured DESC, p.id ASC"

    items = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    return render_template(
        "vortex7/produtos.html",
        products=items,
        categories=categories,
        busca=busca,
        categoria_ativa=categoria,
        ordenar=ordenar,
    )


@app.route("/categoria/<slug>")
def categoria(slug):
    return redirect(url_for("vortex7.produtos", categoria=slug))


@app.route("/ofertas")
def ofertas():
    db = get_db()
    items = db.execute(
        "SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id "
        "WHERE p.promo_price IS NOT NULL ORDER BY p.id"
    ).fetchall()
    return render_template("vortex7/ofertas.html", products=items)


@app.route("/produto/<int:product_id>")
def produto(product_id):
    db = get_db()
    p = db.execute(
        "SELECT p.*, c.name as category_name, c.slug as category_slug FROM products p "
        "JOIN categories c ON p.category_id = c.id WHERE p.id = ?",
        (product_id,),
    ).fetchone()
    if not p:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("vortex7.produtos"))

    related = db.execute(
        "SELECT * FROM products WHERE category_id = ? AND id != ? LIMIT 4",
        (p["category_id"], product_id),
    ).fetchall()

    sizes = [s.strip() for s in (p["sizes"] or "").split(",") if s.strip()]
    colors = [c.strip() for c in (p["colors"] or "").split(",") if c.strip()]

    return render_template(
        "vortex7/produto.html", p=p, related=related, sizes=sizes, colors=colors
    )


# ---------------------------------------------------------------------------
# Carrinho
# ---------------------------------------------------------------------------

@app.route("/carrinho")
def carrinho():
    cart = get_cart()
    db = get_db()
    items = []
    subtotal = 0.0
    for key, data in cart.items():
        p = get_product_or_404(data["product_id"])
        if not p:
            continue
        unit_price = p["promo_price"] if p["promo_price"] else p["price"]
        line_total = unit_price * data["qty"]
        subtotal += line_total
        items.append(
            {
                "key": key,
                "product": p,
                "qty": data["qty"],
                "size": data.get("size"),
                "color": data.get("color"),
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )
    return render_template("vortex7/carrinho.html", items=items, subtotal=subtotal)


@app.route("/carrinho/adicionar/<int:product_id>", methods=["POST"])
def adicionar_carrinho(product_id):
    p = get_product_or_404(product_id)
    if not p:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("vortex7.produtos"))

    qty = int(request.form.get("quantidade", 1))
    qty = max(1, min(qty, p["stock"] if p["stock"] > 0 else 1))
    size = request.form.get("tamanho", "")
    color = request.form.get("cor", "")

    key = f"{product_id}-{size}-{color}"
    cart = get_cart()
    if key in cart:
        cart[key]["qty"] = min(cart[key]["qty"] + qty, p["stock"])
    else:
        cart[key] = {"product_id": product_id, "qty": qty, "size": size, "color": color}
    save_cart(cart)

    flash(f'"{p["name"]}" adicionado ao carrinho.', "success")

    if request.form.get("comprar_agora"):
        return redirect(url_for("vortex7.carrinho"))
    return redirect(request.referrer or url_for("vortex7.produtos"))


@app.route("/carrinho/atualizar/<key>", methods=["POST"])
def atualizar_carrinho(key):
    cart = get_cart()
    if key in cart:
        qty = int(request.form.get("quantidade", 1))
        p = get_product_or_404(cart[key]["product_id"])
        max_stock = p["stock"] if p else 99
        qty = max(1, min(qty, max_stock))
        cart[key]["qty"] = qty
        save_cart(cart)
    return redirect(url_for("vortex7.carrinho"))


@app.route("/carrinho/remover/<key>", methods=["POST"])
def remover_carrinho(key):
    cart = get_cart()
    if key in cart:
        del cart[key]
        save_cart(cart)
        flash("Item removido do carrinho.", "success")
    return redirect(url_for("vortex7.carrinho"))


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = None
        if not name or not email or not password:
            error = "Preencha todos os campos obrigatórios."
        elif len(password) < 6:
            error = "A senha deve ter no mínimo 6 caracteres."
        elif password != confirm:
            error = "As senhas não coincidem."

        if not error:
            db = get_db()
            existing = db.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                error = "Este e-mail já está cadastrado."

        if error:
            flash(error, "error")
            return render_template("vortex7/cadastro.html", name=name, email=email, phone=phone)

        db = get_db()
        db.execute(
            "INSERT INTO users (name, email, password, phone, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, generate_password_hash(password), phone, datetime.utcnow().isoformat()),
        )
        db.commit()

        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Bem-vindo(a) à VORTEX 7, {user['name']}!", "success")
        return redirect(url_for("vortex7.index"))

    return render_template("vortex7/cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash(f"Bem-vindo(a) de volta, {user['name']}!", "success")
            next_url = safe_next_url(request.args.get("next"), url_for("vortex7.index"))
            return redirect(next_url)

        flash("E-mail ou senha inválidos.", "error")
        return render_template("vortex7/login.html", email=email)

    return render_template("vortex7/login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for("vortex7.index"))


@app.route("/minha-conta")
def minha_conta():
    if "user_id" not in session:
        flash("Faça login para acessar sua conta.", "error")
        return redirect(url_for("vortex7.login", next=url_for("vortex7.minha_conta")))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    my_orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 50", (session["user_id"],)
    ).fetchall()
    return render_template("vortex7/minha_conta.html", user=user, orders=my_orders)


@app.route("/minha-conta/editar", methods=["POST"])
def editar_conta():
    if "user_id" not in session:
        flash("Faça login para acessar sua conta.", "error")
        return redirect(url_for("vortex7.login"))

    phone = request.form.get("phone", "").strip()
    cep = request.form.get("cep", "").strip()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "").strip()

    db = get_db()
    db.execute(
        "UPDATE users SET phone = ?, cep = ?, address = ?, city = ?, state = ? WHERE id = ?",
        (phone, cep, address, city, state, session["user_id"]),
    )
    db.commit()
    flash("Dados atualizados com sucesso.", "success")
    return redirect(url_for("vortex7.minha_conta"))


# ---------------------------------------------------------------------------
# Frete (cálculo estimado, sem API externa)
# ---------------------------------------------------------------------------

@app.route("/carrinho/frete", methods=["POST"])
def calcular_frete_route():
    cep = request.form.get("cep", "").strip()
    cart = get_cart()
    subtotal = 0.0
    item_count = 0
    for data in cart.values():
        p = get_product_or_404(data["product_id"])
        if not p:
            continue
        unit_price = p["promo_price"] if p["promo_price"] else p["price"]
        subtotal += unit_price * data["qty"]
        item_count += data["qty"]

    resultado = calcular_frete(cep, subtotal, item_count)
    if resultado is None:
        flash("CEP inválido. Digite os 8 números do CEP.", "error")
        session.pop("frete", None)
    else:
        session["frete"] = resultado
        session.modified = True
        flash("Frete calculado com sucesso.", "success")

    return redirect(url_for("vortex7.carrinho"))


# ---------------------------------------------------------------------------
# Checkout (pedido real: grava no banco, baixa estoque, gera pagamento)
# ---------------------------------------------------------------------------

CHECKOUT_FIELDS = ("name", "email", "phone", "cpf", "address", "complement", "neighborhood", "city", "state", "notes")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _format_phone(digits):
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


def _format_cpf(digits):
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _checkout_defaults():
    """Pré-preenche o formulário com os dados da conta (se o cliente estiver logado)."""
    data = {k: "" for k in CHECKOUT_FIELDS}
    data.update(envio="pac", pagamento="pix")
    uid = session.get("user_id")
    if uid:
        u = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if u:
            data.update(
                name=u["name"] or "", email=u["email"] or "", phone=u["phone"] or "",
                address=u["address"] or "", city=u["city"] or "", state=u["state"] or "",
            )
    return data


def _render_checkout(form):
    cart = get_cart()
    db = get_db()
    settings = load_settings(db)
    lines = cart_lines(db, cart)
    if not lines:
        flash("Seu carrinho está vazio.", "error")
        return redirect(url_for("vortex7.produtos"))

    frete_ses = session.get("frete")
    subtotal = round(sum(l["line_total"] for l in lines), 2)
    frete = calcular_frete(frete_ses["cep"], subtotal, sum(l["qty"] for l in lines)) if frete_ses else None
    if not frete:
        flash("Calcule o frete no carrinho antes de continuar.", "error")
        return redirect(url_for("vortex7.carrinho"))
    session["frete"] = frete  # mantém o frete coerente com o carrinho atual
    session.modified = True

    methods = payments.available_methods(settings)
    try:
        pix_pct = float(settings.get("pix_discount_percent") or 0)
    except ValueError:
        pix_pct = 0.0
    return render_template(
        "vortex7/checkout.html",
        items=lines, subtotal=subtotal, frete=frete, form=form, methods=methods,
        pix_pct=pix_pct, test_mode=settings.get("test_mode") == "1",
    )


@app.route("/checkout")
def checkout():
    if not get_cart():
        flash("Seu carrinho está vazio.", "error")
        return redirect(url_for("vortex7.produtos"))
    if not session.get("frete"):
        flash("Calcule o frete no carrinho antes de continuar.", "error")
        return redirect(url_for("vortex7.carrinho"))
    return _render_checkout(_checkout_defaults())


def _validate_checkout(form):
    errors = []
    if len(form["name"]) < 3:
        errors.append("Informe seu nome completo.")
    if not EMAIL_RE.match(form["email"]):
        errors.append("Informe um e-mail válido.")
    if len(only_digits(form["phone"])) not in (10, 11):
        errors.append("Informe um telefone/WhatsApp com DDD.")
    if form["cpf"] and not valid_cpf(form["cpf"]):
        errors.append("CPF inválido (ou deixe o campo em branco).")
    if len(form["address"]) < 5:
        errors.append("Informe o endereço com número.")
    if len(form["neighborhood"]) < 2:
        errors.append("Informe o bairro.")
    if len(form["city"]) < 2:
        errors.append("Informe a cidade.")
    if not (len(form["state"]) == 2 and form["state"].isalpha()):
        errors.append("Informe a UF com 2 letras.")
    return errors


def _create_mp_link(db, order, settings):
    """Gera o link de pagamento do Mercado Pago (cartão/boleto). None se falhar."""
    token = settings.get("mp_access_token", "").strip()
    if not token:
        return None
    from .orders import log_event
    try:
        pref_id, init_point = payments.mp_create_preference(
            order,
            get_order_items(db, order["id"]),
            token,
            success_url=external_url("vortex7.pedido", settings, number=order["number"], t=order["access_token"]),
            notification_url=external_url("vortex7.webhook_mercadopago", settings),
        )
    except PaymentError as exc:
        log_event(db, order["id"], f"Falha ao gerar link de pagamento: {exc}", "sistema")
        db.commit()
        return None
    db.execute("UPDATE orders SET mp_preference_id=?, mp_init_point=?, updated_at=? WHERE id=?",
               (pref_id, init_point, now_iso(), order["id"]))
    log_event(db, order["id"], "Link de pagamento do Mercado Pago gerado.", "sistema")
    db.commit()
    return init_point


@app.route("/checkout/confirmar", methods=["POST"])
def checkout_confirmar():
    cart = get_cart()
    if not cart:
        flash("Seu carrinho está vazio.", "error")
        return redirect(url_for("vortex7.produtos"))
    frete = session.get("frete")
    if not frete:
        flash("Calcule o frete no carrinho antes de continuar.", "error")
        return redirect(url_for("vortex7.carrinho"))

    db = get_db()
    settings = load_settings(db)
    form = {k: request.form.get(k, "").strip()[:200] for k in CHECKOUT_FIELDS}
    form["state"] = form["state"].upper()
    form["envio"] = "sedex" if request.form.get("envio") == "sedex" else "pac"
    form["pagamento"] = request.form.get("pagamento", "")

    errors = _validate_checkout(form)
    methods = payments.available_methods(settings)
    if form["pagamento"] not in methods or not methods[form["pagamento"]][0]:
        errors.append("Escolha uma forma de pagamento disponível.")
        form["pagamento"] = "pix"
    if errors:
        for err in errors:
            flash(err, "error")
        return _render_checkout(form)

    phone_digits = only_digits(form["phone"])
    cpf_digits = only_digits(form["cpf"])
    customer = {
        "name": form["name"], "email": form["email"].lower(), "phone": _format_phone(phone_digits),
        "cpf": _format_cpf(cpf_digits) if cpf_digits else "",
        "address": form["address"], "complement": form["complement"],
        "neighborhood": form["neighborhood"], "city": form["city"], "state": form["state"],
        "notes": form["notes"],
    }
    try:
        result = create_order(
            db, cart, customer, form["envio"], form["pagamento"], frete, settings,
            user_id=session.get("user_id"),
        )
    except OrderError as exc:
        flash(str(exc), "error")
        return redirect(url_for("vortex7.carrinho"))

    session.pop("cart", None)
    session.pop("frete", None)
    session["last_order"] = {"number": result["number"], "token": result["token"]}
    session.modified = True

    order = get_order_by_number(db, result["number"])
    if form["pagamento"] in ("cartao", "boleto") and settings.get("test_mode") != "1":
        init_point = _create_mp_link(db, order, settings)
        if init_point:
            return redirect(init_point)
        flash("Pedido criado! Não conseguimos abrir a página de pagamento agora — use o botão para tentar de novo.", "error")
    return redirect(url_for("vortex7.pedido", number=result["number"], t=result["token"]))


# ---------------------------------------------------------------------------
# Página do pedido, pagamento e comprovante
# ---------------------------------------------------------------------------

@app.app_template_global("order_url")
def order_url(order, endpoint="vortex7.pedido", **extra):
    return url_for(endpoint, number=order["number"], t=order["access_token"], **extra)


def _can_access(order):
    """Admin, dono logado ou quem tem o link com token do pedido."""
    if is_admin_session():
        return True
    uid = session.get("user_id")
    if uid and order["user_id"] == uid:
        return True
    token = request.args.get("t", "")
    return bool(token) and hmac.compare_digest(token, order["access_token"])


def _load_order_or_404(number):
    order = get_order_by_number(get_db(), number)
    if not order or not _can_access(order):
        abort(404)  # 404 (e não 403) para não revelar que o pedido existe
    return order


def _private(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/pedido/<number>")
def pedido(number):
    db = get_db()
    order = _load_order_or_404(number)
    settings = load_settings(db)
    token = settings.get("mp_access_token", "").strip()
    real_mp = bool(token) and settings.get("test_mode") != "1"

    # Volta do Mercado Pago: confirma o pagamento direto na API (não confia na URL).
    mp_pid = request.args.get("payment_id") or request.args.get("collection_id") or ""
    if real_mp and mp_pid.isdigit() and order["payment_status"] == "pendente":
        try:
            apply_mp_payment(db, order, payments.mp_get_payment(mp_pid, token))
            order = get_order_by_number(db, number)
        except PaymentError:
            flash("Ainda não conseguimos confirmar o pagamento; a página será atualizada automaticamente quando ele for aprovado.", "error")

    pending = order["payment_status"] == "pendente" and order["status"] != "cancelado"
    qr = None
    if order["payment_method"] == "pix" and order["pix_payload"] and pending:
        qr = payments.qr_svg(order["pix_payload"])
    resp = make_response(render_template(
        "vortex7/pedido.html",
        order=order, items=get_order_items(db, order["id"]), settings=settings,
        pending=pending, qr=qr,
        test_mode=settings.get("test_mode") == "1",
        can_retry_mp=real_mp and order["payment_method"] in ("cartao", "boleto") and pending,
    ))
    return _private(resp)


@app.route("/pedido/<number>/pagar", methods=["POST"])
def pedido_pagar(number):
    """(Re)gera o link de pagamento do Mercado Pago."""
    db = get_db()
    order = _load_order_or_404(number)
    settings = load_settings(db)
    if (order["payment_status"] != "pendente" or order["status"] == "cancelado"
            or order["payment_method"] not in ("cartao", "boleto") or settings.get("test_mode") == "1"):
        return redirect(order_url(order))
    init_point = _create_mp_link(db, order, settings)
    if init_point:
        return redirect(init_point)
    flash("Não foi possível abrir a página de pagamento agora. Tente novamente em instantes.", "error")
    return redirect(order_url(order))


@app.route("/pedido/<number>/simular-pagamento", methods=["POST"])
def pedido_simular(number):
    """Só existe em MODO TESTE: marca o pedido como pago sem cobrança real."""
    db = get_db()
    order = _load_order_or_404(number)
    settings = load_settings(db)
    if settings.get("test_mode") != "1":
        abort(404)
    if order["payment_status"] == "pendente" and order["status"] != "cancelado":
        mark_paid(db, order, actor="modo teste", note="(simulado)")
        flash("Pagamento simulado com sucesso (modo teste).", "success")
    return redirect(order_url(order))


@app.route("/pedido/<number>/comprovante")
def comprovante(number):
    db = get_db()
    order = _load_order_or_404(number)
    settings = load_settings(db)
    pending_pix = order["payment_method"] == "pix" and order["payment_status"] == "pendente" and order["pix_payload"]
    return _private(make_response(render_template(
        "vortex7/comprovante.html",
        order=order, items=get_order_items(db, order["id"]), settings=settings,
        qr=payments.qr_svg(order["pix_payload"]) if pending_pix else None,
    )))


@app.route("/pedido/<number>/comprovante.pdf")
def comprovante_pdf(number):
    from .receipt import build_receipt_pdf
    db = get_db()
    order = _load_order_or_404(number)
    pdf = build_receipt_pdf(order, get_order_items(db, order["id"]), load_settings(db))
    resp = send_file(
        io.BytesIO(pdf), mimetype="application/pdf",
        download_name=f"comprovante-{order['number']}.pdf",
        as_attachment=request.args.get("download") == "1",
    )
    return _private(resp)


@app.route("/pedido-confirmado")
def pedido_confirmado():
    """Compatibilidade com o endereço antigo."""
    last = session.get("last_order")
    if not last:
        return redirect(url_for("vortex7.index"))
    return redirect(url_for("vortex7.pedido", number=last["number"], t=last["token"]))


@app.route("/webhook/mercadopago", methods=["GET", "POST"])
def webhook_mercadopago():
    """Notificações do Mercado Pago. Sempre reconsulta a API antes de agir."""
    db = get_db()
    settings = load_settings(db)
    token = settings.get("mp_access_token", "").strip()
    if not token:
        return "", 200
    body = request.get_json(silent=True) or {}
    topic = body.get("type") or body.get("topic") or request.args.get("type") or request.args.get("topic")
    payment_id = str((body.get("data") or {}).get("id") or request.args.get("data.id") or request.args.get("id") or "")
    if topic != "payment" or not payment_id.isdigit():
        return "", 200
    try:
        payment = payments.mp_get_payment(payment_id, token)
    except PaymentError:
        return "", 500  # o Mercado Pago tenta de novo mais tarde
    order = get_order_by_number(db, payment.get("external_reference") or "")
    if order:
        apply_mp_payment(db, order, payment)
    return "", 200

# ---------------------------------------------------------------------------
# Páginas institucionais
# ---------------------------------------------------------------------------

@app.route("/politicas")
def politicas():
    return render_template("vortex7/politicas.html")


@app.route("/atendimento", methods=["GET", "POST"])
def atendimento():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()[:120]
        contato = request.form.get("contato", "").strip()[:120]
        assunto = request.form.get("assunto", "").strip()[:120]
        mensagem = request.form.get("mensagem", "").strip()[:3000]
        if not nome or not mensagem or not contato:
            flash("Preencha nome, contato e mensagem para enviar.", "error")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO messages (name, contact, subject, message, created_at) VALUES (?,?,?,?,?)",
                (nome, contato, assunto, mensagem, now_iso()),
            )
            db.commit()
            flash("Mensagem enviada! Nossa equipe responde em até 24h úteis.", "success")
            return redirect(url_for("vortex7.atendimento"))
    return render_template("vortex7/atendimento.html")


# ---------------------------------------------------------------------------
# Painel administrativo (blueprint aninhado -> /vortex7/admin)
# ---------------------------------------------------------------------------
from .admin import admin_bp  # noqa: E402  (importado no fim para evitar ciclo)

app.register_blueprint(admin_bp, url_prefix="/admin")
