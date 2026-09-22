import os
import re
import sqlite3
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import Blueprint, g, jsonify, render_template, request, Response, url_for

from .data import business, services, whatsapp_url

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"

app = Blueprint(
    "kaka", __name__, template_folder="templates", static_folder="static", static_url_path="/static"
)


def get_db():
    if "kaka_db" not in g:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        g.kaka_db = db
    return g.kaka_db


@app.teardown_app_request
def close_db(exception=None):
    db = g.pop("kaka_db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quote_requests (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL, email TEXT,
          vehicle_type TEXT NOT NULL, brand TEXT NOT NULL, model TEXT NOT NULL,
          year TEXT, color TEXT, service TEXT NOT NULL, condition TEXT NOT NULL,
          notes TEXT, preferred_date TEXT, preferred_period TEXT,
          consent INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'new', created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS quote_created_idx ON quote_requests (created_at DESC);
        CREATE TABLE IF NOT EXISTS booking_requests (
          id TEXT PRIMARY KEY, service TEXT NOT NULL, vehicle TEXT NOT NULL,
          preferred_date TEXT NOT NULL, preferred_period TEXT NOT NULL,
          name TEXT NOT NULL, phone TEXT NOT NULL, notes TEXT,
          status TEXT NOT NULL DEFAULT 'pending_manual_confirmation', created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS booking_created_idx ON booking_requests (created_at DESC);
    """)
    conn.commit(); conn.close()


def clean_text(value, limit=160):
    return str(value or "").strip()[:limit]


def service_by_slug(slug):
    return next((s for s in services if s["slug"] == slug), None)


@app.context_processor
def globals_for_templates():
    return {"business": business, "services": services, "whatsapp_url": whatsapp_url}


@app.route("/")
def home():
    return render_template("kaka/home.html", title="FK Káka Detail")


@app.route("/servicos")
def services_page():
    return render_template("kaka/services.html", title="Serviços")


@app.route("/servicos/<slug>")
def service_detail(slug):
    service = service_by_slug(slug)
    if not service:
        return render_template("kaka/404.html", title="Página não encontrada"), 404
    return render_template("kaka/service_detail.html", title=service["name"], service=service)


@app.route("/galeria")
def gallery():
    return render_template("kaka/gallery.html", title="Galeria")


@app.route("/sobre")
def about():
    return render_template("kaka/about.html", title="Sobre")


@app.route("/contato")
def contact():
    return render_template("kaka/contact.html", title="Contato")


@app.route("/faq")
def faq():
    groups = [
      ("Serviços", [("Como sei qual serviço escolher?", "Conte o que você percebeu no veículo e qual resultado procura. A equipe indica o cuidado mais adequado."), ("Polimento remove todo risco?", "O resultado depende da profundidade de cada marca e da condição do verniz. A avaliação mostra o que pode ser corrigido com segurança."), ("Vitrificação impede riscos?", "Não. Ela ajuda na proteção e facilita a manutenção, mas não deixa a pintura imune a riscos ou impactos.")]),
      ("Agendamento", [("O pedido no site já reserva um horário?", "Ainda não. A data e o período escolhidos são confirmados pela equipe pelo WhatsApp."), ("Qual é o horário de atendimento?", "De segunda a sexta, das 16h40 às 22h30. Aos sábados e domingos, das 7h30 às 21h."), ("Quanto tempo cada serviço leva?", "Depende do veículo e do trabalho escolhido. O prazo é informado no orçamento."), ("Posso reagendar?", "Sim. Avise pelo WhatsApp com pelo menos 24 horas de antecedência para transferir o sinal uma vez para outra data disponível.")]),
      ("Valores e sinal", [("Quanto custa?", "A lavagem para carros populares parte de R$ 85. Serviços de alto padrão podem variar de R$ 1.000 a R$ 3.000, conforme o carro ou a moto e o escopo do trabalho."), ("Quando é cobrado sinal?", "Serviços acima de R$ 500 pedem sinal de 20% depois da aprovação do orçamento. O valor é descontado do total."), ("O sinal é devolvido?", "Sim, em cancelamentos feitos com pelo menos 24 horas de antecedência. Depois desse prazo ou em caso de ausência, o sinal não é devolvido.")]),
      ("Atendimento", [("Onde fica a FK Káka Detail?", "Rua Marechal Napion, 775 A, Barra do Ceará, Fortaleza — CE, CEP 60332-690."), ("Como acompanho minha solicitação?", "Use o identificador recebido e continue a conversa pelo WhatsApp."), ("Qual é o e-mail?", "kássyo.albuquerque2527@gmail.com.")]),
    ]
    return render_template("kaka/faq.html", title="Perguntas frequentes", groups=groups)


@app.route("/orcamento")
def quote():
    selected = service_by_slug(request.args.get("servico", ""))
    return render_template("kaka/quote.html", title="Orçamento", initial_service=selected["name"] if selected else "")


@app.route("/agendamento")
def booking():
    return render_template("kaka/booking.html", title="Agendamento", today=date.today().isoformat())


@app.route("/politicas/<kind>")
def policy(kind):
    content = {
      "privacidade": {"eyebrow":"Política de Privacidade","title":"Seus dados protegidos.","intro":"O site usa apenas as informações necessárias para responder a pedidos de orçamento e agendamento.","sections":[("Dados coletados","Nome, contato, informações do veículo, serviço de interesse, observações e preferências de data quando informadas."),("Finalidade","Responder à solicitação, organizar o atendimento, evitar envios repetidos e manter o histórico necessário da conversa."),("Compartilhamento","Os dados não são vendidos e só são usados por serviços necessários ao funcionamento e ao atendimento."),("Retenção e direitos","Os dados são mantidos pelo tempo necessário ao atendimento. Para pedir acesso, correção ou exclusão, escreva para kássyo.albuquerque2527@gmail.com."),("Segurança","Não envie documentos, senhas ou dados de cartão pelos formulários.")]},
      "agendamento": {"eyebrow":"Política de Agendamento","title":"Seu horário, bem combinado.","intro":"O formulário registra uma preferência. O atendimento fica confirmado depois da resposta da equipe pelo WhatsApp.","sections":[("Horários","De segunda a sexta, o atendimento acontece das 16h40 às 22h30. Aos sábados e domingos, das 7h30 às 21h."),("Confirmação","Use o identificador recebido para acompanhar a solicitação. O horário só fica reservado depois da confirmação da equipe."),("Prazo e duração","A duração depende do veículo e do serviço escolhido e é informada junto com o orçamento."),("Alterações","Pedidos de mudança devem ser feitos pelo WhatsApp e dependem da disponibilidade da nova data.")]},
      "cancelamento": {"eyebrow":"Política de Cancelamento","title":"Combinado com clareza.","intro":"Estas regras ajudam a reservar o tempo necessário para cada veículo e a manter a agenda organizada.","sections":[("Sinal","Serviços com valor acima de R$ 500 exigem sinal de 20% após a aprovação do orçamento. Esse valor é descontado do total do serviço."),("Cancelamento","O sinal é devolvido integralmente quando o cancelamento é solicitado com pelo menos 24 horas de antecedência."),("Reagendamento","Com aviso mínimo de 24 horas, o sinal pode ser transferido uma vez para outra data disponível."),("Cancelamento tardio ou ausência","Em cancelamentos com menos de 24 horas ou quando o cliente não comparece, o sinal não é devolvido porque o período ficou reservado para o serviço."),("Contato","Para cancelar ou reagendar, fale pelo WhatsApp e informe o identificador do atendimento.")]},
    }.get(kind)
    if not content:
        return render_template("kaka/404.html", title="Página não encontrada"), 404
    return render_template("kaka/policy.html", title=content["eyebrow"], content=content)


@app.post("/api/quotes")
def create_quote():
    body = request.get_json(silent=True) or request.form.to_dict()
    if clean_text(body.get("company")):
        return jsonify(ok=True)
    required = ["name","phone","vehicleType","brand","model","service","condition"]
    clean = {key: clean_text(value, 1200 if key in {"condition","notes"} else 160) for key, value in body.items() if key != "consent"}
    consent = body.get("consent") is True or str(body.get("consent","")).lower() in {"true","1","on","yes"}
    if any(not clean.get(key) for key in required) or not consent:
        return jsonify(error="Revise os campos obrigatórios e o aceite de privacidade."), 400
    phone = re.sub(r"\D", "", clean.get("phone", ""))
    if not 10 <= len(phone) <= 13:
        return jsonify(error="Informe um WhatsApp válido com DDD."), 400
    now = int(time.time() * 1000)
    db = get_db()
    recent = db.execute("SELECT id FROM quote_requests WHERE phone=? AND service=? AND created_at>? LIMIT 1", (phone, clean["service"], now-60000)).fetchone()
    if recent:
        return jsonify(error="Esta solicitação já foi recebida. Aguarde um instante antes de tentar novamente."), 429
    ident = f"FK-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"
    db.execute("""INSERT INTO quote_requests (id,name,phone,email,vehicle_type,brand,model,year,color,service,condition,notes,preferred_date,preferred_period,consent,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (ident,clean["name"],phone,clean.get("email") or None,clean["vehicleType"],clean["brand"],clean["model"],clean.get("year") or None,clean.get("color") or None,clean["service"],clean["condition"],clean.get("notes") or None,clean.get("preferredDate") or None,clean.get("preferredPeriod") or None,1,"new",now))
    db.commit()
    return jsonify(ok=True,id=ident)


@app.post("/api/bookings")
def create_booking():
    body = request.get_json(silent=True) or request.form.to_dict()
    if clean_text(body.get("company")):
        return jsonify(ok=True)
    clean = {key: clean_text(value, 1200 if key == "notes" else 160) for key, value in body.items()}
    required = ["service","vehicle","preferredDate","preferredPeriod","name","phone"]
    if any(not clean.get(key) for key in required):
        return jsonify(error="Preencha todas as etapas obrigatórias."), 400
    phone = re.sub(r"\D", "", clean["phone"])
    if not 10 <= len(phone) <= 13:
        return jsonify(error="Informe um WhatsApp válido com DDD."), 400
    try:
        selected = datetime.strptime(clean["preferredDate"], "%Y-%m-%d").date()
    except ValueError:
        return jsonify(error="Escolha uma data futura válida."), 400
    if selected < date.today():
        return jsonify(error="Escolha uma data futura válida."), 400
    now = int(time.time() * 1000)
    db = get_db()
    recent = db.execute("SELECT id FROM booking_requests WHERE phone=? AND service=? AND created_at>? LIMIT 1", (phone, clean["service"], now-60000)).fetchone()
    if recent:
        return jsonify(error="Esta solicitação já foi recebida. Aguarde a confirmação da equipe."), 429
    ident = f"AG-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"
    db.execute("""INSERT INTO booking_requests (id,service,vehicle,preferred_date,preferred_period,name,phone,notes,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
      (ident,clean["service"],clean["vehicle"],clean["preferredDate"],clean["preferredPeriod"],clean["name"],phone,clean.get("notes") or None,"pending_manual_confirmation",now))
    db.commit()
    return jsonify(ok=True,id=ident,status="pending_manual_confirmation")


@app.route("/robots.txt")
def robots():
    return Response(f"User-agent: *\nAllow: /\nSitemap: {request.url_root.rstrip('/')}{url_for('kaka.sitemap')}\n", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    urls = [url_for('kaka.home', _external=True),url_for('kaka.services_page',_external=True),url_for('kaka.gallery',_external=True),url_for('kaka.about',_external=True),url_for('kaka.contact',_external=True),url_for('kaka.faq',_external=True),url_for('kaka.quote',_external=True),url_for('kaka.booking',_external=True)]
    urls += [url_for('kaka.service_detail',slug=s['slug'],_external=True) for s in services]
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{u}</loc></url>' for u in urls) + '</urlset>'
    return Response(xml,mimetype='application/xml')
