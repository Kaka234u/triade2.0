"""
TRÍADE — app principal do portal.

Serve a landing page institucional em "/" e monta cada marca como um
Blueprint Flask independente em seu próprio prefixo de URL:

    /            -> landing page (portal)
    /vortex7/... -> VORTEX 7 FUTSAL (loja, Flask + SQLite)
    /kaka/...    -> FK | KAKA DETAIL (Flask + SQLite)
    /sectest/... -> SECTEST (site institucional estático)

Cada marca mantém seus próprios templates, estáticos e (quando aplicável)
banco de dados, isolados em sua própria pasta — não há mistura de estilos
ou rotas entre as marcas, apenas o mesmo processo Python servindo todas.
"""

import os

from flask import Flask, render_template

from vortex7.routes import app as vortex7_bp
from vortex7.routes import init_db as vortex7_init_db
from kaka.routes import app as kaka_bp
from kaka.routes import init_db as kaka_init_db
from sectest.routes import app as sectest_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "triade-dev-secret-key-change-in-production")

# ---------------------------------------------------------------------------
# Registro das marcas (Blueprints)
# ---------------------------------------------------------------------------
app.register_blueprint(vortex7_bp, url_prefix="/vortex7")
app.register_blueprint(kaka_bp, url_prefix="/kaka")
app.register_blueprint(sectest_bp, url_prefix="/sectest")


# ---------------------------------------------------------------------------
# Landing page do portal
# ---------------------------------------------------------------------------
@app.route("/")
def portal_home():
    return render_template("portal/index.html")


# ---------------------------------------------------------------------------
# Inicialização dos bancos de dados de cada marca
# ---------------------------------------------------------------------------
with app.app_context():
    vortex7_init_db()
    kaka_init_db()
    # SECTEST não usa banco de dados (site 100% estático)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
