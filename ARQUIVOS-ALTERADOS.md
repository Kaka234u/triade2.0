# Arquivos da entrega

Comparação com o ZIP fornecido, sem considerar caches e bancos.

## Arquivos modificados

- `.gitignore`
- `README.md`
- `accounts.py`
- `app.py`
- `client_payments.py`
- `customer_portal.py`
- `kaka/admin.py`
- `kaka/routes.py`
- `kaka/static/js/main.js`
- `kaka/templates/kaka/admin/base.html`
- `sectest/routes.py`
- `sectest/static_site/script.js`
- `sectest_plans.py`
- `static/brand-admin.css`
- `static/client-chat.js`
- `templates/finance/dashboard.html`
- `templates/portal_clients/base.html`
- `templates/portal_clients/detail.html`
- `tests/test_integration.py`
- `tests/test_operations.py`
- `tests/test_standalone.py`

## Arquivos adicionados

- `ATUALIZACAO-RENDER.md`
- `TESTES.md`
- `brand_ui.py`
- `notifications.py`
- `scripts/backup_data.py`
- `sectest/static_site/js/script.js`
- `static/notifications.css`
- `static/notifications.js`
- `templates/sectest/admin_dashboard.html`
- `templates/shared/admin_nav.html`
- `templates/shared/notifications.html`
- `tests/frontend.cjs`
- `tests/test_notifications_navigation.py`
- `vortex7/templates/vortex7/pedido_confirmado.html`
- `ARQUIVOS-ALTERADOS.md`

## Exclusões somente do pacote

`sectest/importacao_inicial.json` continha um cadastro legado e não é distribuído. Não exclua a cópia privada da instalação antes de confirmar sua importação. Bancos, segredos, cache, ambiente virtual e uploads privados não acompanham o ZIP.

## Vortex7

Nenhum arquivo já existente na Vortex7 do ZIP-base foi alterado. O template `vortex7/templates/vortex7/pedido_confirmado.html` foi preservado do GitHub. Comparando com o commit GitHub `5abf906`, precisam ser atualizados `vortex7/admin.py` e `vortex7/templates/vortex7/admin/base.html`: as versões do ZIP-base já incluíam faturamento/exportações. Os módulos de pagamentos e configurações permanecem iguais.
