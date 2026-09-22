# SecTest — Site Institucional (Projeto Acadêmico)

Site institucional fictício para uma empresa de segurança digital empresarial, desenvolvido com **HTML, CSS e JavaScript puros** — sem frameworks e sem back-end.

## Estrutura do projeto

```
SecTest/
├── index.html      Página inicial (hero, serviços em resumo, diferenciais, CTA)
├── sobre.html       Sobre a empresa (história, missão/visão/valores, equipe)
├── servicos.html     Detalhamento dos 6 serviços oferecidos
├── contato.html      Formulário de contato, informações e FAQ
├── cadastro.html     Formulário de cadastro de empresas interessadas
├── admin.html       Painel administrativo (demonstração)
├── css/style.css    Estilos de todo o site
├── js/script.js     Menu mobile, animações, validação de formulários e painel admin
└── assets/favicon.svg
```

## Como testar localmente

1. Baixe a pasta `SecTest` inteira, mantendo a estrutura de subpastas `css/`, `js/` e `assets/`.
2. Abra `index.html` diretamente no navegador (duplo clique) — não é necessário servidor.
3. Navegue pelo menu para visitar as demais páginas.
4. É necessário estar conectado à internet para carregar as fontes (Google Fonts); sem conexão, o site usa fontes do sistema como alternativa.

## Painel administrativo (demonstração)

`admin.html` simula um painel interno. Como o projeto é somente front-end (sem banco de dados), os dados exibidos são fictícios e as credenciais abaixo servem apenas para fins didáticos — não representam uma prática de segurança real:

- **Usuário:** `admin`
- **Senha:** `admin123`

## Metodologia utilizada

1. Planejamento do conteúdo e das páginas
2. Criação do layout e do sistema visual (cores, tipografia, componentes)
3. Desenvolvimento das páginas em HTML/CSS
4. Implementação do JavaScript (menu, animações, formulários, painel admin)
5. Testes de responsividade
6. Revisão final

## Checklist de testes

- [x] Links internos entre as seis páginas conferidos
- [x] Formulário de cadastro valida campos obrigatórios, e-mail e telefone
- [x] Formulário de contato valida campos obrigatórios e e-mail
- [x] Layout responsivo (desktop, tablet e celular)
- [x] Menu mobile abre/fecha corretamente
- [x] Sem erros de JavaScript no console (funções verificam se os elementos existem antes de usá-los)

## Próximos passos possíveis

Para transformar isso em um sistema real (fora do escopo pedido — "HTML, CSS e JavaScript puros"), seria necessário um back-end (ex: Node.js) e um banco de dados para: guardar de verdade os cadastros enviados, autenticar o login do painel com segurança e conectar os dados do `cadastro.html` ao `admin.html`.
