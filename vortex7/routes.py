import os
import random
import sqlite3
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

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


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


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
                "Chuteira de alta performance para campo, com solado adaptativo e cravos de tração "
                "extrema. Desenvolvida para quem busca velocidade e precisão em cada jogada.",
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
                "Luvas de treino com palma reforçada e ajuste ergonômico em velcro. Proteção "
                "e aderência para levantamentos pesados.",
                89.90, None, cat["academia"], "luvas_grip_power.svg", 40, 4.3, 39,
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
                "Garrafa térmica de aço inoxidável, mantém a temperatura por até 12 horas. "
                "Design ergonômico com pegada antiderrapante.",
                69.90, 54.90, cat["acessorios"], "garrafa_hydro.svg", 60, 4.6, 98,
                "600ml", "Preto,Verde", 0,
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
    }


@app.app_template_filter("discount")
def discount_percent(price, promo_price):
    if promo_price and price > 0:
        return round((1 - (promo_price / price)) * 100)
    return 0


@app.app_template_filter("brl")
def format_price(value):
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
            next_url = request.args.get("next") or url_for("vortex7.index")
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
    return render_template("vortex7/minha_conta.html", user=user)


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

def calcular_frete(cep, subtotal, item_count):
    """Estimativa determinística de frete a partir do CEP.
    Não usa serviços externos: simula faixas por região (1º dígito do CEP)
    e ajusta pelo valor/volume da compra.
    """
    digits = "".join(ch for ch in cep if ch.isdigit())
    if len(digits) != 8:
        return None

    region = int(digits[0])
    # Faixas aproximadas de regiões dos Correios (0=SP capital/interior ... 9=RS/SC/PR sul)
    region_base = {
        0: 18.90, 1: 19.90, 2: 22.90, 3: 16.90, 4: 24.90,
        5: 27.90, 6: 32.90, 7: 29.90, 8: 26.90, 9: 25.90,
    }
    base = region_base.get(region, 24.90)
    volume_extra = max(0, item_count - 1) * 3.5

    pac_price = round(base + volume_extra, 2)
    sedex_price = round(pac_price * 1.75, 2)

    frete_gratis = subtotal >= 299.90
    if frete_gratis:
        pac_price = 0.0

    pac_days = 5 + (region % 4)
    sedex_days = 2 + (region % 2)

    return {
        "cep": digits,
        "pac_price": pac_price,
        "pac_days": pac_days,
        "sedex_price": sedex_price,
        "sedex_days": sedex_days,
        "frete_gratis": frete_gratis,
    }


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
# Checkout (simulado — sem gateway de pagamento real)
# ---------------------------------------------------------------------------

@app.route("/checkout")
def checkout():
    cart = get_cart()
    if not cart:
        flash("Seu carrinho está vazio.", "error")
        return redirect(url_for("vortex7.produtos"))

    frete = session.get("frete")
    if not frete:
        flash("Calcule o frete no carrinho antes de continuar.", "error")
        return redirect(url_for("vortex7.carrinho"))

    items = []
    subtotal = 0.0
    for key, data in cart.items():
        p = get_product_or_404(data["product_id"])
        if not p:
            continue
        unit_price = p["promo_price"] if p["promo_price"] else p["price"]
        line_total = unit_price * data["qty"]
        subtotal += line_total
        items.append({"product": p, "qty": data["qty"], "line_total": line_total})

    return render_template("vortex7/checkout.html", items=items, subtotal=subtotal, frete=frete)


@app.route("/checkout/confirmar", methods=["POST"])
def checkout_confirmar():
    cart = get_cart()
    if not cart:
        flash("Seu carrinho está vazio.", "error")
        return redirect(url_for("vortex7.produtos"))

    frete = session.get("frete")
    envio = request.form.get("envio", "pac")
    pagamento = request.form.get("pagamento", "pix")

    numero_pedido = f"V7-{random.randint(100000, 999999)}"

    session["ultimo_pedido"] = {
        "numero": numero_pedido,
        "envio": envio,
        "pagamento": pagamento,
    }
    session.pop("cart", None)
    session.pop("frete", None)
    session.modified = True

    return redirect(url_for("vortex7.pedido_confirmado"))


@app.route("/pedido-confirmado")
def pedido_confirmado():
    pedido = session.get("ultimo_pedido")
    if not pedido:
        return redirect(url_for("vortex7.index"))
    return render_template("vortex7/pedido_confirmado.html", pedido=pedido)


# ---------------------------------------------------------------------------
# Páginas institucionais
# ---------------------------------------------------------------------------

@app.route("/politicas")
def politicas():
    return render_template("vortex7/politicas.html")


@app.route("/atendimento", methods=["GET", "POST"])
def atendimento():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        assunto = request.form.get("assunto", "").strip()
        mensagem = request.form.get("mensagem", "").strip()
        if not nome or not mensagem:
            flash("Preencha nome e mensagem para enviar.", "error")
        else:
            flash("Mensagem enviada! Nossa equipe responde em até 24h úteis.", "success")
            return redirect(url_for("vortex7.atendimento"))
    return render_template("vortex7/atendimento.html")


# ---------------------------------------------------------------------------
# Nota: este módulo agora é um Blueprint (não roda sozinho).
# init_db() é chamado pelo app principal do portal (portal/app.py) durante
# o startup, dentro do app_context() da aplicação Flask combinada.
# ---------------------------------------------------------------------------
