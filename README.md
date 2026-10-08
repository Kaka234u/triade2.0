# Atualização de navegação, notificações e chat

Consulte primeiro **ATUALIZACAO-RENDER.md** para atualizar uma instalação existente.

# Tríade — FK Káka Autodetail, SecTest e Vortex7

## O que foi atualizado

- Login e criação de contas de clientes no FK e no SecTest. As contas e sessões de cada marca são independentes.
- Painel FK protegido em `/kaka/admin`, sem link no menu, rodapé ou catálogo público do FK.
- Sete serviços com faixas de preço ilustrativas, editáveis no painel.
- Administração dos serviços, preços, visibilidade, contatos, imagens, textos, links externos, títulos das páginas, descrição de busca, orçamentos e agendamentos.
- Nova versão do SecTest integrada à Tríade: cadastro empresarial, contato, estatísticas, pesquisa, detalhes dos cadastros e mensagens reais.
- Vortex7 mantém a loja e a autenticação existentes. O portal continua reunindo as três marcas.

## Iniciar no Windows

Requer Python 3.10 ou superior. Abra o terminal na pasta extraída:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Acesse `http://localhost:5000`.

## Criar os administradores

Interrompa o servidor com Ctrl+C ou abra outro terminal na mesma pasta:

```powershell
.\.venv\Scripts\python.exe -m flask --app app criar-admin --marca kaka --email seu-email@exemplo.com
.\.venv\Scripts\python.exe -m flask --app app criar-admin --marca sectest --email seu-email@exemplo.com
```

Cada comando pede uma senha com pelo menos 10 caracteres e sua confirmação. A senha não aparece ao digitar. Não há senha padrão para os novos painéis. Execute novamente para trocar a senha de um administrador; as sessões administrativas anteriores dessa conta serão invalidadas.

Criar uma conta pelo site gera apenas um cliente. Uma conta comum nunca recebe acesso administrativo automaticamente. O Vortex7 continua usando seu próprio administrador e seu procedimento original.

## Endereços

| Área | Caminho na Tríade |
| --- | --- |
| FK público | `/kaka/` |
| Login de clientes FK | `/kaka/login` |
| Cadastro de clientes FK | `/kaka/criar-conta` |
| Painel FK | `/kaka/admin` |
| SecTest público | `/sectest/` |
| Login de clientes SecTest | `/sectest/login` |
| Cadastro de contas SecTest | `/sectest/criar-conta` |
| Cadastro empresarial / diagnóstico SecTest | `/sectest/cadastro.html` |
| Painel SecTest | `/sectest/admin` |
| Vortex7 | `/vortex7/` |

Os sites públicos continuam acessíveis sem login. Agendamentos FK e solicitações SecTest exigem login para garantir o acompanhamento privado. Orçamentos FK podem ser enviados sem conta; os enviados com login aparecem no painel. O login não confirma automaticamente o horário.

## Usar o painel FK

1. **Serviços e preços:** edite cada serviço, suas etapas, benefícios, cuidados, perguntas frequentes e valores mínimo/máximo. Para retirar um serviço do catálogo, desmarque “Visível no site”. Também é possível adicionar novos serviços.
2. **Dados da empresa:** contatos, WhatsApp, endereço, horários, Instagram e imagens de fundo. O WhatsApp usa país e DDD, somente números.
3. **Imagens:** envie PNG, JPEG ou WebP. Copie o endereço apresentado e utilize-o na edição da página ou dos fundos. Os arquivos são convertidos para WebP.
4. **Editar páginas:** abra a página desejada. Clique no texto, imagem ou link externo; use “Todos os campos” para alcançar campos ocultos, título da aba e descrição de busca. “Aplicar à prévia” ainda não publica: confirme com **Salvar alterações**.
5. Textos e imagens do cabeçalho e rodapé são compartilhados entre as páginas. “Restaurar página” remove apenas as edições locais daquela página, preservando as compartilhadas. Para corrigir um campo compartilhado, edite-o novamente.
6. **Agendamentos e conversas:** confirme os novos pedidos, combine a data, informe o valor e converse com o cliente. **Atendimentos** preserva os registros antigos. Veja ATUALIZACAO-FATURAMENTO.md para pagamentos, planos e exportações.

Os preços e textos dos serviços devem ser mantidos em **Serviços e preços**; dados de contato devem ser mantidos em **Dados da empresa**. Use o editor visual para o conteúdo editorial restante. Ele salva texto puro e endereços de imagens/links, não executa código HTML, JavaScript ou templates enviados pelo administrador. A estrutura e o layout do site continuam nos arquivos do projeto.

Faixas iniciais (exemplos, não pesquisa de mercado):

| Serviço | Faixa |
| --- | --- |
| Lavagem detalhada | R$ 85 – R$ 250 |
| Polimento técnico | R$ 350 – R$ 1.200 |
| Proteção de pintura | R$ 150 – R$ 600 |
| Higienização interna | R$ 250 – R$ 700 |
| Vitrificação | R$ 1.000 – R$ 3.000 |
| Revitalização de plásticos | R$ 120 – R$ 350 |
| Detalhamento de rodas | R$ 120 – R$ 300 |

## FK em domínio próprio com `/admin`

A aplicação também permite servir apenas o FK na raiz do domínio:

```powershell
$env:SITE_MODE = 'kaka'
.\.venv\Scripts\python.exe app.py
```

Neste modo o site abre em `/`, o login em `/login` e o painel em `/admin`. Não é necessário incluir `/kaka` no endereço. Para voltar ao portal completo, use `$env:SITE_MODE = 'triade'`.

O pacote não configura DNS nem publica um domínio. Ao hospedar o FK separadamente, use uma instalação/serviço próprio com `SITE_MODE=kaka`. Para o portal completo, mantenha `SITE_MODE=triade`.

## Nova versão do SecTest e preservação de dados

O frontend vem do segundo ZIP. Sua API Node foi adaptada para Flask/SQLite para funcionar no mesmo processo da Tríade, usando `/sectest/api/...`; não é necessário executar Node ou configurar CORS entre servidores.

Esta distribuição não inclui cadastros reais nem o arquivo de importação com dados antigos. Os registros já existentes nos bancos são preservados. Se sua instalação ainda possui uma importação legada pendente, guarde uma cópia privada antes de atualizar; não publique o arquivo no GitHub. Não recrie administradores existentes.

A autenticação administrativa do SecTest agora usa sessão validada no servidor e cookie HttpOnly. Não há token administrativo em localStorage/sessionStorage. Os cadastros e mensagens são persistentes, e não dados simulados.

## Dados, instalação e hospedagem

Arquivos gerados em execução:

- `accounts.db`: contas e sessões do FK/SecTest.
- `kaka/database.db`: conteúdo, serviços e atendimentos do FK.
- `sectest/database.db`: cadastros e mensagens do SecTest.
- `vortex7/database.db`: dados originais da loja.
- `kaka/static/uploads/`: imagens enviadas pelo administrador.
- `.session-secret`: chave aleatória local, criada caso `SECRET_KEY` não esteja definida.

Faça backup desses bancos, das imagens e da chave de sessão antes de atualizar uma instalação. O ZIP não contém bancos de testes, contas de teste ou senhas de acesso. Ao atualizar um site já existente, preserve seus bancos e uploads.

Em hospedagem, use armazenamento persistente para os bancos e uploads. Os caminhos dos bancos podem ser definidos com `TRIADE_AUTH_DB`, `KAKA_DB`, `SECTEST_DB` e `VORTEX7_DB`. Defina uma `SECRET_KEY` forte e estável; com HTTPS, defina `COOKIE_SECURE=1`. A aplicação lê variáveis do ambiente (não carrega automaticamente um arquivo `.env`).

Linux/macOS: crie/ative o ambiente virtual e use `python -m pip install -r requirements.txt`. Para hospedagem Linux, o `Procfile` existente inicia o Gunicorn. O servidor iniciado por `python app.py` é para desenvolvimento local; debug vem desativado.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

Os testes cobrem páginas e arquivos locais, preços, cadastro/login/logout, isolamento entre marcas, restrição administrativa, CSRF, limitação de tentativas, conteúdo seguro, gravação/restauração de edições, configurações, formulários, imagens, preservação dos registros do SecTest e o FK instalado na raiz.
