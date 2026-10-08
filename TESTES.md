# Testes da atualização — 08/10/2026

## Executados e aprovados

**33 testes Python passaram** (`python -m pytest -q`, 33,23 segundos). Usaram bancos temporários e dados sintéticos, sem acessar contas ou bancos de produção.

Cobertura:

- Entrada protegida FK/SecTest, cadastro/login, sessão por empresa, login administrativo separado e destinos de retorno locais.
- Recursos de login e webhook anônimo acessíveis; Vortex7 sem a nova barreira de login.
- Navegação administrativa renderizada nas páginas de conteúdo, atendimento e financeiro; categorias, links e destaque do item atual.
- Criação FK e SecTest, retorno do endereço do pedido/destino correto, validação e acesso restrito ao dono.
- Conversas de cliente/administrador, mensagens incrementais e isolamento mesmo quando o navegador tem ambas as sessões.
- Notificações por pedido, mensagem, mudança de situação e recebimento; filtragem por empresa/dono/papel; leitura individual por administrador; persistência após sair/entrar; marcação repetida e migração repetida.
- Financeiro existente: recebimentos parciais, rejeição de duplicação/excesso, filtros, CSV/XLSX e proteção contra fórmulas nas exportações; contratos mensais e geração idempotente.
- Integração Mercado Pago com respostas simuladas: referência, valor, moeda, assinatura e repetição de callback. Callback testado sem sessão de cliente.
- Pix FK lendo recebedor de um banco Vortex7 temporário e renderizando o pagamento sem conceder acesso administrativo Vortex7.
- Modos de execução independentes e importação legada com arquivo sintético, sem dados pessoais.

**Testes JavaScript com DOM simulado também passaram** (`tests/frontend.cjs`):

- Polling do chat preserva rascunho e posição ao ler mensagens antigas.
- Próximo ao fim, a conversa acompanha a mensagem nova.
- Repetir uma mensagem não duplica o elemento.
- Texto digitado durante um envio permanece; falha de envio preserva a mensagem.
- Conteúdo recebido é inserido como texto, sem executar HTML.
- Sino mostra contador, abre/fecha, marca as notificações vistas e esconde contador zerado.

Reprodução opcional, sem acrescentar Node ao servidor de produção:

```sh
npm install --prefix /tmp/triade-dom-tests jsdom@26
NODE_PATH=/tmp/triade-dom-tests/node_modules node tests/frontend.cjs
```

O ZIP foi conferido por lista de arquivos: não contém bancos, credenciais de ambiente, cache, ambiente virtual ou cadastro legado. Os arquivos existentes da Vortex7 foram comparados byte a byte com o ZIP de origem e permanecem iguais.

## Limitações e checagens pendentes

**Não foi possível concluir a inspeção visual em navegador real, no celular e computador.** O navegador local não iniciou por restrição de IPC do ambiente; o navegador remoto não alcançou o servidor local. A estrutura HTML foi testada pelo Flask, o CSS contém adaptação móvel e os comportamentos JavaScript foram testados em DOM simulado. Isso não comprova ausência de sobreposição ou qualidade visual em aparelhos reais. Use a lista de checagem de `ATUALIZACAO-RENDER.md` após iniciar uma cópia de homologação ou atualizar o serviço.

Não houve deploy, teste de cobrança real, acesso a banco/conta de produção nem inspeção confiável do site público. Pagamentos reais dependem das credenciais e configurações do provedor; o recebimento Pix direto continua exigindo conferência manual. Persistência de bancos e uploads depende do armazenamento configurado no Render.

Os testes automatizados criam dados temporários durante sua execução; nenhuma conta criada por eles acompanha o pacote.
