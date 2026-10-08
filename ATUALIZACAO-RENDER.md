# Atualização Tríade — 8 de outubro de 2026

## Base e comparação

Base: `triade-faturamento-e-clientes.zip` enviado nesta conversa, comparado ao GitHub `Kaka234u/triade2.0`, commit `5abf90664375c46ec76ea636c2ce3baa8a112714` de 08/10/2026.

O código principal era igual. O ZIP contém faturamento e exportações financeiras Vortex7 que não estavam nesse commit. Mantivemos essa implementação e a exportação antiga de pedidos, sem criar outro sistema. Dois arquivos adicionais de código/template do GitHub foram preservados. Bancos, caches e cópias redundantes de templates não foram usados como fonte de código.

A aplicação publicada não foi alterada. Não houve push nem deploy no Render. O endereço público não pôde ser inspecionado de forma confiável neste ambiente; a comparação foi feita com o repositório clonado e o ZIP fornecido.

## Melhorias

- FK e SecTest compartilham o mesmo componente de navegação em todas as páginas administrativas. Categorias recolhíveis com setas, indicação da página atual e categoria aberta. No FK: serviços, páginas, imagens, dados da empresa, solicitações antigas, agendamentos/conversas, faturamento/cobranças/exportações. No SecTest: cadastros/contatos, solicitações/conversas, planos, contratos e financeiro. Não foram inventadas telas de edição de conteúdo que não existiam no SecTest.
- Visitantes sem sessão são encaminhados ao login na entrada de FK/SecTest. Cadastro, login administrativo, recursos estáticos e webhook de pagamentos permanecem acessíveis. APIs retornam 401 em vez de HTML de login. Uma sessão válida da empresa permite continuar navegando; o login de outra empresa não concede acesso. A Vortex7 permanece com seu fluxo anterior.
- Sino com contador, lista, links para pedidos e marcação individual/todas como lidas. Atualização a cada 10 segundos enquanto a aba está visível. Notificações armazenadas no banco da própria empresa, com leitura por usuário e papel. Administradores da mesma empresa recebem os eventos da equipe, mas cada um mantém sua própria leitura. Clientes recebem somente os seus eventos.
- Eventos: novo pedido para a equipe; nova mensagem para a outra parte; mudança de status/data/confirmação para o cliente; recebimento confirmado, inclusive parcial, para o cliente. O recebimento parcial não significa quitação de toda a cobrança: o saldo continua visível no financeiro.
- Chat incremental a cada 10 segundos e envio sem recarregar. Texto em edição é preservado. Mensagens novas só levam ao fim quando a pessoa já está perto do fim; ao ler mensagens antigas, a rolagem é preservada. Falha de envio mantém o texto.
- Agendamento/orçamento FK, cadastro de solicitação SecTest e diagnóstico encaminham ao pedido criado após sucesso. A tela informa envio, status, conversa e cobranças disponíveis. Erros continuam na tela do formulário.
- Correção da leitura do banco de configurações Vortex7 em `client_payments.py`: compatibilidade com o caminho em string fornecido por `vortex7.common`.

## Antes de atualizar o Render

1. **Confirme onde estão os quatro bancos ativos e as imagens enviadas.** Preserve os valores atuais de `TRIADE_AUTH_DB`, `KAKA_DB`, `SECTEST_DB` e `VORTEX7_DB`. Não aponte para bancos novos/vazios.
2. Faça backup consistente de SQLite e das imagens. O script `scripts/backup_data.py` não importa a aplicação, não cria usuários e usa a API de backup SQLite, incluindo dados confirmados que ainda estejam no WAL. Copie esse script para a instalação atual antes do deploy, ou use sua rotina de backup existente. Exemplo com destino novo em armazenamento persistente:

   ```sh
   python scripts/backup_data.py --destino /var/data/backups/pre-atualizacao-20261008
   ```

   O script copia os bancos configurados, `kaka/static/uploads`, `vortex7/static/images/products` e a `.session-secret` local, se existir. Guarde também as variáveis do serviço por um meio privado. Baixe o backup antes de mexer em discos ou caminhos. Ele contém dados privados e **não deve ir para o GitHub**.
3. No Render, alterações em arquivos locais fora de um disco persistente são perdidas em reinicializações/deploys. Se os bancos ou uploads atuais estiverem no sistema temporário, exporte-os primeiro e faça a migração para armazenamento persistente antes de atualizar. Esta entrega não pode garantir preservação de arquivos que o Render descarta.
4. Preserve a `SECRET_KEY` atual; não a regenere neste deploy. Preserve credenciais, configuração do recebedor, `PUBLIC_BASE_URL`, `COOKIE_SECURE`, `FK_MP_WEBHOOK_SECRET` e modo de teste. Bancos e segredos encontrados no GitHub não foram incluídos no pacote. Se alguma credencial real já foi publicada, trate sua remoção/rotação separadamente, sem apagar os bancos em uso.

## Arquivos e implantação

1. Extraia o ZIP. `app.py`, `requirements.txt`, `kaka/`, `sectest/` e `vortex7/` devem continuar na raiz configurada no Render.
2. Sobreponha **arquivos de código** à sua cópia atual. Não apague bancos, `.session-secret`, `.env`, imagens enviadas ou configurações existentes. Não use sincronização com exclusão automática. A lista exata de arquivos alterados está em `ARQUIVOS-ALTERADOS.md`.
3. Suba os arquivos de código ao GitHub. Se o deploy automático estiver habilitado, faça isso somente depois do backup. `.gitignore` não retira arquivos sensíveis que já estejam rastreados: confira a lista do commit e não inclua bancos nem dados novos.
4. Configuração de execução preservada:

   ```text
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
   SITE_MODE: triade
   PUBLIC_BASE_URL: https://triade2-0.onrender.com
   COOKIE_SECURE: 1
   SECRET_KEY: manter a chave atual
   ```

5. Os caminhos dos bancos devem continuar apontando para os arquivos persistentes existentes. Por exemplo, **somente se esses já forem os arquivos ativos**:

   ```text
   TRIADE_AUTH_DB=/var/data/accounts.db
   KAKA_DB=/var/data/kaka.db
   SECTEST_DB=/var/data/sectest.db
   VORTEX7_DB=/var/data/vortex7.db
   ```

6. As imagens continuam usando os caminhos antigos. Para persistência, mantenha os mounts/symlinks de `kaka/static/uploads/` e `vortex7/static/images/products/` da instalação. Se usa symlinks para um disco, recrie-os no comando de inicialização antes do Gunicorn a cada deploy; copie antes as imagens existentes para o destino. Não monte uma pasta vazia por cima das imagens atuais. Esta atualização não move uploads automaticamente.
7. Inicie o deploy. As tabelas e triggers de notificações são criadas na inicialização normal da aplicação, **em tempo de execução**, quando o disco está montado. Não coloque a migração em um build/pre-deploy sem acesso ao disco.
8. Confira os logs, abra os logins, entre com contas existentes e faça a checagem abaixo. Se surgir erro, não apague bancos nem recrie contas como tentativa de correção.

## Migrações e preservação

A migração acrescenta `notifications`, `notification_reads`, índices e triggers nos bancos FK e SecTest. Não há DROP/TRUNCATE, limpeza de contas ou reescrita de pedidos. Pode rodar novamente sem duplicar notificações. Eventos anteriores à atualização não são transformados em notificações antigas.

Os eventos são gravados na mesma transação do pedido, mensagem, status ou recebimento. Um rollback também desfaz a notificação. Repetir uma confirmação sem alteração, um recebimento com a mesma referência ou o webhook do mesmo pagamento não gera outra notificação. Marcar como lida é idempotente.

Pedidos antigos sem vínculo de cliente continuam no administrativo antigo. Não associamos registros pelo nome, telefone ou e-mail: isso poderia expor pedidos de outra pessoa. Pedidos já vinculados mantêm seus donos e IDs. Alterações de pedidos vinculados no menu antigo encaminham para o detalhe unificado.

A entrega não inclui `.db`, credenciais, `.env`, `.session-secret`, contas persistidas de teste nem o JSON legado que continha um cadastro. Não remova a cópia privada desse JSON da sua instalação antes de verificar se sua importação antiga já foi feita. Os testes criam apenas bancos temporários isolados.

## Vortex7: dependências e arquivos exatos

O FK reutiliza:

- `vortex7/common.py`: caminho `VORTEX7_DB`, `load_settings` e configurações do recebedor.
- `vortex7/payments.py`: payload Pix, QR e chamadas autenticadas Mercado Pago.
- Tabela `settings` do banco Vortex7: `pix_key`, `pix_receiver_name`, `pix_city`, `mp_access_token`, `test_mode` e demais parâmetros usados pelo gerador Pix original.

A leitura usa uma conexão própria e não cria sessão administrativa Vortex7. O painel Vortex7 exige a sua autenticação original; login FK/SecTest não é aceito por ele.

**Em relação ao ZIP fornecido:** nenhum arquivo já existente dentro de `vortex7/` foi modificado nesta atualização. Foi preservado o template adicional `vortex7/templates/vortex7/pedido_confirmado.html` encontrado no GitHub.

**Em relação ao commit GitHub comparado:** atualize estes dois arquivos com as versões presentes no ZIP final, pois o ZIP fornecido já tinha esse avanço:

1. `vortex7/admin.py` — preserva `/pedidos/exportar.csv` e inclui o faturamento/CSV/XLSX já implementado na versão fornecida.
2. `vortex7/templates/vortex7/admin/base.html` — mantém o link único de Faturamento dessa versão.

`vortex7/common.py`, `vortex7/payments.py`, `vortex7/routes.py`, `vortex7/orders.py` e o template adicional já presente no GitHub não precisam de mudanças. Não foi criado um terceiro exportador nem duplicado o menu.

## Pagamentos e configuração externa

Pix direto continua manual: o administrador confere o crédito e registra o recebimento; isso gera a notificação. A mensagem do cliente não confirma pagamento.

Mercado Pago continua consultado pelo servidor, com validação de referência, valor e moeda. O callback permanece liberado do login em `/kaka/webhook/pagamentos`, com validação de assinatura quando `FK_MP_WEBHOOK_SECRET` está configurado. Retornar do checkout não prova pagamento. É necessário configurar a credencial correta, o HTTPS público e os eventos/segredo no provedor.

SecTest continua em demonstração financeira, conforme a versão fornecida. As exportações originais da Vortex7 foram preservadas.

## Testes e checagem pós-deploy

Instale os testes e execute com bancos temporários:

```sh
pip install -r requirements-dev.txt
python -m pytest -q
```

Resultados detalhados: `TESTES.md`.

Após o deploy, confira com contas reais autorizadas:

- FK e SecTest sem sessão abrem login, com opção de cadastro; Vortex7 abre como antes.
- Conta existente permanece conectada ao trocar de página. Login de uma marca não abre painel de outra.
- Todos os grupos do menu abrem/fecham em celular e computador. Financeiro mantém os links de conteúdo e atendimento.
- Novo pedido abre o próprio detalhe; erro de formulário não redireciona.
- Duas sessões separadas recebem mensagens em até cerca de 10 segundos, mantendo rascunho e posição da conversa.
- Sino atualiza, marcações de leitura persistem e cada cliente só vê seus eventos.
- Confirmação manual Pix gera aviso; callback real Mercado Pago deve ser validado com a conta/sandbox configurada no provedor.
- Filtros, CSV/XLSX, contratos e imagens antigas continuam disponíveis.

## Reversão

Guarde o código anterior e o backup pré-deploy. As tabelas novas podem permanecer se precisar voltar ao código anterior: ele não as consulta. Não restaure um backup antigo por cima dos bancos atuais se houve pedidos/pagamentos após o backup, pois isso apagaria os novos registros. Investigue primeiro e preserve uma nova cópia dos bancos.

## Referências operacionais

- Render: https://render.com/docs/disks — armazenamento persistente, acesso somente em runtime e restrições de mount.
- Render/Flask: https://render.com/docs/deploy-flask
- Mercado Pago: https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications
