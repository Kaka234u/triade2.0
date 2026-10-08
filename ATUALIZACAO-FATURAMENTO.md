# Tríade — faturamento, agendamentos e área do cliente

## O que esta atualização contém

- FK: novos pedidos vinculados ao login, painel do cliente, conversa privada com atualização a cada 10 segundos, confirmação de horário e valor final.
- Três estados do atendimento: aguardando pagamento, agendado e finalizado. O administrador confirma a data e o valor; o pagamento é acompanhado separadamente.
- FK e SecTest: cobranças com vencimento, recebimentos parciais, saldo, estornos de registro e exportação. Cada administrador só acessa a sua marca; o cliente só acessa pedidos vinculados à sua própria conta.
- SecTest: planos editáveis, formulário de estimativa e gestão de mensalidades. Operação financeira em demonstração, sem cobrança real.
- Três empresas: faturamento com gráfico, filtros por período, status e busca, além de CSV e XLSX. O formato correto do Excel é `.xlsx`.
- FK: foto em todos os serviços, imagem editável no catálogo, preço no vermelho da marca e correção da galeria. A camada de ampliação agora respeita o estado oculto; há fechamento por clique e Esc.
- Vortex7: apenas a área de faturamento/exportação e seu link no menu administrativo. A loja e o fluxo de pagamento existente foram mantidos.

## Atualização da instalação existente

1. Faça uma cópia dos bancos existentes e dos arquivos enviados pelos administradores.
2. O ZIP contém o código completo. Atualize os arquivos mantendo seus bancos `.db`, sua `SECRET_KEY`, a `.session-secret` local e as pastas de uploads. O pacote não contém contas, senhas, credenciais de pagamento ou bancos de teste.
3. Na pasta do projeto, atualize as dependências:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

No Render, use `pip install -r requirements.txt` no build e `gunicorn app:app` para iniciar. As tabelas novas são criadas na inicialização; as tabelas anteriores são preservadas. Recarregue as páginas após o deploy para carregar os novos arquivos de CSS e JavaScript.

No Render, os bancos SQLite e uploads precisam de armazenamento persistente. Um sistema de arquivos temporário pode perder os dados em reinicializações e novos deploys. Mantenha `TRIADE_AUTH_DB`, `KAKA_DB`, `SECTEST_DB` e `VORTEX7_DB` apontando para os bancos persistentes existentes. Não troque os caminhos para bancos vazios na atualização.

Os pedidos anteriores à atualização permanecem em **Atendimentos**. Não são associados automaticamente a uma nova conta somente pelo nome, telefone ou e-mail, para evitar expor pedidos de outra pessoa. Novas solicitações feitas com login passam a aparecer no painel do cliente.

## Endereços

| Área | Caminho |
|---|---|
| Cliente FK | `/kaka/login` → `/kaka/meus-pedidos` |
| Agendamentos e conversas FK | `/kaka/admin/agendamentos` |
| Faturamento FK | `/kaka/admin/faturamento` |
| Cliente SecTest | `/sectest/login` → `/sectest/meus-pedidos` |
| Planos públicos SecTest | `/sectest/planos` |
| Formulário de estimativa | `/sectest/diagnostico` |
| Preços dos planos | `/sectest/admin/planos` |
| Contratos mensais | `/sectest/admin/contratos` |
| Faturamento SecTest | `/sectest/admin/faturamento` |
| Faturamento Vortex7 | `/vortex7/admin/faturamento` |

No modo de domínio próprio do FK (`SITE_MODE=kaka`), retire `/kaka` dos caminhos.

## Fluxo FK

1. O cliente cria conta e entra antes de solicitar um agendamento. A preferência de data não reserva o horário automaticamente.
2. O administrador abre **Agendamentos e conversas**, confere a solicitação, conversa com o cliente, informa o valor combinado e a data/horário e confirma o atendimento.
3. Em **Pagamentos deste pedido**, emita a cobrança do sinal, saldo ou parcelas com seus vencimentos. O painel sugere 20% de sinal, mas o administrador define o valor de cada cobrança conforme o acordo. Confira a soma das parcelas.
4. O cliente visualiza as cobranças em seu próprio painel. Recebimentos parciais deixam o saldo restante em aberto.
5. No Pix direto, confira o crédito no banco e registre o recebimento. O cliente não pode marcar sua própria cobrança como paga.
6. Ao terminar o serviço, confirme o valor final e marque o atendimento como **finalizado**. Finalizar o atendimento não inventa um recebimento; confira também o saldo financeiro.

## Pagamento e confirmação automática

O FK lê o recebedor Pix, a credencial Mercado Pago e o modo de teste já configurados na Vortex7, sem conceder acesso ao painel Vortex7 para os administradores FK. Cada cobrança tem referência e valor próprios.

- **Pix direto:** usa a mesma chave/recebedor. O QR é gerado com o saldo da cobrança. A confirmação depende da conferência do administrador, como no Pix original da Vortex7.
- **Mercado Pago:** o cliente é encaminhado ao provedor. O servidor consulta o pagamento usando a credencial configurada e confere referência, moeda e valor antes de registrar o recebimento. Notificações repetidas não duplicam o crédito. O cliente também pode usar **Atualizar confirmação do pagamento**.
- **Teste:** se o modo de teste da Vortex7 estiver ativo, o FK mostra demonstração e não inicia uma cobrança real. O SecTest permanece em demonstração.

No Render, configure:

```text
PUBLIC_BASE_URL=https://triade2-0.onrender.com
COOKIE_SECURE=1
SECRET_KEY=<uma chave secreta fixa, mantida entre deploys>
FK_MP_WEBHOOK_SECRET=<assinatura secreta da aplicação Mercado Pago>
```

No Mercado Pago, configure eventos de pagamento para:

```text
https://triade2-0.onrender.com/kaka/webhook/pagamentos
```

No domínio próprio, use o endereço desse domínio e o caminho `/webhook/pagamentos`. O código também envia o endereço de notificação ao criar a preferência. `FK_MP_WEBHOOK_SECRET`, quando definida, valida a assinatura recebida. A consulta autenticada ao provedor e a validação do valor são realizadas independentemente da assinatura. Nunca coloque credenciais em HTML, no chat ou em repositório público.

Referência da integração: [notificações oficiais Mercado Pago](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro-preferences/payment-notifications).

Os testes desta entrega usam respostas simuladas do provedor. Nenhuma transação real foi iniciada e nenhuma credencial do serviço hospedado foi acessada.

## Planos SecTest

Valores iniciais editáveis: Pessoal R$ 39,90/mês; Pequeno Negócio R$ 149,90/mês; Profissional R$ 349,90/mês; Diagnóstico avulso a partir de R$ 499; Empresarial sob consulta.

A estimativa acrescenta R$ 50 por ataque anterior, dados sensíveis e mais de 1.000 visitas/dia; R$ 30 por site além da franquia. Casos com mais de 10.000 visitas/dia, 200 usuários ou R$ 100 mil/mês em anúncios ficam sob consulta. Essas regras comerciais iniciais não constituem diagnóstico técnico nem garantem proteção automática.

O administrador ativa um contrato com o preço combinado. **Emitir mensalidade** cria uma cobrança para o mês escolhido, vencendo no dia 10; repetir o mês não duplica a cobrança. **Pausar contrato** impede novas emissões enquanto inativo. Não existe débito bancário recorrente automático; a emissão mensal é uma ação administrativa.

Alterar os preços públicos não reescreve cobranças já emitidas. Para mudar o valor de um contrato existente, atualize seu preço em Contratos mensais após combinar com o cliente.

## Relatórios

Os filtros e o gráfico usam o **vencimento da cobrança**. Na Vortex7, usam a data de criação do pedido, pois o modelo original não possui vencimento unificado. O gráfico mostra o valor recebido dessas cobranças por mês de vencimento; não é um extrato de entradas por data bancária.

CSV: UTF-8 com separador `;`, adequado ao Excel em português. XLSX: valores numéricos e cabeçalho com filtro. Textos exportados têm proteção contra execução de fórmulas. Cobranças canceladas são identificadas; não entram nos totais ativos. O modo de demonstração do SecTest é indicado no painel.

Estornar um registro manual no painel não devolve dinheiro automaticamente ao cliente. Reembolsos Mercado Pago devem ser feitos no provedor; as notificações atualizam o registro correspondente.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Inclui testes de acesso entre clientes/empresas, mensagens, CSRF, planos, parcelas, exportações, idempotência de cobranças e confirmação do provedor. A galeria, as imagens e os painéis também foram conferidos em navegador com tamanhos de computador e celular.
