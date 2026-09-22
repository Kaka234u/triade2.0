"""
SECTEST — Blueprint Flask.

Site 100% estático (HTML/CSS/JS puros, sem back-end nem banco de dados),
conforme o próprio projeto original. Aqui ele é apenas montado dentro do
portal em /sectest, servindo os arquivos exatamente como estão — nenhuma
lógica foi adicionada além do necessário para o Flask localizar os arquivos.
"""

import os

from flask import Blueprint, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE_DIR, "static_site")

# static_folder aponta direto para a pasta do site; static_url_path="" faz
# com que /sectest/<arquivo> sirva exatamente <static_site>/<arquivo>,
# preservando os caminhos relativos (style.css, js/script.js,
# assets/favicon.svg, sobre.html, etc.) sem precisar alterar nada no
# código original do site.
app = Blueprint(
    "sectest",
    __name__,
    static_folder="static_site",
    static_url_path="",
)


@app.route("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")
