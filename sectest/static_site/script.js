// API do SecTest dentro da Tríade. Sessão HttpOnly; nenhum token em armazenamento JavaScript.
const sectestBase = new URL('.', document.currentScript.src);
let csrfPromise;
async function apiFetch(path, options = {}) {
  if (!csrfPromise) csrfPromise = fetch(new URL('api/csrf', sectestBase)).then(r => {if(!r.ok) throw new Error('Sessão indisponível'); return r.json();}).catch(e => {csrfPromise=null;throw e;});
  const csrf = await csrfPromise;
  const headers = new Headers(options.headers || {});
  if (options.method && options.method !== 'GET') headers.set('X-CSRF-Token', csrf.token);
  return fetch(new URL(path.replace(/^\//, ''), sectestBase), {...options, headers, credentials:'same-origin'});
}
function escapeHtml(value) { const el=document.createElement('span'); el.textContent=String(value ?? ''); return el.innerHTML; }
/* =========================================================================
   SecTest — script.js
   Funções compartilhadas por todas as páginas do site.
   Cada função verifica se os elementos que precisa existem antes de rodar,
   já que nem toda página tem os mesmos elementos (ex: formulário de
   cadastro só existe em cadastro.html).
   ========================================================================= */

document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initActiveNavLink();
  initScrollHeader();
  initScrollReveal();
  initFooterYear();
  initCadastroForm();
  initContatoForm();
  initAdminPanel();
});

/* ---------- Menu mobile ---------- */
function initMobileMenu() {
  const toggle = document.getElementById('menuToggle');
  const nav = document.getElementById('mainNav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('is-open');
    toggle.classList.toggle('is-active', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
  });

  // Fecha o menu ao clicar em um link (importante em telas menores)
  nav.querySelectorAll('.nav-link').forEach((link) => {
    link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      toggle.classList.remove('is-active');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

/* ---------- Marca o link ativo no menu conforme a página atual ---------- */
function initActiveNavLink() {
  const links = document.querySelectorAll('.nav-link');
  if (!links.length) return;

  let currentPage = window.location.pathname.split('/').pop();
  if (currentPage === '') currentPage = 'index.html';

  links.forEach((link) => {
    if (link.getAttribute('href') === currentPage) {
      link.classList.add('active');
    }
  });
}

/* ---------- Cabeçalho muda de aparência ao rolar a página ---------- */
function initScrollHeader() {
  const header = document.getElementById('siteHeader');
  if (!header) return;

  const onScroll = () => {
    header.classList.toggle('is-scrolled', window.scrollY > 12);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
}

/* ---------- Animação suave ao rolar (fade + slide) ---------- */
function initScrollReveal() {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;

  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  items.forEach((el) => observer.observe(el));
}

/* ---------- Atualiza o ano no rodapé ---------- */
function initFooterYear() {
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();
}

/* ---------- Utilitários de validação ---------- */
function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function isValidPhone(value) {
  const digits = value.replace(/\D/g, '');
  return digits.length >= 10 && digits.length <= 11;
}

function maskPhone(value) {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  if (digits.length > 10) {
    return digits.replace(/(\d{2})(\d{5})(\d{0,4})/, '($1) $2-$3').replace(/-$/, '');
  }
  if (digits.length > 5) {
    return digits.replace(/(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3').replace(/-$/, '');
  }
  if (digits.length > 2) {
    return digits.replace(/(\d{2})(\d{0,5})/, '($1) $2');
  }
  return digits;
}

function setFieldError(field, message) {
  field.classList.add('is-invalid');
  const errorEl = field.closest('.form-group')?.querySelector('.form-error');
  if (errorEl) {
    errorEl.textContent = message;
    errorEl.classList.add('is-visible');
  }
}

function clearFieldError(field) {
  field.classList.remove('is-invalid');
  const errorEl = field.closest('.form-group')?.querySelector('.form-error');
  if (errorEl) {
    errorEl.textContent = '';
    errorEl.classList.remove('is-visible');
  }
}

/* ---------- Formulário de cadastro (cadastro.html) ---------- */
function initCadastroForm() {
  const form = document.getElementById('cadastroForm');
  if (!form) return;

  const phoneField = document.getElementById('telefone');
  if (phoneField) {
    phoneField.addEventListener('input', () => {
      phoneField.value = maskPhone(phoneField.value);
    });
  }

  const requiredFields = form.querySelectorAll('[required]');

  function validateField(field) {
    if (field.type === 'checkbox') {
      if (!field.checked) {
        setFieldError(field, 'É necessário concordar para continuar.');
        return false;
      }
      clearFieldError(field);
      return true;
    }
    if (!field.value.trim()) {
      setFieldError(field, 'Este campo é obrigatório.');
      return false;
    }
    if (field.type === 'email' && !isValidEmail(field.value)) {
      setFieldError(field, 'Informe um e-mail válido.');
      return false;
    }
    if (field.id === 'telefone' && !isValidPhone(field.value)) {
      setFieldError(field, 'Informe um telefone válido, com DDD.');
      return false;
    }
    clearFieldError(field);
    return true;
  }

  requiredFields.forEach((field) => {
    field.addEventListener('input', () => clearFieldError(field));
    field.addEventListener('blur', () => validateField(field));
  });

  const submitBtn = form.querySelector('button[type="submit"]');
  const formErrorEl = document.getElementById('cadastroFormError');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let isValid = true;
    let firstInvalid = null;

    requiredFields.forEach((field) => {
      if (!validateField(field)) {
        isValid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!isValid) {
      firstInvalid?.focus();
      return;
    }

    const servicos = Array.from(form.querySelectorAll('input[name="servicos"]:checked')).map((el) => el.value);

    const payload = {
      empresa: document.getElementById('empresa').value.trim(),
      cnpj: document.getElementById('cnpj').value.trim(),
      funcionarios: document.getElementById('funcionarios').value,
      responsavel: document.getElementById('responsavel').value.trim(),
      email: document.getElementById('email').value.trim(),
      telefone: document.getElementById('telefone').value.trim(),
      servicos,
      mensagem: document.getElementById('mensagem').value.trim(),
      consentimento: document.getElementById('consentimento').checked,
    };

    if (formErrorEl) formErrorEl.textContent = '';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const response = await apiFetch('/api/cadastro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Não foi possível enviar o cadastro.');
      }

      const data = await response.json();
      if (data.redirect_url) { window.location.assign(data.redirect_url); return; }
      const successPanel = document.getElementById('cadastroSuccess');
      form.classList.add('hidden');
      successPanel?.classList.remove('hidden');
      successPanel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
      if (formErrorEl) {
        formErrorEl.textContent = 'Não foi possível enviar seu cadastro agora. Verifique sua conexão e tente novamente.';
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

/* ---------- Formulário de contato (contato.html) ---------- */
function initContatoForm() {
  const form = document.getElementById('contatoForm');
  if (!form) return;

  const requiredFields = form.querySelectorAll('[required]');

  requiredFields.forEach((field) => {
    field.addEventListener('input', () => clearFieldError(field));
  });

  const submitBtn = form.querySelector('button[type="submit"]');
  const formErrorEl = document.getElementById('contatoFormError');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let isValid = true;
    let firstInvalid = null;

    requiredFields.forEach((field) => {
      let fieldValid = true;
      if (!field.value.trim()) {
        fieldValid = false;
        setFieldError(field, 'Este campo é obrigatório.');
      } else if (field.type === 'email' && !isValidEmail(field.value)) {
        fieldValid = false;
        setFieldError(field, 'Informe um e-mail válido.');
      } else {
        clearFieldError(field);
      }
      if (!fieldValid) {
        isValid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!isValid) {
      firstInvalid?.focus();
      return;
    }

    const payload = {
      nome: document.getElementById('contatoNome').value.trim(),
      email: document.getElementById('contatoEmail').value.trim(),
      assunto: document.getElementById('contatoAssunto').value,
      mensagem: document.getElementById('contatoMensagem').value.trim(),
    };

    if (formErrorEl) formErrorEl.textContent = '';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const response = await apiFetch('/api/contato', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Não foi possível enviar a mensagem.');
      }

      const successPanel = document.getElementById('contatoSuccess');
      form.classList.add('hidden');
      successPanel?.classList.remove('hidden');
      successPanel?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (err) {
      if (formErrorEl) {
        formErrorEl.textContent = 'Não foi possível enviar sua mensagem agora. Verifique sua conexão e tente novamente.';
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

/* ---------- Painel administrativo (admin.html) ----------
   Login e dados agora vêm de verdade do back-end (Node.js + SQLite), via
   /api/admin/*. A sessão é mantida em cookie HttpOnly e validada no servidor. */


function initAdminPanel() {
  const loginForm = document.getElementById('adminLoginForm');
  if (!loginForm) return;

  const loginSection = document.getElementById('adminLogin');
  const dashboardSection = document.getElementById('adminDashboard');
  const loginError = document.getElementById('loginError');
  const logoutBtn = document.getElementById('logoutBtn');
  const searchInput = document.getElementById('tableSearch');
  const tableBody = document.getElementById('registrationsTableBody');
  const submitBtn = loginForm.querySelector('button[type="submit"]');

  let registrations = [];

  function formatDate(isoString) {
    const d = new Date(isoString.replace(' ', 'T') + 'Z');
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('pt-BR');
  }

  function renderTable(rows) {
    if (!tableBody) return;
    if (!rows.length) {
      tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--color-fog);">Nenhum resultado encontrado.</td></tr>';
      return;
    }
    tableBody.innerHTML = rows
      .map((row) => {
        const servico = row.servicos && row.servicos.length ? row.servicos[0] : '—';
        return `
      <tr>
        <td><details><summary>${escapeHtml(row.empresa)}</summary><p>CNPJ: ${escapeHtml(row.cnpj || "Não informado")}</p><p>Funcionários: ${escapeHtml(row.funcionarios)}</p><p>Telefone: ${escapeHtml(row.telefone)}</p><p>Serviços: ${escapeHtml((row.servicos || []).join(", "))}</p><p>${escapeHtml(row.mensagem)}</p></details></td>
        <td>${escapeHtml(row.responsavel)}</td>
        <td>${escapeHtml(row.email)}</td>
        <td><span class="badge">${escapeHtml(servico)}</span></td>
        <td class="mono">${formatDate(row.createdAt)}</td>
      </tr>`;
      })
      .join('');
  }

  function updateStats(stats) {
    const statTotal = document.getElementById('statTotal');
    const statWeek = document.getElementById('statWeek');
    const statMessages = document.getElementById('statMessages');
    const statActive = document.getElementById('statActive');
    if (statTotal) statTotal.textContent = stats.total;
    if (statWeek) statWeek.textContent = stats.week;
    if (statMessages) statMessages.textContent = stats.messages;
    if (statActive) statActive.textContent = stats.activeCompanies;
  }

  function showDashboard() {
    loginSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
  }

  function showLogin() {
    dashboardSection.classList.add('hidden');
    loginSection.classList.remove('hidden');
  }

  function authHeaders() {
    return {};
  }

  async function loadDashboard() {
    try {
      const [statsRes, regsRes, messagesRes] = await Promise.all([
        apiFetch('/api/admin/stats', { headers: authHeaders() }),
        apiFetch('/api/admin/registrations', { headers: authHeaders() }),
        apiFetch('/api/admin/messages'),
      ]);

      if (statsRes.status === 401 || regsRes.status === 401) {

        showLogin();
        if (loginError) loginError.textContent = 'Sua sessão expirou. Faça login novamente.';
        return;
      }

      if (![statsRes,regsRes,messagesRes].every(r=>r.ok)) throw new Error('Falha no painel');
      const messages = await messagesRes.json();
      const messagesBody = document.getElementById('messagesTableBody');
      if(messagesBody) messagesBody.innerHTML=messages.length ? messages.map(m=>`<tr><td>${escapeHtml(m.nome)}</td><td>${escapeHtml(m.email)}</td><td><strong>${escapeHtml(m.assunto)}</strong><p>${escapeHtml(m.mensagem)}</p></td><td>${formatDate(m.created_at)}</td></tr>`).join('') : '<tr><td colspan=4>Nenhuma mensagem recebida.</td></tr>';
      const stats = await statsRes.json();
      registrations = await regsRes.json();

      updateStats(stats);
      renderTable(registrations);
      showDashboard();
    } catch (err) {
      if (loginError) loginError.textContent = 'Não foi possível carregar os dados do painel agora.';
    }
  }

  // Se já existir um token válido (ex.: usuário deu F5), pula a tela de login.
  loadDashboard();

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('adminUser').value.trim();
    const password = document.getElementById('adminPass').value;

    if (loginError) loginError.textContent = '';
    if (submitBtn) submitBtn.disabled = true;

    try {
      const response = await apiFetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (loginError) loginError.textContent = data.error || 'Usuário ou senha inválidos.';
        return;
      }


      loginForm.reset();
      await loadDashboard();
    } catch (err) {
      if (loginError) loginError.textContent = 'Não foi possível conectar ao servidor agora.';
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });

  logoutBtn?.addEventListener('click', async () => {
    try { const response=await apiFetch('/api/admin/logout', {method:'POST'}); if(!response.ok) throw new Error(); } catch { alert('Não foi possível sair. Tente novamente.'); return; }
    window.location.href = 'admin/login';
    showLogin();
    loginForm.reset();
  });

  searchInput?.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase().trim();
    const filtered = registrations.filter(
      (row) =>
        row.empresa.toLowerCase().includes(term) ||
        row.responsavel.toLowerCase().includes(term) ||
        (row.servicos || []).some((s) => s.toLowerCase().includes(term))
    );
    renderTable(filtered);
  });
}
