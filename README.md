# TRÍADE — portal + marcas

Landing page institucional (hub) + as três marcas, todas rodando no mesmo
processo Flask, cada uma como um **Blueprint** isolado (rotas, templates e
arquivos estáticos próprios, sem misturar nada entre elas):

```
triade/
├── app.py                      # app principal: landing page em "/" + registra os 3 Blueprints
├── requirements.txt
├── Procfile
├── templates/
│   └── portal/
│       └── index.html          # landing page (hub das 3 empresas)
├── vortex7/                     # VORTEX 7 FUTSAL — loja completa (Flask + SQLite)
│   ├── routes.py                 # Blueprint "vortex7", montado em /vortex7
│   ├── database.db
│   ├── templates/vortex7/         # templates namespaced
│   └── static/
├── kaka/                         # FK | KAKA DETAIL — site + orçamento/agendamento (Flask + SQLite)
│   ├── routes.py                  # Blueprint "kaka", montado em /kaka
│   ├── data.py                    # dados da empresa e dos serviços
│   ├── templates/kaka/             # templates namespaced
│   └── static/
└── sectest/                     # SECTEST — site institucional 100% estático
    ├── routes.py                  # Blueprint "sectest", montado em /sectest
    └── static_site/                # arquivos originais do site, sem alterações
```

## Como rodar localmente

```bash
cd triade
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Acesse:
- Portal: http://localhost:5000/
- Vortex 7: http://localhost:5000/vortex7/
- Kaka Detail: http://localhost:5000/kaka/
- SecTest: http://localhost:5000/sectest/

## Como funciona a integração

Cada marca é um **Blueprint Flask** isolado dentro do mesmo processo
Python, com suas próprias rotas, templates e arquivos estáticos, montado
em um prefixo de URL:

| Marca              | Prefixo      | Status                                  |
|---------------------|--------------|-------------------------------------------|
| Portal (landing)     | `/`          | pronto                                  |
| VORTEX 7 FUTSAL      | `/vortex7/`  | pronto (loja completa, Flask + SQLite)  |
| FK \| KAKA DETAIL    | `/kaka/`     | pronto (site + orçamento/agendamento, Flask + SQLite) |
| SECTEST              | `/sectest/`  | pronto (site institucional estático)    |

Não há mistura de estilos, rotas ou templates entre marcas — cada uma
mantém sua identidade visual e seu próprio banco de dados. O único ponto
compartilhado é o processo Python que serve todas elas.

Os bancos de dados (`vortex7/database.db` e `kaka/database.db`) são
criados/atualizados automaticamente no início do `app.py`, chamando o
`init_db()` de cada Blueprint dentro do `app_context()` da aplicação.

## Testado

- Todas as páginas das 3 marcas (200 OK), incluindo os detalhes de
  produto/serviço e as páginas de política.
- Fluxo de compra da Vortex 7 (carrinho → frete → checkout).
- APIs de orçamento e agendamento da Kaka Detail (`/kaka/api/quotes`,
  `/kaka/api/bookings`).
- `robots.txt` e `sitemap.xml` da Kaka Detail.
- Todos os assets estáticos (CSS, JS, logos, favicons) de cada marca.

## Deploy

O `Procfile` já está configurado para plataformas estilo Render/Heroku
(`gunicorn app:app`). Antes de ir para produção, troque o `SECRET_KEY`
(hoje com um valor de desenvolvimento) por uma variável de ambiente real.
