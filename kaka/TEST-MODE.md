# Modo de testes FK

Entre como administrador e abra **Modo de testes** no menu. Clique em **Iniciar testes**. O aviso amarelo identifica as páginas enquanto o modo estiver ativo.

1. Abra a área do cliente e faça um agendamento.
2. Abra o atendimento no admin, confirme e crie a cobrança.
3. Abra o pagamento como cliente e simule aprovação, pendência, recusa ou estorno.
4. Confira o faturamento e as notificações. Use **Limpar dados de teste** para recomeçar ou **Sair dos testes** para retornar aos dados reais.

Cada administrador tem um banco separado em `instance/fk-demo` (configurável por `FK_DEMO_DIR` na configuração Flask). Os dados persistem até a limpeza. O modo depende da sessão autenticada do administrador e não é habilitado para clientes comuns. Nenhuma cobrança é enviada ao provedor de pagamentos; não há PIX real. A edição de conteúdo e uploads fica bloqueada durante os testes. Os dados de demonstração não são copiados para o banco real.

O simulador verifica a integração interna dos atendimentos, cobranças e recebimentos. Ele não substitui a homologação do Mercado Pago e seus webhooks com credenciais de teste.

As novas fotos padrão são referências ilustrativas servidas pelo Pexels; imagens personalizadas cadastradas no admin são preservadas. Fontes em `IMAGE-CREDITS.md`.
