(() => {
  const menu = document.getElementById('mobileMenu');
  const toggle = document.getElementById('menuButton');
  const closeMenu = () => {
    if (!menu || !toggle) return;
    menu.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Abrir menu');
    document.getElementById('siteHeader')?.classList.remove('is-open');
  };
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && menu && !menu.hidden) { closeMenu(); toggle.focus(); }
  });
  menu?.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
  window.matchMedia('(min-width:1101px)').addEventListener('change', e => { if (e.matches) closeMenu(); });
  document.addEventListener('click', e => { if (menu && !menu.hidden && !e.target.closest('#siteHeader')) closeMenu(); });

  const search = document.getElementById('serviceSearch');
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  search?.addEventListener('input', () => {
    const query = normalize(search.value.trim());
    let count = 0;
    document.querySelectorAll('.services-page .service-card').forEach(card => {
      card.hidden = !normalize(card.textContent).includes(query);
      if (!card.hidden) count++;
    });
    document.getElementById('serviceCount').textContent = `${count} ${count === 1 ? 'serviço encontrado' : 'serviços encontrados'}`;
    document.getElementById('serviceEmpty').hidden = count > 0;
  });
  document.querySelectorAll('[data-gallery-filter]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-gallery-filter]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  }));
  // Preserve the chosen service when navigating from a detail page.
  const selected = new URLSearchParams(location.search).get('servico');
  if (selected) document.querySelectorAll('[data-service-slug]').forEach(button => {
    if (button.dataset.serviceSlug === selected) button.click();
  });
})();
